"""
Owner Job Tracking — audit trail for autonomous AI work.

Purpose:
  Track all autonomous jobs (repairs, updates, creations) with live status,
  results, and audit logs. Owner can see what the AI did, approve/reject,
  and investigate failures.

Schema:
  owner_jobs (append-only audit log)
    id, job_id, archetype, action, status, autonomy_score, started_at,
    completed_at, duration_ms, result_summary, error_message, approved_by,
    rejected_by, rejection_reason

  owner_job_steps (task breakdown)
    job_id, step_num, step_name, status, output, error_message

  owner_job_approvals (approval audit trail)
    job_id, approved_by, approval_timestamp, approval_type, note

Data flow:
  AI executes job autonomously
        ↓ record_owner_job()
  owner_jobs + owner_job_steps written
        ↓ /api/v2/owner/jobs (fetch live status)
  Dashboard polls every 5s
        ↓ real-time updates
  Owner sees: "Linting repair completed (lint_error) — 23 files, 4s"
        ↓ approve/reject buttons
  Owner clicks Approve
        ↓ record_job_approval()
  Tombstone written, job moved to "approved" lane
        ↓ workflow can proceed (e.g., merge PR)
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List

from contextlib import contextmanager


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ApprovalType(Enum):
    AUTO_APPROVED = "auto-approved"
    OWNER_APPROVED = "owner-approved"
    OWNER_REJECTED = "owner-rejected"


@dataclass
class OwnerJob:
    """Autonomous job record."""
    job_id: str
    archetype: str              # e.g., "github_lint_repair"
    action: str                 # e.g., "auto-format linting"
    autonomy_score: int         # 0-100
    status: JobStatus
    started_at: str             # ISO datetime
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    result_summary: str = ""
    error_message: Optional[str] = None
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class JobStep:
    """Individual step within a job."""
    job_id: str
    step_num: int
    step_name: str
    status: JobStatus
    output: str = ""
    error_message: Optional[str] = None


class OwnerJobTracker:
    """Track autonomous jobs for owner visibility + approval."""
    
    def __init__(self, db_path: Path = Path("/data/db/owner_jobs.db")):
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def _db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_db(self):
        """Create schema if not exists."""
        with self._db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS owner_jobs (
                    job_id TEXT PRIMARY KEY,
                    archetype TEXT NOT NULL,
                    action TEXT NOT NULL,
                    autonomy_score INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_ms INTEGER,
                    result_summary TEXT,
                    error_message TEXT,
                    approved_by TEXT,
                    rejected_by TEXT,
                    rejection_reason TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS owner_job_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    step_num INTEGER NOT NULL,
                    step_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES owner_jobs(job_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS owner_job_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    approval_type TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    approval_timestamp TEXT NOT NULL,
                    note TEXT,
                    FOREIGN KEY (job_id) REFERENCES owner_jobs(job_id)
                )
            """)
            conn.commit()
    
    def start_job(self, job_id: str, archetype: str, action: str, autonomy_score: int) -> OwnerJob:
        """Record that an autonomous job is starting."""
        now = datetime.now(timezone.utc).isoformat()
        job = OwnerJob(
            job_id=job_id,
            archetype=archetype,
            action=action,
            autonomy_score=autonomy_score,
            status=JobStatus.RUNNING,
            started_at=now,
            created_at=now,
        )
        
        with self._db() as conn:
            conn.execute("""
                INSERT INTO owner_jobs
                  (job_id, archetype, action, autonomy_score, status, started_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id, job.archetype, job.action, job.autonomy_score,
                job.status.value, job.started_at, job.created_at
            ))
            conn.commit()
        
        return job
    
    def complete_job(
        self,
        job_id: str,
        status: JobStatus,
        result_summary: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Mark job as complete."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self._db() as conn:
            row = conn.execute("SELECT started_at FROM owner_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                return False
            
            started = datetime.fromisoformat(row["started_at"])
            completed = datetime.fromisoformat(now)
            duration_ms = int((completed - started).total_seconds() * 1000)
            
            conn.execute("""
                UPDATE owner_jobs
                SET status = ?, completed_at = ?, duration_ms = ?, result_summary = ?, error_message = ?
                WHERE job_id = ?
            """, (status.value, now, duration_ms, result_summary, error_message, job_id))
            conn.commit()
        
        return True
    
    def add_step(
        self,
        job_id: str,
        step_num: int,
        step_name: str,
        output: str = "",
        error_message: Optional[str] = None,
    ) -> bool:
        """Log a step within the job."""
        now = datetime.now(timezone.utc).isoformat()
        status = JobStatus.FAILED if error_message else JobStatus.COMPLETED
        
        with self._db() as conn:
            conn.execute("""
                INSERT INTO owner_job_steps
                  (job_id, step_num, step_name, status, output, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (job_id, step_num, step_name, status.value, output, error_message, now))
            conn.commit()
        
        return True
    
    def approve_job(self, job_id: str, approver: str, note: str = "") -> bool:
        """Owner approves a completed autonomous job."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self._db() as conn:
            # Update job status
            conn.execute("""
                UPDATE owner_jobs SET status = ?, approved_by = ? WHERE job_id = ?
            """, (JobStatus.APPROVED.value, approver, job_id))
            
            # Record approval
            conn.execute("""
                INSERT INTO owner_job_approvals
                  (job_id, approval_type, approved_by, approval_timestamp, note)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, ApprovalType.OWNER_APPROVED.value, approver, now, note))
            
            conn.commit()
        
        return True
    
    def reject_job(self, job_id: str, rejector: str, reason: str) -> bool:
        """Owner rejects a completed autonomous job."""
        with self._db() as conn:
            conn.execute("""
                UPDATE owner_jobs SET status = ?, rejected_by = ?, rejection_reason = ?
                WHERE job_id = ?
            """, (JobStatus.REJECTED.value, rejector, reason, job_id))
            
            conn.execute("""
                INSERT INTO owner_job_approvals
                  (job_id, approval_type, approved_by, approval_timestamp, note)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, ApprovalType.OWNER_REJECTED.value, rejector,
                  datetime.now(timezone.utc).isoformat(), reason))
            
            conn.commit()
        
        return True
    
    def get_job(self, job_id: str) -> Optional[dict]:
        """Fetch a single job."""
        with self._db() as conn:
            row = conn.execute("""
                SELECT * FROM owner_jobs WHERE job_id = ?
            """, (job_id,)).fetchone()
            if row:
                return dict(row)
        return None
    
    def list_jobs(self, limit: int = 50, status: Optional[str] = None) -> List[dict]:
        """Fetch recent jobs, optionally filtered by status."""
        with self._db() as conn:
            if status:
                rows = conn.execute("""
                    SELECT * FROM owner_jobs WHERE status = ? ORDER BY started_at DESC LIMIT ?
                """, (status, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM owner_jobs ORDER BY started_at DESC LIMIT ?
                """, (limit,)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_job_steps(self, job_id: str) -> List[dict]:
        """Fetch all steps for a job."""
        with self._db() as conn:
            rows = conn.execute("""
                SELECT * FROM owner_job_steps WHERE job_id = ? ORDER BY step_num ASC
            """, (job_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_stats(self) -> dict:
        """Get aggregate statistics."""
        with self._db() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM owner_jobs").fetchone()["cnt"]
            by_status = conn.execute("""
                SELECT status, COUNT(*) as cnt FROM owner_jobs GROUP BY status
            """).fetchall()
            by_archetype = conn.execute("""
                SELECT archetype, COUNT(*) as cnt, AVG(duration_ms) as avg_duration_ms
                FROM owner_jobs WHERE completed_at IS NOT NULL GROUP BY archetype
            """).fetchall()
            
            avg_autonomy = conn.execute("""
                SELECT AVG(autonomy_score) as avg FROM owner_jobs
            """).fetchone()["avg"]
            
            return {
                "total_jobs": total,
                "by_status": {row["status"]: row["cnt"] for row in by_status},
                "by_archetype": [
                    {"archetype": row["archetype"], "count": row["cnt"], "avg_duration_ms": row["avg_duration_ms"]}
                    for row in by_archetype
                ],
                "avg_autonomy_score": round(avg_autonomy or 0, 1),
            }


# Singleton instance
_tracker = None

def get_tracker() -> OwnerJobTracker:
    global _tracker
    if _tracker is None:
        _tracker = OwnerJobTracker()
    return _tracker
