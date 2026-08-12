import time

from recsys_lite import db
from recsys_lite.constants import EVENT_VIEW
from recsys_lite.drift import compute_drift_report, population_stability_index, severity_of


def test_psi_is_zero_for_identical_distributions():
    baseline = {1: 50, 2: 50}
    recent = {1: 50, 2: 50}
    assert population_stability_index(baseline, recent) == 0.0


def test_psi_is_large_for_a_total_distribution_flip():
    baseline = {1: 100, 2: 0}
    recent = {1: 0, 2: 100}
    psi = population_stability_index(baseline, recent)
    assert psi > PSI_LARGE_THRESHOLD


PSI_LARGE_THRESHOLD = 1.0


def test_severity_thresholds():
    assert severity_of(0.05) == "stable"
    assert severity_of(0.15) == "moderate"
    assert severity_of(0.5) == "significant"


def test_compute_drift_report_flags_insufficient_data_with_no_events(tmp_path):
    conn = db.reset_db(tmp_path / "empty.db")
    conn.execute(
        "INSERT INTO products (item_id, title, category_id, brand_id, price, price_bucket) "
        "VALUES (1, 'A', 1, 1, 10.0, 1)"
    )
    conn.commit()

    report = compute_drift_report(conn, now=int(time.time()))

    assert report["note"] is not None
    assert all(f.severity == "insufficient_data" for f in report["features"])


def test_compute_drift_report_detects_a_deliberate_category_shift(tmp_path):
    conn = db.reset_db(tmp_path / "shift.db")
    conn.executemany(
        "INSERT INTO products (item_id, title, category_id, brand_id, price, price_bucket) VALUES (?,?,?,?,?,?)",
        [(1, "A", 1, 1, 10.0, 1), (2, "B", 2, 1, 10.0, 1)],
    )
    conn.execute("INSERT INTO users (user_id) VALUES (1)")

    now = int(time.time())
    baseline_ts = now - 5 * 86400  # inside the 7-day baseline window
    recent_ts = now - 1 * 86400  # inside the 3-day recent window

    # baseline: entirely category 1. recent: entirely category 2 -> maximal shift.
    events = [(1, 1, EVENT_VIEW, baseline_ts) for _ in range(30)] + [
        (1, 2, EVENT_VIEW, recent_ts) for _ in range(30)
    ]
    conn.executemany(
        "INSERT INTO events (user_id, item_id, event_type, ts) VALUES (?, ?, ?, ?)", events
    )
    conn.commit()

    report = compute_drift_report(conn, now=now, recent_days=3, baseline_days=7)
    category_result = next(f for f in report["features"] if f.feature == "category_id")

    assert report["note"] is None
    assert category_result.severity == "significant"
    assert category_result.psi is not None and category_result.psi > 1.0
