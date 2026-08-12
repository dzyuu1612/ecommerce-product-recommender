from fastapi.testclient import TestClient


def test_health_reports_a_promoted_champion(serving_env):
    with TestClient(serving_env.app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["champion_version"] is not None
        assert body["n_items"] > 0


def test_catalog_returns_products(serving_env):
    with TestClient(serving_env.app) as client:
        resp = client.get("/api/catalog?limit=5")
        assert resp.status_code == 200
        products = resp.json()
        assert 0 < len(products) <= 5
        assert {"item_id", "title", "category_id", "brand_id", "price"} <= products[0].keys()


def test_recommend_returns_k_items_with_scores_in_unit_interval(serving_env):
    with TestClient(serving_env.app) as client:
        users = client.get("/api/users").json()["user_ids"]
        user_id = users[0]

        resp = client.get(f"/api/recommend/{user_id}?k=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == user_id
        assert body["ab_variant"] == "champion"
        assert len(body["items"]) <= 5
        for item in body["items"]:
            assert 0.0 <= item["score"] <= 1.0
        # results must be sorted by score, descending
        scores = [item["score"] for item in body["items"]]
        assert scores == sorted(scores, reverse=True)


def test_recommend_handles_a_cold_start_user_with_no_history(serving_env):
    with TestClient(serving_env.app) as client:
        resp = client.get("/api/recommend/999999?k=5")
        assert resp.status_code == 200
        # a brand-new user still gets popularity-fallback candidates, not an error
        assert isinstance(resp.json()["items"], list)


def test_logging_an_event_for_an_unknown_item_returns_404(serving_env):
    with TestClient(serving_env.app) as client:
        resp = client.post("/api/events", json={"user_id": 1, "item_id": 10_000_000, "event_type": "view"})
        assert resp.status_code == 404


def test_logging_a_valid_event_is_recorded(serving_env):
    with TestClient(serving_env.app) as client:
        item_id = client.get("/api/catalog?limit=1").json()[0]["item_id"]
        resp = client.post("/api/events", json={"user_id": 424242, "item_id": item_id, "event_type": "view"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"


def test_metrics_endpoint_is_prometheus_text_format(serving_env):
    with TestClient(serving_env.app) as client:
        client.get("/health")
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "recsys_lite_uptime_seconds" in resp.text


def test_categories_endpoint_covers_the_full_category_vocab(serving_env):
    with TestClient(serving_env.app) as client:
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        categories = resp.json()
        assert len(categories) > 0
        assert all(c["n_items"] > 0 for c in categories)


def test_user_profile_reflects_real_interaction_history(serving_env):
    with TestClient(serving_env.app) as client:
        user_id = client.get("/api/users").json()["user_ids"][0]
        resp = client.get(f"/api/users/{user_id}/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == user_id
        assert body["n_events"] > 0
        assert body["is_cold_start"] is False


def test_user_profile_flags_an_unseen_user_as_cold_start(serving_env):
    with TestClient(serving_env.app) as client:
        resp = client.get("/api/users/777777777/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["n_events"] == 0
        assert body["is_cold_start"] is True
        assert body["preferred_categories"] == []


def test_models_endpoint_reports_exactly_one_champion(serving_env):
    with TestClient(serving_env.app) as client:
        resp = client.get("/api/models")
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) >= 1
        champions = [v for v in versions if v["is_champion"]]
        assert len(champions) == 1
        assert champions[0]["test_auc"] is not None


def test_product_detail_returns_a_single_product(serving_env):
    with TestClient(serving_env.app) as client:
        item_id = client.get("/api/catalog?limit=1").json()[0]["item_id"]
        resp = client.get(f"/api/products/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["item_id"] == item_id


def test_product_detail_404s_for_an_unknown_item(serving_env):
    with TestClient(serving_env.app) as client:
        assert client.get("/api/products/10000000").status_code == 404


def test_similar_items_share_the_category_and_exclude_the_anchor(serving_env):
    with TestClient(serving_env.app) as client:
        anchor = client.get("/api/catalog?limit=1").json()[0]
        resp = client.get(f"/api/similar/{anchor['item_id']}?k=3")
        assert resp.status_code == 200
        for item in resp.json():
            assert item["category_id"] == anchor["category_id"]
            assert item["item_id"] != anchor["item_id"]


def test_similar_items_404s_for_an_unknown_item(serving_env):
    with TestClient(serving_env.app) as client:
        assert client.get("/api/similar/10000000").status_code == 404


def test_event_batch_records_every_line(serving_env):
    with TestClient(serving_env.app) as client:
        ids = [p["item_id"] for p in client.get("/api/catalog?limit=3").json()]
        resp = client.post(
            "/api/events/batch",
            json={"events": [
                {"user_id": 5150, "item_id": i, "event_type": "purchase"} for i in ids
            ]},
        )
        assert resp.status_code == 200
        assert resp.json()["n_events"] == len(ids)


def test_event_batch_rejects_the_whole_order_if_any_item_is_unknown(serving_env):
    """A checkout must not half-record: one bad line rolls back the batch."""
    with TestClient(serving_env.app) as client:
        good = client.get("/api/catalog?limit=1").json()[0]["item_id"]
        before = client.get("/api/users/6270/profile").json()["n_events"]

        resp = client.post(
            "/api/events/batch",
            json={"events": [
                {"user_id": 6270, "item_id": good, "event_type": "purchase"},
                {"user_id": 6270, "item_id": 10_000_000, "event_type": "purchase"},
            ]},
        )

        assert resp.status_code == 404
        after = client.get("/api/users/6270/profile").json()["n_events"]
        assert after == before  # the valid line was not written either


def test_event_batch_rejects_an_empty_list(serving_env):
    with TestClient(serving_env.app) as client:
        assert client.post("/api/events/batch", json={"events": []}).status_code == 422


def test_stats_endpoint_reports_consistent_totals(serving_env):
    with TestClient(serving_env.app) as client:
        stats = client.get("/api/stats").json()
        assert stats["n_products"] > 0
        assert stats["n_users"] > 0
        assert stats["n_categories"] > 0
        # per-type counts must add up to the overall event total
        assert sum(stats["events_by_type"].values()) == stats["n_events"]
        assert stats["events_last_24h"] <= stats["n_events"]
        assert stats["n_model_versions"] >= 1
        assert stats["champion_version"] is not None


def test_stats_counts_a_newly_written_event(serving_env):
    with TestClient(serving_env.app) as client:
        before = client.get("/api/stats").json()
        item_id = client.get("/api/catalog?limit=1").json()[0]["item_id"]
        client.post("/api/events", json={"user_id": 8801, "item_id": item_id, "event_type": "cart"})
        after = client.get("/api/stats").json()
        assert after["n_events"] == before["n_events"] + 1
        assert after["events_by_type"]["cart"] == before["events_by_type"].get("cart", 0) + 1


def test_recent_events_are_newest_first_and_named(serving_env):
    with TestClient(serving_env.app) as client:
        events = client.get("/api/events/recent?limit=10").json()
        assert len(events) > 0
        timestamps = [e["ts"] for e in events]
        assert timestamps == sorted(timestamps, reverse=True)
        for e in events:
            # event_type is exposed as a readable name, not the raw integer code
            assert e["event_type"] in {"view", "cart", "purchase"}
            assert e["item_title"]


def test_recent_events_limit_is_clamped(serving_env):
    with TestClient(serving_env.app) as client:
        assert len(client.get("/api/events/recent?limit=3").json()) <= 3
        # an absurd limit is clamped rather than dumping the whole table
        assert len(client.get("/api/events/recent?limit=99999").json()) <= 200


def test_drift_endpoint_returns_a_report_shape(serving_env):
    with TestClient(serving_env.app) as client:
        resp = client.get("/api/drift?recent_days=3&baseline_days=7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["recent_days"] == 3
        assert body["baseline_days"] == 7
        assert {f["feature"] for f in body["features"]} == {"category_id", "price_bucket", "event_type"}
