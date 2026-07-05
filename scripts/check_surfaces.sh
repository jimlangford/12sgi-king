#!/usr/bin/env bash
# scripts/check_surfaces.sh
# Health check script for Tailscale surfaces on port 8782.
# Exits with non-zero if any surface is unreachable. Logs which surface failed.

set -euo pipefail

# Default surfaces (placeholders). Replace the TS_* values with actual Tailscale IPs or hostnames.
# Format: name=host:port
DEFAULT_SURFACES=(
  "surfaceA=TS_IP_OR_HOSTNAME_A:8782"
  "surfaceB=TS_IP_OR_HOSTNAME_B:8782"
  "surfaceC=TS_IP_OR_HOSTNAME_C:8782"
)

# You can override the list by setting SURFACES_LIST environment variable to a comma-separated
# list of name=host:port entries, e.g.:
# SURFACES_LIST="surfaceA=100.x.y.z:8782,surfaceB=100.a.b.c:8782"

IFS=',' read -r -a ENTRIES <<< "${SURFACES_LIST:-$(printf "%s," "${DEFAULT_SURFACES[@]}")}" 

FAILED=0

echo "Starting surface health checks..."
for entry in "${ENTRIES[@]}"; do
  # Trim whitespace
  entry=$(echo "$entry" | tr -d '\r' | xargs)
  if [ -z "$entry" ]; then
    continue
  fi
  name=${entry%%=*}
  hostport=${entry#*=}

  if [ -z "$name" ] || [ -z "$hostport" ]; then
    echo "Skipping malformed entry: $entry"
    continue
  fi

  url="http://$hostport/"
  echo -n "Checking $name ($hostport) ... "
  if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
    echo "OK"
  else
    echo "FAILED"
    echo "  -> $name unreachable at $url" >&2
    FAILED=1
  fi
done

if [ "$FAILED" -ne 0 ]; then
  echo "One or more surfaces are unreachable" >&2
  exit 2
fi

echo "All surfaces reachable"
