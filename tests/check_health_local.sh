#!/usr/bin/env bash
# tests/check_health_local.sh
# Quick smoke test that queries the local FastAPI health endpoints.
set -euo pipefail
BASE=${1:-"http://localhost:8000"}

echo "Checking live..."
curl -fsS "$BASE/api/v1/live" | jq || { echo "live failed"; exit 1; }

echo "Checking ready..."
curl -fsS "$BASE/api/v1/ready" | jq || { echo "ready failed"; exit 1; }

echo "Checking health..."
curl -fsS "$BASE/api/v1/health" | jq || { echo "health failed"; exit 1; }

echo "All health endpoints responded"
