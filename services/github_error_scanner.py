"""
GitHub CI/CD Error Autonomous Repair — teach models to clear errors independently.

Purpose:
  Monitor GitHub Actions workflows, detect failures, classify errors, and
  autonomously repair common issues (linting, type errors, missing deps, etc.)
  without owner intervention.

Architecture:
  GitHub Actions Workflow (fails)
        ↓ webhook / polling
  github_error_scanner (detects + classifies)
        ↓ error archetype + context
  workboard (emits repair job, engineering lane)
        ↓ poll
  king-bridge + ai_autonomy (classify as repair task)
        ↓ if autonomy_score >= 75
  king-repair model (autonomous fix)
        ↓ generate patch / config change
  auto_git_commit (push fix + trigger re-run)
        ↓
  GitHub Actions re-run (passes)
        ↓ webhook
  workboard (record success)

Error Archetypes (Repair Autonomy):
  ✓ lint_error (95)           — Auto-fix linting (black, ruff, etc.)
  ✓ type_error (90)           — Add type hints, fix mypy/pyright issues
  ✓ test_flake (85)           — Retry test, investigate timing issues
  ✓ missing_dependency (80)   — Add to requirements.txt, poetry.lock, Pipfile
  ✓ import_error (85)         — Fix broken imports, circular deps
  ✓ version_mismatch (75)     — Update version constraints in lock files
  ✓ env_variable (70)         — Update CI workflow env or .env.example
  ✓ config_missing (65)       — Create missing config file with defaults
  ⚠ docker_build_fail (60)    — Rebuild Dockerfile, update base image
  ⚠ deployment_fail (40)      — Manual inspection often needed
  ✗ permission_error (20)     — Usually auth issue, owner may need to rotate keys
  ✗ external_api_error (10)   — External service down, needs owner investigation

Repair Strategy by Error Type:

1. LINT_ERROR (autonomy 95)
   Detection: grep -E "error: |ERROR|fail|FAILED" | grep -i "lint|format|style"
   Repair: Run auto-formatter (black, ruff --fix, prettier, etc.)
   Success: Re-run linting, check no errors
   Retry: Up to 3 times (formatter idempotency)

2. TYPE_ERROR (autonomy 90)
   Detection: "error: Argument of type X cannot be assigned to parameter of type Y"
   Repair: Analyze stack trace → generate type hint fix
   Success: mypy/pyright passes with no errors
   Retry: Up to 2 times (complex type inference)

3. TEST_FLAKE (autonomy 85)
   Detection: "FAILED test_X" + "flaky" | "timeout" | "connection refused"
   Repair: Re-run test suite (mark test as retry-able, add timeout)
   Success: All tests pass
   Retry: Up to 5 times (for timing-dependent tests)

4. MISSING_DEPENDENCY (autonomy 80)
   Detection: "ModuleNotFoundError: No module named X" | "ERROR: Could not find"
   Repair: Add X to requirements.txt / poetry / pipenv, re-lock
   Success: pip install / poetry lock passes
   Retry: Up to 2 times (resolver may need multiple passes)

5. IMPORT_ERROR (autonomy 85)
   Detection: "ImportError: cannot import name X" | "circular import"
   Repair: Trace import graph → reorganize imports or add __all__
   Success: No import errors, all modules load
   Retry: Up to 3 times (may require structure changes)

6. CONFIG_MISSING (autonomy 65)
   Detection: "FileNotFoundError: .env" | "Config file not found"
   Repair: Create template config with defaults, commit to repo
   Success: App starts without config errors
   Retry: Up to 2 times

Repair Execution Flow:

1. GitHub Actions workflow fails
2. Webhook posts to /api/v2/github/error-webhook
3. Scan logs, classify error (archetype + confidence)
4. Emit repair job to workboard (engineering lane, high priority)
5. king-bridge polls, classifies as repair task
6. Model rates autonomy: if >= 75%, execute repair autonomously
7. Model generates fix:
   - For linting: run formatter, commit changes
   - For type errors: generate type hints, commit changes
   - For missing deps: update lock files, commit changes
8. Auto-commit fix to feature branch or main
9. Trigger GitHub Actions re-run
10. Monitor re-run for success/failure
11. Record outcome in workboard (autonomous-repair: success/partial/failed)

Implementation:

- services/github_error_scanner.py:
  - GHClient: Wrap GitHub API (PyGithub or http)
  - scan_workflow_logs(): Poll recent workflows, capture failure logs
  - classify_error(): Pattern-match error → archetype + confidence
  - error_context(): Extract stack trace, file:line, error message

- services/github_auto_repair.py:
  - Repair task models (for each archetype)
  - repair_lint_error(), repair_import_error(), etc.
  - generate_fix_patch(): Return git diff + commit message
  - push_repair_commit(): Create branch, commit, push, open PR
  - trigger_workflow_rerun(): Call GitHub API to re-run failed job

- Integrate into ai_autonomy.py:
  - New archetype: "github_repair" (autonomy score by error type)
  - Safety gates: "Stop if error affects deployment", "Stop if affects >10 files"

- Integrate into king-bridge polling:
  - Monitor GitHub Actions every 5 minutes
  - Emit repair jobs for failures
  - Execute with autonomy constraints

Environment Variables:

  GITHUB_TOKEN              — Personal access token (read:workflow, write:repo)
  GITHUB_OWNER              — Repository owner (your GitHub username)
  GITHUB_REPO               — Repository name (12sgi-king)
  GITHUB_ERROR_SCAN_INTERVAL_SECONDS  — Poll interval (default 300)
  GITHUB_AUTO_REPAIR_ENABLED          — Global on/off (default true)
  GITHUB_AUTO_REPAIR_DRY_RUN          — Test mode (no commits) (default false)

CLI Testing:

  # Scan recent workflow runs
  python -m services.github_error_scanner --scan-recent

  # Classify an error from log file
  python -m services.github_error_scanner --classify-error /path/to/log.txt

  # Simulate autonomous repair (dry-run)
  python -m services.github_auto_repair --error-type lint_error --dry-run
"""

