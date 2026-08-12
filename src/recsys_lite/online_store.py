"""In-memory online feature store.

Stands in for the Redis-backed Feast online store in the full-scale
architecture: it answers "what does this user's behavior sequence look like
right now, and which items are worth scoring for them" in O(1)/O(k) time,
refreshed from the SQLite system of record on a TTL instead of via
Flink -> Kafka -> Redis streaming writes.
"""

from __future__ import annotations

import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass

from recsys_lite import db
from recsys_lite.constants import SEQ_LEN
from recsys_lite.features import HistoryEvent, ItemFeature, load_item_features, load_user_histories


@dataclass
class UserSequence:
    hist_item_ids: list[int]
    hist_event_type_ids: list[int]
    hist_category_ids: list[int]
    hist_brand_ids: list[int]
    hist_price_bucket_ids: list[int]
    seen_item_ids: set[int]
    preferred_categories: list[int]


class OnlineFeatureStore:
    """Loaded once from SQLite, refreshed on a TTL. Read path is pure dict lookups."""

    def __init__(self, db_path=db.DEFAULT_DB_PATH, ttl_seconds: float = 30.0):
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self._items: dict[int, ItemFeature] = {}
        self._sequences: dict[int, UserSequence] = {}
        self._popular_items: list[int] = []
        self._by_category: dict[int, list[int]] = defaultdict(list)
        self._loaded_at = 0.0
        self.refresh(force=True)

    def refresh(self, force: bool = False) -> None:
        if not force and (time.time() - self._loaded_at) < self.ttl_seconds:
            return
        conn = db.connect(self.db_path)
        try:
            self._items = load_item_features(conn)
            histories = load_user_histories(conn)
            self._sequences = {
                user_id: self._build_sequence(events) for user_id, events in histories.items()
            }
            self._popular_items = self._compute_popularity(conn)
            self._by_category = defaultdict(list)
            for item in self._items.values():
                self._by_category[item.category_id].append(item.item_id)
        finally:
            conn.close()
        self._loaded_at = time.time()

    def _build_sequence(self, events: list[HistoryEvent]) -> UserSequence:
        window = events[-SEQ_LEN:]
        cat_counts: Counter[int] = Counter()
        for event in events:
            feat = self._items.get(event.item_id)
            if feat:
                cat_counts[feat.category_id] += 1
        return UserSequence(
            hist_item_ids=[e.item_id for e in window],
            hist_event_type_ids=[e.event_type for e in window],
            hist_category_ids=[self._items[e.item_id].category_id for e in window if e.item_id in self._items],
            hist_brand_ids=[self._items[e.item_id].brand_id for e in window if e.item_id in self._items],
            hist_price_bucket_ids=[self._items[e.item_id].price_bucket for e in window if e.item_id in self._items],
            seen_item_ids={e.item_id for e in events},
            preferred_categories=[cat for cat, _ in cat_counts.most_common(3)],
        )

    @staticmethod
    def _compute_popularity(conn: sqlite3.Connection) -> list[int]:
        rows = conn.execute(
            "SELECT item_id, COUNT(*) AS n FROM events GROUP BY item_id ORDER BY n DESC LIMIT 200"
        ).fetchall()
        return [row["item_id"] for row in rows]

    def get_sequence(self, user_id: int) -> UserSequence:
        self.refresh()
        return self._sequences.get(
            user_id,
            UserSequence([], [], [], [], [], set(), []),
        )

    def get_candidates(self, user_id: int, k: int = 50) -> list[int]:
        self.refresh()
        seq = self.get_sequence(user_id)
        candidates: list[int] = []
        for cat in seq.preferred_categories:
            candidates.extend(self._by_category.get(cat, []))
        candidates.extend(self._popular_items)
        deduped: list[int] = []
        seen_local: set[int] = set()
        for item_id in candidates:
            if item_id in seq.seen_item_ids or item_id in seen_local:
                continue
            seen_local.add(item_id)
            deduped.append(item_id)
            if len(deduped) >= k:
                break
        if len(deduped) < k:
            for item_id in self._items:
                if item_id in seq.seen_item_ids or item_id in seen_local:
                    continue
                deduped.append(item_id)
                if len(deduped) >= k:
                    break
        return deduped

    def get_item_features(self, item_ids: list[int]) -> dict[int, ItemFeature]:
        return {item_id: self._items[item_id] for item_id in item_ids if item_id in self._items}

    @property
    def n_items(self) -> int:
        return len(self._items)

    @property
    def n_users(self) -> int:
        return len(self._sequences)
