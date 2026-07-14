"""Task orchestration layer for tenant work coordination.

Handles task queuing, dispatch, tracking, and completion across all tenants.
Integrates with error correction to retry failed tasks automatically.

Usage:
  from services.task_orchestrator import TaskOrchestrator
  orch = TaskOrchestrator()
  orch.queue_tenant_task("tenant-123", "render video", priority="high")
  orch.process_all_tasks()
"""

import json
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import dict, list


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class Task:
    """Represents a single tenant task."""
    
    def __init__(self, tenant_id: str, work_type: str, params: dict = None, priority: str = "normal"):
        self.id = str(uuid.uuid4())[:8]
        self.tenant_id = tenant_id
        self.work_type = work_type  # "render", "transcode", "upload", "sync", etc.
        self.params = params or {}
        self.priority = priority  # "low", "normal", "high", "critical"
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None
        self.retry_count = 0
        self.max_retries = 3
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "work_type": self.work_type,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "error": self.error,
            "params": self.params
        }


class TaskOrchestrator:
    """Orchestrates task execution across tenants."""
    
    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path("logs/tasks")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.task_queue = []
        self.completed_tasks = []
        self.failed_tasks = []
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def _priority_score(self, task: Task) -> int:
        """Higher score = higher priority."""
        scores = {"critical": 4, "high": 3, "normal": 2, "low": 1}
        return scores.get(task.priority, 2)
    
    def _log_task(self, task: Task):
        """Log task event."""
        try:
            log_file = self.log_dir / f"tasks-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(task.to_dict()) + "\n")
        except Exception as e:
            print(f"Error logging task: {e}")
    
    def queue_tenant_task(self, tenant_id: str, work_type: str, params: dict = None, priority: str = "normal") -> str:
        """Queue a task for a tenant.
        
        Args:
            tenant_id: tenant identifier
            work_type: "render", "transcode", "upload", "sync", "backup", etc.
            params: task-specific parameters
            priority: "low", "normal", "high", "critical"
        
        Returns:
            task ID
        """
        task = Task(tenant_id, work_type, params, priority)
        self.task_queue.append(task)
        self._log_task(task)
        print(f"[QUEUE] {tenant_id} — {work_type} (id: {task.id}, priority: {priority})")
        return task.id
    
    def sort_queue_by_priority(self):
        """Sort task queue by priority (critical → low)."""
        self.task_queue.sort(key=lambda t: self._priority_score(t), reverse=True)
    
    def get_next_task(self) -> Task:
        """Pop the highest-priority pending task."""
        self.sort_queue_by_priority()
        
        for i, task in enumerate(self.task_queue):
            if task.status == TaskStatus.PENDING:
                return self.task_queue.pop(i)
        
        return None
    
    def start_task(self, task: Task) -> bool:
        """Mark task as running."""
        task.status = TaskStatus.RUNNING
        task.started_at = self._now()
        self._log_task(task)
        print(f"[START] {task.tenant_id} — {task.work_type} (id: {task.id})")
        return True
    
    def complete_task(self, task: Task, result: dict = None) -> bool:
        """Mark task as completed."""
        task.status = TaskStatus.COMPLETED
        task.completed_at = self._now()
        task.result = result or {}
        self.completed_tasks.append(task)
        self._log_task(task)
        print(f"[COMPLETE] {task.tenant_id} — {task.work_type} (id: {task.id})")
        return True
    
    def fail_task(self, task: Task, error: str = "unknown error", auto_retry: bool = True) -> bool:
        """Mark task as failed and optionally retry."""
        task.error = error
        task.retry_count += 1
        
        if auto_retry and task.retry_count < task.max_retries:
            # Retry: reset to pending
            task.status = TaskStatus.RETRYING
            self.task_queue.append(task)  # Re-queue
            self._log_task(task)
            print(f"[RETRY {task.retry_count}/{task.max_retries}] {task.tenant_id} — {task.work_type} (id: {task.id})")
            print(f"       Error: {error}")
            return True
        else:
            # Final failure
            task.status = TaskStatus.FAILED
            task.completed_at = self._now()
            self.failed_tasks.append(task)
            self._log_task(task)
            print(f"[FAILED] {task.tenant_id} — {task.work_type} (id: {task.id}) after {task.retry_count} retries")
            print(f"       Error: {error}")
            return False
    
    def execute_task(self, task: Task) -> bool:
        """Execute a task (dispatch to appropriate handler).
        
        Returns True if successful, False if failed.
        """
        self.start_task(task)
        
        try:
            # Route to appropriate handler based on work_type
            if task.work_type == "render":
                return self._handle_render_task(task)
            elif task.work_type == "transcode":
                return self._handle_transcode_task(task)
            elif task.work_type == "upload":
                return self._handle_upload_task(task)
            elif task.work_type == "sync":
                return self._handle_sync_task(task)
            elif task.work_type == "backup":
                return self._handle_backup_task(task)
            else:
                raise ValueError(f"Unknown work_type: {task.work_type}")
        
        except Exception as e:
            self.fail_task(task, str(e), auto_retry=True)
            return False
    
    def _handle_render_task(self, task: Task) -> bool:
        """Handle ComfyUI/diffusion render tasks."""
        # TODO: Queue to ComfyUI API
        workflow_id = task.params.get("workflow_id", "default")
        print(f"  → Queueing render workflow: {workflow_id}")
        self.complete_task(task, {"workflow_id": workflow_id, "status": "queued"})
        return True
    
    def _handle_transcode_task(self, task: Task) -> bool:
        """Handle video/audio transcoding tasks."""
        # TODO: Queue to ffmpeg or transcoding service
        input_file = task.params.get("input", "")
        output_format = task.params.get("format", "mp4")
        print(f"  → Transcoding {input_file} to {output_format}")
        self.complete_task(task, {"input": input_file, "format": output_format})
        return True
    
    def _handle_upload_task(self, task: Task) -> bool:
        """Handle file upload tasks."""
        # TODO: Queue to S3/storage service
        file_path = task.params.get("file", "")
        destination = task.params.get("destination", "storage")
        print(f"  → Uploading {file_path} to {destination}")
        self.complete_task(task, {"file": file_path, "destination": destination})
        return True
    
    def _handle_sync_task(self, task: Task) -> bool:
        """Handle data sync/backup tasks."""
        # TODO: Queue to sync service
        source = task.params.get("source", "")
        target = task.params.get("target", "")
        print(f"  → Syncing {source} to {target}")
        self.complete_task(task, {"source": source, "target": target})
        return True
    
    def _handle_backup_task(self, task: Task) -> bool:
        """Handle backup tasks."""
        # TODO: Queue to backup service
        backup_type = task.params.get("type", "full")
        print(f"  → Creating {backup_type} backup")
        self.complete_task(task, {"type": backup_type})
        return True
    
    def process_all_tasks(self, max_iterations: int = 100) -> dict:
        """Process all queued tasks until queue is empty or max iterations reached.
        
        Returns:
            dict with execution summary
        """
        summary = {
            "timestamp": self._now(),
            "total_processed": 0,
            "completed": 0,
            "failed": 0,
            "iterations": 0
        }
        
        for iteration in range(max_iterations):
            task = self.get_next_task()
            if not task:
                break  # Queue empty
            
            summary["iterations"] += 1
            success = self.execute_task(task)
            
            if success:
                summary["completed"] += 1
            else:
                if task.status == TaskStatus.FAILED:
                    summary["failed"] += 1
            
            summary["total_processed"] += 1
            time.sleep(0.1)  # Small delay between tasks
        
        return summary
    
    def get_tenant_tasks(self, tenant_id: str) -> dict:
        """Get task summary for a specific tenant."""
        pending = [t for t in self.task_queue if t.tenant_id == tenant_id and t.status == TaskStatus.PENDING]
        completed = [t for t in self.completed_tasks if t.tenant_id == tenant_id]
        failed = [t for t in self.failed_tasks if t.tenant_id == tenant_id]
        
        return {
            "tenant_id": tenant_id,
            "pending": len(pending),
            "completed": len(completed),
            "failed": len(failed),
            "total": len(pending) + len(completed) + len(failed)
        }
    
    def get_queue_status(self) -> dict:
        """Get status of entire task queue."""
        pending = [t for t in self.task_queue if t.status == TaskStatus.PENDING]
        running = [t for t in self.task_queue if t.status == TaskStatus.RUNNING]
        retrying = [t for t in self.task_queue if t.status == TaskStatus.RETRYING]
        
        # Count by priority
        by_priority = {}
        for task in pending:
            priority = task.priority
            by_priority[priority] = by_priority.get(priority, 0) + 1
        
        return {
            "timestamp": self._now(),
            "total_queued": len(self.task_queue),
            "pending": len(pending),
            "running": len(running),
            "retrying": len(retrying),
            "by_priority": by_priority,
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks)
        }
    
    def generate_report(self) -> str:
        """Generate a task execution report."""
        total_tasks = len(self.completed_tasks) + len(self.failed_tasks) + len(self.task_queue)
        completed = len(self.completed_tasks)
        failed = len(self.failed_tasks)
        pending = len([t for t in self.task_queue if t.status == TaskStatus.PENDING])
        
        report = f"""
═══════════════════════════════════════════════════════════════
  TASK ORCHESTRATION REPORT — {self._now()}
═══════════════════════════════════════════════════════════════

TOTAL TASKS: {total_tasks}
  ✓ Completed: {completed}
  ✗ Failed: {failed}
  ⏳ Pending: {pending}
  Success Rate: {int(completed / (completed + failed) * 100) if (completed + failed) else 0}%

QUEUE STATUS:
"""
        for tenant_id, count_dict in self._group_by_tenant().items():
            report += f"\n  {tenant_id}:\n"
            for work_type, count in count_dict.items():
                report += f"    - {work_type}: {count}\n"
        
        report += f"\n═══════════════════════════════════════════════════════════════\n"
        return report
    
    def _group_by_tenant(self) -> dict:
        """Group tasks by tenant."""
        grouped = {}
        for task in self.completed_tasks + self.failed_tasks:
            tenant = task.tenant_id
            if tenant not in grouped:
                grouped[tenant] = {}
            work_type = task.work_type
            grouped[tenant][work_type] = grouped[tenant].get(work_type, 0) + 1
        return grouped
