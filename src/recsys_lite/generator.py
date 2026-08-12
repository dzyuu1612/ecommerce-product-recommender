"""Synthetic e-commerce catalog, users, and behavior-event generator.

Mirrors the *shape* of a real interaction log without needing a real
storefront: users have a stable per-user category preference (so the
learned embeddings have something real to pick up on), sessions escalate
view -> cart -> purchase with decaying probability, and a small fraction
of "power users" account for a disproportionate share of events (Pareto
skew), which is what makes the ranking problem non-trivial.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from recsys_lite import db
from recsys_lite.constants import (
    EVENT_CART,
    EVENT_PURCHASE,
    EVENT_VIEW,
    NUM_BRANDS,
    NUM_CATEGORIES,
    NUM_PRICE_BUCKETS,
    PRICE_MAX,
    PRICE_MIN,
)

_TITLE_NOUNS = [
    "Jacket", "Sneakers", "Backpack", "Headphones", "Watch", "Blender",
    "Desk Lamp", "Notebook", "Water Bottle", "Sunglasses", "Keyboard",
    "Monitor Stand", "Yoga Mat", "Coffee Grinder", "Phone Case",
]


@dataclass
class Product:
    item_id: int
    title: str
    category_id: int
    brand_id: int
    price: float
    price_bucket: int


def _price_bucket(price: float) -> int:
    span = (PRICE_MAX - PRICE_MIN) / NUM_PRICE_BUCKETS
    bucket = int((price - PRICE_MIN) // span) + 1
    return max(1, min(NUM_PRICE_BUCKETS, bucket))


def generate_catalog(n_items: int, rng: random.Random) -> list[Product]:
    products: list[Product] = []
    # A handful of brands dominate each category, mimicking real retail skew.
    category_house_brands = {
        cat: rng.sample(range(1, NUM_BRANDS + 1), k=3) for cat in range(1, NUM_CATEGORIES + 1)
    }
    for item_id in range(1, n_items + 1):
        category_id = rng.randint(1, NUM_CATEGORIES)
        if rng.random() < 0.6:
            brand_id = rng.choice(category_house_brands[category_id])
        else:
            brand_id = rng.randint(1, NUM_BRANDS)
        price = round(rng.uniform(PRICE_MIN, PRICE_MAX), 2)
        title = f"{rng.choice(_TITLE_NOUNS)} #{item_id}"
        products.append(
            Product(
                item_id=item_id,
                title=title,
                category_id=category_id,
                brand_id=brand_id,
                price=price,
                price_bucket=_price_bucket(price),
            )
        )
    return products


def _weighted_session_length(rng: random.Random) -> int:
    return min(8, 1 + rng.choices(range(8), weights=[30, 25, 18, 12, 7, 4, 2, 2])[0])


def generate_events(
    conn,
    products: list[Product],
    n_users: int,
    rng: random.Random,
    days_back: int = 30,
    power_user_fraction: float = 0.1,
) -> int:
    """Write users and behavior events for `n_users` synthetic users. Returns event count."""
    by_category: dict[int, list[Product]] = {}
    for product in products:
        by_category.setdefault(product.category_id, []).append(product)

    now = int(time.time())
    horizon_seconds = days_back * 86400
    total_events = 0

    for user_id in range(1, n_users + 1):
        conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        is_power_user = rng.random() < power_user_fraction
        n_sessions = rng.randint(4, 12) if is_power_user else rng.randint(1, 4)
        preferred_categories = rng.sample(
            range(1, NUM_CATEGORIES + 1), k=rng.randint(1, 3)
        )

        for _ in range(n_sessions):
            session_start = now - rng.randint(0, horizon_seconds)
            ts = session_start
            category = rng.choice(preferred_categories) if rng.random() < 0.8 else rng.randint(1, NUM_CATEGORIES)
            pool = by_category.get(category) or products
            session_items = rng.sample(pool, k=min(_weighted_session_length(rng), len(pool)))

            cart_prob, purchase_prob = 0.35, 0.15
            for product in session_items:
                ts += rng.randint(5, 240)
                conn.execute(
                    "INSERT INTO events (user_id, item_id, event_type, ts) VALUES (?, ?, ?, ?)",
                    (user_id, product.item_id, EVENT_VIEW, ts),
                )
                total_events += 1
                if rng.random() < cart_prob:
                    ts += rng.randint(5, 60)
                    conn.execute(
                        "INSERT INTO events (user_id, item_id, event_type, ts) VALUES (?, ?, ?, ?)",
                        (user_id, product.item_id, EVENT_CART, ts),
                    )
                    total_events += 1
                    if rng.random() < purchase_prob:
                        ts += rng.randint(5, 120)
                        conn.execute(
                            "INSERT INTO events (user_id, item_id, event_type, ts) VALUES (?, ?, ?, ?)",
                            (user_id, product.item_id, EVENT_PURCHASE, ts),
                        )
                        total_events += 1
    conn.commit()
    return total_events


def generate_all(
    db_path=db.DEFAULT_DB_PATH,
    n_items: int = 800,
    n_users: int = 2000,
    seed: int = 42,
    days_back: int = 30,
) -> dict:
    rng = random.Random(seed)
    conn = db.reset_db(db_path)
    try:
        products = generate_catalog(n_items, rng)
        conn.executemany(
            "INSERT INTO products (item_id, title, category_id, brand_id, price, price_bucket) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (p.item_id, p.title, p.category_id, p.brand_id, p.price, p.price_bucket)
                for p in products
            ],
        )
        conn.commit()
        n_events = generate_events(conn, products, n_users, rng, days_back=days_back)
        return {"n_items": n_items, "n_users": n_users, "n_events": n_events}
    finally:
        conn.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic catalog/users/events.")
    parser.add_argument("--items", type=int, default=800)
    parser.add_argument("--users", type=int, default=2000)
    parser.add_argument("--days-back", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--db-path", type=str, default=str(db.DEFAULT_DB_PATH))
    args = parser.parse_args()

    stats = generate_all(
        db_path=args.db_path,
        n_items=args.items,
        n_users=args.users,
        seed=args.seed,
        days_back=args.days_back,
    )
    print(f"Generated {stats['n_items']} items, {stats['n_users']} users, {stats['n_events']} events "
          f"-> {args.db_path}")


if __name__ == "__main__":
    main()
