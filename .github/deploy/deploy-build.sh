#!/usr/bin/env bash
# Sample deploy-build.sh to run on the release directory after rsync
# This file runs server-side inside the new release folder. It now includes a surfaces healthcheck.
# Put this file in the repo root (it will be copied to each release folder during rsync)
# The deploy workflow will run it remotely if POST_DEPLOY_BUILD == 'true'
set -euo pipefail

# Run surface healthcheck if the script exists in ./scripts/check_surfaces.sh
if [ -f ./scripts/check_surfaces.sh ]; then
  echo "Running surface healthcheck: ./scripts/check_surfaces.sh"
  chmod +x ./scripts/check_surfaces.sh
  if ! ./scripts/check_surfaces.sh; then
    echo "Surface healthcheck failed. Aborting deploy-build." >&2
    exit 10
  fi
else
  echo "No surface healthcheck script found at ./scripts/check_surfaces.sh; skipping.";
fi

# Example steps - customize as needed
# Install composer deps
if [ -f composer.json ]; then
  echo "Running composer install"
  composer install --no-dev --optimize-autoloader
fi

# If using npm frontend
if [ -f package.json ]; then
  echo "Running npm ci and build"
  npm ci
  npm run build || true
fi

# Clear caches if applicable
if [ -d wp-content ]; then
  echo "Clearing WP cache (if any)"
  # place cache clear commands here
fi

# Optional: run database migrations (be careful)
# php artisan migrate --force

echo "Build steps complete"