import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple, List
from enum import Enum

# ── Error Archetype Definitions ───────────────────────────────────────────────

class ErrorSeverity(Enum):
    CRITICAL = "critical"      # Blocks deployment
    HIGH = "high"              # Major functionality broken
    MEDIUM = "medium"          # Feature broken but workaround exists
    LOW = "low"                # Minor issue, doesn't block
    INFO = "info"              # Non-error (warning, deprecation)


@dataclass
class ErrorArchetype:
    """CI/CD error archetype with repair autonomy."""
    name: str
    pattern: str                       # Regex to detect in logs
    severity: ErrorSeverity
    autonomy_score: int                # 0-100: safe to repair autonomously
    repair_timeout_seconds: int
    max_retries: int
    repair_strategy: str               # Brief description of fix approach
    safety_gates: List[str]           # Conditions that prevent autonomous repair
    
    def matches(self, log_text: str) -> Tuple[bool, Optional[re.Match]]:
        """Check if error pattern is present in log."""
        try:
            match = re.search(self.pattern, log_text, re.IGNORECASE | re.MULTILINE)
            return bool(match), match
        except re.error:
            return False, None


# Registry of common CI/CD errors and autonomous repair strategies
ERROR_ARCHETYPES = {
    "lint_error": ErrorArchetype(
        name="lint_error",
        pattern=r"(error: |ERROR).*?(lint|format|style|flake8|pylint|ruff|black|prettier)",
        severity=ErrorSeverity.LOW,
        autonomy_score=95,
        repair_timeout_seconds=60,
        max_retries=3,
        repair_strategy="Run auto-formatter (black, ruff --fix), commit changes, re-run linting",
        safety_gates=[
            "Stop if > 100 files changed",
            "Stop if formatter modifies non-code files (docs, data)",
        ]
    ),
    
    "type_error": ErrorArchetype(
        name="type_error",
        pattern=r"(error|ERROR).*?(type mismatch|Argument of type|cannot be assigned|expected|got|mypy|pyright|type check)",
        severity=ErrorSeverity.MEDIUM,
        autonomy_score=90,
        repair_timeout_seconds=120,
        max_retries=2,
        repair_strategy="Analyze type error, generate type hint fix, validate with type checker",
        safety_gates=[
            "Stop if error is in third-party code",
            "Stop if affects > 5 functions",
        ]
    ),
    
    "test_flake": ErrorArchetype(
        name="test_flake",
        pattern=r"(FAILED|ERROR).*?(test|spec).*?(flaky|timeout|connection|PASSED on retry|intermittent)",
        severity=ErrorSeverity.MEDIUM,
        autonomy_score=85,
        repair_timeout_seconds=300,
        max_retries=5,
        repair_strategy="Re-run test suite (mark flaky, add retry logic, increase timeout)",
        safety_gates=[
            "Stop if test consistently fails (not flaky)",
            "Stop if > 3 retries still fail",
        ]
    ),
    
    "missing_dependency": ErrorArchetype(
        name="missing_dependency",
        pattern=r"(ModuleNotFoundError|ImportError|ERROR: Could not find|package .* not found|No module named|dependencies|UNMET DEPENDENCY)",
        severity=ErrorSeverity.HIGH,
        autonomy_score=80,
        repair_timeout_seconds=180,
        max_retries=2,
        repair_strategy="Add missing package to requirements.txt/poetry.lock, re-lock, re-run",
        safety_gates=[
            "Stop if package name is ambiguous (multiple options)",
            "Stop if requires version negotiation with other deps",
        ]
    ),
    
    "import_error": ErrorArchetype(
        name="import_error",
        pattern=r"(ImportError|cannot import name|circular import|ModuleNotFoundError).*?(from|import)",
        severity=ErrorSeverity.HIGH,
        autonomy_score=85,
        repair_timeout_seconds=120,
        max_retries=3,
        repair_strategy="Trace import graph, fix circular refs, reorganize imports",
        safety_gates=[
            "Stop if circular import spans > 3 modules",
            "Stop if affects > 10 files",
        ]
    ),
    
    "version_mismatch": ErrorArchetype(
        name="version_mismatch",
        pattern=r"(version conflict|requirement .* not satisfied|incompatible|version mismatch|requires .* but .* is installed)",
        severity=ErrorSeverity.MEDIUM,
        autonomy_score=75,
        repair_timeout_seconds=180,
        max_retries=2,
        repair_strategy="Update version constraints in lock files, re-resolve dependencies",
        safety_gates=[
            "Stop if multiple incompatible versions required",
            "Stop if requires downgrading critical packages",
        ]
    ),
    
    "env_variable": ErrorArchetype(
        name="env_variable",
        pattern=r"(missing environment variable|env variable not set|undefined|ENV|MISSING.*VAR|KeyError:.*ENV)",
        severity=ErrorSeverity.MEDIUM,
        autonomy_score=70,
        repair_timeout_seconds=90,
        max_retries=1,
        repair_strategy="Update CI workflow env or .env.example with sensible defaults",
        safety_gates=[
            "Stop if env var is a secret (API key, token, password)",
            "Stop if default value could be wrong",
        ]
    ),
    
    "config_missing": ErrorArchetype(
        name="config_missing",
        pattern=r"(FileNotFoundError|config.*not found|cannot open|No such file|\.env|\.config)",
        severity=ErrorSeverity.MEDIUM,
        autonomy_score=65,
        repair_timeout_seconds=90,
        max_retries=2,
        repair_strategy="Create config template with sensible defaults, commit to repo",
        safety_gates=[
            "Stop if config structure is unclear",
            "Stop if requires secrets in defaults",
        ]
    ),
    
    "docker_build_fail": ErrorArchetype(
        name="docker_build_fail",
        pattern=r"(docker|container).*?(failed|error|build failed|no such file|denied|permission)",
        severity=ErrorSeverity.HIGH,
        autonomy_score=60,
        repair_timeout_seconds=300,
        max_retries=2,
        repair_strategy="Rebuild Dockerfile, update base image, fix layer caching",
        safety_gates=[
            "Stop if base image is malicious/unknown",
            "Stop if Dockerfile has security issues",
        ]
    ),
    
    "permission_error": ErrorArchetype(
        name="permission_error",
        pattern=r"(permission denied|access denied|unauthorized|PERMISSION|401|403|forbidden)",
        severity=ErrorSeverity.HIGH,
        autonomy_score=20,
        repair_timeout_seconds=60,
        max_retries=0,
        repair_strategy="Auth issue — owner may need to rotate tokens or grant permissions",
        safety_gates=[
            "ALWAYS STOP — permission errors require owner investigation",
        ]
    ),
    
    "external_api_error": ErrorArchetype(
        name="external_api_error",
        pattern=r"(connection refused|timeout|503|502|external service|api.*error|network|dns)",
        severity=ErrorSeverity.LOW,
        autonomy_score=10,
        repair_timeout_seconds=120,
        max_retries=3,
        repair_strategy="Retry with exponential backoff, check service status",
        safety_gates=[
            "Stop if service is persistently down (> 5 min)",
            "Stop if error persists after 3 retries",
        ]
    ),
}


