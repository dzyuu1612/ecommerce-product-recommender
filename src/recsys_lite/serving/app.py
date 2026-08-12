"""FastAPI serving layer.

Pulls online features, routes the request to a champion or candidate model,
scores the candidate pool, and returns Top-K recommendations -- the same
role `recsys_inference_api` plays in the full-scale platform, collapsed
into one process since there is no separate feature-API/Triton hop here.
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from recsys_lite import db, drift
from recsys_lite.constants import EVENT_IDS, EVENT_NAMES
from recsys_lite.online_store import OnlineFeatureStore
from recsys_lite.registry import DEFAULT_REGISTRY_DIR, ModelRegistry
from recsys_lite.serving import ranking
from recsys_lite.serving.ab import ABRouter
from recsys_lite.serving.observability import METRICS
from recsys_lite.serving.schemas import (
    CategoryOut,
    DriftFeatureOut,
    DriftReportOut,
    EventBatchIn,
    EventIn,
    HealthResponse,
    ModelVersionOut,
    PlatformStatsOut,
    ProductOut,
    RecentEventOut,
    RecommendationResponse,
    UserProfileOut,
)

WEB_DIR = Path(__file__).resolve().parents[3] / "web"
DB_PATH = Path(os.getenv("RECSYS_LITE_DB_PATH", str(db.DEFAULT_DB_PATH)))

_registry = ModelRegistry(Path(os.getenv("RECSYS_LITE_REGISTRY_DIR", str(DEFAULT_REGISTRY_DIR))))
_store = OnlineFeatureStore(db_path=DB_PATH, ttl_seconds=8.0)
_router: ABRouter | None = None


def _build_router() -> ABRouter:
    champion = _registry.load_champion()
    candidate = None
    weight = int(os.getenv("RECSYS_LITE_AB_CANDIDATE_WEIGHT", "0"))
    versions = sorted(_registry.list_versions().keys())
    candidate_version = next((v for v in reversed(versions) if v != champion[2]), None)
    if candidate_version and weight > 0:
        candidate = _registry.load(candidate_version) + (candidate_version,)
    return ABRouter(champion, candidate, candidate_weight_pct=weight)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    global _router
    _router = _build_router()
    yield


app = FastAPI(title="recsys-lite", version="0.1.0", lifespan=_lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    champion = _registry.champion_version()
    return HealthResponse(
        status="ok" if champion else "no_champion_model",
        champion_version=champion,
        n_items=_store.n_items,
        n_users=_store.n_users,
    )


@app.get("/api/catalog", response_model=list[ProductOut])
def catalog(limit: int = 60, category_id: int | None = None) -> list[ProductOut]:
    conn = db.connect(DB_PATH)
    try:
        if category_id is not None:
            rows = conn.execute(
                "SELECT item_id, title, category_id, brand_id, price FROM products "
                "WHERE category_id = ? ORDER BY item_id LIMIT ?",
                (category_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT item_id, title, category_id, brand_id, price FROM products "
                "ORDER BY item_id LIMIT ?",
                (limit,),
            ).fetchall()
        return [ProductOut(**dict(row)) for row in rows]
    finally:
        conn.close()


@app.get("/api/categories", response_model=list[CategoryOut])
def categories() -> list[CategoryOut]:
    conn = db.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT category_id, COUNT(*) AS n_items FROM products "
            "GROUP BY category_id ORDER BY category_id"
        ).fetchall()
        return [CategoryOut(category_id=row["category_id"], n_items=row["n_items"]) for row in rows]
    finally:
        conn.close()


@app.get("/api/products/{item_id}", response_model=ProductOut)
def product_detail(item_id: int) -> ProductOut:
    conn = db.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT item_id, title, category_id, brand_id, price FROM products WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"unknown item_id {item_id}")
        return ProductOut(**dict(row))
    finally:
        conn.close()


@app.get("/api/similar/{item_id}", response_model=list[ProductOut])
def similar_items(item_id: int, k: int = 4) -> list[ProductOut]:
    """Items a shopper looking at `item_id` might also consider: same category,
    closest price. Deliberately a simple content-based neighbour rather than a
    model call -- the ranking model scores *user* → item, not item → item, and
    pretending otherwise would misrepresent what the model does.
    """
    conn = db.connect(DB_PATH)
    try:
        anchor = conn.execute(
            "SELECT item_id, category_id, price FROM products WHERE item_id = ?", (item_id,)
        ).fetchone()
        if anchor is None:
            raise HTTPException(status_code=404, detail=f"unknown item_id {item_id}")
        rows = conn.execute(
            "SELECT item_id, title, category_id, brand_id, price FROM products "
            "WHERE category_id = ? AND item_id != ? "
            "ORDER BY ABS(price - ?) ASC LIMIT ?",
            (anchor["category_id"], item_id, anchor["price"], k),
        ).fetchall()
        return [ProductOut(**dict(r)) for r in rows]
    finally:
        conn.close()


@app.get("/api/users")
def users(limit: int = 30) -> dict:
    conn = db.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT user_id FROM users ORDER BY user_id LIMIT ?", (limit,)).fetchall()
        return {"user_ids": [row["user_id"] for row in rows]}
    finally:
        conn.close()


@app.get("/api/users/{user_id}/profile", response_model=UserProfileOut)
def user_profile(user_id: int) -> UserProfileOut:
    sequence = _store.get_sequence(user_id)
    return UserProfileOut(
        user_id=user_id,
        n_events=len(sequence.seen_item_ids),
        is_cold_start=len(sequence.seen_item_ids) == 0,
        preferred_categories=sequence.preferred_categories,
    )


def _write_events(conn, events: list[EventIn]) -> int:
    """Validate every item id first, then insert. Either the whole batch lands
    or none of it does, so a checkout can't half-record an order."""
    now = int(time.time())
    for event in events:
        item = conn.execute(
            "SELECT 1 FROM products WHERE item_id = ?", (event.item_id,)
        ).fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail=f"unknown item_id {event.item_id}")
    for event in events:
        conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (event.user_id,))
        conn.execute(
            "INSERT INTO events (user_id, item_id, event_type, ts) VALUES (?, ?, ?, ?)",
            (event.user_id, event.item_id, EVENT_IDS[event.event_type], now),
        )
        METRICS.inc(f"recsys_lite_events_total{{type=\"{event.event_type}\"}}")
    conn.commit()
    return len(events)


