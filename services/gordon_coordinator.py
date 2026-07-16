"""Gordon AI Local Coordinator — main orchestration engine.

Coordinates web search, error correction, task orchestration, and learning.
Runs continuously as a background service, handling all system duties.

Usage:
  from services.gordon_coordinator import GordonCoordinator
  gordon = GordonCoordinator()
  gordon.run_continuous_loop(interval=60)  # Check every 60 seconds
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path


from services.error_corrector import ErrorMonitor
from services.task_orchestrator import TaskOrchestrator
from services.web_search import search_web, get_best_practices, search_error_solution
from services.tenant_healer import TenantHealer


class GordonCoordinator:
    """Main AI coordination engine for system health, task execution, and learning."""
    
    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path("logs/gordon-coordinator")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.error_monitor = ErrorMonitor(self.log_dir / "errors")
        self.task_orchestrator = TaskOrchestrator(self.log_dir / "tasks")
        self.tenant_healer = TenantHealer()  # Add tenant healing
        
        self.system_state = {}
        self.learning_log = []
        self.session_start = datetime.now(timezone.utc).isoformat()
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def _log_action(self, action: dict):
        """Log a coordination action."""
        action["ts"] = self._now()
        try:
            log_file = self.log_dir / f"actions-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(action) + "\n")
            self.learning_log.append(action)
        except Exception as e:
            print(f"Error logging action: {e}")
    
    def health_check_cycle(self) -> dict:
        """Run complete health check: errors, fixes, solutions, learning."""
        print(f"\n[GORDON] Health check cycle at {self._now()}")
        
        # Step 1: Detect all errors
        print("[1/4] Scanning for errors...")
        health_status = self.error_monitor.check_all_services()
        self._log_action({
            "type": "health_check",
            "issues_found": health_status["total_issues"],
            "critical": health_status["critical"],
            "high": health_status["high"]
        })
        
        # Step 2: Auto-correct errors
        print("[2/4] Attempting auto-corrections...")
        corrections = self.error_monitor.auto_fix_errors()
        self._log_action({
            "type": "auto_corrections",
            "attempted": corrections["fixes_attempted"],
            "successful": corrections["fixes_successful"],
            "failed": corrections["fixes_failed"]
        })
        
        # Step 3: Search for solutions to remaining errors
        print("[3/4] Searching web for solutions...")
        solutions = self.error_monitor.search_solutions()
        self._log_action({
            "type": "solution_search",
            "errors_researched": len(solutions),
            "solutions_count": sum(len(v.get("solutions", [])) for v in solutions.values())
        })
        
        # Step 4: Learn from patterns
        print("[4/4] Logging learnings...")
        self._learn_from_errors(health_status["issues"], solutions)
        
        return {
            "timestamp": self._now(),
            "health_status": health_status,
            "corrections": corrections,
            "solutions": solutions,
            "learning_updated": True
        }
    
    def _learn_from_errors(self, errors: list, solutions: dict):
        """Extract patterns from errors and solutions for future reference."""
        if not errors:
            return
        
        # Count error types
        error_types = {}
        for error in errors:
            error_type = error.get("error", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # Log pattern
        self._log_action({
            "type": "learning",
            "pattern": "error_frequency",
            "error_types": error_types,
            "solutions_found": len(solutions)
        })
    
    def process_tenant_tasks_cycle(self) -> dict:
        """Process all queued tenant tasks."""
        print(f"\n[GORDON] Task processing cycle at {self._now()}")
        
        # Get queue status before
        before = self.task_orchestrator.get_queue_status()
        print(f"  Queue status: {before['total_queued']} tasks queued")
        
        # Process all tasks
        results = self.task_orchestrator.process_all_tasks(max_iterations=50)
        print(f"  Processed {results['total_processed']} tasks: {results['completed']} ✓, {results['failed']} ✗")
        
        # Get queue status after
        after = self.task_orchestrator.get_queue_status()
        
        self._log_action({
            "type": "task_processing",
            "total_processed": results["total_processed"],
            "completed": results["completed"],
            "failed": results["failed"],
            "queue_before": before["total_queued"],
            "queue_after": after["total_queued"]
        })
        
        return {
            "timestamp": self._now(),
            "results": results,
            "queue_before": before,
            "queue_after": after
        }
    
    def discover_best_practices(self, topics: list) -> dict:
        """Proactively search for best practices on key topics."""
        print(f"\n[GORDON] Discovering best practices...")
        
        practices = {}
        for topic in topics:
            print(f"  → Researching: {topic}")
            result = get_best_practices(topic)
            practices[topic] = result
            
            self._log_action({
                "type": "best_practice_discovery",
                "topic": topic,
                "results_count": result["count"]
            })
        
        return practices
    
    def update_system_state(self) -> dict:
        """Update internal system state model based on latest observations."""
        state = {
            "timestamp": self._now(),
            "health": self.error_monitor.check_all_services(),
            "tasks": self.task_orchestrator.get_queue_status(),
            "session_duration": self._session_duration()
        }
        self.system_state = state
        return state
    
    def _session_duration(self) -> str:
        """Get duration of current session."""
        try:
            start = datetime.fromisoformat(self.session_start)
            now = datetime.now(timezone.utc)
            delta = now - start
            hours = delta.total_seconds() // 3600
            minutes = (delta.total_seconds() % 3600) // 60
            return f"{int(hours)}h {int(minutes)}m"
        except Exception:
            return "unknown"
    
    def run_continuous_loop(self, interval: int = 60, duration_hours: int = None, tenant_ids: list = None):
        """Run Gordon coordination loop continuously.
        
        Args:
            interval: seconds between check cycles
            duration_hours: stop after N hours (None = infinite)
            tenant_ids: list of tenant IDs to heal (optional)
        """
        if tenant_ids is None:
            tenant_ids = ["default"]
        
        print(f"[GORDON] Starting continuous loop (interval: {interval}s)")
        print(f"[GORDON] Session: {self.session_start}")
        print(f"[GORDON] Monitoring tenants: {', '.join(tenant_ids)}")
        
        iteration = 0
        start_time = time.time()
        max_duration_secs = duration_hours * 3600 if duration_hours else float('inf')
        
        try:
            while (time.time() - start_time) < max_duration_secs:
                iteration += 1
                print(f"\n{'═' * 70}")
                print(f"[ITERATION {iteration}] {self._now()}")
                print(f"{'═' * 70}")
                
                try:
                    # Cycle 1: Health checks and corrections
                    health_result = self.health_check_cycle()
                    
                    # Cycle 2: Task processing
                    task_result = self.process_tenant_tasks_cycle()
                    
                    # Cycle 3: Tenant healing (every 2 iterations)
                    if iteration % 2 == 0:
                        print("[HEALING] Running self-healing cycle for tenants...")
                        healing_results = {}
                        for tenant_id in tenant_ids:
                            healing_results[tenant_id] = self.tenant_healer.run_full_healing_cycle(tenant_id)
                        self._log_action({
                            "type": "tenant_healing_cycle",
                            "tenant_count": len(tenant_ids),
                            "results": healing_results
                        })
                    
                    # Cycle 4: Update state
                    state = self.update_system_state()
                    
                    # Cycle 5: Discovery (every 10 iterations)
                    if iteration % 10 == 0:
                        practices = self.discover_best_practices([
                            "Docker container health checks",
                            "GPU memory optimization",
                            "Python error handling",
                            "Async task queue best practices"
                        ])
                    
                    # Print summary
                    print(f"\n[SUMMARY]")
                    print(f"  Errors: {health_result['health_status']['total_issues']}")
                    print(f"  Auto-fixes: {health_result['corrections']['fixes_successful']} ✓")
                    print(f"  Tasks: {task_result['queue_after']['total_queued']} queued")
                    print(f"  Duration: {state['session_duration']}")
                    
                except Exception as e:
                    print(f"[ERROR in coordination loop: {e}")
                    self._log_action({
                        "type": "coordination_error",
                        "error": str(e),
                        "iteration": iteration
                    })
                
                # Wait for next cycle
                print(f"[SLEEPING] Next cycle in {interval}s...")
                time.sleep(interval)
        
        except KeyboardInterrupt:
            print(f"\n[GORDON] Loop interrupted by user")
        finally:
            self.print_session_report()
    
    def print_session_report(self):
        """Print a comprehensive session report."""
        print(f"\n{'═' * 70}")
        print(f"[SESSION REPORT] {self._now()}")
        print(f"{'═' * 70}")
        
        print(f"\nDuration: {self._session_duration()}")
        print(f"Learning events: {len(self.learning_log)}")
        
        # Breakdown by action type
        action_types = {}
        for action in self.learning_log:
            action_type = action.get("type", "unknown")
            action_types[action_type] = action_types.get(action_type, 0) + 1
        
        print(f"\nActions taken:")
        for action_type, count in sorted(action_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {action_type}: {count}")
        
        # Final error/task status
        final_health = self.error_monitor.check_all_services()
        final_queue = self.task_orchestrator.get_queue_status()
        
        print(f"\nFinal system status:")
        print(f"  Outstanding errors: {final_health['total_issues']}")
        print(f"  Queued tasks: {final_queue['total_queued']}")
        print(f"  Completed tasks: {final_queue['completed']}")
        
        print(f"\n{'═' * 70}\n")


# Quick start
if __name__ == "__main__":
    coordinator = GordonCoordinator()
    # Run for 1 hour, checking every 30 seconds
    coordinator.run_continuous_loop(interval=30, duration_hours=1)
