# Architecture

How recsys-lite is put together, and — just as importantly — what it
deliberately leaves out.

- [System shape](#system-shape)
- [Component reference](#component-reference)
- [The offline path](#the-offline-path)
- [The online path](#the-online-path)
- [Data model](#data-model)
- [Model architecture](#model-architecture)
- [What stands in for what](#what-stands-in-for-what)
- [Design decisions and their trade-offs](#design-decisions-and-their-trade-offs)

---

## System shape

One Python process serves the API and the web console. One SQLite file is the
system of record. There is no message broker, no orchestrator, no separate
inference server, and no external cache.

```mermaid
flowchart TB
    subgraph client["Browser — Kestrel console"]
        shop["Shop routes<br/>storefront · catalog · product · cart · checkout"]
        ops["Operations routes<br/>overview · models · drift · event stream"]
    end

    subgraph api["FastAPI process"]
        routes["serving/app.py<br/>HTTP layer"]
        rank["serving/ranking.py<br/>candidate scoring · Top-K"]
        ab["serving/ab.py<br/>sticky champion/candidate router"]
        obs["serving/observability.py<br/>/metrics"]
        store["online_store.py<br/>in-memory features, 8s TTL"]
        reg["registry.py<br/>versioned checkpoints"]
    end

    db[("SQLite<br/>products · users · events")]

    subgraph offline["Offline (CLI, run on demand)"]
        gen["generator.py"]
        feat["features.py"]
        train["train.py"]
        drift["drift.py"]
    end

    shop -->|"GET /api/*"| routes
    ops -->|"GET /api/*"| routes
    shop -->|"POST /api/events"| routes
    routes --> rank --> ab
    routes --> obs
    routes --> store
    ab --> reg
    routes -->|read + append| db
    store -->|"refresh on TTL"| db
    gen --> db
    db --> feat --> train --> reg
    db --> drift --> routes
```

The important edge is `shop -->|POST /api/events| routes --> db --> store`.
That is the feedback loop: what a shopper does becomes a row, the row becomes
a feature, and the feature changes the next recommendation. Nothing in the UI
is mocked to simulate it.

---

## Component reference

| Module | Responsibility | Notes |
|---|---|---|
| `constants.py` | Shared vocabulary sizes (item/category/brand/price-bucket/event) | Every embedding table is sized from here, so the generator can never emit an id the model cannot embed |
| `db.py` | SQLite schema, connections, reset | `PRAGMA foreign_keys = ON`; indexes on `(user_id, ts)` and `item_id` |
| `generator.py` | Synthetic catalog, shoppers, behaviour events | Per-shopper category preference and Pareto-ish activity skew, so the ranking problem is non-trivial |
| `features.py` | Point-in-time training rows | Temporal correctness + configurable hard-negative sampling |
| `online_store.py` | Serving-time features | In-memory, TTL-refreshed; read path is dict lookups |
| `dataset.py` | Torch `Dataset`, padding, temporal split | Split is by timestamp, never random |
| `model.py` | `RankingModel` | Built on `nn.TransformerEncoder` |
| `metrics.py` | ROC-AUC, NDCG@K, HitRate@K | numpy only, no scikit-learn |
| `drift.py` | Population Stability Index | Computed on request, not scheduled |
| `train.py` | Training CLI | Evaluates, registers, auto-promotes |
| `registry.py` | Model registry | `registry.json` + per-version checkpoint dirs |
| `serving/app.py` | HTTP surface | All routes; see [API.md](API.md) |
| `serving/ranking.py` | Scoring + Top-K | Builds one batch for the whole candidate pool |
| `serving/ab.py` | Traffic split | Stable hash of shopper id |
| `serving/observability.py` | `/metrics` | Prometheus text exposition |
| `web/` | Kestrel console | No build step, no dependencies |

---

## The offline path

Run explicitly, in order. Each stage writes an artifact the next one reads.

```mermaid
flowchart LR
    A["generator.py<br/>--items --users"] -->|"products, users, events"| B[("SQLite")]
    B --> C["features.py<br/>--hard-negative-fraction"]
    C -->|"training_examples.jsonl<br/>+ .meta.json with sha256"| D["train.py<br/>--epochs --embed-dim"]
    D -->|"state dict + config + metrics"| E[("models/vN/")]
    D -->|"promote if val NDCG@5 wins"| F["registry.json<br/>champion pointer"]
```

**1 — Generate.** Shoppers get a stable category preference; sessions escalate
view → cart → purchase with decaying probability; ~10% of shoppers are "power
users" producing a disproportionate share of events.

**2 — Build features.** For every cart/purchase event with at least
`min_history` prior interactions, emit one positive row whose history contains
**only events strictly before that event**, plus `negatives_per_positive`
negatives sharing the same history context. Half the negatives are drawn from
the positive's own category by default (`--hard-negative-fraction 0.5`).

**3 — Train.** Sort by timestamp, cut train/val/test, train with
`BCEWithLogitsLoss`, evaluate per epoch, keep the best-validation-NDCG@5
checkpoint, register it, and promote it to champion if it beats the incumbent.

Every artifact is reproducible from a seed. `features.py` also writes a
`sha256` of the JSONL so a model can be tied to the exact data it saw.

---

## The online path

```mermaid
sequenceDiagram
    participant U as Shopper
    participant W as Kestrel (browser)
    participant A as FastAPI
    participant S as Online store
    participant M as Model
    participant D as SQLite

    U->>W: opens a product
    W->>A: POST /api/events {view}
    A->>D: INSERT INTO events
    W->>A: GET /api/recommend/{user}
    A->>S: sequence + candidate pool
    alt cache older than 8s
        S->>D: reload products, histories, popularity
    end
    S-->>A: features
    A->>M: score whole candidate pool in one batch
    M-->>A: scores
    A-->>W: Top-K + model version + A/B variant
    W-->>U: renders with match bars
```

Two properties worth calling out:

- **One batch per request.** The candidate pool is scored as a single forward
  pass, not one call per item.
- **The TTL is visible in the UI.** After an action the storefront waits ~9s
  before re-querying, because the online store's cache is 8s. The delay is
  real and the interface says so rather than pretending it is instant.

---

## Data model

```mermaid
erDiagram
    PRODUCTS ||--o{ EVENTS : "referenced by"
    USERS    ||--o{ EVENTS : "generates"

    PRODUCTS {
        int  item_id PK
        text title
        int  category_id
        int  brand_id
        real price
        int  price_bucket
    }
    USERS {
        int user_id PK
    }
    EVENTS {
        int event_id PK
        int user_id FK
        int item_id FK
        int event_type "1=view 2=cart 3=purchase"
        int ts "unix seconds"
    }
```

`events` is append-only. Nothing in the system updates or deletes a row, which
is what makes point-in-time reconstruction honest: replaying the log at any
timestamp yields exactly the state the model would have seen.

---

## Model architecture

`RankingModel` scores one **(shopper history, candidate item)** pair.

```mermaid
flowchart LR
    subgraph inputs["Per-position embeddings, summed"]
        I["item id"] --> SUM
        C["category"] --> SUM
        B["brand"] --> SUM
        P["price bucket"] --> SUM
        E["event type"] --> SUM
        POS["position"] --> SUM
    end
    SUM["history tokens"] --> SEQ
    TGT["candidate item token<br/>(no event type — it has not happened yet)"] --> SEQ
    SEQ["sequence = history + candidate"] --> TE["nn.TransformerEncoder<br/>src_key_padding_mask"]
    TE --> POOL["take output at the candidate position"]
    POOL --> MLP["Linear → GELU → Dropout → Linear"]
    MLP --> OUT["logit → sigmoid → P(interaction)"]
```

The idea of appending the candidate to the behaviour sequence and letting
self-attention relate them comes from the Behavior Sequence Transformer
literature ([Chen et al., 2019](https://arxiv.org/abs/1905.06874)). The
implementation is original and uses PyTorch's stock encoder — see
[../THIRD_PARTY.md](../THIRD_PARTY.md).

**Cold start is a real path, not a special case.** A shopper with no history
arrives as an all-padding sequence. `src_key_padding_mask` masks it out and
the model scores on candidate attributes alone. See the honest caveat about
cold-start score *calibration* in [../README.md](../README.md#known-limitations).

---

## What stands in for what

This is a vertical slice. Each row is a deliberate substitution, not an
oversight.

| In this repo | Stands in for | Consciously omitted |
|---|---|---|
| SQLite | Operational Postgres | Replication, CDC |
| `generator.py` | A live storefront's traffic | Kafka / Debezium |
| `features.py` | Spark or dbt batch jobs | Distributed compute, a warehouse |
| `online_store.py` (TTL dict) | Feast + Redis | Streaming materialisation |
| `registry.py` (JSON + files) | MLflow tracking + registry | A tracking server, artifact store |
| `serving/app.py` | Feature API + inference API + gateway | Kubernetes, Triton, service mesh |
| `serving/ab.py` | Progressive rollout controller | Shadow traffic, automatic rollback |
| `/metrics` | Prometheus + Grafana | A scraper and dashboards |
| `drift.py` on request | Evidently on a schedule | A scheduler |

---

## Design decisions and their trade-offs

**SQLite as the system of record.** Zero setup, and the whole database is one
file you can copy. Costs: one writer at a time, and `online_store.py` reloads
in full rather than incrementally. Fine at this scale; wrong past it.

**TTL cache instead of streaming materialisation.** A dict rebuilt every 8s is
~20 lines and easy to reason about. It means a shopper's action is not visible
to the recommender for up to 8 seconds — the UI states this rather than hiding
it.

**No build step for the frontend.** Plain ES modules mean the console is
editable with any text editor and has no `node_modules`, no bundler and no
supply chain. Costs: no JSX, no tree-shaking, manual DOM work.

**Hard negatives on by default.** Uniform-random negatives are mostly trivial
and inflate offline metrics. Sampling half from the positive's own category
makes the numbers less flattering and more honest — the effect is measured in
the README.

**Model scores user → item only.** "Similar products" on the product page is a
content-based lookup (same category, nearest price), not a model call, because
this model has no item→item notion. Dressing it up as ML would misrepresent
what it does.

---

## Related documents

- [BUSINESS-FLOW.md](BUSINESS-FLOW.md) — the end-to-end journeys
- [API.md](API.md) — endpoint reference
- [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) — UI tokens and rules
- [DEVELOPMENT.md](DEVELOPMENT.md) — running and extending it
