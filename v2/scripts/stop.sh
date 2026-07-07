#!/usr/bin/env bash
# stop.sh — stop and remove containers (volumes are preserved).
# Run from the v2/ directory: bash scripts/stop.sh

set -euo pipefail
cd "$(dirname "$0")/.."

echo "Stopping 12 Stones v2 stack..."
docker compose down
echo "Done. Volumes (data, models, ollama_data, hf_cache, tailscale_state) are preserved."
