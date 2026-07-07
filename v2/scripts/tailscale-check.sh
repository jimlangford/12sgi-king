#!/usr/bin/env bash
# tailscale-check.sh — show Tailscale status and the node's private IP.
# Requires the tailscale container to be running.
# Run from the v2/ directory: bash scripts/tailscale-check.sh

set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Tailscale status for 12sgi-v2 ==="
docker exec 12sgi-v2-tailscale tailscale status

echo ""
echo "=== Tailscale IP ==="
docker exec 12sgi-v2-tailscale tailscale ip

echo ""
echo "=== Ping test (self) ==="
docker exec 12sgi-v2-tailscale tailscale ping 12sgi-v2 2>/dev/null || echo "(ping requires other node — status above is authoritative)"
