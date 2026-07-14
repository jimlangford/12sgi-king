"""
GORDON SELF-HEALING AI SYSTEM
═════════════════════════════════════════════════════════════════════════════════

A fully autonomous AI system that detects, diagnoses, and fixes programming errors,
system issues, and tenant problems — then shows you real-time what it's fixing.

✨ WATCH IT HEAL ITSELF IN REAL-TIME ✨

═════════════════════════════════════════════════════════════════════════════════
QUICK START
═════════════════════════════════════════════════════════════════════════════════

1. Start the system:
   python king-watchdog.py

2. Open healing dashboard:
   http://localhost:8799/go/healing.html
   (or via Tailscale: https://your-tailscale-domain/king/go/healing)

3. Watch Gordon work:
   - See tenant status tabs (one per tenant)
   - View real-time health score (0-100)
   - Read live guidance as it heals
   - Click "Run Healing Cycle" to trigger manual repair

═════════════════════════════════════════════════════════════════════════════════
WHAT IT DOES (Automatically)
═════════════════════════════════════════════════════════════════════════════════

Every 30 seconds for EACH TENANT:

  [1/3] DIAGNOSIS (2-3 seconds)
  ├─ Scans Python code for errors
  │  └─ Syntax errors, missing imports, logic bugs, exception handling, resource leaks
  ├─ Checks system health
  │  └─ Docker, GPU (temperature/VRAM), disk space, services
  └─ Reviews task queue
     └─ Pending tasks, failures, completions

  [2/3] REPAIR (1-2 seconds)
  ├─ Auto-fix safe commands
  │  └─ docker restart, docker prune, service restarts
  ├─ Process queued tasks
  │  └─ Retry failed tasks, execute pending work
  └─ Search web for solutions
     └─ Find best practices and error fixes

  [3/3] GUIDANCE (real-time)
  └─ Display:
     ├─ What was fixed
     ├─ What still needs attention
     └─ Recommended next steps

RESULT: Green 🟢 (healthy), Yellow 🟡 (degraded), Red 🔴 (critical)

═════════════════════════════════════════════════════════════════════════════════
THE DASHBOARD
═════════════════════════════════════════════════════════════════════════════════

TABS (one per tenant):
  tenant-123      [Health: 87/100 🟢]
  tenant-456      [Health: 64/100 🟡]
  tenant-789      [Health: 12/100 🔴]

FOR EACH TENANT:
  ┌─────────────────────────────────────────┐
  │ Health Score: 87/100 🟢                 │
  │ Status: HEALTHY                         │
  │ Progress Bar: [████████░░]              │
  ├─────────────────────────────────────────┤
  │ Diagnostics: 42  Repairs: 37  Guidance: 15 │
  │ Last Check: 2 min ago                   │
  ├─────────────────────────────────────────┤
  │ GUIDANCE:                               │
  │ Code Quality:                           │
  │   Fix 3 syntax errors                   │
  │   Install: requests, pandas             │
  │   Add exception handling (2 places)     │
  │                                         │
  │ System Health:                          │
  │   GPU at 78% VRAM (OK)                 │
  │   Disk: 65% full (OK)                  │
  │   All services running                 │
  │                                         │
  │ Task Queue:                             │
  │   5 tasks pending                       │
  │   2 completed this hour                 │
  ├─────────────────────────────────────────┤
  │ [🔧 Run Healing Cycle] [📊 Full Report]│
  └─────────────────────────────────────────┘

═════════════════════════════════════════════════════════════════════════════════
ERROR DETECTION (What it finds)
═════════════════════════════════════════════════════════════════════════════════

CODE ISSUES:
  • Syntax errors (SyntaxError, IndentationError)
    → Fix: Check syntax with python -m py_compile
  
  • Missing imports (ImportError)
    → Fix: pip install module_name
  
  • Logic errors
    → Bare except (catches all exceptions)
    → Mutable default arguments (list/dict)
    → Potential None comparisons
    → Fix: Code review + correction
  
  • Exception handling gaps
    → Risky operations without try-except
    → File I/O, subprocess, network, JSON parsing
    → Fix: Add try-except blocks
  
  • Resource leaks
    → Files opened without context manager
    → Unclosed connections
    → Fix: Use 'with' statements

SYSTEM ISSUES:
  • Docker container crashes (restart loops)
  • GPU overheating (> 85°C)
  • VRAM exhaustion (> 95%)
  • Disk full (> 90%)
  • Service connectivity failures
  • High CPU usage
  • Memory pressure

TASK ISSUES:
  • Failed tasks (auto-retry up to 3x)
  • Blocked tasks (waiting for resources)
  • Stale tasks (pending too long)

═════════════════════════════════════════════════════════════════════════════════
HEALING PHASES (Priority Order)
═════════════════════════════════════════════════════════════════════════════════

PHASE 1: CRITICAL FIXES (blocks everything)
  └─ Syntax errors, import failures
     Time: immediate (< 1 second)

PHASE 2: HIGH PRIORITY (breaks functionality)
  └─ Bare excepts, missing error handling, resource leaks
     Time: < 2 seconds

PHASE 3: MEDIUM PRIORITY (degrades performance)
  └─ Logic improvements, resource optimization
     Time: < 5 seconds

PHASE 4: LOW PRIORITY (code quality)
  └─ Cleanup, readability, best practices
     Time: < 30 seconds

═════════════════════════════════════════════════════════════════════════════════
API ENDPOINTS
═════════════════════════════════════════════════════════════════════════════════

GET /gordon/healing/dashboard
  → Get status of all tenants
  Response: { tenants: [{id, health_score, status, ...}] }

GET /gordon/healing/dashboard?tenant_ids=tenant-123,tenant-456
  → Get status of specific tenants

GET /gordon/healing/tenant/{tenant_id}
  → Get full history for one tenant

GET /gordon/healing/diagnose/{tenant_id}
  → Run diagnostics only (no repairs)

POST /gordon/healing/repair/{tenant_id}
  → Apply repairs (no diagnostics)

GET /gordon/healing/guidance/{tenant_id}
  → Get healing guidance

POST /gordon/healing/cycle/{tenant_id}
  → Run full cycle: diagnose → repair → guide

POST /gordon/healing/cycle/multi?tenant_ids=t1,t2,t3
  → Run cycle for multiple tenants

GET /gordon/healing/summary
  → Quick summary of all tenants

CURL EXAMPLES:

  # Get dashboard
  curl http://localhost:8799/gordon/healing/dashboard | jq

  # Run healing for one tenant
  curl -X POST http://localhost:8799/gordon/healing/cycle/tenant-123 | jq

  # Get guidance
  curl http://localhost:8799/gordon/healing/guidance/tenant-123 | jq .actions

═════════════════════════════════════════════════════════════════════════════════
CONFIGURATION
═════════════════════════════════════════════════════════════════════════════════

DEFAULT (all free):

  Healing Cycle Interval: 30 seconds (per tenant)
  Cycle Phases: Every iteration (diagnose → repair → guide)
  Tenant Healing: Every 2nd iteration of main loop
  Best Practices Search: Every 10 iterations
  Max Auto-Retries: 3 per task
  Web Search: DuckDuckGo (free, no API key)

TO CUSTOMIZE:

  # In king-watchdog.py
  coordinator.run_continuous_loop(interval=60, tenant_ids=["tenant-123"])

  # For different healing frequency
  # (edit gordon_coordinator.py run_continuous_loop)

═════════════════════════════════════════════════════════════════════════════════
TENANT LIFECYCLE
═════════════════════════════════════════════════════════════════════════════════

1. CREATE TENANT
   POST /gordon/healing/cycle/new-tenant-id
   → Gordon creates and registers the tenant

2. INITIAL DIAGNOSIS
   → Scans for all issues (code, system, tasks)
   → Health score calculated (0-100)

3. FIRST REPAIRS
   → Auto-fixes safe issues
   → Processes queued tasks
   → Searches web for guidance

4. CONTINUOUS MONITORING
   → Every 30 seconds per tenant
   → Auto-heal on schedule
   → Manual healing on-demand via dashboard

5. HEALTH TRACKING
   → All events logged to logs/tenant-healing/tenant-{id}.jsonl
   → Dashboard shows real-time status
   → API returns full history

═════════════════════════════════════════════════════════════════════════════════
LOGS & DATA
═════════════════════════════════════════════════════════════════════════════════

HEALING LOGS:
  logs/self-healing/healing-YYYY-MM-DD.jsonl
    └─ Self-healing diagnostic events

TENANT LOGS:
  logs/tenant-healing/tenant-{id}.jsonl
    └─ Per-tenant healing events (diagnosis, repairs, guidance)

ERROR CORRECTIONS:
  logs/gordon-coordinator/errors/corrections-YYYY-MM-DD.jsonl
    └─ Auto-fix attempts and results

TASK PROCESSING:
  logs/gordon-coordinator/tasks/tasks-YYYY-MM-DD.jsonl
    └─ Task queue events

COORDINATOR ACTIONS:
  logs/gordon-coordinator/actions-YYYY-MM-DD.jsonl
    └─ All coordination events (healing, searches, updates)

VIEW LOGS:

  # Follow tenant healing in real-time
  tail -f logs/tenant-healing/tenant-123.jsonl | jq

  # Count issues found
  cat logs/self-healing/healing-*.jsonl | jq '.total_issues' | jq -s 'add'

  # Watch auto-corrections
  tail -f logs/gordon-coordinator/errors/corrections-*.jsonl | jq

═════════════════════════════════════════════════════════════════════════════════
FILES CREATED
═════════════════════════════════════════════════════════════════════════════════

HEALING ENGINE:
  services/self_healer.py       (17 KB) — Detects Python code issues
  services/tenant_healer.py     (13 KB) — Per-tenant healing coordination
  services/healing_api.py       (4 KB) — FastAPI endpoints

DASHBOARD:
  go/healing.html               (16 KB) — Live tenant healing dashboard

INTEGRATION:
  services/gordon_coordinator.py (updated) — Includes tenant healing cycles
  services/board_api/main.py    (updated) — Routes /gordon/healing/*
  king-watchdog.py              (updated) — Passes tenant IDs to coordinator

═════════════════════════════════════════════════════════════════════════════════
MONITORING THE HEALER
═════════════════════════════════════════════════════════════════════════════════

WATCHDOG STATUS:
  tail -f watchdog.log

GORDON HEALING OUTPUT:
  [TENANT tenant-123] Running diagnostics...
  [TENANT tenant-123] Applying repairs...
  [TENANT tenant-123] Generating guidance...
  [SUMMARY] Tenant tenant-123: HEALTHY (health: 92/100)

DASHBOARD ACCESS:
  Local: http://localhost:8799/go/healing.html
  Tailscale: https://your-domain/king/go/healing.html

═════════════════════════════════════════════════════════════════════════════════
EXAMPLE SCENARIO
═════════════════════════════════════════════════════════════════════════════════

MINUTE 0:
  ✗ Tenant has:
    - 3 syntax errors in Python code
    - Docker container restarting
    - GPU at 96% VRAM
    - 5 pending tasks

MINUTE 0:30 (First Healing Cycle)
  [DIAGNOSIS]
  - Found: 3 syntax, 1 Docker issue, 1 GPU issue, 5 tasks
  - Health Score: 35/100 🔴 CRITICAL
  
  [REPAIR]
  - Auto-fixed: docker restart container (✓)
  - Processed: 3 tasks completed, 2 still pending
  - Manual: Syntax errors need code review
  
  [GUIDANCE]
  - Priority 1: Fix Python syntax errors
  - Priority 2: Reduce GPU VRAM usage (use smaller model)
  - Next: Retry remaining 2 tasks

MINUTE 1:00 (After Manual Fixes)
  You fix the syntax errors manually
  
MINUTE 1:30 (Healing Recognizes Fix)
  [DIAGNOSIS]
  - Syntax: Fixed ✓
  - Docker: Running healthy ✓
  - GPU: Still 94% (monitor) ⚠
  - Tasks: 2/5 complete
  
  [REPAIR]
  - Processed: 2 pending tasks (✓)
  
  [GUIDANCE]
  - All systems optimal
  - Reduce VRAM load in next iteration
  - Health Score: 78/100 🟡 DEGRADED

MINUTE 2:00 (Full Recovery)
  You manually offload a model
  
MINUTE 2:30 (Healing Confirms Health)
  [DIAGNOSIS]
  - All checks: PASS ✓
  - Health Score: 95/100 🟢 HEALTHY
  
  [REPAIR]
  - No issues to fix
  
  [GUIDANCE]
  - System is healthy
  - Continue monitoring GPU usage
  - All tasks complete

═════════════════════════════════════════════════════════════════════════════════
TROUBLESHOOTING
═════════════════════════════════════════════════════════════════════════════════

Issue: Dashboard shows "No tenants yet"
  Solution: Run healing cycle for at least one tenant:
    curl -X POST http://localhost:8799/gordon/healing/cycle/my-tenant

Issue: Health score not improving
  Solution: Check logs for what's blocking:
    tail -f logs/tenant-healing/my-tenant.jsonl
  Likely: Code issues that need manual fixes (auto-fix can't fix all)

Issue: Auto-fixes not working
  Solution: Auto-fix only runs safe commands (docker restart, prune).
  For other issues: Review guidance and fix manually.

Issue: Healing cycle slow
  Solution: Normal. Each cycle:
    - Scans all Python files (1-2 sec)
    - Checks all services (2-3 sec)
    - Searches web (optional, 2-5 sec)
    - Logs everything (< 1 sec)

═════════════════════════════════════════════════════════════════════════════════
GETTING HELP
═════════════════════════════════════════════════════════════════════════════════

API Documentation:
  /gordon/healing/dashboard → JSON schema of response

Guidance Specific to Your Tenant:
  /gordon/healing/guidance/{tenant_id} → Human-readable recommendations

Full Report:
  /gordon/healing/report?tenant_id=my-tenant → Comprehensive status

Live Dashboard:
  http://localhost:8799/go/healing.html → Watch it heal

═════════════════════════════════════════════════════════════════════════════════
"""

if __name__ == "__main__":
    print(__doc__)
    print("\n\nTO START:")
    print("  python king-watchdog.py")
    print("\nTO OPEN DASHBOARD:")
    print("  http://localhost:8799/go/healing.html")
