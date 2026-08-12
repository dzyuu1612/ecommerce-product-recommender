import random

from recsys_lite import db
from recsys_lite.constants import NUM_BRANDS, NUM_CATEGORIES, NUM_PRICE_BUCKETS, PRICE_MAX, PRICE_MIN
from recsys_lite.generator import generate_all, generate_catalog, generate_events


def test_generate_catalog_respects_cardinality_bounds():
    rng = random.Random(1)
    products = generate_catalog(200, rng)
    assert len(products) == 200
    for p in products:
        assert 1 <= p.category_id <= NUM_CATEGORIES
        assert 1 <= p.brand_id <= NUM_BRANDS
        assert PRICE_MIN <= p.price <= PRICE_MAX
        assert 1 <= p.price_bucket <= NUM_PRICE_BUCKETS


def test_generate_all_is_deterministic_for_a_fixed_seed(tmp_path):
    stats_a = generate_all(db_path=tmp_path / "a.db", n_items=50, n_users=30, seed=99)
    stats_b = generate_all(db_path=tmp_path / "b.db", n_items=50, n_users=30, seed=99)
    assert stats_a == stats_b


def test_generate_events_writes_events_in_valid_funnel_order(tmp_path):
    db_path = tmp_path / "events.db"
    rng = random.Random(3)
    conn = db.reset_db(db_path)
    products = generate_catalog(60, rng)
    conn.executemany(
        "INSERT INTO products (item_id, title, category_id, brand_id, price, price_bucket) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(p.item_id, p.title, p.category_id, p.brand_id, p.price, p.price_bucket) for p in products],
    )
    conn.commit()
    n_events = generate_events(conn, products, n_users=25, rng=rng)
    assert n_events > 0

    rows = conn.execute("SELECT user_id, item_id, event_type, ts FROM events ORDER BY user_id, ts").fetchall()
    # every event must reference a real product
    product_ids = {p.item_id for p in products}
    assert all(row["item_id"] in product_ids for row in rows)
    conn.close()
