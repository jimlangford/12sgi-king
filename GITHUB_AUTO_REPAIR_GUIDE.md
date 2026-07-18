# GitHub Workflow Auto-Repair Guide

## What It Does

Your local AI now **automatically monitors GitHub for CI/CD failures** and fixes them:

```
GitHub Actions fails
  ↓ (github_workflow_monitor polls every 5 minutes)
Detect: YAML syntax, linting, type errors, missing deps
  ↓ (classify with autonomy score)
Autonomy >= 75%?
  ↓ (AutonomousRepairExecutor executes fix)
Format code, fix indentation, create config, add deps
  ↓ (push to repair/* branch)
GitHub auto-triggers workflow
  ↓ (monitor polls for success)
Owner sees job in dashboard ✓
```

## Error Types Auto-Repaired

| Error Type | Autonomy | Fix |
|---|---|---|
| **Workflow YAML** | 80 | Fix indentation, convert tabs→spaces, normalize schema |
| **Linting** | 95 | Run black/ruff auto-formatter |
| **Type errors** | 90 | Generate type hints |
| **Import errors** | 85 | Fix circular imports |
| **Missing deps** | 80 | Add package to requirements.txt |
| **Config missing** | 65 | Create template config file |

## Enable the Monitor

### Option 1: Start with Docker Compose (Recommended)

```bash
cd 12sgi-king

# Ensure GITHUB_TOKEN is set
export GITHUB_TOKEN=ghp_xxxxx

# Start the V2 stack + monitor
docker compose -f docker-compose.v2.yml up -d github-workflow-monitor

# Watch logs
docker compose -f docker-compose.v2.yml logs -f github-workflow-monitor
```

### Option 2: Run Standalone

```bash
export GITHUB_TOKEN=ghp_xxxxx
export GITHUB_OWNER=jimlangford
export GITHUB_REPO=12sgi-king

# Test (dry-run, single cycle)
python -m services.github_workflow_monitor_service --dry-run --once

# Run continuous (5 minutes between checks)
python -m services.github_workflow_monitor_service
```

## Configuration

Set these environment variables to customize behavior:

```bash
# GitHub credentials (REQUIRED)
GITHUB_TOKEN=ghp_xxxxx

# Min autonomy score to auto-repair (default: 75)
# Set to 100 to be very conservative
# Set to 50 to repair more aggressively
GITHUB_REPAIR_AUTONOMY_THRESHOLD=75

# Scan failures from last N minutes (default: 60)
GITHUB_REPAIR_LOOKBACK_MINUTES=60

# Check interval in seconds (default: 300)
GITHUB_REPAIR_INTERVAL_SECONDS=300

# Max repairs per cycle (default: 3)
# Prevents spamming GitHub with too many repairs
GITHUB_REPAIR_MAX_CONCURRENT=3

# Disable repairs (just watch, don't fix)
GITHUB_AUTO_REPAIR_DRY_RUN=false
```

## Monitor Job Tracking

All repairs are tracked in the Owner Job Dashboard:

- **URL**: https://king.tail760750.ts.net/owner_jobs.html
- **Displays**: All autonomous repairs with status
- **Approve/Reject**: Each completed repair waits for owner approval

## How It Works: Step-by-Step

### 1. Failure Detection

Monitor polls GitHub every 5 minutes (configurable):
```
GET /repos/{owner}/{repo}/actions/runs?status=failure&created=>2026-07-14T...
```

### 2. Log Analysis

Downloads workflow logs and matches against error patterns:
```
if "black.*format" in logs:
    error_type = "lint_error"
    autonomy = 95
```

### 3. Autonomy Check

Only repairs if autonomy >= threshold:
```
if autonomy >= 75:  # configurable
    execute_repair()
```

### 4. Repair Execution

