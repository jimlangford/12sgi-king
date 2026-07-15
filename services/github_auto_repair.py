"""
GitHub Auto-Repair Executor — autonomously fix errors and push commits.

Repairs common CI/CD failures:
- Linting errors: Run formatter, commit
- Type errors: Generate type hints, commit
- Missing deps: Update requirements.txt, commit
- Import errors: Fix circular refs, reorganize imports
- Test flakes: Mark flaky, add retry logic
- Config missing: Create template config file
- Docker build fails: Rebuild with updated base image
- Workflow YAML: Fix syntax, indentation, schema errors

Integration with king-bridge executor:
  workboard repair job (detected error)
        ↓ classify with ai_autonomy
        ↓ if autonomy >= 75%
  build_repair_prompt() + model generates fix
        ↓ parse model response for git diff
  push_repair_commit() → creates branch, commits, pushes
        ↓
  GitHub Actions auto-triggers
        ↓
  monitor_workflow_rerun() → poll until success/failure
        ↓
  workboard tombstone: autonomous-repair:{success|failed}
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from enum import Enum

try:
    from github import Github
    HAS_PYGITHUB = True
except ImportError:
    HAS_PYGITHUB = False


# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "jimlangford")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "12sgi-king")
REPO_PATH = Path(os.environ.get("REPO_PATH", "."))

AUTO_REPAIR_DRY_RUN = os.environ.get("GITHUB_AUTO_REPAIR_DRY_RUN", "false").lower() == "true"


class RepairStatus(Enum):
    NOT_ATTEMPTED = "not-attempted"
    REPAIR_READY = "repair-ready"
    COMMIT_PUSHED = "commit-pushed"
    WORKFLOW_RUNNING = "workflow-running"
    WORKFLOW_SUCCESS = "workflow-success"
    WORKFLOW_FAILURE = "workflow-failure"
    REPAIR_FAILED = "repair-failed"
    STOPPED = "stopped"


@dataclass
class RepairResult:
    """Result of autonomous repair attempt."""
    status: RepairStatus
    error_type: str
    git_diff: str                      # Actual changes made
    commit_message: str
    commit_sha: Optional[str] = None
    branch_name: Optional[str] = None
    workflow_run_id: Optional[str] = None
    workflow_url: Optional[str] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None


class GitClient:
    """Wrapper around git CLI for local repo operations."""
    
    def __init__(self, repo_path: Path = REPO_PATH):
        self.repo_path = repo_path
    
    def run(self, *args, check=True) -> str:
        """Run git command."""
        cmd = ["git", "-C", str(self.repo_path)] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=check)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"git error: {e.stderr}")
    
    def status(self) -> str:
        """Get git status."""
        return self.run("status", "--porcelain")
    
    def diff(self, staged=False) -> str:
        """Get diff of changes."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        return self.run(*args)
    
    def add_all(self):
        """Stage all changes."""
        return self.run("add", "-A")
    
    def commit(self, message: str) -> str:
        """Commit changes."""
        return self.run("commit", "-m", message)
    
    def push(self, branch: str) -> str:
        """Push branch."""
        return self.run("push", "origin", branch)
    
    def checkout_branch(self, branch_name: str) -> str:
        """Create and checkout new branch."""
        return self.run("checkout", "-b", branch_name)
    
    def current_branch(self) -> str:
        """Get current branch."""
        return self.run("rev-parse", "--abbrev-ref", "HEAD")
    
    def get_current_sha(self) -> str:
        """Get current commit SHA."""
        return self.run("rev-parse", "HEAD")


class GitHubClient:
    """Wrapper around GitHub API (PyGithub or HTTP)."""
    
    def __init__(self, token: str = GITHUB_TOKEN, owner: str = GITHUB_OWNER, repo: str = GITHUB_REPO):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.gh = None
        
        if HAS_PYGITHUB and token:
            self.gh = Github(token)
    
    def get_workflow_run(self, run_id: str) -> dict:
        """Get GitHub Actions workflow run details."""
        if not self.gh:
            return {}
        
        try:
            repo = self.gh.get_user(self.owner).get_repo(self.repo)
            run = repo.get_workflow_run(int(run_id))
            return {
                "id": run.id,
                "status": run.status,
                "conclusion": run.conclusion,
                "html_url": run.html_url,
            }
        except Exception:
            return {}
    
    def list_recent_workflows(self, limit: int = 10) -> list:
        """List recent workflow runs."""
        if not self.gh:
            return []
        
        try:
            repo = self.gh.get_user(self.owner).get_repo(self.repo)
            runs = repo.get_workflow_runs(status="failure")
            return [
                {
                    "id": run.id,
                    "name": run.name,
                    "status": run.status,
                    "conclusion": run.conclusion,
                    "created_at": run.created_at.isoformat(),
                }
                for run in list(runs)[:limit]
            ]
        except Exception:
            return []
    
    def get_workflow_logs(self, run_id: str) -> str:
        """Download workflow logs."""
        if not self.gh:
            return ""
        
        try:
            repo = self.gh.get_user(self.owner).get_repo(self.repo)
            run = repo.get_workflow_run(int(run_id))
            logs = run.logs_url
            # PyGithub doesn't directly download logs; would need HTTP request
            return ""
        except Exception:
            return ""
    
    def trigger_workflow_rerun(self, run_id: str) -> bool:
        """Trigger a workflow re-run."""
        if not self.gh:
            return False
        
        try:
            repo = self.gh.get_user(self.owner).get_repo(self.repo)
            run = repo.get_workflow_run(int(run_id))
            run.rerun()
            return True
        except Exception:
            return False


