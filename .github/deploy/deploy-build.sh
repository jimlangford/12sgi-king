#!/usr/bin/env bash
# Sample deploy-build.sh to run on the release directory after rsync
# Put this file in the repo root (it will be copied to each release folder during rsync)
# The deploy workflow will run it remotely if POST_DEPLOY_BUILD == 'true'
set -euo pipefail

# Example steps - customize as needed
# cd to release dir (the deploy workflow runs this in the release dir)
# Install composer deps
if [ -f composer.json ]; then
  composer install --no-dev --optimize-autoloader
fi

# If using npm frontend
if [ -f package.json ]; then
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
