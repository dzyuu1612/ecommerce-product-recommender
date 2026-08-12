#!/usr/bin/env bash
# Trains a second model version against the SAME training_examples.jsonl as
# the current champion, so the comparison is fair (same data, different
# architecture/hyperparameters). If it beats the champion's validation
# NDCG@5 it is auto-promoted; otherwise it's registered as a non-promoted
# candidate. Either way, /api/models will now list two versions and you can
# demo real A/B routing between them.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
py="$root/.venv/bin/python"

embed_dim="${1:-64}"
epochs="${2:-4}"
seed="${3:-99}"

"$py" -m recsys_lite.train --embed-dim "$embed_dim" --epochs "$epochs" --seed "$seed"

cat <<'EOF'

Two model versions are now registered. To route live traffic between them, set:
  export RECSYS_LITE_AB_CANDIDATE_WEIGHT=30   # 30% of users see the non-champion version
before starting the server, then check the "Model registry" section of the storefront
and the ab_variant field in /api/recommend/{user_id} responses.
EOF
