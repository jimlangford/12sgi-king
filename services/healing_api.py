"""Healing dashboard API endpoints for real-time tenant diagnostics.

Endpoints:
  /gordon/healing/dashboard        - overall dashboard
  /gordon/healing/tenant/<id>      - specific tenant status
  /gordon/healing/cycle/<id>       - run healing cycle for tenant
  /gordon/healing/diagnose/<id>    - run diagnostics only
  /gordon/healing/repair/<id>      - run repairs only
  /gordon/healing/guidance/<id>    - get guidance only

Usage: included in board_api and gordon_api
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from services.tenant_healer import TenantHealer

router = APIRouter(prefix="/gordon/healing", tags=["gordon_healing"])

# Global tenant healer instance
tenant_healer = TenantHealer()


@router.get("/dashboard")
async def get_dashboard(tenant_ids: Optional[str] = None):
    """Get healing dashboard for all or specific tenants.
    
    Args:
        tenant_ids: comma-separated tenant IDs (optional, uses all if not provided)
    """
    tenant_list = None
    if tenant_ids:
        tenant_list = [t.strip() for t in tenant_ids.split(",")]
    
    return tenant_healer.get_dashboard_data(tenant_list)


@router.get("/tenant/{tenant_id}")
async def get_tenant_status(tenant_id: str):
    """Get healing status for a specific tenant."""
    status = tenant_healer.get_tenant_status(tenant_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
    return status


@router.get("/diagnose/{tenant_id}")
async def run_diagnostics(tenant_id: str):
    """Run diagnostics only (no repairs)."""
    result = tenant_healer.diagnose_tenant(tenant_id)
    return result


@router.post("/repair/{tenant_id}")
async def apply_repairs(tenant_id: str):
    """Apply repairs to detected issues."""
    result = tenant_healer.apply_repairs(tenant_id)
    return result


@router.get("/guidance/{tenant_id}")
async def get_guidance(tenant_id: str):
    """Get healing guidance for tenant."""
    result = tenant_healer.generate_guidance(tenant_id)
    return result


@router.post("/cycle/{tenant_id}")
async def run_healing_cycle(tenant_id: str):
    """Run complete healing cycle: diagnose → repair → guide."""
    result = tenant_healer.run_full_healing_cycle(tenant_id)
    return result


@router.post("/cycle/multi")
async def run_all_cycles(tenant_ids: Optional[str] = None):
    """Run healing cycle for multiple tenants."""
    tenant_list = None
    if tenant_ids:
        tenant_list = [t.strip() for t in tenant_ids.split(",")]
    
    result = tenant_healer.run_all_tenants_cycle(tenant_list)
    return result


@router.get("/report")
async def get_report(tenant_id: Optional[str] = None):
    """Get comprehensive healing report."""
    if tenant_id:
        status = tenant_healer.get_tenant_status(tenant_id)
        return {
            "report": tenant_healer.generate_dashboard_report(),
            "tenant_status": status
        }
    else:
        return {
            "report": tenant_healer.generate_dashboard_report(),
            "total_tenants": len(tenant_healer.tenants)
        }


@router.get("/summary")
async def get_summary():
    """Get quick summary of all tenant health."""
    dashboard = tenant_healer.get_dashboard_data()
    
    # Calculate totals
    total_health = 0
    healthy_count = 0
    degraded_count = 0
    critical_count = 0
    
    for tenant in dashboard["tenants"]:
        total_health += tenant["health_score"]
        if tenant["status"] == "healthy":
            healthy_count += 1
        elif tenant["status"] == "degraded":
            degraded_count += 1
        else:
            critical_count += 1
    
    avg_health = int(total_health / len(dashboard["tenants"])) if dashboard["tenants"] else 0
    
    return {
        "timestamp": dashboard["timestamp"],
        "total_tenants": dashboard["total_tenants"],
        "average_health": avg_health,
        "status_breakdown": {
            "healthy": healthy_count,
            "degraded": degraded_count,
            "critical": critical_count
        },
        "tenants": dashboard["tenants"]
    }