Creates a `repair/*` branch and applies fix:
```
git checkout -b repair/lint/20260714T123456
black services/file.py
git add -A
git commit -m "repair: Auto-fix linting errors"
git push origin repair/lint/20260714T123456
```

### 5. GitHub Auto-Trigger

Push triggers the failed workflow to re-run automatically.

### 6. Result Tracking

Records in owner job tracker:
```
Job ID: gh-repair-12345
Status: completed
Autonomy: 95
Message: "repair: Auto-fix linting errors"
```

## Testing

### Test 1: Dry-Run (No Commits)

```bash
python -m services.github_workflow_monitor_service --dry-run --once
```

Expected output:
```
[2026-07-14 12:34:56] INFO: Scanning for workflow failures in last 60 minutes...
[2026-07-14 12:34:57] INFO: Found 2 recent failure(s)
[2026-07-14 12:34:57] INFO: Detected error type: lint_error (autonomy=95)
[2026-07-14 12:34:58] INFO: Repair result: repair-ready (lint_error)
```

### Test 2: Single Cycle

```bash
python -m services.github_workflow_monitor_service --once
```

This runs once and exits. Check:
- Owner Job Dashboard for new repairs
- GitHub for new `repair/*` branches
- GitHub Actions for re-triggered workflows

### Test 3: Continuous Mode

```bash
python -m services.github_workflow_monitor_service
# Ctrl+C to stop
```

Runs forever, checking every 5 minutes.

## Logs & Debugging

### Docker Compose Logs

```bash
# Follow logs (10 lines, stay attached)
docker compose -f docker-compose.v2.yml logs -f --tail=10 github-workflow-monitor

# View all logs
docker compose -f docker-compose.v2.yml logs github-workflow-monitor > /tmp/monitor.log
```

### Standalone Logs

Logs to stdout + JSON format. Pipe to file:
```bash
python -m services.github_workflow_monitor_service > /tmp/monitor.log 2>&1 &
```

### Database Logs

All repairs recorded to:
```
/data/db/owner_jobs.db
```

Query repairs:
```bash
sqlite3 /data/db/owner_jobs.db "SELECT * FROM owner_jobs WHERE archetype LIKE 'github%' ORDER BY created_at DESC LIMIT 10;"
```

## Troubleshooting

### Monitor starts but does no repairs

1. Check GITHUB_TOKEN is set and valid
2. Check autonomy threshold: `echo $GITHUB_REPAIR_AUTONOMY_THRESHOLD`
3. Manually run: `python -m services.github_workflow_monitor_service --dry-run --once`
4. View logs: `docker compose -f docker-compose.v2.yml logs github-workflow-monitor`

### Repairs created but workflows don't re-run

1. Repair branch was pushed: `git branch -a | grep repair/`
2. GitHub Actions might not auto-trigger on internal pushes
3. Manually re-run workflow in GitHub UI as fallback

### Too many repairs (fix the threshold)

```bash
# Be more conservative (only repair obvious errors)
export GITHUB_REPAIR_AUTONOMY_THRESHOLD=90

docker compose -f docker-compose.v2.yml up -d github-workflow-monitor
```

## Dashboard Integration

The Owner Job Dashboard automatically displays all autonomous repairs:

1. **Navigate to**: https://king.tail760750.ts.net/owner_jobs.html
2. **Filter by archetype**: `github_workflow_yaml_repair`, `github_lint_repair`, etc.
3. **Approve/Reject**: Each completed repair requires owner approval
4. **View Details**: Click job ID to see repair diff and result

## Next Steps

1. **Deploy**: `docker compose -f docker-compose.v2.yml up -d github-workflow-monitor`
2. **Monitor**: Watch Owner Job Dashboard for repairs
3. **Tune**: Adjust GITHUB_REPAIR_AUTONOMY_THRESHOLD based on results
4. **Expand**: Add more error patterns to github_workflow_monitor.py

---

**Status**: Live & ready. Monitor is polling GitHub for failures every 5 minutes.
