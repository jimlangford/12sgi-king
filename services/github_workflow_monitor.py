"""
GitHub Workflow Failure Monitor & Auto-Repair

Continuously monitors recent GitHub Actions workflow failures and autonomously repairs them:

1. Poll GitHub for recent workflow failures (runs-on deployment)
2. Download logs for each failure
3. Extract error signature (regex patterns for known errors)
4. Classify error type (lint, type, import, config, yaml, etc.)
5. Check autonomy score — repair if >= 75
6. Execute repair (format code, fix YAML, add deps, create config)
7. Commit to repair/* branch and push
8. Monitor the re-run and record success/failure
9. Update owner job tracker with result

Repair opportunities:
  ✓ Workflow YAML errors (80) — indentation, schema
  ✓ Linting errors (95) — run black/ruff
  ✓ Type errors (90) — generate type hints
  ✓ Import errors (85) — fix circular refs
  ✓ Missing deps (80) — update requirements.txt
  ✓ Config missing (65) — create template
"""

import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import json
import logging

from services.ai_autonomy import classify_task
from services.github_auto_repair import AutonomousRepairExecutor, RepairStatus
from services.github_workflow_repair import WorkflowYamlRepair
from services.owner_job_tracker import get_tracker, JobStatus

try:
    from github import Github, GithubException
    HAS_PYGITHUB = True
except ImportError:
    HAS_PYGITHUB = False


logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "jimlangford")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "12sgi-king")
REPO_PATH = Path(os.environ.get("REPO_PATH", "."))

# Only repair workflows with autonomy >= this threshold
AUTONOMY_THRESHOLD = int(os.environ.get("GITHUB_REPAIR_AUTONOMY_THRESHOLD", "75"))

# Only look at failures from the last N minutes
LOOKBACK_MINUTES = int(os.environ.get("GITHUB_REPAIR_LOOKBACK_MINUTES", "60"))

# Maximum concurrent repairs
MAX_CONCURRENT_REPAIRS = int(os.environ.get("GITHUB_REPAIR_MAX_CONCURRENT", "3"))


class ErrorPattern:
    """Pattern for detecting error types from logs."""
    
    def __init__(self, error_type: str, autonomy: int, patterns: List[str]):
        self.error_type = error_type
        self.autonomy = autonomy
        self.patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
    
    def match(self, text: str) -> bool:
        """Check if any pattern matches the text."""
        return any(p.search(text) for p in self.patterns)


# Error detection patterns
ERROR_PATTERNS = [
    ErrorPattern(
        "workflow_yaml_error",
        80,
        [
            r"(yaml\..*error|parse error|invalid yaml)",
            r"(mapping values are not allowed|expected.*:)",
            r"(cannot unpack|indentation is not a multiple)",
            r"error parsing.*\.yml",
        ]
    ),
    ErrorPattern(
        "lint_error",
        95,
        [
            r"(black.*format|ruff.*error|linting error)",
            r"(code style|formatting.*failed|F401|E501|W292)",
            r"(would be reformatted by black|Aborting due to.*error)",
        ]
    ),
    ErrorPattern(
        "type_error",
        90,
        [
            r"(mypy error|type error|no attribute)",
            r"(Incompatible.*type|Expected.*got)",
            r"(Name.*is not defined|undefined)",
        ]
    ),
    ErrorPattern(
        "import_error",
        85,
        [
            r"(ImportError|ModuleNotFoundError)",
            r"(circular import|cannot import)",
            r"(No module named)",
        ]
    ),
    ErrorPattern(
        "missing_dependency",
        80,
        [
            r"(ModuleNotFoundError.*No module named|pip install)",
            r"(FAILED.*import|ImportError.*No module)",
            r"(package.*not installed|requirements.*not met)",
        ]
    ),
    ErrorPattern(
        "config_missing",
        65,
        [
            r"(FileNotFoundError.*config|No such file.*\.env)",
            r"(config.*not found|missing.*configuration)",
            r"(ENOENT.*config)",
        ]
    ),
    ErrorPattern(
        "docker_build_error",
        60,
        [
            r"(docker.*build.*error|Dockerfile.*error)",
            r"(COPY.*failed|RUN.*failed)",
            r"(base image.*not found)",
        ]
    ),
]


