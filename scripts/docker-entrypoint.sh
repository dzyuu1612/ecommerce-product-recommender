#!/usr/bin/env bash
# On first boot (no registered model yet) this bootstraps a full demo dataset
# and trains a champion model, so `docker run -p 8000:8000 recsys-lite` works
# with zero setup. Mount /app/data and /app/models as volumes to persist
# across restarts instead of re-generating/re-training every time.
set -euo pipefail

data_db="${RECSYS_LITE_DB_PATH:-/app/data/recsys_lite.db}"
registry_dir="${RECSYS_LITE_REGISTRY_DIR:-/app/models}"
data_dir="$(dirname "$data_db")"
examples_path="$data_dir/training_examples.jsonl"

if [ ! -f "$registry_dir/registry.json" ]; then
  echo "[entrypoint] No trained model found under $registry_dir -- bootstrapping a demo dataset and model."
  python -m recsys_lite.generator \
    --items "${RECSYS_LITE_GEN_ITEMS:-800}" \
    --users "${RECSYS_LITE_GEN_USERS:-2000}" \
    --db-path "$data_db"
  python -m recsys_lite.features --db-path "$data_db" --out "$examples_path"
  python -m recsys_lite.train \
    --db-path "$data_db" \
    --examples-path "$examples_path" \
    --registry-dir "$registry_dir" \
    --epochs "${RECSYS_LITE_TRAIN_EPOCHS:-6}"
else
  echo "[entrypoint] Existing model registry found at $registry_dir -- skipping bootstrap."
fi

exec python -m uvicorn recsys_lite.serving.app:app --host 0.0.0.0 --port 8000
