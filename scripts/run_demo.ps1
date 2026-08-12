# Sets up the environment (if needed), generates data, trains a model, and
# starts the API + storefront at http://127.0.0.1:8000.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "$root\.venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv "$root\.venv"
}
$py = "$root\.venv\Scripts\python.exe"

Write-Host "Installing recsys-lite (editable, with dev extras)..."
& $py -m pip install --quiet -e "$root[dev]"

Write-Host "Generating synthetic catalog/users/events..."
& $py -m recsys_lite.generator --items 800 --users 2000

Write-Host "Building point-in-time training examples..."
& $py -m recsys_lite.features

Write-Host "Training the ranking model..."
& $py -m recsys_lite.train --epochs 6

Write-Host "Starting the API + storefront on http://127.0.0.1:8000 ..."
& $py -m uvicorn recsys_lite.serving.app:app --host 127.0.0.1 --port 8000