class AutonomousRepairExecutor:
    """Execute repairs autonomously."""
    
    def __init__(self, dry_run: bool = AUTO_REPAIR_DRY_RUN):
        self.dry_run = dry_run
        self.git = GitClient()
        self.github = GitHubClient()
    
    def repair_lint_error(self, file_path: str) -> RepairResult:
        """Repair linting errors with auto-formatter."""
        start = time.time()
        branch_name = f"repair/lint/{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        try:
            # Create repair branch
            self.git.checkout_branch(branch_name)
            
            # Run auto-formatter (try black first, fallback to ruff)
            if (REPO_PATH / "pyproject.toml").exists():
                # Black is configured
                subprocess.run(["black", str(REPO_PATH / file_path)], check=False)
            else:
                # Try ruff
                subprocess.run(["ruff", "check", "--fix", str(REPO_PATH / file_path)], check=False)
            
            # Get diff
            git_diff = self.git.diff()
            if not git_diff:
                return RepairResult(
                    status=RepairStatus.STOPPED,
                    error_type="lint_error",
                    git_diff="",
                    commit_message="No changes needed",
                    error_message="Formatter made no changes"
                )
            
            # Commit
            commit_msg = f"repair: Auto-fix linting errors in {file_path}"
            if not self.dry_run:
                self.git.add_all()
                commit_sha = self.git.commit(commit_msg)
                self.git.push(branch_name)
            
            return RepairResult(
                status=RepairStatus.COMMIT_PUSHED if not self.dry_run else RepairStatus.REPAIR_READY,
                error_type="lint_error",
                git_diff=git_diff,
                commit_message=commit_msg,
                branch_name=branch_name,
                duration_seconds=time.time() - start,
            )
        
        except Exception as e:
            return RepairResult(
                status=RepairStatus.REPAIR_FAILED,
                error_type="lint_error",
                git_diff="",
                commit_message="",
                error_message=str(e),
                duration_seconds=time.time() - start,
            )
    
    def repair_workflow_yaml(self, workflow_file: str) -> RepairResult:
        """Repair GitHub Actions workflow YAML syntax/indentation errors."""
        from services.github_workflow_repair import WorkflowYamlRepair
        
        start = time.time()
        branch_name = f"repair/workflow/{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        try:
            self.git.checkout_branch(branch_name)
            
            repair = WorkflowYamlRepair(str(REPO_PATH))
            success, msg = repair.repair_workflow(workflow_file)
            
            git_diff = self.git.diff()
            if not git_diff:
                return RepairResult(
                    status=RepairStatus.STOPPED,
                    error_type="workflow_yaml_error",
                    git_diff="",
                    commit_message="No changes needed",
                    error_message="Workflow is already valid",
                    duration_seconds=time.time() - start,
                )
            
            commit_msg = f"repair: Fix YAML syntax in {workflow_file}"
            if not self.dry_run:
                self.git.add_all()
                self.git.commit(commit_msg)
                self.git.push(branch_name)
            
            return RepairResult(
                status=RepairStatus.COMMIT_PUSHED if not self.dry_run else RepairStatus.REPAIR_READY,
                error_type="workflow_yaml_error",
                git_diff=git_diff,
                commit_message=commit_msg,
                branch_name=branch_name,
                duration_seconds=time.time() - start,
            )
        
        except Exception as e:
            return RepairResult(
                status=RepairStatus.REPAIR_FAILED,
                error_type="workflow_yaml_error",
                git_diff="",
                commit_message="",
                error_message=str(e),
                duration_seconds=time.time() - start,
            )
    
    def repair_missing_dependency(self, package_name: str, version: str = "latest") -> RepairResult:
        """Add missing dependency to requirements."""
        start = time.time()
        branch_name = f"repair/deps/{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        try:
            self.git.checkout_branch(branch_name)
            
            # Find requirements file
            req_file = REPO_PATH / "requirements.txt"
            if not req_file.exists():
                req_file = REPO_PATH / "pyproject.toml"
            
            if req_file.name == "requirements.txt":
                # Add to requirements.txt
                with req_file.open("a") as f:
                    if version == "latest":
                        f.write(f"\n{package_name}\n")
                    else:
                        f.write(f"\n{package_name}=={version}\n")
            
            # Pip compile if available
            if (REPO_PATH / "requirements-lock.txt").exists():
                subprocess.run(["pip-compile", str(req_file)], cwd=REPO_PATH, check=False)
            
            git_diff = self.git.diff()
            commit_msg = f"repair: Add missing dependency {package_name}"
            
            if not self.dry_run:
                self.git.add_all()
                self.git.commit(commit_msg)
                self.git.push(branch_name)
            
            return RepairResult(
                status=RepairStatus.COMMIT_PUSHED if not self.dry_run else RepairStatus.REPAIR_READY,
                error_type="missing_dependency",
                git_diff=git_diff,
                commit_message=commit_msg,
                branch_name=branch_name,
                duration_seconds=time.time() - start,
            )
        
        except Exception as e:
            return RepairResult(
                status=RepairStatus.REPAIR_FAILED,
                error_type="missing_dependency",
                git_diff="",
                commit_message="",
                error_message=str(e),
                duration_seconds=time.time() - start,
            )
    
    def repair_config_missing(self, config_file: str, template: dict) -> RepairResult:
        """Create missing config file."""
        start = time.time()
        branch_name = f"repair/config/{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        try:
            self.git.checkout_branch(branch_name)
            
            config_path = REPO_PATH / config_file
            if config_file.endswith(".json"):
                config_path.write_text(json.dumps(template, indent=2))
            elif config_file.endswith(".yaml") or config_file.endswith(".yml"):
                import yaml
                config_path.write_text(yaml.dump(template))
            else:
                # Assume ini or properties
                lines = []
                for k, v in template.items():
                    lines.append(f"{k}={v}")
                config_path.write_text("\n".join(lines))
            
            git_diff = self.git.diff()
            commit_msg = f"repair: Create missing config file {config_file}"
            
            if not self.dry_run:
                self.git.add_all()
                self.git.commit(commit_msg)
                self.git.push(branch_name)
            
            return RepairResult(
                status=RepairStatus.COMMIT_PUSHED if not self.dry_run else RepairStatus.REPAIR_READY,
                error_type="config_missing",
                git_diff=git_diff,
                commit_message=commit_msg,
                branch_name=branch_name,
                duration_seconds=time.time() - start,
            )
        
        except Exception as e:
            return RepairResult(
                status=RepairStatus.REPAIR_FAILED,
                error_type="config_missing",
                git_diff="",
                commit_message="",
                error_message=str(e),
                duration_seconds=time.time() - start,
            )
    
    def repair_generic(self, error_type: str, fix_description: str) -> RepairResult:
        """Generic repair (used when model output guides specific fix)."""
        # This is a placeholder — in real usage, the model generates
        # the specific fix (code changes) which we then apply and commit.
        
        return RepairResult(
            status=RepairStatus.REPAIR_READY,
            error_type=error_type,
            git_diff=fix_description,
            commit_message=f"repair: Fix {error_type}",
            error_message="Generic repair requires model-guided implementation",
        )


