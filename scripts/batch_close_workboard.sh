#!/usr/bin/env bash
# Batch-close all open workboard jobs for 2026-07-06.
# Usage: bash scripts/batch_close_workboard.sh
set -euo pipefail
cd "$(dirname "$0")/.."
python -m services.v2_workboard --outcome "batch-closed-2026-07-06"