@dataclass
class DetectedError:
    """Result of error detection and classification."""
    archetype_name: str
    severity: ErrorSeverity
    autonomy_score: int
    confidence: float                  # 0.0-1.0: how confident in classification
    log_snippet: str                   # Relevant error line from log
    file_path: Optional[str]           # File that errored (if available)
    line_number: Optional[int]         # Line number (if available)
    full_log: str                      # Complete log for context
    timestamp: str
    github_run_id: Optional[str]       # GitHub Actions run ID
    can_repair_autonomously: bool      # autonomy_score >= 75
    
    def to_repair_job(self) -> dict:
        """Convert to workboard repair job payload."""
        return {
            "error_type": self.archetype_name,
            "severity": self.severity.value,
            "autonomy_score": self.autonomy_score,
            "confidence": self.confidence,
            "log_snippet": self.log_snippet,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "github_run_id": self.github_run_id,
            "timestamp": self.timestamp,
        }


def detect_errors_in_log(log_text: str, github_run_id: Optional[str] = None) -> List[DetectedError]:
    """
    Scan GitHub Actions log for errors and classify by archetype.
    Returns list of detected errors, sorted by severity + autonomy.
    """
    errors = []
    
    for archetype_name, archetype in ERROR_ARCHETYPES.items():
        matches, match = archetype.matches(log_text)
        if matches:
            # Extract context around match
            lines = log_text.split('\n')
            match_line_idx = None
            for i, line in enumerate(lines):
                if match.group() in line:
                    match_line_idx = i
                    break
            
            context_start = max(0, (match_line_idx or 0) - 2)
            context_end = min(len(lines), (match_line_idx or 0) + 3)
            log_snippet = '\n'.join(lines[context_start:context_end])
            
            # Try to extract file:line from common error patterns
            file_path = None
            line_number = None
            file_pattern = re.search(r'([\w/._-]+\.py):(\d+)', log_text)
            if file_pattern:
                file_path = file_pattern.group(1)
                line_number = int(file_pattern.group(2))
            
            # Confidence: higher if pattern matches multiple times
            match_count = len(re.findall(archetype.pattern, log_text, re.IGNORECASE))
            confidence = min(1.0, 0.7 + (match_count * 0.1))  # Start at 0.7, up to 1.0
            
            errors.append(DetectedError(
                archetype_name=archetype_name,
                severity=archetype.severity,
                autonomy_score=archetype.autonomy_score,
                confidence=confidence,
                log_snippet=log_snippet,
                file_path=file_path,
                line_number=line_number,
                full_log=log_text,
                timestamp=datetime.now(timezone.utc).isoformat(),
                github_run_id=github_run_id,
                can_repair_autonomously=archetype.autonomy_score >= 75,
            ))
    
    # Sort by severity (critical first) + autonomy (higher first)
    errors.sort(
        key=lambda e: (
            -["critical", "high", "medium", "low", "info"].index(e.severity.value),
            -e.autonomy_score
        )
    )
    return errors