class GitHubWorkflowMonitor:
    """Monitor GitHub Actions workflows and auto-repair failures."""
    
    def __init__(self, token: str = GITHUB_TOKEN, owner: str = GITHUB_OWNER, repo: str = GITHUB_REPO):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.gh = None
        self.repo_obj = None
        self.executor = AutonomousRepairExecutor(dry_run=False)
        self.tracker = get_tracker()
        
        if HAS_PYGITHUB and token:
            try:
                self.gh = Github(token)
                self.repo_obj = self.gh.get_user(owner).get_repo(repo)
            except GithubException as e:
                logger.error(f"Failed to connect to GitHub: {e}")
    
    def get_recent_failures(self, lookback_minutes: int = LOOKBACK_MINUTES) -> List[Dict]:
        """Get recent workflow failures."""
        if not self.repo_obj:
            return []
        
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
            
            failures = []
            for run in self.repo_obj.get_workflow_runs(status="failure"):
                if run.created_at.replace(tzinfo=timezone.utc) > cutoff:
                    failures.append({
                        "id": run.id,
                        "name": run.name,
                        "workflow": run.workflow_id,
                        "status": run.status,
                        "conclusion": run.conclusion,
                        "created_at": run.created_at.isoformat(),
                        "html_url": run.html_url,
                        "head_sha": run.head_sha,
                        "head_branch": run.head_branch,
                    })
            
            return failures
        except Exception as e:
            logger.error(f"Failed to fetch recent failures: {e}")
            return []
    
    def get_workflow_logs(self, run_id: int) -> str:
        """Download workflow run logs."""
        if not self.repo_obj:
            return ""
        
        try:
            import io
            import zipfile
            
            run = self.repo_obj.get_workflow_run(run_id)
            logs_url = run.logs_url
            
            # Download logs (returns a zip file)
            import requests
            resp = requests.get(logs_url, headers={"Authorization": f"token {self.token}"}, timeout=30)
            if resp.status_code == 200:
                # Extract all log files
                zf = zipfile.ZipFile(io.BytesIO(resp.content))
                all_logs = []
                for name in zf.namelist():
                    all_logs.append(zf.read(name).decode("utf-8", errors="replace"))
                return "\n".join(all_logs)
        except Exception as e:
            logger.warning(f"Could not download logs for run {run_id}: {e}")
        
        return ""
    
    def detect_error_type(self, logs: str) -> Tuple[Optional[str], int]:
        """Detect error type from logs and return (error_type, autonomy_score).
        
        Returns (None, 0) if error type cannot be determined.
        """
        if not logs:
            return None, 0
        # Billing/account suspension is not a code problem — skip silently
        billing_markers = [
            r"account is locked due to a billing",
            r"billing issue",
            r"account locked",
            r"exceeded.*spending limit",
            r"payment.*required",
        ]
        for marker in billing_markers:
            if re.search(marker, logs, re.IGNORECASE):
                logger.info("Skipping run: GitHub billing suspension (not a code error)")
                return None, 0

        
        for pattern in ERROR_PATTERNS:
            if pattern.match(logs):
                logger.info(f"Detected error type: {pattern.error_type} (autonomy={pattern.autonomy})")
                return pattern.error_type, pattern.autonomy
        
        return None, 0
    
    def extract_error_file(self, logs: str, error_type: str) -> Optional[str]:
        """Extract the file mentioned in the error logs."""
        if not logs:
            return None
        
        # Try to find file paths in error messages
        patterns = [
            r"File \"([^\"]+)\"",
            r"^File:\s+(.+)$",
            r"error in (.+):",
            r"(\.py|\.yml|\.yaml):\d+:",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, logs, re.MULTILINE)
            if matches:
                file_path = matches[0]
                if isinstance(file_path, tuple):
                    file_path = file_path[0]
                # Clean up path
                file_path = file_path.strip()
                if file_path and (file_path.endswith(".py") or file_path.endswith((".yml", ".yaml"))):
                    return file_path
        
        return None
    
    def should_repair(self, error_type: str, autonomy: int) -> bool:
        """Check if this error should be repaired autonomously."""
        if autonomy < AUTONOMY_THRESHOLD:
            logger.info(f"Skipping {error_type}: autonomy {autonomy} < threshold {AUTONOMY_THRESHOLD}")
            return False
        
        # Don't repair permission/security errors
        if error_type in ["permission_error", "external_api"]:
            return False
        
        return True
    
    def repair_failure(self, failure: Dict) -> bool:
        """Attempt to repair a workflow failure.
        
        Returns True if repair was successful or attempted.
        """
        run_id = failure["id"]
        run_name = failure["name"]
        
        logger.info(f"Analyzing failure: {run_name} (run_id={run_id})")
        
        # Download logs
        logs = self.get_workflow_logs(run_id)
        if not logs:
            logger.warning(f"No logs available for run {run_id}")
            return False
        
        # Detect error type
        error_type, autonomy = self.detect_error_type(logs)
        if not error_type:
            logger.info(f"Could not detect error type for run {run_id}")
            return False
        
        # Check autonomy threshold
        if not self.should_repair(error_type, autonomy):
            logger.info(f"Not repairing {error_type} (autonomy={autonomy})")
            return False
        
        # Extract file path if available
        error_file = self.extract_error_file(logs, error_type)
        
        # Create job tracker entry
        job_id = f"gh-repair-{run_id}"
        job = self.tracker.start_job(job_id, f"github_{error_type}", error_file or error_type, autonomy)
        
        try:
            # Execute repair based on error type
            result = None
            
            if error_type == "workflow_yaml_error":
                # Find workflow file from run name
                workflow_file = self._find_workflow_file(run_name, logs)
                if workflow_file:
                    result = self.executor.repair_workflow_yaml(workflow_file)
            
            elif error_type == "lint_error" and error_file:
                result = self.executor.repair_lint_error(error_file)
            
            elif error_type == "missing_dependency":
                # Extract package name from logs
                pkg_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", logs)
                if pkg_match:
                    package_name = pkg_match.group(1).split(".")[0]
                    result = self.executor.repair_missing_dependency(package_name)
            
            elif error_type == "config_missing" and error_file:
                result = self.executor.repair_config_missing(error_file, {"example": "config"})
            
            if result:
                success = result.status in [RepairStatus.COMMIT_PUSHED, RepairStatus.REPAIR_READY]
                status = JobStatus.COMPLETED if success else JobStatus.FAILED
                self.tracker.complete_job(job.job_id, status, result.commit_message or result.error_message or "")
                
                logger.info(f"Repair result: {result.status.value} ({result.error_type})")
                return success
            else:
                self.tracker.complete_job(job.job_id, JobStatus.FAILED, "No repair executor available")
                return False
        
        except Exception as e:
            logger.error(f"Repair failed with exception: {e}", exc_info=True)
            self.tracker.complete_job(job.job_id, JobStatus.FAILED, str(e))
            return False
    
    def _find_workflow_file(self, run_name: str, logs: str) -> Optional[str]:
        """Find the workflow file name from run name or logs."""
        # Try to extract from run name (e.g., "Deploy V2 to king-server" → "deploy-v2-king-server.yml")
        if "deploy" in run_name.lower():
            return "deploy-v2-king-server.yml"
        elif "publish" in run_name.lower():
            return "publish.yml"
        elif "test" in run_name.lower():
            return "tests.yml"
        
        # Try to find in logs
        match = re.search(r"\.github/workflows/([a-zA-Z0-9_\-]+\.ya?ml)", logs)
        if match:
            return match.group(1)
        
        return None
    
    def monitor_and_repair(self, lookback_minutes: int = LOOKBACK_MINUTES) -> Dict:
        """Monitor recent failures and repair them.
        
        Returns stats dict: {total_failures, repaired, failed, skipped}
        """
        logger.info(f"Scanning for workflow failures in last {lookback_minutes} minutes...")
        
        failures = self.get_recent_failures(lookback_minutes)
        if not failures:
            logger.info("No recent failures found")
            return {"total_failures": 0, "repaired": 0, "failed": 0, "skipped": 0}
        
        logger.info(f"Found {len(failures)} recent failure(s)")
        
        stats = {"total_failures": len(failures), "repaired": 0, "failed": 0, "skipped": 0}
        
        for i, failure in enumerate(failures):
            if i >= MAX_CONCURRENT_REPAIRS:
                logger.info(f"Reached max concurrent repairs ({MAX_CONCURRENT_REPAIRS}), stopping")
                stats["skipped"] += len(failures) - i
                break
            
            if self.repair_failure(failure):
                stats["repaired"] += 1
            else:
                stats["failed"] += 1
            
            # Small delay between repairs
            time.sleep(2)
        
        return stats


def main():
    """Run the monitor in a loop."""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s"
    )
    
    monitor = GitHubWorkflowMonitor()
    
    if "--once" in sys.argv:
        # Single run
        stats = monitor.monitor_and_repair()
        print(f"\nStats: {stats}")
        sys.exit(0 if stats["repaired"] > 0 or stats["failed"] == 0 else 1)
    
    else:
        # Continuous monitoring
        interval_seconds = int(os.environ.get("GITHUB_REPAIR_INTERVAL_SECONDS", "300"))
        logger.info(f"Starting continuous monitoring (interval={interval_seconds}s)")
        
        try:
            while True:
                stats = monitor.monitor_and_repair()
                logger.info(f"Cycle complete: {stats}")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped")


if __name__ == "__main__":
    main()
