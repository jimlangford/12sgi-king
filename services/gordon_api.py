"""Gordon AI API — expose coordination capabilities via FastAPI.

Endpoints:
  /gordon/health           - system health status
  /gordon/tasks/queue      - task queue status
  /gordon/tasks/create     - create new task
  /gordon/search           - web search
  /gordon/best-practices   - get best practices
  /gordon/errors           - get detected errors
  /gordon/corrections      - auto-fix errors
  /gordon/report           - session report

Usage: included in board_api.main:app
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
import subprocess
import json

from services.error_corrector import ErrorMonitor
from services.task_orchestrator import TaskOrchestrator
from services.web_search import search_web, get_best_practices, search_error_solution
from services.gordon_coordinator import GordonCoordinator

router = APIRouter(prefix="/gordon", tags=["gordon"])

# Global instances (shared with coordinator)
error_monitor = ErrorMonitor()
task_orchestrator = TaskOrchestrator()
gordon_coordinator = None  # Set by watchdog


class CreateTaskRequest(BaseModel):
    tenant_id: str
    work_type: str
    params: Optional[dict] = None
    priority: Optional[str] = "normal"


class SearchRequest(BaseModel):
    query: str
    sources: Optional[list] = None


@router.get("/health")
async def gordon_health():
    """Get system health overview."""
    health = error_monitor.check_all_services()
    tasks = task_orchestrator.get_queue_status()
    
    return {
        "status": "operational",
        "health": health,
        "tasks": tasks,
        "coordinator_running": gordon_coordinator is not None
    }


@router.get("/tasks/queue")
async def get_task_queue():
    """Get current task queue status."""
    return task_orchestrator.get_queue_status()


@router.post("/tasks/create")
async def create_task(request: CreateTaskRequest):
    """Create a new task for a tenant."""
    task_id = task_orchestrator.queue_tenant_task(
        tenant_id=request.tenant_id,
        work_type=request.work_type,
        params=request.params,
        priority=request.priority
    )
    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks/tenant/{tenant_id}")
async def get_tenant_tasks(tenant_id: str):
    """Get all tasks for a specific tenant."""
    return task_orchestrator.get_tenant_tasks(tenant_id)


@router.get("/search")
async def web_search(query: str = Query(..., min_length=3)):
    """Search the web for information."""
    results = search_web(query)
    return {"query": query, "results": results, "count": len(results)}


@router.get("/best-practices")
async def get_practices(topic: str = Query(..., min_length=3)):
    """Get best practices for a topic."""
    return get_best_practices(topic)


@router.get("/errors")
async def get_errors():
    """Get all detected system errors."""
    error_monitor.check_all_services()
    return {
        "total": len(error_monitor.errors),
        "errors": error_monitor.errors
    }


@router.post("/errors/fix")
async def fix_errors(auto_fix: bool = True):
    """Detect and fix errors."""
    error_monitor.check_all_services()
    if auto_fix:
        results = error_monitor.auto_fix_errors()
        return {
            "auto_fixed": results,
            "report": error_monitor.generate_report()
        }
    return {"errors": error_monitor.errors}


@router.get("/errors/solutions")
async def get_error_solutions():
    """Search for solutions to detected errors."""
    error_monitor.check_all_services()
    solutions = error_monitor.search_solutions()
    return {"errors_researched": len(solutions), "solutions": solutions}


@router.get("/report")
async def get_report(report_type: str = Query("summary", regex="^(summary|errors|tasks|full)$")):
    """Get comprehensive system report."""
    if report_type == "errors":
        return {"report": error_monitor.generate_report()}
    elif report_type == "tasks":
        return {"report": task_orchestrator.generate_report()}
    elif report_type == "full":
        return {
            "errors_report": error_monitor.generate_report(),
            "tasks_report": task_orchestrator.generate_report(),
            "timestamp": str(__import__("datetime").datetime.now())
        }
    else:  # summary
        health = error_monitor.check_all_services()
        queue = task_orchestrator.get_queue_status()
        return {
            "health": {
                "total_issues": health["total_issues"],
                "critical": health["critical"],
                "high": health["high"]
            },
            "tasks": {
                "queued": queue["total_queued"],
                "completed": queue["completed"],
                "failed": queue["failed"]
            }
        }


@router.post("/manual-search")
async def manual_search(request: SearchRequest):
    """Perform a manual web search (same as /search)."""
    results = search_web(request.query, sources=request.sources)
    return {"query": request.query, "results": results, "count": len(results)}


@router.get("/capability-matrix")
async def capability_matrix():
    """Get matrix of all Gordon capabilities."""
    return {
        "web_search": {
            "endpoint": "/gordon/search",
            "method": "GET",
            "description": "Search web for information",
            "free": True
        },
        "error_detection": {
            "endpoint": "/gordon/errors",
            "method": "GET",
            "description": "Detect all system errors",
            "auto_correct": True
        },
        "task_management": {
            "endpoint": "/gordon/tasks/queue",
            "method": "GET",
            "description": "Manage tenant task queue",
            "features": ["create", "track", "retry"]
        },
        "best_practices": {
            "endpoint": "/gordon/best-practices",
            "method": "GET",
            "description": "Discover best practices",
            "sources": ["web", "documentation"]
        },
        "auto_healing": {
            "endpoint": "/gordon/errors/fix",
            "method": "POST",
            "description": "Automatically fix errors",
            "safe_commands_only": True
        }
    }
