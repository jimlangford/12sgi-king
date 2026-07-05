#!/usr/bin/env bash
# Server-side helper: rollback.sh
# Place this on the server at e.g. /usr/local/bin/rollback.sh and make executable.
# Usage: rollback.sh <release-folder-name>
set -euo pipefail

RELEASE_DIR=${1:-}
BASE_PATH="/var/www/elementlotus"  # update if you use a different DEPLOY_PATH on server
RELEASES_PATH="$BASE_PATH/releases"
CURRENT_SYMLINK="$BASE_PATH/current"

if [ -z "$RELEASE_DIR" ]; then
  echo "Usage: $0 <release-folder-name>"
  echo "Available releases:" >&2
  ls -1 "$RELEASES_PATH" || true
  exit 2
fi

if [ ! -d "$RELEASES_PATH/$RELEASE_DIR" ]; then
  echo "Release $RELEASE_DIR not found in $RELEASES_PATH" >&2
  exit 3
fi

# Switch symlink
ln -sfn "$RELEASES_PATH/$RELEASE_DIR" "$CURRENT_SYMLINK"
# Record last release
echo "$RELEASE_DIR" > "$BASE_PATH/CURRENT_RELEASE"

# Optionally reload webserver / services
if command -v systemctl >/dev/null 2>&1; then
  echo "Reloading webserver"
  systemctl reload nginx || true
fi

echo "Rolled back to $RELEASE_DIR"