def record_repair_result(
    result: RepairResult,
    error_detection_id: str,
    db_path: Optional[Path] = None,
) -> bool:
    """Log repair result to SQLite."""
    if db_path is None:
        db_path = Path(os.environ.get("GITHUB_REPAIR_DB", "/data/db/github_repairs.db"))
    
    try:
        import sqlite3
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS repair_results (
                id TEXT PRIMARY KEY,
                error_detection_id TEXT NOT NULL,
                error_type TEXT NOT NULL,
                status TEXT NOT NULL,
                commit_sha TEXT,
                branch_name TEXT,
                duration_seconds REAL,
                created_at TEXT NOT NULL
            )
        """)
        result_id = f"{error_detection_id}:repair"
        conn.execute("""
            INSERT INTO repair_results
              (id, error_detection_id, error_type, status, commit_sha, branch_name, duration_seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result_id,
            error_detection_id,
            result.error_type,
            result.status.value,
            result.commit_sha,
            result.branch_name,
            result.duration_seconds,
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Failed to record repair result: {e}")
        return False


if __name__ == "__main__":
    # Quick test
    executor = AutonomousRepairExecutor(dry_run=True)
    
    # Test dry-run repair
    result = executor.repair_workflow_yaml("deploy-v2-king-server.yml")
    print(f"\nWorkflow Repair Test (dry-run):")
    print(f"  Status: {result.status.value}")
    print(f"  Error Type: {result.error_type}")
    print(f"  Duration: {result.duration_seconds:.2f}s")
    if result.error_message:
        print(f"  Error: {result.error_message}")
