"""Feature drift detection using the Population Stability Index (PSI).

PSI is a standard statistic for comparing a categorical/binned feature's
distribution between a baseline window and a more recent window:

    PSI = sum_over_bins( (recent_pct - baseline_pct) * ln(recent_pct / baseline_pct) )

It is the same statistic used broadly across the ML-monitoring and credit-risk
world (not tied to any specific paper or codebase); the conventional
thresholds below (<0.1 stable, 0.1-0.25 moderate, >=0.25 significant) are a
widely used rule of thumb, reproduced here as constants rather than any
library's code.

This stands in for the full-scale platform's Evidently + scheduled Airflow
drift job: the same statistical idea, computed on demand from SQLite instead
of on a schedule against Iceberg tables.
"""

from __future__ import annotations

import math
import sqlite3
import time
from dataclasses import dataclass

PSI_STABLE_THRESHOLD = 0.1
PSI_SIGNIFICANT_THRESHOLD = 0.25


@dataclass
class DriftFeatureResult:
    feature: str
    psi: float | None
    severity: str  # "stable" | "moderate" | "significant" | "insufficient_data"


def population_stability_index(
    baseline_counts: dict[int, int], recent_counts: dict[int, int]
) -> float:
    bins = set(baseline_counts) | set(recent_counts)
    baseline_total = sum(baseline_counts.values())
    recent_total = sum(recent_counts.values())
    if baseline_total == 0 or recent_total == 0:
        return 0.0

    eps = 1e-6
    psi = 0.0
    for b in bins:
        baseline_pct = max(baseline_counts.get(b, 0) / baseline_total, eps)
        recent_pct = max(recent_counts.get(b, 0) / recent_total, eps)
        psi += (recent_pct - baseline_pct) * math.log(recent_pct / baseline_pct)
    return psi


def severity_of(psi: float) -> str:
    if psi < PSI_STABLE_THRESHOLD:
        return "stable"
    if psi < PSI_SIGNIFICANT_THRESHOLD:
        return "moderate"
    return "significant"


_FEATURE_QUERIES = {
    "category_id": (
        "SELECT p.category_id AS bin, COUNT(*) AS n FROM events e "
        "JOIN products p ON p.item_id = e.item_id "
        "WHERE e.ts >= ? AND e.ts < ? GROUP BY p.category_id"
    ),
    "price_bucket": (
        "SELECT p.price_bucket AS bin, COUNT(*) AS n FROM events e "
        "JOIN products p ON p.item_id = e.item_id "
        "WHERE e.ts >= ? AND e.ts < ? GROUP BY p.price_bucket"
    ),
    "event_type": (
        "SELECT e.event_type AS bin, COUNT(*) AS n FROM events e "
        "WHERE e.ts >= ? AND e.ts < ? GROUP BY e.event_type"
    ),
}


def _bin_counts(conn: sqlite3.Connection, feature: str, start: int, end: int) -> dict[int, int]:
    rows = conn.execute(_FEATURE_QUERIES[feature], (start, end)).fetchall()
    return {row["bin"]: row["n"] for row in rows}


def compute_drift_report(
    conn: sqlite3.Connection,
    now: int | None = None,
    recent_days: int = 3,
    baseline_days: int = 7,
) -> dict:
    now = now if now is not None else int(time.time())
    recent_start = now - recent_days * 86400
    baseline_end = recent_start
    baseline_start = baseline_end - baseline_days * 86400

    n_recent = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE ts >= ? AND ts < ?", (recent_start, now)
    ).fetchone()["n"]
    n_baseline = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE ts >= ? AND ts < ?", (baseline_start, baseline_end)
    ).fetchone()["n"]

    note = None
    if n_recent == 0 or n_baseline == 0:
        note = (
            "Not enough events in one of the two windows to compute a meaningful PSI. "
            "Generate more history (larger --days-back) or widen the window."
        )

    features = []
    for feature in _FEATURE_QUERIES:
        if n_recent == 0 or n_baseline == 0:
            features.append(DriftFeatureResult(feature, None, "insufficient_data"))
            continue
        baseline_counts = _bin_counts(conn, feature, baseline_start, baseline_end)
        recent_counts = _bin_counts(conn, feature, recent_start, now)
        psi = population_stability_index(baseline_counts, recent_counts)
        features.append(DriftFeatureResult(feature, round(psi, 4), severity_of(psi)))

    return {
        "recent_days": recent_days,
        "baseline_days": baseline_days,
        "n_recent_events": n_recent,
        "n_baseline_events": n_baseline,
        "note": note,
        "features": features,
    }
