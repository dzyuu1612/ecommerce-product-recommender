from __future__ import annotations

from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    item_id: int
    title: str
    category_id: int
    brand_id: int
    price: float


class RecommendationItem(BaseModel):
    item_id: int
    title: str
    category_id: int
    brand_id: int
    price: float
    score: float


class RecommendationResponse(BaseModel):
    user_id: int
    model_version: str
    ab_variant: str
    items: list[RecommendationItem]


class EventIn(BaseModel):
    user_id: int
    item_id: int
    event_type: str = Field(pattern="^(view|cart|purchase)$")


class EventBatchIn(BaseModel):
    """Checkout submits every purchased line in one request, so a completed
    order writes real purchase events that feed back into future features."""

    events: list[EventIn] = Field(min_length=1, max_length=100)


class HealthResponse(BaseModel):
    status: str
    champion_version: str | None
    n_items: int
    n_users: int


class CategoryOut(BaseModel):
    category_id: int
    n_items: int


class UserProfileOut(BaseModel):
    user_id: int
    n_events: int
    is_cold_start: bool
    preferred_categories: list[int]


class ModelVersionOut(BaseModel):
    version: str
    is_champion: bool
    created_at: float
    val_ndcg: float | None = None
    test_auc: float | None = None
    test_ndcg: float | None = None
    epoch_history: list[dict] = []


class DriftFeatureOut(BaseModel):
    feature: str
    psi: float | None
    severity: str


class DriftReportOut(BaseModel):
    recent_days: int
    baseline_days: int
    n_recent_events: int
    n_baseline_events: int
    note: str | None = None
    features: list[DriftFeatureOut]


class PlatformStatsOut(BaseModel):
    """Aggregate counters for the operations overview."""

    n_products: int
    n_users: int
    n_events: int
    n_categories: int
    events_by_type: dict[str, int]
    events_last_24h: int
    n_model_versions: int
    champion_version: str | None
    champion_test_auc: float | None


class RecentEventOut(BaseModel):
    event_id: int
    user_id: int
    item_id: int
    item_title: str
    event_type: str
    ts: int