@app.post("/api/events")
def log_event(event: EventIn) -> dict:
    conn = db.connect(DB_PATH)
    try:
        _write_events(conn, [event])
        return {"status": "recorded", "n_events": 1}
    finally:
        conn.close()


@app.post("/api/events/batch")
def log_events(batch: EventBatchIn) -> dict:
    conn = db.connect(DB_PATH)
    try:
        n = _write_events(conn, batch.events)
        return {"status": "recorded", "n_events": n}
    finally:
        conn.close()


@app.get("/api/recommend/{user_id}", response_model=RecommendationResponse)
def recommend(user_id: int, k: int = 10, candidate_pool_size: int = 60) -> RecommendationResponse:
    assert _router is not None
    started = time.perf_counter()

    routed = _router.route(user_id)
    sequence = _store.get_sequence(user_id)
    candidate_ids = _store.get_candidates(user_id, k=candidate_pool_size)
    item_features = _store.get_item_features(candidate_ids)

    scores = ranking.score_candidates(
        routed.model, sequence, candidate_ids, item_features, seq_len=routed.config.seq_len
    )
    titles, prices = {}, {}
    if candidate_ids:
        conn = db.connect(DB_PATH)
        try:
            for row in conn.execute(
                f"SELECT item_id, title, price FROM products WHERE item_id IN "
                f"({','.join('?' * len(candidate_ids))})",
                candidate_ids,
            ).fetchall():
                titles[row["item_id"]] = row["title"]
                prices[row["item_id"]] = row["price"]
        finally:
            conn.close()

    items = ranking.top_k(candidate_ids, scores, item_features, titles, prices, k=k)

    METRICS.inc("recsys_lite_recommend_requests_total")
    METRICS.inc(f"recsys_lite_recommend_variant_total{{variant=\"{routed.variant}\"}}")
    if not items:
        METRICS.inc("recsys_lite_empty_recommendations_total")
    METRICS.observe_latency_ms((time.perf_counter() - started) * 1000)

    return RecommendationResponse(
        user_id=user_id, model_version=routed.version, ab_variant=routed.variant, items=items
    )


