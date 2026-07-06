#!/usr/bin/env bash
# start.sh — build and start the v2 local owner stack.
# Run from the v2/ directory: bash scripts/start.sh

set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== 12 Stones v2 Local Owner Stack ==="
echo "Checking secret files..."

for f in secrets/hf_token.txt secrets/github_token.txt secrets/ts_authkey.txt; do
    if [[ ! -f "$f" ]]; then
        echo "  MISSING: $f"
        echo "  Create it: echo 'your_token_here' > $f"
    else
        echo "  OK: $f"
    fi
done

echo ""
echo "Starting services..."
docker compose up -d --build

echo ""
echo "Services:"
docker compose ps

echo ""
echo "Health check in 5 seconds..."
sleep 5
curl -sf http://127.0.0.1:8088/health && echo "" || echo "App not yet ready — check: docker compose logs app"
