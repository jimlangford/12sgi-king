"""
12 Stones v2 Local Owner Node — main API entry point.

Runs inside Docker on the owner machine. Accessible only via
localhost or through the Tailscale private network (12sgi-v2).
Never exposed to the public internet without explicit review.

V2 four-lane architecture:
  INPUT        → ingest PDFs, agendas, public records, farm/grant data
  AI           → local LLM / HF model analysis (private, never public)
  VERIFY       → source links, timestamps, audit log, human approval
  OUTPUT       → only clean approved content reaches 12sgi.com / govOS
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
import sys
from pathlib import Path

# Allow importing workboard from the repo root when run inside Docker/local
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from services.v2_workboard import (
    approve_workboard_job,
    pending_approvals,
    reject_workboard_job,
    selfheal_engineering_jobs,
)
from watchers import pulse_geometry

app = FastAPI(
    title="12 Stones v2 Local Owner Node",
    description=(
        "Private owner dashboard. Accessible via localhost or Tailscale only. "
        "All approval gates for creative and output lane content live here."
    ),
)

WORKBOARD_LOG = Path(os.getenv("WORKBOARD_DISPATCH_LOG", "")) or None


def _read_secret(name: str) -> str | None:
    """Read a Docker secret from /run/secrets/<name>."""
    p = Path(f"/run/secrets/{name}")
    if p.exists():
        return p.read_text().strip() or None
    return None


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "12sgi-v2",
        "mode": "local-owner-tailscale",
        "env": os.getenv("APP_ENV", "local"),
    }


@app.get("/")
def root():
    return {
        "message": "12 Stones v2 local owner node is running.",
        "access": "Localhost or Tailscale only.",
        "docs": "/docs",
        "lanes": {
            "engineering": "auto-heals — no gate required",
            "creative": "human review required before output",
            "output": "owner approval required before publish to 12sgi.com",
        },
    }


# ── Approval gate (VERIFY lane) ───────────────────────────────────────────────

@app.get("/approvals/pending")
def list_pending_approvals():
    """List all creative and output lane jobs waiting for human review.

    These are the items that must be approved before any content goes public.
    Engineering lane jobs never appear here — they self-heal automatically.
    """
    items = pending_approvals(log_path=WORKBOARD_LOG)
    return {
        "count": len(items),
        "pending": [
            {
                "job_id": (item.get("job") or {}).get("id"),
                "lane": item.get("lane"),
                "action": (item.get("job") or {}).get("action"),
                "source": item.get("source"),
                "iso": item.get("iso"),
                "payload": (item.get("job") or {}).get("payload") or {},
            }
            for item in items
        ],
    }


class ApproveRequest(BaseModel):
    approver: str
    note: str | None = None


@app.post("/approvals/{job_id}/approve")
def approve_job(job_id: str, body: ApproveRequest):
    """Approve a creative or output lane job.

    Records an approval tombstone.  This is the human gate that allows
    approved content to move toward the OUTPUT lane (publish to 12sgi.com).
    """
    tombstone = approve_workboard_job(
        job_id,
        body.approver,
        note=body.note,
        log_path=WORKBOARD_LOG,
    )
    return {
        "approved": True,
        "job_id": job_id,
        "tombstone_id": tombstone["job"]["id"],
        "iso": tombstone["iso"],
    }


class RejectRequest(BaseModel):
    reason: str
    rejector: str = "owner"


@app.post("/approvals/{job_id}/reject")
def reject_job(job_id: str, body: RejectRequest):
    """Reject a creative or output lane job.

    Records a rejection tombstone.  Rejected jobs stay in the audit log
    and are never published.  Resubmit a corrected version as a new job.
    """
    tombstone = reject_workboard_job(
        job_id,
        body.reason,
        rejector=body.rejector,
        log_path=WORKBOARD_LOG,
    )
    return {
        "rejected": True,
        "job_id": job_id,
        "tombstone_id": tombstone["job"]["id"],
        "iso": tombstone["iso"],
    }


@app.get("/pulse/geometry")
def pulse_geometry_snapshot():
    """Return the dedicated pulse lane×skill geometry snapshot.

    This is a PRIVATE read surface over the additive geometry model. It does not
    modify the existing workboard or publish anything.
    """
    snap = pulse_geometry.snapshot()
    return {
        "layer": snap["layer"],
        "minimum_geometry": snap["minimum_geometry"],
        "full_hina_cycle": snap["full_hina_cycle"],
        "counts": snap["counts"],
        "place_tuning": snap["place_tuning"],
        "geometry_complete": snap["geometry_complete"],
        "lane_sample": snap["lanes"][:6],
        "skill_sample": snap["skills"][:6],
        "element_sample": snap["elements"][:6],
        "residence_frequency_sample": snap["residence_frequencies"],
        "cell_sample": snap["cells_sample"],
        "forecast_sample": snap["forecasts"],
    }


@app.post("/pulse/geometry/refresh")
def refresh_pulse_geometry():
    """Project the pulse geometry lattice into Neo4j under its own additive layer."""
    ok = pulse_geometry.refresh()
    return {"refreshed": bool(ok), "layer": pulse_geometry.LAYER}


# ── Engineering self-heal (manual trigger) ────────────────────────────────────

@app.post("/selfheal")
def trigger_selfheal():
    """Manually trigger the engineering lane self-healer.

    Engineering jobs (auth events, storage uploads, AI analysis) are approved
    to fix themselves forward.  This endpoint runs the heal pass on demand.
    Calling it is always safe — it will never touch creative or output jobs.
    """
    healed = selfheal_engineering_jobs(log_path=WORKBOARD_LOG, outcome="self-healed")
    return {"healed": healed, "lane": "engineering"}


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8088"))
    uvicorn.run(app, host=host, port=port)
