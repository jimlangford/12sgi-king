# Test Autonomous Repairs — End-to-End Workflow

This guide tests the complete autonomous repair system: detect errors → classify → repair → approve.

## Quick Start

### 1. Start king-bridge (if not running)
```bash
docker compose -f docker-compose.v2.yml up -d king-bridge
# Verify: curl http://localhost:8109/api/v2/ready
```

### 2. Access Owner Job Dashboard
Navigate to: `https://king.tail760750.ts.net/owner_jobs.html`

Should show:
- Stats: 0 total jobs (initially empty)
- Empty jobs table
- Auto-refresh every 5s

### 3. Simulate an Autonomous Job

Run this Python snippet to emit a test repair job:

```python
import sys
from pathlib import Path

# Add repo to path
_REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO))

from services.owner_job_tracker import get_tracker, JobStatus

tracker = get_tracker()

# Simulate a linting repair job
job = tracker.start_job(
    job_id="test-lint-123",
    archetype="github_lint_repair",
    action="auto-format linting errors",
    autonomy_score=95
)

# Simulate execution steps
tracker.add_step(job.job_id, 1, "checkout branch", output="✓ Branch feature/lint/123 created")
tracker.add_step(job.job_id, 2, "run formatter", output="✓ black fixed 12 files, ruff fixed 3 issues")
tracker.add_step(job.job_id, 3, "git commit", output="✓ Committed: auto-fix linting errors")
tracker.add_step(job.job_id, 4, "git push", output="✓ Pushed to origin/feature/lint/123")

# Mark complete
tracker.complete_job(
    job.job_id,
    status=JobStatus.COMPLETED,
    result_summary="Linting errors fixed in 15 files, pushed to feature branch",
)

print(f"✓ Created test job: {job.job_id}")
```

### 4. Watch Dashboard Update

Refresh browser or wait 5s for auto-refresh. You should see:

| Job ID | Archetype | Action | Status | Autonomy | Time | Duration |
|--------|-----------|--------|--------|----------|------|----------|
| test-l... | github_lint_repair | auto-format... | completed | 95/100 | 12:34:56 | 1.2s |

### 5. Test Approval Workflow

Click the **Approve** button on the job row:

1. Modal opens with job ID pre-filled
2. "Approve" is pre-selected
3. Add optional note (e.g., "Looks good")
4. Click "Submit"

Expected behavior:
- Modal closes
- Job status changes to "approved" (green badge)
- Dashboard updates immediately

### 6. Test Rejection Workflow

Create another test job, then:

1. Click **Reject** button
2. Modal opens, select "Reject" radio
3. Add rejection reason (e.g., "Too many file changes")
4. Click "Submit"

Expected behavior:
- Job status changes to "rejected" (red badge)
- Rejection reason stored for audit

## Full Integration Test (Real Repair)

If you have a real GitHub Actions failure:

### 1. Manually trigger a linting failure

```bash
echo "x = 1" > services/test_lint_error.py  # Badly formatted
git add services/test_lint_error.py
git commit -m "test: intentional linting error"
git push origin test-lint-branch
```

### 2. Monitor GitHub Actions

Wait for workflow to fail on linting check.

### 3. Run error scanner

```bash
python -m services.github_error_scanner --scan-recent
```

Should output:
```
Detected 1 error(s):
  - lint_error (autonomy 95, confidence 92%)
```

### 4. Emit repair job to workboard

```python
from services.github_error_scanner import detect_errors_in_log
from services.v2_workboard import emit_workboard_job

# Get logs from GitHub (manually or via API)
logs = """
error: Line too long (82 > 79 characters)
FAILED: Linting check
"""

errors = detect_errors_in_log(logs)
if errors:
    error = errors[0]
    
    # Emit repair job
    emit_workboard_job(
        source="github-error-scanner",
        action=f"repair_{error.archetype_name}",
        event=f"Autonomous repair: {error.log_snippet}",
        lane="engineering",
        status="queued",
        priority="high",
        payload=error.to_repair_job(),
    )
    
    print(f"✓ Emitted repair job: {error.archetype_name} (autonomy {error.autonomy_score})")
```

### 5. Poll workboard (simulate executor)

```bash
curl -X POST http://localhost:8109/api/v2/bridge/poll \
  -H "X-Service-Token: dev-internal-token"
```

Should process and auto-heal the repair job:
```json
{
  "processed": 1,
  "results": [
    {
      "bridge_id": "...",
      "job_id": "...",
      "model": "king-repair",
      "grounded": true,
      "response_preview": "I've detected linting errors..."
    }
  ]
}
```

### 6. Monitor Job Tracking

Dashboard should now show:
- New job with archetype "github_lint_repair"
- Status "completed" (green)
- Duration and execution timestamp

### 7. Approve the repair

Click Approve, add note: "Linting repair looks correct"

## Statistics View

After several jobs, dashboard stats should show:

```
Total Jobs: 5
Completed: 4
Running: 1
Approved: 3
Avg Autonomy: 82/100
```

Breakdown by archetype:
```
github_lint_repair: 3 jobs, avg duration 1.2s
github_type_repair: 1 job, avg duration 3.4s
github_deps_repair: 1 job, avg duration 2.1s
```

## API Testing (curl)

### Fetch all jobs
```bash
curl http://localhost:8109/api/v2/owner/jobs \
  -H "X-Service-Token: dev-internal-token" | jq
```

### Fetch single job with steps
```bash
curl http://localhost:8109/api/v2/owner/jobs/test-lint-123 \
  -H "X-Service-Token: dev-internal-token" | jq
```

### Approve a job
```bash
curl -X POST http://localhost:8109/api/v2/owner/jobs/test-lint-123/approval \
  -H "X-Service-Token: dev-internal-token" \
  -H "Content-Type: application/json" \
  -d '{"decision":"approve","reason":"Looks good"}'
```

### Reject a job
```bash
curl -X POST http://localhost:8109/api/v2/owner/jobs/test-lint-123/approval \
  -H "X-Service-Token: dev-internal-token" \
  -H "Content-Type: application/json" \
  -d '{"decision":"reject","reason":"Too many files changed"}'
```

## Troubleshooting

### Dashboard shows "No jobs yet"
- Check `/data/db/owner_jobs.db` exists
- Verify SQLite schema: `sqlite3 /data/db/owner_jobs.db ".schema owner_jobs"`
- Check browser console for JS errors

### Approve/Reject buttons don't work
- Verify INTERNAL_TOKEN matches (default: `dev-internal-token`)
- Check browser Network tab for 400/500 errors
- Ensure king-bridge is running on port 8109

### Jobs not appearing in table
- Check auto-refresh is active (look for "🔄 Auto-refreshing every 5s")
- Wait 5s for next refresh cycle
- Manually refresh browser

### Repair job not created
- Verify error detection worked: `python -m services.github_error_scanner --scan-recent`
- Check workboard emit: `tail -10 .dispatch_log.jsonl`
- Verify king-bridge polling: `curl http://localhost:8109/api/v2/bridge/poll`

## Next Steps

1. **Real CI/CD Integration**: Hook GitHub Actions webhooks → auto-detect errors
2. **Automatic Repair Execution**: king-bridge autonomously executes repairs + commits
3. **PR Auto-Merge**: If all approvals passed, auto-merge the repair PR
4. **Feedback Loop**: Record repair success rate, improve models over time
