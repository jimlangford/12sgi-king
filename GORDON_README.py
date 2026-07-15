#!/usr/bin/env python3
"""
GORDON — Local AI Coordinator for 12sgi-king

A complete autonomous system that:
✓ Searches the web for best practices (free, no API keys)
✓ Detects & auto-fixes errors in real-time
✓ Manages tenant task queues with retry logic
✓ Coordinates all system services
✓ Learns from patterns & improves continuously

═══════════════════════════════════════════════════════════════════════════════
QUICK START
═══════════════════════════════════════════════════════════════════════════════

1. START THE SYSTEM:

   python king-watchdog.py
   
   This will:
   - Start board-api (port 8799)
   - Start king-bridge (port 8109)
   - Start Gordon AI coordinator (background daemon)
   - Monitor all Docker containers
   - Check Ollama, ComfyUI, system health every 30 seconds

2. ACCESS GORDON VIA API:

   # Health status
   curl http://localhost:8799/gordon/health

   # Task queue
   curl http://localhost:8799/gordon/tasks/queue

   # Web search
   curl "http://localhost:8799/gordon/search?query=Docker+best+practices"

   # Get best practices
   curl "http://localhost:8799/gordon/best-practices?topic=GPU+memory+optimization"

   # Detect & fix errors
   curl -X POST http://localhost:8799/gordon/errors/fix?auto_fix=true

   # System report
   curl "http://localhost:8799/gordon/report?report_type=full"

3. CREATE & MANAGE TASKS:

   curl -X POST http://localhost:8799/gordon/tasks/create \\
     -H "Content-Type: application/json" \\
     -d '{
       "tenant_id": "tenant-123",
       "work_type": "render",
       "params": {"workflow_id": "default"},
       "priority": "high"
     }'

═══════════════════════════════════════════════════════════════════════════════
ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│  king-watchdog (main process)                               │
│  ├─ Monitors Docker containers                              │
│  ├─ Restarts failed services                                │
│  └─ Starts Gordon coordinator thread                        │
│                                                              │
│  └─ GordonCoordinator (background daemon thread)            │
│     ├─ ErrorMonitor                                         │
│     │  ├─ Docker health checks                              │
│     │  ├─ GPU/VRAM monitoring                               │
│     │  ├─ Disk space alerts                                 │
│     │  └─ Auto-fix safe commands                            │
│     ├─ TaskOrchestrator                                     │
│     │  ├─ Task queueing by priority                         │
│     │  ├─ Retry logic (max 3 retries)                       │
│     │  └─ Tenant coordination                               │
│     ├─ WebSearch                                            │
│     │  └─ DuckDuckGo (free, no key)                         │
│     └─ Learning Loop                                        │
│        ├─ Pattern detection                                 │
│        └─ Improvement suggestions                           │
│                                                              │
│  board_api (FastAPI)                                        │
│  ├─ /board/api/* (existing endpoints)                       │
│  └─ /gordon/* (new AI capabilities)                         │
└─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
KEY FEATURES
═══════════════════════════════════════════════════════════════════════════════

1. WEB SEARCH (Free, no API key required)
   ─────────────────────────────────────

   Uses DuckDuckGo for research. Find:
   - Error solutions ("CUDA out of memory fix")
   - Best practices ("Docker health check best practices")
   - Documentation ("Ollama VRAM optimization")
   - Technology trends

   Endpoint: /gordon/search?query=...
   Example:
     /gordon/search?query=Python+async+error+handling
     → Returns links + summaries for implementation

2. ERROR DETECTION & AUTO-CORRECTION
   ──────────────────────────────────

   Continuously monitors:
   ✓ Docker daemon + containers (status, restarts, health checks)
   ✓ GPU temperature & VRAM usage (alerts on 85°C, 95% VRAM)
   ✓ System disk space (alerts on 90%, 75%)
   ✓ Service health (port connectivity)
   ✓ CPU & memory usage

   Auto-fixes:
   - docker restart <container>
   - docker system prune
   - Service restarts

   Searches web for solutions if auto-fix fails.

   Endpoint: /gordon/errors
   Auto-fix: /gordon/errors/fix?auto_fix=true

3. TASK ORCHESTRATION
   ──────────────────

   Queue work for tenants:
   - Render jobs (ComfyUI)
   - Video transcoding
   - File uploads
   - Data syncing
   - Backups

   Features:
   ✓ Priority scheduling (critical > high > normal > low)
   ✓ Automatic retry (up to 3 times)
   ✓ Per-tenant tracking
   ✓ Success rate logging

   Endpoint: /gordon/tasks/create
   Example:
     POST /gordon/tasks/create
     {
       "tenant_id": "tenant-abc",
       "work_type": "render",
       "params": {"workflow": "my_workflow.json"},
       "priority": "high"
     }

4. BEST PRACTICES DISCOVERY
   ────────────────────────

   Proactively searches for:
   - Docker container best practices
   - GPU memory optimization
   - Python error handling patterns
   - Async task queue design
   - CI/CD improvements

   Endpoint: /gordon/best-practices?topic=...

5. CONTINUOUS COORDINATION LOOP
   ───────────────────────────

   Every 30 seconds (configurable):
   1. Scan system for errors
   2. Auto-fix critical/high severity issues
   3. Search web for solutions to remaining errors
   4. Process up to 50 queued tenant tasks
   5. Log learnings & patterns
   6. Update internal state model

   Output: logs/gordon-coordinator/actions-YYYY-MM-DD.jsonl

═══════════════════════════════════════════════════════════════════════════════
FILE LOCATIONS
═══════════════════════════════════════════════════════════════════════════════

Core implementation:
  services/web_search.py           (4.5 KB) — DuckDuckGo integration
  services/error_corrector.py      (13 KB) — Health monitoring & fixing
  services/task_orchestrator.py    (13 KB) — Task queue & coordination
  services/gordon_coordinator.py   (11 KB) — Main AI loop
  services/gordon_api.py           (6 KB) — FastAPI endpoints

Integration:
  king-watchdog.py                 (6 KB) — Modified to start Gordon
  services/board_api/main.py       (includes /gordon routes)

Logs & Data:
  logs/gordon-coordinator/actions-YYYY-MM-DD.jsonl
  logs/gordon-coordinator/errors/corrections-YYYY-MM-DD.jsonl
  logs/gordon-coordinator/tasks/tasks-YYYY-MM-DD.jsonl
  watchdog.log                     (watchdog events)

═══════════════════════════════════════════════════════════════════════════════
CONFIGURATION
═══════════════════════════════════════════════════════════════════════════════

Default settings (all free/no API keys):

  Web Search:
    - Provider: DuckDuckGo (free, no key required)
    - Timeout: 5 seconds
    - Max results: 5-20 per search

  Error Monitoring:
    - Cycle interval: 30 seconds
    - Docker check timeout: 4 seconds
    - Service health check: 3 second timeout
    - GPU temp alert: >= 85°C
    - VRAM alert: >= 95%
    - Disk alert: >= 90%

  Task Orchestration:
    - Max retries: 3
    - Retry delay: 100ms between tasks
    - Max tasks per cycle: 50

To customize, edit:
  king-watchdog.py (POLL_S = 30)
  services/gordon_coordinator.py (run_continuous_loop parameters)
  services/error_corrector.py (thresholds in check_* methods)

═══════════════════════════════════════════════════════════════════════════════
EXTENDING GORDON
═══════════════════════════════════════════════════════════════════════════════

1. Add a new task handler:

   In services/task_orchestrator.py:

   def _handle_my_task(self, task: Task) -> bool:
       my_param = task.params.get("my_param", "default")
       # Do work...
       self.complete_task(task, {"result": "success"})
       return True

   Then register in execute_task():
   elif task.work_type == "my_task":
       return self._handle_my_task(task)

2. Add a new error check:

   In services/error_corrector.py:

   def check_my_service(self) -> list:
       issues = []
       # Check your service...
       if problem_detected:
           issues.append({
               "service": "my_service",
               "error": "description",
               "severity": "high",
               "fix": "corrective command"
           })
       return issues

   Then call in check_all_services():
   all_issues.extend(self.check_my_service())

3. Add a new API endpoint:

   In services/gordon_api.py:

   @router.get("/my-endpoint")
   async def my_endpoint(param: str = Query(...)):
       result = do_something(param)
       return {"result": result}

═══════════════════════════════════════════════════════════════════════════════
MONITORING & LOGS
═══════════════════════════════════════════════════════════════════════════════

View real-time coordination:

  # Follow watchdog log
  tail -f watchdog.log

  # Follow Gordon actions
  tail -f logs/gordon-coordinator/actions-$(date +%Y-%m-%d).jsonl

  # Check error corrections
  tail -f logs/gordon-coordinator/errors/corrections-$(date +%Y-%m-%d).jsonl

Get JSON summary:

  curl http://localhost:8799/gordon/report?report_type=full | jq

Check specific service health:

  curl http://localhost:8799/gordon/health | jq .health

═══════════════════════════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

Problem: Gordon not starting
  Solution: Check watchdog.log for ImportError. Ensure all services/ files exist.

Problem: Web search returns no results
  Solution: Check internet connection. DuckDuckGo may be rate-limited.
  Fallback: Manual search at https://duckduckgo.com

Problem: Auto-fix not working for my error
  Solution: auto_fix only runs safe commands (docker restart, prune).
  Manual fixes: curl -X POST /gordon/errors/fix?auto_fix=false
  Then read the suggestions and apply manually.

Problem: Tasks not being processed
  Solution: Check /gordon/tasks/queue for queue status.
  Verify tenant_id format and task handlers exist.

═══════════════════════════════════════════════════════════════════════════════
DEPENDENCIES
═══════════════════════════════════════════════════════════════════════════════

Required (included):
  - Python 3.8+
  - FastAPI
  - Uvicorn

Optional (for full features):
  - psutil (CPU/memory monitoring) — pip install psutil
  - nvidia-smi (GPU monitoring) — auto-detected

Free (no installation needed):
  - DuckDuckGo search (built-in urllib)
  - Docker CLI (must be installed)

═══════════════════════════════════════════════════════════════════════════════
"""

if __name__ == "__main__":
    print(__doc__)
    print("\nTo get started: python king-watchdog.py")
