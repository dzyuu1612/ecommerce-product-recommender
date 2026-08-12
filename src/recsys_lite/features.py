"""Offline feature building: turn the raw event log into point-in-time
training rows, the same way the full-scale platform's Spark/Feast layer
turns Iceberg silver tables into a BST training table.

The key invariant is temporal correctness: the behavior history attached to
a training row only ever contains events that happened *before* the row's
timestamp. Positive labels come from cart/purchase events (stronger intent
than a view); negatives are sampled uniformly from the catalog per rubric
"negative sampling" convention.
"""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from recsys_lite.constants import EVENT_CART, EVENT_PURCHASE, SEQ_LEN

DEFAULT_FEATURES_PATH = Path(__file__).resolve().parents[2] / "data" / "training_examples.jsonl"


@dataclass(frozen=True)
class ItemFeature:
    item_id: int
    category_id: int
    brand_id: int
    price_bucket: int


@dataclass
class HistoryEvent:
    ts: int
    item_id: int
    event_type: int


@dataclass
class TrainingExample:
    user_id: int
    ts: int
    hist_item_ids: list[int]
    hist_event_type_ids: list[int]
    hist_category_ids: list[int]
    hist_brand_ids: list[int]
    hist_price_bucket_ids: list[int]
    target_item_id: int
    target_category_id: int
    target_brand_id: int
    target_price_bucket: int
    label: int


def load_item_features(conn: sqlite3.Connection) -> dict[int, ItemFeature]:
    rows = conn.execute(
        "SELECT item_id, category_id, brand_id, price_bucket FROM products"
    ).fetchall()
    return {
        row["item_id"]: ItemFeature(
            item_id=row["item_id"],
            category_id=row["category_id"],
            brand_id=row["brand_id"],
            price_bucket=row["price_bucket"],
        )
        for row in rows
    }


def load_user_histories(conn: sqlite3.Connection) -> dict[int, list[HistoryEvent]]:
    rows = conn.execute(
        "SELECT user_id, item_id, event_type, ts FROM events ORDER BY user_id, ts ASC"
    ).fetchall()
    histories: dict[int, list[HistoryEvent]] = {}
    for row in rows:
        histories.setdefault(row["user_id"], []).append(
            HistoryEvent(ts=row["ts"], item_id=row["item_id"], event_type=row["event_type"])
        )
    return histories


def _encode_history(
    buffer: list[HistoryEvent], items: dict[int, ItemFeature], seq_len: int
) -> tuple[list[int], list[int], list[int], list[int], list[int]]:
    window = buffer[-seq_len:]
    hist_item, hist_event, hist_cat, hist_brand, hist_price = [], [], [], [], []
    for event in window:
        feat = items.get(event.item_id)
        hist_item.append(event.item_id)
        hist_event.append(event.event_type)
        hist_cat.append(feat.category_id if feat else 0)
        hist_brand.append(feat.brand_id if feat else 0)
        hist_price.append(feat.price_bucket if feat else 0)
    return hist_item, hist_event, hist_cat, hist_brand, hist_price


def build_training_examples(
    conn: sqlite3.Connection,
    seq_len: int = SEQ_LEN,
    negatives_per_positive: int = 4,
    min_history: int = 1,
    seed: int = 7,
    hard_negative_fraction: float = 0.5,
) -> list[TrainingExample]:
    """`hard_negative_fraction` controls how many negatives are drawn from the
    *same category* as the positive target (a genuine near-miss the model has
    to actually learn to tell apart) versus uniformly at random from the whole
    catalog (an easy negative -- wrong category, usually wrong price range
    too). Pure uniform sampling (fraction=0) inflates offline AUC/NDCG because
    most negatives are trivially separable; real recommenders are evaluated
    against harder negatives for exactly this reason.
    """
    items = load_item_features(conn)
    item_ids = list(items.keys())
    items_by_category: dict[int, list[int]] = {}
    for item in items.values():
        items_by_category.setdefault(item.category_id, []).append(item.item_id)
    histories = load_user_histories(conn)
    rng = random.Random(seed)

    examples: list[TrainingExample] = []
    for user_id, events in histories.items():
        buffer: list[HistoryEvent] = []
        for event in events:
            if event.event_type in (EVENT_CART, EVENT_PURCHASE) and len(buffer) >= min_history:
                target = items.get(event.item_id)
                if target is None:
                    buffer.append(event)
                    continue
                hist_item, hist_event, hist_cat, hist_brand, hist_price = _encode_history(
                    buffer, items, seq_len
                )
                examples.append(
                    TrainingExample(
                        user_id=user_id,
                        ts=event.ts,
                        hist_item_ids=hist_item,
                        hist_event_type_ids=hist_event,
                        hist_category_ids=hist_cat,
                        hist_brand_ids=hist_brand,
                        hist_price_bucket_ids=hist_price,
                        target_item_id=target.item_id,
                        target_category_id=target.category_id,
                        target_brand_id=target.brand_id,
                        target_price_bucket=target.price_bucket,
                        label=1,
                    )
                )
                seen = {e.item_id for e in buffer} | {event.item_id}
                negatives_drawn = 0
                attempts = 0
                same_category_pool = items_by_category.get(target.category_id, item_ids)
                while negatives_drawn < negatives_per_positive and attempts < negatives_per_positive * 10:
                    attempts += 1
                    draw_hard = rng.random() < hard_negative_fraction
                    pool = same_category_pool if draw_hard else item_ids
                    neg_id = rng.choice(pool)
                    if neg_id in seen:
                        continue
                    neg = items[neg_id]
                    examples.append(
                        TrainingExample(
                            user_id=user_id,
                            ts=event.ts,
                            hist_item_ids=hist_item,
                            hist_event_type_ids=hist_event,
                            hist_category_ids=hist_cat,
                            hist_brand_ids=hist_brand,
                            hist_price_bucket_ids=hist_price,
                            target_item_id=neg.item_id,
                            target_category_id=neg.category_id,
                            target_brand_id=neg.brand_id,
                            target_price_bucket=neg.price_bucket,
                            label=0,
                        )
                    )
                    negatives_drawn += 1
            buffer.append(event)
    return examples


def write_jsonl(examples: list[TrainingExample], path: Path = DEFAULT_FEATURES_PATH) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex.__dict__) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    meta = {
        "path": str(path),
        "n_examples": len(examples),
        "n_positive": sum(1 for e in examples if e.label == 1),
        "content_hash": digest,
    }
    (path.with_suffix(".meta.json")).write_text(json.dumps(meta, indent=2))
    return meta


def main() -> None:
    import argparse

    from recsys_lite import db

    parser = argparse.ArgumentParser(description="Build point-in-time training examples.")
    parser.add_argument("--db-path", type=str, default=str(db.DEFAULT_DB_PATH))
    parser.add_argument("--out", type=str, default=str(DEFAULT_FEATURES_PATH))
    parser.add_argument("--negatives-per-positive", type=int, default=4)
    parser.add_argument(
        "--hard-negative-fraction",
        type=float,
        default=0.5,
        help="Fraction of negatives drawn from the same category as the positive (near-miss) "
        "rather than uniformly from the whole catalog. 0.0 = old easy-only behavior.",
    )
    args = parser.parse_args()

    conn = db.connect(args.db_path)
    examples = build_training_examples(
        conn,
        negatives_per_positive=args.negatives_per_positive,
        hard_negative_fraction=args.hard_negative_fraction,
    )
    meta = write_jsonl(examples, Path(args.out))
    print(f"Wrote {meta['n_examples']} examples ({meta['n_positive']} positive) -> {meta['path']}")


if __name__ == "__main__":
    main()
