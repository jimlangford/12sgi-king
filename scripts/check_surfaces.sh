#!/usr/bin/env bash
# scripts/check_surfaces.sh
# Health check script for Tailscale surfaces and minimal runtime checks.
# - Reads SURFACES_LIST from environment (preferred) or .env file if present.
# - Produces clear logs and exits non-zero if any check fails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env if present and SURFACES_LIST not set in environment
if [ -z "${SURFACES_LIST:-}" ] && [ -f "$SCRIPT_DIR/../.env" ]; then
  # shellcheck disable=SC1090
  source "$SCRIPT_DIR/../.env"
fi

# If SURFACES_LIST still empty, fall back to .env.example defaults
if [ -z "${SURFACES_LIST:-}" ] && [ -f "$SCRIPT_DIR/../.env.example" ]; then
  # shellcheck disable=SC1090
  source "$SCRIPT_DIR/../.env.example"
fi

# Final fallback to hard-coded defaults (placeholders)
if [ -z "${SURFACES_LIST:-}" ]; then
  SURFACES_LIST="surfaceA=TS_IP_OR_HOSTNAME_A:8782,surfaceB=TS_IP_OR_HOSTNAME_B:8782"
fi

# Normalize into array
IFS=',' read -r -a ENTRIES <<< "$SURFACES_LIST"

FAILED=0

log() { printf "%s %s\n" "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')]" "$*"; }

# Check tailscaled presence and status (best effort)
log "Checking Tailscale..."
if command -v tailscale >/dev/null 2>&1; then
  if tailscale status >/dev/null 2>&1; then
    log "✓ Tailscale: command available and returned status"
  else
    log "✗ Tailscale: tailscale command returned non-zero or no peers visible"
    # We don't abort immediately; the surface checks may still succeed if network is fine
  fi
else
  log "✗ Tailscale: tailscale command not found on this host (continuing with host checks)"
fi

log "Starting surface health checks..."
for entry in "${ENTRIES[@]}"; do
  entry=$(echo "$entry" | tr -d '\r' | xargs)
  [ -z "$entry" ] && continue
  name=${entry%%=*}
  hostport=${entry#*=}
  if [ -z "$name" ] || [ -z "$hostport" ]; then
    log "Skipping malformed entry: $entry"
    continue
  fi

  url="http://$hostport/"
  printf "Checking %s (%s) ... " "$name" "$hostport"
  if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
    echo "OK"
    log "Checking $name... ✓ OK"
  else
    echo "FAILED"
    log "Checking $name... ✗ FAILED"
    log "  -> $name unreachable at $url"
    FAILED=1
  fi
done

if [ "$FAILED" -ne 0 ]; then
  log "One or more surfaces are unreachable. Exiting with failure."
  exit 2
fi

log "All surfaces reachable"
exit 0
