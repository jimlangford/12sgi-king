#!/usr/bin/env bash
# pull-models.sh — pull the configured Hugging Face model into the local models volume.
# Requires the app container to be running: bash scripts/start.sh first.
# Run from the v2/ directory: bash scripts/pull-models.sh

set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_ID="${HF_MODEL_ID:-Qwen/Qwen2.5-Coder-7B-Instruct}"
echo "Pulling model: $MODEL_ID"
echo "Using HF token from container secret /run/secrets/hf_token"
echo ""

docker compose exec app python /workspace/app/hf_pull.py
echo ""
echo "Done. Model is in the models/ volume."
