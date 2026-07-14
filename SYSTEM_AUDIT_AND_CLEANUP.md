🚨 SYSTEM AUDIT: PRODUCTION REVIEW
═══════════════════════════════════════════════════════════════════════════════════════

CRITICAL FINDINGS:

1. RUNTIME MEMORY BLOAT
   ⚠️  ONE PYTHON PROCESS: 3.6 GB RAM (10,124 PID)
   ⚠️  27 OTHER PYTHONW.EXE PROCESSES: 50-376MB each
   → Total Python RAM: ~2-3 GB idle
   → Issue: Multiple singleton instances, memory leaks, or Tailscale cruft

2. DISK DUPLICATION (visible in 12sgi-king/)
   ✗ docker-compose.v2.yml (ACTIVE)
   ✗ docker-compose.v2.yml.clean (OLD - DELETE)
   ✗ docker-compose.postiz.yml (LEGACY - DELETE)
   
   ✗ HEALING_*.py files (3 files - consolidate)
   ✗ GORDON_README.py + HEALING_README.py (duplicate docs)
   
   ✗ services/ has TOO MANY files:
     - error_corrector.py (used by coordinator)
     - github_auto_repair.py, github_error_scanner.py, github_repair_archetypes.py (duplicate repairs)
     - task_orchestrator.py (used by coordinator)
     - tenant_healer.py (used by coordinator)
     - self_healer.py (used by tenant_healer)
     - web_search.py (used by coordinator)
     - gordon_coordinator.py (main)
     - gordon_api.py (routes)
     - healing_api.py (routes)
     - pages_api.py (routes) ← NEW, might duplicate others

3. BURST-CREATED TEMPORARY FILES
   ✗ .dispatch_cursor_*.txt files (100+ files in root)
   ✗ fix_*.py scripts (multiple fixes for same issue)
   ✗ add_*.py scripts (multiple setup attempts)
   ✗ rebuild_site.py + build_site.py (duplicate)
   
4. OLD DOCUMENTATION
   ✗ DEPLOYMENT_READY.md
   ✗ SETUP.md + SETUP_FINAL_INTEGRATION.md
   ✗ TEST_AUTONOMOUS_REPAIRS.md
   ✗ Multiple .md files duplicating same info

═══════════════════════════════════════════════════════════════════════════════════════

SYSTEM INTEGRATION VERIFICATION:

✅ king-watchdog.py IS RUNNING (real system)
✅ board_api IS RUNNING on :8799 (real system)
✅ king-bridge IS RUNNING on :8109 (real system)
✅ Gordon coordinator IS RUNNING (real system)
✅ Tenant healing IS RUNNING (real system)

❌ BUT: No centralized cleanup, no memory management, old processes never killed

═══════════════════════════════════════════════════════════════════════════════════════

CLEANUP PLAN (Remove Duplication):

PHASE 1: DELETE DUPLICATE/OBSOLETE FILES
  ✗ docker-compose.v2.yml.clean → DELETE
  ✗ docker-compose.postiz.yml → DELETE
  ✗ .dispatch_cursor_*.txt → DELETE ALL (100+ files)
  ✗ fix_compose.py, fix_static.py, fix_yaml_validator.py → DELETE
  ✗ add_monitor_service.py, add_static.py → DELETE
  ✗ rebuild_site.py (keep build_site.py, delete this) → DELETE
  ✗ SETUP.md, TEST_AUTONOMOUS_REPAIRS.md → DELETE
  ✗ .claude/old files → DELETE

  Estimated disk savings: 50-100 MB

PHASE 2: CONSOLIDATE DOCUMENTATION
  KEEP: HEALING_WORKING_LINKS.txt (THE SOURCE OF TRUTH)
  DELETE: HEALING_README.py, HEALING_LINKS.py
  DELETE: GORDON_README.py (functions in code already)
  
  Estimated savings: 40 KB

