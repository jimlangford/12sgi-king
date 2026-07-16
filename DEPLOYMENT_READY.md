# 🤖 GitHub Autonomous Workflow Monitor — DEPLOYMENT READY

## What's Built

Your local AI now **autonomously scans GitHub for CI/CD failures** and fixes them:

```
GitHub Actions fails
  ↓ (every 5 minutes)
github_workflow_monitor polls GitHub
  ↓ (downloads logs, analyzes)
Detects: YAML syntax, linting, types, imports, deps, config errors
  ↓ (classifies with autonomy score)
Autonomy >= 75%?
  ↓ YES (repair automatically)
AutonomousRepairExecutor runs fix (format, indent, create files)
  ↓ (git push repair/* branch)
GitHub auto-triggers workflow re-run
  ↓ (workflow passes)
Owner sees job in Dashboard ✓
```

## 📦 New Modules (Committed to Main)

1. **services/github_workflow_monitor.py** (15KB)
   - Polls GitHub for recent failures
   - Analyzes logs with 6 error patterns
   - Classifies error type + autonomy score
   - Executes repair if score >= threshold

2. **services/github_workflow_monitor_service.py** (4KB)
   - Async background service wrapper
   - Supports --dry-run and --once modes
   - Continuous monitoring loop
   - JSON logging

3. **services/github_workflow_repair.py** (8KB)
   - Detects YAML syntax, indentation errors
   - Fixes tab→space, normalizes indentation
   - Validates workflow schema
   - Dry-run support

4. **services/github_repair_archetypes.py** (Updated)
   - Added github_workflow_yaml_repair (autonomy 80)

5. **services/github_auto_repair.py** (Updated)
   - Added repair_workflow_yaml() executor method

6. **GITHUB_AUTO_REPAIR_GUIDE.md**
   - Complete user guide with examples

## 🚀 How to Deploy

### Option 1: Docker Compose (Recommended)

```bash
cd 12sgi-king
export GITHUB_TOKEN=ghp_xxxxx

# Manually add this service to docker-compose.v2.yml before 'volumes:' section:

cat >> docker-compose.v2.yml.patch << 'EOF'

  github-workflow-monitor:
    build: { context: ., dockerfile: services/Dockerfile }
    command: ["python", "-m", "services.github_workflow_monitor_service"]
    environment:
      <<: *common-env
      GITHUB_TOKEN: ${GITHUB_TOKEN:-}
      GITHUB_OWNER: ${GITHUB_OWNER:-jimlangford}
      GITHUB_REPO: ${GITHUB_REPO:-12sgi-king}
      GITHUB_WORKFLOW_MONITOR_ENABLED: ${GITHUB_WORKFLOW_MONITOR_ENABLED:-true}
      GITHUB_REPAIR_LOOKBACK_MINUTES: ${GITHUB_REPAIR_LOOKBACK_MINUTES:-60}
      GITHUB_REPAIR_INTERVAL_SECONDS: ${GITHUB_REPAIR_INTERVAL_SECONDS:-300}
      GITHUB_REPAIR_AUTONOMY_THRESHOLD: ${GITHUB_REPAIR_AUTONOMY_THRESHOLD:-75}
      GITHUB_REPAIR_MAX_CONCURRENT: ${GITHUB_REPAIR_MAX_CONCURRENT:-3}
      GITHUB_AUTO_REPAIR_DRY_RUN: ${GITHUB_AUTO_REPAIR_DRY_RUN:-false}
      REPO_PATH: /repo
    volumes:
      - v2-db:/data/db
      - v2-dispatch:/data/dispatch
      - .:/repo
    depends_on: [king-bridge]
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

# Then start:
docker compose -f docker-compose.v2.yml up -d github-workflow-monitor

# Watch logs
docker compose -f docker-compose.v2.yml logs -f github-workflow-monitor
```

### Option 2: Standalone

```bash
export GITHUB_TOKEN=ghp_xxxxx

# Test (dry-run, single cycle)
python -m services.github_workflow_monitor_service --dry-run --once

# Run continuous
python -m services.github_workflow_monitor_service
```

## 📊 Configuration

Set these to customize:

```bash
GITHUB_REPAIR_AUTONOMY_THRESHOLD=75    # Min score to repair (50-100)
GITHUB_REPAIR_LOOKBACK_MINUTES=60      # Scan window
GITHUB_REPAIR_INTERVAL_SECONDS=300     # Check interval (5 min default)
GITHUB_REPAIR_MAX_CONCURRENT=3         # Max repairs per cycle
GITHUB_AUTO_REPAIR_DRY_RUN=false       # Test mode
```

## ✅ Auto-Repaired Error Types

| Error | Autonomy | Fix |
|---|---|---|
| Workflow YAML | 80 | Fix indentation, tabs→spaces |
| Linting | 95 | Run black/ruff |
| Type errors | 90 | Generate type hints |
| Imports | 85 | Fix circular refs |
| Missing deps | 80 | Add to requirements.txt |
| Config missing | 65 | Create template |

## 📈 Monitor Job Dashboard

All repairs tracked and visible at:
- **URL**: https://king.tail760750.ts.net/owner_jobs.html
- **View**: All autonomous repairs with timestamps
- **Approve/Reject**: Each repair waits for owner sign-off

## 🧪 Testing

### 1. Dry-Run (No Commits)
```bash
python -m services.github_workflow_monitor_service --dry-run --once
```

### 2. Single Cycle
```bash
python -m services.github_workflow_monitor_service --once
```

### 3. Continuous
```bash
python -m services.github_workflow_monitor_service
# Ctrl+C to stop
```

## 📝 Status

✅ **All code committed to main**
- github_workflow_monitor.py
- github_workflow_monitor_service.py  
- github_workflow_repair.py (+ fixes)
- github_repair_archetypes.py (+ yaml repair)
- github_auto_repair.py (+ repair_workflow_yaml method)
- GITHUB_AUTO_REPAIR_GUIDE.md

⚠️ **Manual Step Needed**
- Add github-workflow-monitor service to docker-compose.v2.yml (copy from Option 1 above)
- OR run standalone: `python -m services.github_workflow_monitor_service`

## 🔍 Debugging

```bash
# View monitor logs
docker compose -f docker-compose.v2.yml logs -f github-workflow-monitor

# View owner job tracker DB
sqlite3 /data/db/owner_jobs.db "SELECT * FROM owner_jobs WHERE archetype LIKE 'github%' LIMIT 5;"

# Test dry-run
python -m services.github_workflow_monitor_service --dry-run --once
```

## 📖 Full Documentation

See **GITHUB_AUTO_REPAIR_GUIDE.md** for:
- Step-by-step how it works
- All configuration options
- Troubleshooting guide
- Dashboard integration

---

**Next Steps:**

1. Add service to docker-compose.v2.yml (see Option 1 above)
2. Set GITHUB_TOKEN env var
3. Start: `docker compose -f docker-compose.v2.yml up -d github-workflow-monitor`
4. Watch: `docker compose -f docker-compose.v2.yml logs -f github-workflow-monitor`
5. Approve repairs in Owner Job Dashboard

**Status**: Ready to deploy. All code tested and committed.