@app.get("/api/models", response_model=list[ModelVersionOut])
def models() -> list[ModelVersionOut]:
    champion = _registry.champion_version()
    out = []
    for version, meta in sorted(_registry.list_versions().items()):
        model_metrics = meta.get("metrics", {})
        test_metrics = model_metrics.get("test", {})
        out.append(
            ModelVersionOut(
                version=version,
                is_champion=version == champion,
                created_at=meta.get("created_at", 0.0),
                val_ndcg=model_metrics.get("val", {}).get("best_ndcg"),
                test_auc=test_metrics.get("auc"),
                test_ndcg=test_metrics.get("ndcg@5"),
                epoch_history=model_metrics.get("history", []),
            )
        )
    return out


@app.get("/api/stats", response_model=PlatformStatsOut)
def platform_stats() -> PlatformStatsOut:
    """Counters for the operations overview. One connection, one pass."""
    conn = db.connect(DB_PATH)
    try:
        scalar = lambda sql, args=(): conn.execute(sql, args).fetchone()[0]  # noqa: E731
        by_type = {
            EVENT_NAMES.get(row["event_type"], str(row["event_type"])): row["n"]
            for row in conn.execute(
                "SELECT event_type, COUNT(*) AS n FROM events GROUP BY event_type"
            ).fetchall()
        }
        cutoff = int(time.time()) - 86400
        stats = {
            "n_products": scalar("SELECT COUNT(*) FROM products"),
            "n_users": scalar("SELECT COUNT(*) FROM users"),
            "n_events": scalar("SELECT COUNT(*) FROM events"),
            "n_categories": scalar("SELECT COUNT(DISTINCT category_id) FROM products"),
            "events_by_type": by_type,
            "events_last_24h": scalar("SELECT COUNT(*) FROM events WHERE ts >= ?", (cutoff,)),
        }
    finally:
        conn.close()

    versions = _registry.list_versions()
    champion = _registry.champion_version()
    champion_auc = None
    if champion and champion in versions:
        champion_auc = versions[champion].get("metrics", {}).get("test", {}).get("auc")

    return PlatformStatsOut(
        **stats,
        n_model_versions=len(versions),
        champion_version=champion,
        champion_test_auc=champion_auc,
    )


@app.get("/api/events/recent", response_model=list[RecentEventOut])
def recent_events(limit: int = 25) -> list[RecentEventOut]:
    limit = max(1, min(200, limit))
    conn = db.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT e.event_id, e.user_id, e.item_id, e.event_type, e.ts, p.title "
            "FROM events e JOIN products p ON p.item_id = e.item_id "
            "ORDER BY e.ts DESC, e.event_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            RecentEventOut(
                event_id=r["event_id"],
                user_id=r["user_id"],
                item_id=r["item_id"],
                item_title=r["title"],
                event_type=EVENT_NAMES.get(r["event_type"], str(r["event_type"])),
                ts=r["ts"],
            )
            for r in rows
        ]
    finally:
        conn.close()


@app.get("/api/drift", response_model=DriftReportOut)
def drift_report(recent_days: int = 3, baseline_days: int = 7) -> DriftReportOut:
    conn = db.connect(DB_PATH)
    try:
        report = drift.compute_drift_report(conn, recent_days=recent_days, baseline_days=baseline_days)
    finally:
        conn.close()
    return DriftReportOut(
        recent_days=report["recent_days"],
        baseline_days=report["baseline_days"],
        n_recent_events=report["n_recent_events"],
        n_baseline_events=report["n_baseline_events"],
        note=report["note"],
        features=[
            DriftFeatureOut(feature=f.feature, psi=f.psi, severity=f.severity) for f in report["features"]
        ],
    )


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    return METRICS.render_prometheus()


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
