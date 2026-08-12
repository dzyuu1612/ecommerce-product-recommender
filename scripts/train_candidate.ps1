# Trains a second model version against the SAME training_examples.jsonl as
# the current champion, so the comparison is fair (same data, different
# architecture/hyperparameters). If it beats the champion's validation
# NDCG@5 it is auto-promoted; otherwise it's registered as a non-promoted
# candidate. Either way, `/api/models` will now list two versions and you
# can demo real A/B routing between them.
param(
    [int]$EmbedDim = 64,
    [int]$Epochs = 4,
    [int]$Seed = 99
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\.venv\Scripts\python.exe"

& $py -m recsys_lite.train --embed-dim $EmbedDim --epochs $Epochs --seed $Seed

Write-Host ""
Write-Host "Two model versions are now registered. To route live traffic between them, set:"
Write-Host '  $env:RECSYS_LITE_AB_CANDIDATE_WEIGHT = "30"   # 30% of users see the non-champion version'
Write-Host "before starting the server, then check the 'Model registry' section of the storefront"
Write-Host "and the ab_variant field in /api/recommend/{user_id} responses."
