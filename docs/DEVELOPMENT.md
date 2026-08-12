# Development guide

- [Requirements](#requirements)
- [Setup](#setup)
- [The four commands](#the-four-commands)
- [Configuration](#configuration)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Working on the frontend](#working-on-the-frontend)
- [Common tasks](#common-tasks)
- [Troubleshooting](#troubleshooting)

---

## Requirements

| | |
|---|---|
| Python | 3.11+ |
| Disk | ~2 GB (mostly the PyTorch CPU wheel) |
| Network | Only for `pip install` |
| GPU | Not used. CPU-only throughout |
| Node.js | Not required — the frontend has no build step |

---

## Setup

```bash
git clone https://github.com/dzyuu1612/ecommerce-product-recommender.git
cd ecommerce-product-recommender

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Or run everything in one shot:

```powershell
.\scripts\run_demo.ps1     # Windows
```
```bash
./scripts/run_demo.sh      # macOS / Linux
```

That creates the venv, installs, generates data, trains a model and starts the
server on <http://127.0.0.1:8000>.

---

## The four commands

Each stage writes an artifact the next one reads, so you can stop and inspect
anywhere.

```bash
# 1. Generate the synthetic world           -> data/recsys_lite.db
python -m recsys_lite.generator --items 800 --users 2000 --days-back 30

# 2. Build point-in-time training rows      -> data/training_examples.jsonl
python -m recsys_lite.features --hard-negative-fraction 0.5

# 3. Train, evaluate, register, auto-promote -> models/vN/
python -m recsys_lite.train --epochs 6

# 4. Serve API + console
python -m uvicorn recsys_lite.serving.app:app --reload
```

### Useful flags

| Command | Flag | Effect |
|---|---|---|
| `generator` | `--items` / `--users` / `--days-back` | Size of the synthetic world |
| | `--seed` | Determinism — same seed, same database |
| `features` | `--negatives-per-positive` | Negatives sampled per positive (default 4) |
| | `--hard-negative-fraction` | Share drawn from the positive's own category. `0` reproduces the easy baseline |
| `train` | `--epochs` / `--batch-size` / `--lr` / `--embed-dim` | Standard knobs |
| | `--seed` | Reproducible weights |

Regenerating data **invalidates existing models** — they were fitted to
different item ids. Delete `models/` and retrain after a regeneration.

---

## Configuration

All via environment variables; there is no config file.

| Variable | Default | Purpose |
|---|---|---|
| `RECSYS_LITE_DB_PATH` | `data/recsys_lite.db` | SQLite location |
| `RECSYS_LITE_REGISTRY_DIR` | `models/` | Registry root |
| `RECSYS_LITE_AB_CANDIDATE_WEIGHT` | `0` | % of shoppers routed to the newest non-champion version |
| `RECSYS_LITE_GEN_ITEMS` / `_GEN_USERS` | `800` / `2000` | Docker first-run bootstrap size |
| `RECSYS_LITE_TRAIN_EPOCHS` | `6` | Docker first-run bootstrap epochs |

The A/B weight is read **at startup**, so changing it needs a restart:

```bash
RECSYS_LITE_AB_CANDIDATE_WEIGHT=30 python -m uvicorn recsys_lite.serving.app:app
```

---

## Project layout

```
src/recsys_lite/
    constants.py        shared vocab sizes — every embedding is sized from here
    db.py               SQLite schema + connections
    generator.py        synthetic catalog / shoppers / events
    features.py         point-in-time training rows, hard negatives
    online_store.py     serving-time features, 8s TTL
    dataset.py          torch Dataset, padding, temporal split
    model.py            RankingModel (nn.TransformerEncoder)
    metrics.py          AUC / NDCG@K / HitRate@K (numpy only)
    drift.py            Population Stability Index
    train.py            training CLI
    registry.py         versioned model registry
    serving/
        app.py          FastAPI routes
        ranking.py      candidate scoring + Top-K
        ab.py           sticky champion/candidate router
        observability.py  Prometheus /metrics
        schemas.py      request/response models
web/                    Kestrel console — no build step
    index.html          app shell
    style.css           design tokens + components
    app.js              hash router + all pages
    icons.js            the single SVG icon family
    illustrations.js    generated product artwork
tests/                  pytest suite
scripts/                run_demo, train_candidate, docker-entrypoint
docs/                   this documentation set
```

---

## Testing

```bash
pytest tests -q                       # all
pytest tests/test_features.py -q      # one module
pytest tests -q -k drift              # by keyword
pytest tests -q -x --ff               # stop at first failure, failed-first
```

`tests/conftest.py` builds a **real** miniature environment once per session:
generate → build features → train → serve. Serving tests then run against a
genuinely trained model rather than a mock, which is why they catch
integration problems a mocked suite would not.

### What is covered

| Area | Examples |
|---|---|
| Generator | Determinism for a seed; cardinality bounds |
| Features | History never contains the triggering event or anything after it; hard-negative sampling stays in-category |
| Dataset | Padding, truncation to most-recent, temporal split ordering |
| Model | Output shape, NaN-safety, cold-start all-padding, target actually influences the score |
| Metrics | AUC on perfect / inverted / tied inputs; DCG against hand-computed values |
| Drift | PSI = 0 for identical distributions; `significant` for a constructed shift |
| A/B router | Stickiness, zero-weight, split ratio over 2000 ids |
| API | Every endpoint, plus batch rollback and limit clamping |

### Adding a test

Put it in the module matching the unit under test. Use the `serving_env`
fixture for anything that needs a live app:

```python
from fastapi.testclient import TestClient

def test_catalog_respects_the_limit(serving_env):
    with TestClient(serving_env.app) as client:
        assert len(client.get("/api/catalog?limit=3").json()) <= 3
```

Name tests as a sentence describing the guarantee
(`test_event_batch_rejects_the_whole_order_if_any_item_is_unknown`), not
`test_batch_2`.

---

## Working on the frontend

No build, no watcher, no dependencies. Edit a file in `web/` and reload.

`web/app.js` is organised as: state → api → chrome → shared fragments → shop
pages → operations pages → router → boot.

### Adding a page

1. Write `async function pageThing(view, params)` that sets `view.innerHTML`.
2. Register it in `PAGES` with a title.
3. Add a case to `parseRoute()`.
4. If it deserves a sidebar entry, add it to `NAV`. If it is a detail view of
   an existing section, map it in `NAV_PARENT` so the parent stays highlighted
   — otherwise the user loses their place.

### Adding an icon

Add the path data to `PATHS` in `web/icons.js`. Keep the 24×24 viewBox and
1.5px stroke, use `currentColor`, and add no fills. Do not introduce a second
icon set, and never use an emoji.

### Frontend conventions

- Escape every interpolated string with `esc()`.
- Reserve layout with `aspect-ratio` and sized skeletons so nothing jumps.
- Capture DOM references **before** an `await` — `e.currentTarget` is null once
  dispatch ends, which was a real bug here.
- Any collapsing grid track uses `minmax(0, 1fr)`, including inside media
  queries.

Syntax check without a bundler:

```bash
node --check web/app.js
```

---

## Common tasks

**Train a second model for A/B**

```powershell
.\scripts\train_candidate.ps1 -EmbedDim 64 -Epochs 4
```
```bash
./scripts/train_candidate.sh 64 4 99
```

**Start from scratch**

```bash
rm -rf data/*.db data/*.jsonl data/*.meta.json models/v* models/registry.json
python -m recsys_lite.generator && python -m recsys_lite.features && python -m recsys_lite.train
```

**Watch the loop close**

Open the storefront in one tab and `#/ops/events` with auto-refresh in
another. Add something to the cart and watch the row appear, then wait ~9s and
reload the storefront to see the recommendations move.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/health` returns `no_champion_model` | Nothing trained | `python -m recsys_lite.train` |
| `no training examples at …` | Features not built | `python -m recsys_lite.features` |
| Recommendations do not change after an action | Online store TTL | Wait ~9s, then reload |
| A/B always shows `champion` | Weight unset, or only one version | Set `RECSYS_LITE_AB_CANDIDATE_WEIGHT` **and restart** |
| `IndexError` in embedding lookup | Model trained against a different catalog | Retrain after regenerating |
| Console shows a blank page | ES module failed to parse | Check the browser console; `node --check web/app.js` |
| Docker image ~8 GB | CUDA wheel pulled | Ensure the CPU-index line in the `Dockerfile` runs before `pip install -e .` |
