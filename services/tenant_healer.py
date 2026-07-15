"""Tenant-based healing dashboard and status tracking.

Tracks healing progress for each tenant:
- Code diagnostics
- Auto-repairs
- Task execution
- Health metrics
- Guidance suggestions

Usage:
  from services.tenant_healer import TenantHealer
  healer = TenantHealer()
  healer.diagnose_tenant("tenant-123")
  status = healer.get_tenant_status("tenant-123")
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from services.self_healer import SelfHealer, DiagnosticIssue
from services.error_corrector import ErrorMonitor
from services.task_orchestrator import TaskOrchestrator


class TenantHealingStatus:
    """Tracks healing status for a single tenant."""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_check = None
        self.diagnostics = []
        self.repairs_applied = []
        self.guidance_given = []
        self.tasks_processed = 0
        self.health_score = 100  # 0-100
        self.status = "healthy"  # healthy, degraded, critical
    
    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "created_at": self.created_at,
            "last_check": self.last_check,
            "diagnostic_count": len(self.diagnostics),
            "repairs_count": len(self.repairs_applied),
            "guidance_count": len(self.guidance_given),
            "tasks_processed": self.tasks_processed,
            "health_score": self.health_score,
            "status": self.status
        }


class TenantHealer:
    """Manages healing for all tenants."""
    
    def __init__(self):
        self.tenants = {}  # tenant_id -> TenantHealingStatus
        self.self_healer = SelfHealer()
        self.error_monitor = ErrorMonitor()
        self.task_orchestrator = TaskOrchestrator()
        self.log_dir = Path("logs/tenant-healing")
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def _log_tenant_event(self, tenant_id: str, event: dict):
        """Log tenant-specific event."""
        event["tenant_id"] = tenant_id
        event["ts"] = self._now()
        try:
            log_file = self.log_dir / f"tenant-{tenant_id}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"Error logging tenant event: {e}")
    
    def get_or_create_tenant(self, tenant_id: str) -> TenantHealingStatus:
        """Get existing tenant status or create new."""
        if tenant_id not in self.tenants:
            self.tenants[tenant_id] = TenantHealingStatus(tenant_id)
        return self.tenants[tenant_id]
    
    def diagnose_tenant(self, tenant_id: str) -> dict:
        """Run full diagnostics for a tenant."""
        tenant = self.get_or_create_tenant(tenant_id)
        print(f"[TENANT {tenant_id}] Running diagnostics...")
        
        result = {
            "tenant_id": tenant_id,
            "timestamp": self._now(),
            "diagnostics": {}
        }
        
        # 1. Code diagnostics
        code_diag = self.self_healer.diagnose_project()
        result["diagnostics"]["code"] = {
            "total_issues": code_diag["total_issues"],
            "by_severity": code_diag["by_severity"],
            "by_type": code_diag["by_type"]
        }
        
        # 2. System health
        system_health = self.error_monitor.check_all_services()
        result["diagnostics"]["system"] = {
            "total_issues": system_health["total_issues"],
            "critical": system_health["critical"],
            "high": system_health["high"]
        }
        
        # 3. Task queue
        queue_status = self.task_orchestrator.get_queue_status()
        result["diagnostics"]["tasks"] = {
            "queued": queue_status["total_queued"],
            "completed": queue_status["completed"],
            "failed": queue_status["failed"]
        }
        
        # Update tenant status
        tenant.last_check = self._now()
        tenant.diagnostics.append(result)
        
        # Calculate health score
        code_issues = code_diag["total_issues"]
        system_issues = system_health["total_issues"]
        task_failures = queue_status["failed"]
        
        tenant.health_score = max(0, 100 - (code_issues * 2 + system_issues * 3 + task_failures))
        tenant.status = "critical" if tenant.health_score < 50 else "degraded" if tenant.health_score < 80 else "healthy"
        
        self._log_tenant_event(tenant_id, {
            "type": "diagnosis_complete",
            "health_score": tenant.health_score,
            "status": tenant.status,
            "code_issues": code_issues,
            "system_issues": system_issues,
            "task_failures": task_failures
        })
        
        return result
    
    def apply_repairs(self, tenant_id: str) -> dict:
        """Attempt to repair detected issues."""
        tenant = self.get_or_create_tenant(tenant_id)
        print(f"[TENANT {tenant_id}] Applying repairs...")
        
        result = {
            "tenant_id": tenant_id,
            "timestamp": self._now(),
            "repairs": {
                "code": 0,
                "system": 0,
                "tasks": 0
            },
            "details": []
        }
        
        # 1. System repairs
        system_repairs = self.error_monitor.auto_fix_errors()
        result["repairs"]["system"] = system_repairs["fixes_successful"]
        result["details"].append({
            "type": "system_repairs",
            "attempted": system_repairs["fixes_attempted"],
            "successful": system_repairs["fixes_successful"],
            "failed": system_repairs["fixes_failed"]
        })
        
        # 2. Task repairs (retry failed tasks)
        task_repairs = self.task_orchestrator.process_all_tasks(max_iterations=50)
        result["repairs"]["tasks"] = task_repairs["completed"]
        result["details"].append({
            "type": "task_processing",
            "processed": task_repairs["total_processed"],
            "completed": task_repairs["completed"],
            "failed": task_repairs["failed"]
        })
        
        tenant.repairs_applied.append(result)
        
        self._log_tenant_event(tenant_id, {
            "type": "repairs_applied",
            "system_repairs": system_repairs["fixes_successful"],
            "tasks_processed": task_repairs["total_processed"]
        })
        
        return result
    
    def generate_guidance(self, tenant_id: str) -> dict:
        """Generate healing guidance for tenant."""
        tenant = self.get_or_create_tenant(tenant_id)
        print(f"[TENANT {tenant_id}] Generating guidance...")
        
        guidance = {
            "tenant_id": tenant_id,
            "timestamp": self._now(),
            "health_score": tenant.health_score,
            "status": tenant.status,
            "actions": [],
            "next_steps": []
        }
        
        # Code guidance
        code_guidance = self.self_healer.get_healing_guidance()
        guidance["actions"].append({
            "category": "Code Quality",
            "guidance": code_guidance,
            "priority": "immediate" if "SYNTAX" in code_guidance else "high"
        })
        
        # System guidance
        if self.error_monitor.errors:
            guidance["actions"].append({
                "category": "System Health",
                "guidance": self.error_monitor.generate_report(),
                "priority": "high" if any(e.get("severity") == "critical" for e in self.error_monitor.errors) else "medium"
            })
        
        # Task guidance
        queue_status = self.task_orchestrator.get_queue_status()
        if queue_status["total_queued"] > 0:
            guidance["actions"].append({
                "category": "Task Queue",
                "guidance": f"Process remaining {queue_status['total_queued']} queued tasks",
                "priority": "normal"
            })
        
        # Recommendations
        if tenant.health_score < 50:
            guidance["next_steps"].append("CRITICAL: Run full system diagnostics immediately")
        elif tenant.health_score < 80:
            guidance["next_steps"].append("Review recent repairs and test thoroughly")
        
        guidance["next_steps"].append("Monitor system for 5 minutes after repairs")
        guidance["next_steps"].append("Run automated tests to verify fixes")
        
        tenant.guidance_given.append(guidance)
        
        self._log_tenant_event(tenant_id, {
            "type": "guidance_generated",
            "action_count": len(guidance["actions"]),
            "health_score": tenant.health_score
        })
        
        return guidance
    
    def get_tenant_status(self, tenant_id: str) -> dict:
        """Get current healing status for tenant."""
        tenant = self.get_or_create_tenant(tenant_id)
        return {
            "tenant_id": tenant_id,
            "status_info": tenant.to_dict(),
            "recent_diagnostics": tenant.diagnostics[-3:] if tenant.diagnostics else [],
            "recent_repairs": tenant.repairs_applied[-3:] if tenant.repairs_applied else [],
            "recent_guidance": tenant.guidance_given[-1:] if tenant.guidance_given else []
        }
    
    def run_full_healing_cycle(self, tenant_id: str) -> dict:
        """Run complete healing cycle: diagnose → repair → guide."""
        print(f"\n{'═'*70}")
        print(f"[TENANT {tenant_id}] STARTING HEALING CYCLE")
        print(f"{'═'*70}\n")
        
        cycle_result = {
            "tenant_id": tenant_id,
            "timestamp": self._now(),
            "stages": {}
        }
        
        # Stage 1: Diagnose
        print("[1/3] DIAGNOSIS")
        diagnostic_result = self.diagnose_tenant(tenant_id)
        cycle_result["stages"]["diagnosis"] = diagnostic_result
        
        # Stage 2: Repair
        print("[2/3] REPAIR")
        repair_result = self.apply_repairs(tenant_id)
        cycle_result["stages"]["repair"] = repair_result
        
        # Stage 3: Guidance
        print("[3/3] GUIDANCE")
        guidance_result = self.generate_guidance(tenant_id)
        cycle_result["stages"]["guidance"] = guidance_result
        
        # Final status
        tenant = self.tenants[tenant_id]
        cycle_result["final_status"] = {
            "health_score": tenant.health_score,
            "status": tenant.status
        }
        
        print(f"\n[SUMMARY] Tenant {tenant_id}: {tenant.status.upper()} (health: {tenant.health_score}/100)")
        print(f"{'═'*70}\n")
        
        self._log_tenant_event(tenant_id, {
            "type": "healing_cycle_complete",
            "health_score": tenant.health_score,
            "status": tenant.status
        })
        
        return cycle_result
    
    def run_all_tenants_cycle(self, tenant_ids: list = None) -> dict:
        """Run healing cycle for multiple tenants."""
        if tenant_ids is None:
            tenant_ids = list(self.tenants.keys()) or ["default"]
        
        results = {
            "timestamp": self._now(),
            "total_tenants": len(tenant_ids),
            "cycles": []
        }
        
        for tenant_id in tenant_ids:
            cycle = self.run_full_healing_cycle(tenant_id)
            results["cycles"].append(cycle)
        
        return results
    
    def get_dashboard_data(self, tenant_ids: list = None) -> dict:
        """Get data for healing dashboard."""
        if tenant_ids is None:
            tenant_ids = list(self.tenants.keys()) or ["default"]
        
        dashboard = {
            "timestamp": self._now(),
            "total_tenants": len(tenant_ids),
            "tenants": []
        }
        
        for tenant_id in tenant_ids:
            tenant = self.get_or_create_tenant(tenant_id)
            
            dashboard["tenants"].append({
                "id": tenant_id,
                "health_score": tenant.health_score,
                "status": tenant.status,
                "last_check": tenant.last_check,
                "diagnostics_count": len(tenant.diagnostics),
                "repairs_count": len(tenant.repairs_applied),
                "guidance_count": len(tenant.guidance_given),
                "recent_guidance": tenant.guidance_given[-1] if tenant.guidance_given else None
            })
        
        return dashboard
    
    def generate_dashboard_report(self) -> str:
        """Generate readable dashboard report."""
        report = f"\n{'═'*70}\n"
        report += f"TENANT HEALING DASHBOARD\n"
        report += f"{'═'*70}\n\n"
        
        for tenant_id, tenant in self.tenants.items():
            status_icon = "🟢" if tenant.status == "healthy" else "🟡" if tenant.status == "degraded" else "🔴"
            report += f"{status_icon} {tenant_id}\n"
            report += f"   Health: {tenant.health_score}/100 ({tenant.status})\n"
            report += f"   Diagnostics: {len(tenant.diagnostics)} runs\n"
            report += f"   Repairs: {len(tenant.repairs_applied)} applied\n"
            report += f"   Guidance: {len(tenant.guidance_given)} issued\n"
            report += f"   Last Check: {tenant.last_check or 'never'}\n\n"
        
        report += f"{'═'*70}\n"
        return report
