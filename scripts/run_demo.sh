#!/usr/bin/env bash
# Sets up the environment (if needed), generates data, trains a model, and
# starts the API + storefront at http://127.0.0.1:8000.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if [ ! -d "$root/.venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$root/.venv"
fi
py="$root/.venv/bin/python"

echo "Installing recsys-lite (editable, with dev extras)..."
"$py" -m pip install --quiet -e "$root[dev]"

echo "Generating synthetic catalog/users/events..."
"$py" -m recsys_lite.generator --items 800 --users 2000

echo "Building point-in-time training examples..."
"$py" -m recsys_lite.features

echo "Training the ranking model..."
"$py" -m recsys_lite.train --epochs 6

echo "Starting the API + storefront on http://127.0.0.1:8000 ..."
"$py" -m uvicorn recsys_lite.serving.app:app --host 127.0.0.1 --port 8000