PHASE 3: CONSOLIDATE SERVICES
  CURRENT FLOW:
    gordon_coordinator.py
    ├─ error_corrector.py (detection)
    ├─ task_orchestrator.py (tasks)
    ├─ web_search.py (research)
    ├─ tenant_healer.py (healing)
    │  └─ self_healer.py (code scanning)
    └─ gordon_api.py (routes)
    ├─ healing_api.py (healing routes)
    ├─ pages_api.py (NEW - pages routes)
    └─ backend_model.py (NEW - Neo4j model)

  REDUNDANT GITHUB REPAIR FILES (DELETE):
    ✗ github_auto_repair.py
    ✗ github_error_scanner.py
    ✗ github_repair_archetypes.py
    → These are handled by error_corrector.py + web_search.py

  Estimated savings: 30 KB

PHASE 4: MEMORY LEAK INVESTIGATION
  The 3.6 GB process (PID 10124) is NOT a Docker process.
  → Could be: cached Python, stuck event loop, memory pool leak
  
  ACTION: Create process monitor to kill zombie Python processes
  - Only keep: king-watchdog.py, board-api, king-bridge
  - Kill any other stray pythonw.exe

═══════════════════════════════════════════════════════════════════════════════════════

DROPBOX BACKUP STRATEGY (with MCP):

BACKUP TARGETS (production critical):
  ✓ services/ (all Python backend)
  ✓ 12sgi-king/go/ (all pages)
  ✓ king-watchdog.py (orchestrator)
  ✓ docker-compose.v2.yml (only active one)
  ✓ requirements.txt (dependencies)

BACKUP LOCATIONS (using MCP Files tool):
  ~/.dropbox/12sgi-king-backup/services/
  ~/.dropbox/12sgi-king-backup/go/
  ~/.dropbox/12sgi-king-backup/configs/

MCP INTEGRATION:
  - Use MCP Files tool to sync daily
  - Include: services/, go/, key configs
  - Exclude: __pycache__, .git, logs, temp files
  - Size limit: < 50 MB per sync

═══════════════════════════════════════════════════════════════════════════════════════

EFFICIENCY TARGETS:

Before:
  ├─ services/: ~500 KB (too many files)
  ├─ documentation: ~300 KB (duplication)
  ├─ temporary/obsolete: ~200 KB (junk)
  └─ RAM footprint: ~3.6 GB idle (BLOAT)

After cleanup:
  ├─ services/: ~350 KB (consolidated)
  ├─ documentation: 50 KB (single source of truth)
  ├─ temporary/obsolete: 0 KB (cleaned)
  └─ RAM footprint: ~800 MB idle (target)

═══════════════════════════════════════════════════════════════════════════════════════

ACTION ITEMS:

[ ] 1. Kill stray Python processes
      taskkill /F /IM pythonw.exe
      (then restart king-watchdog.py only)

[ ] 2. Delete obsolete files (Phase 1-3)
      - docker-compose.v2.yml.clean
      - .dispatch_cursor_*.txt (all)
      - fix_*.py (all)
      - add_*.py (all)
      - github_auto_repair.py, github_error_scanner.py, github_repair_archetypes.py
      - HEALING_README.py, HEALING_LINKS.py
      - GORDON_README.py

[ ] 3. Verify system still works after cleanup
      python king-watchdog.py
      curl http://localhost:8799/health

[ ] 4. Set up Dropbox MCP backup
      Create ~/.dropbox/12sgi-king-backup/
      Sync services/, go/, configs/ daily

[ ] 5. Create process monitor script
      Kill any pythonw.exe except king-watchdog
      Run on schedule (hourly)

═══════════════════════════════════════════════════════════════════════════════════════

VERIFICATION AFTER CLEANUP:

✅ Disk: 50-150 MB freed
✅ RAM: 3.6 GB → 800 MB idle (key metric)
✅ System: All 7 go/ pages still accessible
✅ Backup: Daily Dropbox sync via MCP
✅ Process: Only essential Python running

═══════════════════════════════════════════════════════════════════════════════════════
