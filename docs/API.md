# API reference

Base URL when running locally: `http://127.0.0.1:8000`

Interactive docs are generated from the Pydantic models and served at
[`/docs`](http://127.0.0.1:8000/docs) (Swagger UI) and
[`/redoc`](http://127.0.0.1:8000/redoc). This page is the narrative version.

- [Conventions](#conventions)
- [Health and metrics](#health-and-metrics)
- [Catalog](#catalog)
- [Shoppers](#shoppers)
- [Events](#events)
- [Recommendations](#recommendations)
- [Operations](#operations)
- [Error handling](#error-handling)
- [Endpoint summary](#endpoint-summary)

---

## Conventions

- All responses are JSON. All timestamps are **unix seconds** (integers).
- Money is a float in a nominal currency; the demo renders it as USD.
- `event_type` is `view` | `cart` | `purchase` on the wire. The database
  stores `1` | `2` | `3`; translation happens at the boundary.
- There is **no authentication**. Every endpoint is public and unauthenticated
  by design — see [SECURITY.md](../SECURITY.md) before exposing this anywhere.
- No rate limiting, no pagination cursors. Where a limit exists it is clamped
  server-side rather than trusted.

---

## Health and metrics

### `GET /health`

Liveness plus a snapshot of what is loaded.

```json
{ "status": "ok", "champion_version": "v2", "n_items": 800, "n_users": 2000 }
```

`status` is `ok`, or `no_champion_model` when the registry has no promoted
model — the API still starts so you can diagnose it.

### `GET /metrics`

Prometheus text exposition. Scrapeable by a real Prometheus with no adapter.

```
recsys_lite_uptime_seconds 3241.02
recsys_lite_recommend_requests_total 110.0
recsys_lite_recommend_variant_total{variant="champion"} 73.0
recsys_lite_recommend_variant_total{variant="candidate"} 37.0
recsys_lite_events_total{type="cart"} 12.0
recsys_lite_recommend_latency_ms_p50 8.41
recsys_lite_recommend_latency_ms_p95 19.77
```

Counters are in-process and reset when the process restarts.

---

## Catalog

### `GET /api/catalog`

| Query | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | `60` | Rows to return |
| `category_id` | int | — | Restrict to one category |

```json
[{ "item_id": 23, "title": "Jacket #23", "category_id": 17,
   "brand_id": 77, "price": 165.46 }]
```

### `GET /api/categories`

```json
[{ "category_id": 1, "n_items": 27 }]
```

### `GET /api/products/{item_id}`

One product. `404` if unknown.

### `GET /api/similar/{item_id}`

| Query | Type | Default |
|---|---|---|
| `k` | int | `4` |

Products in the **same category** with the **nearest price**, excluding the
anchor. `404` if the anchor is unknown.

> This is a content-based lookup, **not** a model call. The ranking model
> scores *shopper → item*; it has no item→item notion. Presenting this as ML
> would misrepresent it.

---

## Shoppers

### `GET /api/users`

| Query | Type | Default |
|---|---|---|
| `limit` | int | `30` |

```json
{ "user_ids": [1, 2, 3] }
```

### `GET /api/users/{user_id}/profile`

Works for **any** id — an unknown shopper is a valid cold-start profile, not a
`404`.

```json
{ "user_id": 1, "n_events": 42, "is_cold_start": false,
  "preferred_categories": [17, 20, 21] }
```

`preferred_categories` is the top three by interaction count, derived at
serving time from the online feature store.

---

## Events

### `POST /api/events`

```json
{ "user_id": 1, "item_id": 23, "event_type": "cart" }
```

→ `{ "status": "recorded", "n_events": 1 }`

`event_type` must match `^(view|cart|purchase)$`; anything else is `422`.
Unknown `item_id` is `404`. Unknown `user_id` is **accepted** — the row is
created, which is how new shoppers come into existence.

### `POST /api/events/batch`

Used by checkout to record a whole order.

```json
{ "events": [
    { "user_id": 1, "item_id": 23, "event_type": "purchase" },
    { "user_id": 1, "item_id": 91, "event_type": "purchase" }
] }
```

→ `{ "status": "recorded", "n_events": 2 }`

**All or nothing.** Every `item_id` is validated before any row is inserted.
One bad line means `404` and **nothing** is written. Empty list is `422`;
maximum 100 events per call.

### `GET /api/events/recent`

| Query | Type | Default | Clamp |
|---|---|---|---|
| `limit` | int | `25` | 1–200 |

Newest first, joined to product titles.

```json
[{ "event_id": 23709, "user_id": 1, "item_id": 23,
   "item_title": "Jacket #23", "event_type": "view", "ts": 1786500000 }]
```

---

## Recommendations

### `GET /api/recommend/{user_id}`

| Query | Type | Default | Notes |
|---|---|---|---|
| `k` | int | `10` | Items to return |
| `candidate_pool_size` | int | `60` | Items scored before Top-K |

```json
{
  "user_id": 1,
  "model_version": "v2",
  "ab_variant": "champion",
  "items": [
    { "item_id": 515, "title": "Watch #515", "category_id": 20,
      "brand_id": 105, "price": 163.73, "score": 0.081 }
  ]
}
```

- `score` is the model's sigmoid output for that (shopper, item) pair.
- Items are sorted by descending score.
- `ab_variant` is `champion` or `candidate`; `model_version` names the registry
  version that answered.
- Any `user_id` is valid. Unknown shoppers get a popularity-based candidate
  pool.

> **Scores are not comparable between cold-start and warm shoppers.** See
> [known limitations](../README.md#known-limitations).

---

## Operations

### `GET /api/stats`

```json
{
  "n_products": 800, "n_users": 2000, "n_events": 23709, "n_categories": 24,
  "events_by_type": { "view": 16949, "cart": 5853, "purchase": 905 },
  "events_last_24h": 199,
  "n_model_versions": 2, "champion_version": "v2",
  "champion_test_auc": 0.9992632250973011
}
```

`sum(events_by_type.values()) == n_events` is asserted by test.

### `GET /api/models`

```json
[{
  "version": "v2", "is_champion": true, "created_at": 1786464424.43,
  "val_ndcg": 0.9976, "test_auc": 0.9993, "test_ndcg": 0.9986,
  "epoch_history": [{ "epoch": 1, "train_loss": 0.508, "auc": 0.559,
                      "ndcg@5": 0.631, "hit_rate@5": 0.999, "n_groups": 1013 }]
}]
```

Every number comes from that version's real training run.

### `GET /api/drift`

| Query | Type | Default |
|---|---|---|
| `recent_days` | int | `3` |
| `baseline_days` | int | `7` |

```json
{
  "recent_days": 3, "baseline_days": 7,
  "n_recent_events": 1711, "n_baseline_events": 5460,
  "note": null,
  "features": [
    { "feature": "category_id", "psi": 0.0545, "severity": "stable" }
  ]
}
```

`severity` is `stable` (< 0.1) | `moderate` (0.1–0.25) | `significant` (≥ 0.25)
| `insufficient_data`. When a window is empty, `psi` is `null`, severity is
`insufficient_data`, and `note` explains why — no fabricated number.

---

## Error handling

| Status | When | Body |
|---|---|---|
| `404` | Unknown `item_id` | `{"detail": "unknown item_id 999"}` |
| `422` | Schema violation | FastAPI validation detail |
| `500` | Unhandled server error | FastAPI default |

The console surfaces `detail` verbatim in an inline error with a **Retry**
button, rather than a generic "something went wrong".

There is no `503` for a missing model: `/health` reports
`no_champion_model` and recommendation calls fail loudly instead of silently
returning empty results.

---

## Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness + loaded state |
| `GET` | `/metrics` | Prometheus text |
| `GET` | `/api/catalog` | Product list |
| `GET` | `/api/categories` | Categories + counts |
| `GET` | `/api/products/{item_id}` | One product |
| `GET` | `/api/similar/{item_id}` | Content-based neighbours |
| `GET` | `/api/users` | Shopper ids |
| `GET` | `/api/users/{user_id}/profile` | Profile + cold-start flag |
| `POST` | `/api/events` | Record one event |
| `POST` | `/api/events/batch` | Record an order, all-or-nothing |
| `GET` | `/api/events/recent` | Newest events |
| `GET` | `/api/recommend/{user_id}` | Top-K recommendations |
| `GET` | `/api/stats` | Platform counters |
| `GET` | `/api/models` | Registry with metrics |
| `GET` | `/api/drift` | PSI report |