def build_repair_prompt(error: DetectedError, archetype: ErrorArchetype) -> str:
    """Build specialized prompt to teach model how to repair this error."""
    lines = [
        f"You are king-repair, trained to autonomously fix GitHub CI/CD errors.",
        f"",
        f"ERROR CLASSIFICATION:",
        f"  Type: {error.archetype_name}",
        f"  Severity: {error.severity.value}",
        f"  Autonomy: {error.autonomy_score}/100",
        f"  Confidence: {error.confidence*100:.0f}%",
        f"",
        f"ERROR CONTEXT:",
        f"  {error.log_snippet}",
        f"",
        f"FILE: {error.file_path or '(unknown)'}",
        f"LINE: {error.line_number or '(unknown)'}",
        f"",
        f"REPAIR STRATEGY: {archetype.repair_strategy}",
        f"",
        f"SAFETY GATES (stop immediately if ANY trigger):",
        *[f"  • {gate}" for gate in archetype.safety_gates],
        f"",
        f"EXECUTION LIMITS:",
        f"  Timeout: {archetype.repair_timeout_seconds}s",
        f"  Max retries: {archetype.max_retries}",
        f"",
        f"YOUR TASK:",
        f"1. Confirm you understand the error and repair strategy",
        f"2. Check all safety gates — STOP if any trigger",
        f"3. Generate a fix (code change, config update, file creation, etc.)",
        f"4. Show the exact git diff or file content for the fix",
        f"5. Provide a concise commit message",
        f"6. Report: FIX_READY | STOPPED | ERROR",
        f"",
        f"Remember: You're autonomously modifying the codebase. Be confident but cautious.",
    ]
    return "\n".join(lines)


def record_error_detection(
    error: DetectedError,
    db_path: Optional[Path] = None,
) -> bool:
    """Log detected error to SQLite audit."""
    if db_path is None:
        db_path = Path(os.environ.get("GITHUB_ERROR_DB", "/data/db/github_errors.db"))
    
    try:
        import sqlite3
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS detected_errors (
                id TEXT PRIMARY KEY,
                github_run_id TEXT,
                archetype TEXT NOT NULL,
                severity TEXT NOT NULL,
                autonomy_score INTEGER NOT NULL,
                confidence REAL NOT NULL,
                file_path TEXT,
                line_number INTEGER,
                log_snippet TEXT,
                can_repair_autonomously INTEGER,
                detected_at TEXT NOT NULL
            )
        """)
        exec_id = f"{error.github_run_id or 'manual'}:{datetime.now(timezone.utc).isoformat()}"
        conn.execute("""
            INSERT INTO detected_errors
              (id, github_run_id, archetype, severity, autonomy_score, confidence,
               file_path, line_number, log_snippet, can_repair_autonomously, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            exec_id,
            error.github_run_id,
            error.archetype_name,
            error.severity.value,
            error.autonomy_score,
            error.confidence,
            error.file_path,
            error.line_number,
            error.log_snippet[:500],
            int(error.can_repair_autonomously),
            error.timestamp,
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Failed to record error detection: {e}")
        return False


if __name__ == "__main__":
    # Quick test
    test_log = """
    ERROR: Linting failed
    error: Line too long (line 1 of main.py)
    FAILED: lint check
    """
    
    errors = detect_errors_in_log(test_log, github_run_id="run-12345")
    print(f"\nDetected {len(errors)} error(s):")
    for err in errors:
        print(f"  - {err.archetype_name} (autonomy {err.autonomy_score}, confidence {err.confidence*100:.0f}%)")
        if err.can_repair_autonomously:
            print(f"    → Can repair autonomously")
