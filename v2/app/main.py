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
import base64
import binascii
import hashlib
import hmac
import json
import logging
import secrets as _secrets
import sys
import os
import uvicorn
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

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
from services.event_bus import get_recent_events, get_dead_letters
from services.connectors import registry as _connector_registry
from watchers import graph_refresh
from watchers import pulse_geometry

app = FastAPI(
    title="12 Stones v2 Local Owner Node",
    description=(
        "Private owner dashboard. Accessible via localhost or Tailscale only. "
        "All approval gates for creative and output lane content live here."
    ),
)

_log = logging.getLogger(__name__)

WORKBOARD_LOG = Path(os.getenv("WORKBOARD_DISPATCH_LOG", "")) or None

# ── Auth signing secret (shared with the auth service) ───────────────────────
# AUTH_SIGNING_SECRET must match the secret used by services/auth to sign
# owner tokens.  Read from env (injected via docker-compose or .env) or from
# the Docker secret file at /run/secrets/auth_signing_secret.

_AUTH_SIGNING_SECRET: str | None = None


def _read_secret(name: str) -> str | None:
    """Read a Docker secret from /run/secrets/<name>."""
    p = Path(f"/run/secrets/{name}")
    if p.exists():
        return p.read_text().strip() or None
    return None


def _get_signing_secret() -> str | None:
    """Return the auth signing secret from env or Docker secret file."""
    global _AUTH_SIGNING_SECRET
    if _AUTH_SIGNING_SECRET is None:
        _AUTH_SIGNING_SECRET = (
            os.getenv("AUTH_SIGNING_SECRET")
            or _read_secret("auth_signing_secret")
        )
    return _AUTH_SIGNING_SECRET


def _b64url_decode(s: str) -> bytes:
    padded = s + "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(padded)


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _verify_owner_token(token: str) -> dict:
    """Verify a govOS owner JWT and return its claims.

    Raises HTTPException 401/403 on any failure.
    The token must have role=='Owner' and must not be expired.
    """
    signing_secret = _get_signing_secret()
    if not signing_secret:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "auth_unavailable", "message": "AUTH_SIGNING_SECRET not configured"}},
        )

    try:
        header_part, payload_part, sig_part = token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Malformed token"}})

    unsigned = f"{header_part}.{payload_part}".encode()
    expected_sig = _b64url_encode(hmac.new(signing_secret.encode(), unsigned, hashlib.sha256).digest())
    if not _secrets.compare_digest(expected_sig, sig_part):
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Invalid token signature"}})

    try:
        claims = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Malformed token payload"}})

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if int(claims.get("exp", 0)) <= now_ts:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Token expired"}})

    if claims.get("role") != "Owner":
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden", "message": "Owner role required"}})

    return claims


def _require_owner(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: validate Authorization: ****** as Owner."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Authorization: ****** required"}},
        )
    token = authorization.split(" ", 1)[1].strip()
    return _verify_owner_token(token)


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
def approve_job(job_id: str, body: ApproveRequest, owner: dict = Depends(_require_owner)):
    """Approve a creative or output lane job.

    Requires a valid owner OAuth token (Authorization: ******).
    The approver identity defaults to the token subject when not supplied.
    Records an approval tombstone — the human gate that allows approved
    content to move toward the OUTPUT lane (publish to 12sgi.com).
    """
    approver = body.approver or owner.get("sub") or "owner"
    tombstone = approve_workboard_job(
        job_id,
        approver,
        note=body.note,
        log_path=WORKBOARD_LOG,
    )
    return {
        "approved": True,
        "job_id": job_id,
        "tombstone_id": tombstone["job"]["id"],
        "iso": tombstone["iso"],
    }


class BatchApproveRequest(BaseModel):
    job_ids: list[str] | None = None  # None/omitted = approve all pending
    note: str | None = None


@app.post("/approvals/batch")
def batch_approve(body: BatchApproveRequest = BatchApproveRequest(), owner: dict = Depends(_require_owner)):
    """Approve multiple pending jobs in one call.

    Requires a valid owner OAuth token (Authorization: ******).
    The approver identity is taken directly from the token subject — no
    additional input needed, so the owner can click through in one action.

    - Supply ``job_ids`` to approve a specific subset.
    - Omit ``job_ids`` (or pass ``null``) to approve every pending creative
      and output lane job at once.

    Returns a summary of approved and skipped items.
    """
    approver = owner.get("sub") or "owner"
    if body.job_ids is None:
        targets = [
            (item.get("job") or {}).get("id")
            for item in pending_approvals(log_path=WORKBOARD_LOG)
        ]
        targets = [jid for jid in targets if jid]
    else:
        targets = body.job_ids

    approved = []
    skipped = []
    for job_id in targets:
        try:
            tombstone = approve_workboard_job(
                job_id,
                approver,
                note=body.note,
                log_path=WORKBOARD_LOG,
            )
            approved.append({"job_id": job_id, "tombstone_id": tombstone["job"]["id"], "iso": tombstone["iso"]})
        except Exception as exc:
            _log.warning("batch_approve: skipped job %s: %s", job_id, exc)
            skipped.append({"job_id": job_id, "reason": "approval failed — see owner node log"})

    return {
        "approved_count": len(approved),
        "skipped_count": len(skipped),
        "approver": approver,
        "approved": approved,
        "skipped": skipped,
    }


class RejectRequest(BaseModel):
    reason: str
    rejector: str = "owner"


@app.post("/approvals/{job_id}/reject")
def reject_job(job_id: str, body: RejectRequest, owner: dict = Depends(_require_owner)):
    """Reject a creative or output lane job.

    Requires a valid owner OAuth token (Authorization: ******).
    Records a rejection tombstone.  Rejected jobs stay in the audit log
    and are never published.  Resubmit a corrected version as a new job.
    """
    rejector = body.rejector or owner.get("sub") or "owner"
    tombstone = reject_workboard_job(
        job_id,
        body.reason,
        rejector=rejector,
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
        "context_sample": snap["contexts"],
        "quadrant_sample": snap["quadrants"],
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


@app.get("/graph/status")
def graph_status():
    """Return PRIVATE freshness/status for the v5.2 Neo4j graph stack."""
    return graph_refresh.status()


class GraphRefreshRequest(BaseModel):
    mode: str = "full"
    reason: str = "owner-manual"
    targets: list[str] | None = None


@app.post("/graph/refresh")
def refresh_graph(body: GraphRefreshRequest):
    """Refresh graph/vector/spine/pulse layers through the single PRIVATE ratchet."""
    ok = graph_refresh.refresh(mode=body.mode, reason=body.reason, targets=body.targets)
    return {"refreshed": bool(ok), "status": graph_refresh.status()}


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


# ── Platform event log (owner-only) ──────────────────────────────────────────

@app.get("/events")
def list_platform_events(
    limit: int = 50,
    event_type: str | None = None,
    producer: str | None = None,
):
    """Return recent platform events from the append-only event log.

    This is the PRIVATE owner-console surface for the platform event bus
    described in docs/EVENT_BUS.md. Filters:
      ?limit=N           — max events to return (default 50, max 200)
      ?event_type=x      — exact match on event type
      ?producer=x        — exact match on producer

    Events include workboard lane transitions (job.created / job.approved /
    job.rejected / engineering.selfhealed) and any other service that calls
    services.event_bus.publish_event().
    """
    events = get_recent_events(
        limit=min(limit, 200),
        event_type=event_type,
        producer=producer,
    )
    return {"count": len(events), "events": events}


@app.get("/events/dead-letters")
def list_dead_letters(limit: int = 20):
    """Return recent dead-letter events (oversized or undeliverable payloads)."""
    items = get_dead_letters(limit=min(limit, 100))
    return {"count": len(items), "dead_letters": items}


# ── MCP Connector layer — per-platform OAuth token lifecycle ──────────────────
#
# Each publishing platform (wordpress / youtube / tiktok / facebook / linkedin)
# has an entry in the connector registry.  The registry tracks token validity
# and can attempt silent refreshes before falling through to a "needs_auth" card
# that the console surfaces as an [Authorize <Platform>] button.
#
# Flow for a batch publish triggered by "Approve All":
#   1. For each platform in the draft's destination list:
#      a. ensure_valid() → "valid" or "refreshed"  → publish immediately
#      b. ensure_valid() → "needs_auth"             → skip + return auth card
#   2. Console shows one ⚠️ card per platform that needs re-authorization.
#   3. All other platforms already published.  Owner only sees the stuck ones.

@app.get("/connectors")
def list_connectors():
    """Return token-status cards for every publishing platform.

    This is the owner console's "connector health" surface.  It never
    exposes raw tokens — only status, expiry, account label, and scopes.
    """
    cards = _connector_registry.status_all()
    meta = {m["platform"]: m for m in _connector_registry.all_platform_meta()}
    result = []
    for platform, card in cards.items():
        result.append({
            **meta.get(platform, {}),
            **card,
        })
    return {"connectors": result}


@app.post("/connectors/{platform}/refresh")
def refresh_connector_token(platform: str, owner: dict = Depends(_require_owner)):
    """Attempt a silent OAuth token refresh for a platform.

    Requires owner OAuth token.  Returns the updated status card.
    If the refresh fails the card will have status == 'needs_auth'.
    """
    try:
        ok = _connector_registry.refresh(platform)
    except ValueError as exc:
        _log.warning("connector refresh %s: %s", platform, exc)
        raise HTTPException(status_code=400, detail={"error": "unknown or misconfigured platform"})
    card = _connector_registry.status(platform)
    return {"refreshed": ok, **card}


@app.get("/connectors/{platform}/authorize")
def connector_authorize_url(platform: str, redirect_uri: str, state: str = ""):
    """Return the OAuth authorization URL for a platform.

    The console navigates the owner to this URL to (re-)authorize the
    connector.  After authorization, the platform redirects to redirect_uri
    with ?code=...  The owner node's /connectors/{platform}/callback then
    exchanges the code for tokens.

    WordPress returns an empty string — use /connectors/wordpress/app-password.
    """
    try:
        url = _connector_registry.authorize_url(platform, redirect_uri=redirect_uri, state=state)
    except ValueError as exc:
        _log.warning("connector authorize_url %s: %s", platform, exc)
        raise HTTPException(status_code=400, detail={"error": "unknown platform or missing credentials — check .env.v2"})
    return {"platform": platform, "authorize_url": url}


class ConnectorCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


@app.post("/connectors/{platform}/callback")
def connector_oauth_callback(
    platform: str,
    body: ConnectorCallbackRequest,
    owner: dict = Depends(_require_owner),
):
    """Exchange an OAuth authorization code for platform tokens and store them.

    Called by the console after the platform redirects back with ?code=...
    Requires owner OAuth token.
    """
    try:
        card = _connector_registry.exchange_code(platform, body.code, body.redirect_uri)
    except (ValueError, RuntimeError) as exc:
        _log.warning("connector callback %s: %s", platform, exc)
        raise HTTPException(status_code=400, detail={"error": "token exchange failed — check platform credentials"})
    return {"stored": True, **card}


class WordPressAppPasswordRequest(BaseModel):
    username: str
    app_password: str
    site_url: str | None = None


@app.post("/connectors/wordpress/app-password")
def connector_wordpress_app_password(
    body: WordPressAppPasswordRequest,
    owner: dict = Depends(_require_owner),
):
    """Store a WordPress Application Password for the connector.

    WordPress uses Basic-auth app passwords rather than OAuth.
    Generate one at: WP Admin → Users → Edit → Application Passwords.
    Requires owner OAuth token.
    """
    card = _connector_registry.store_app_password(
        username=body.username,
        app_password=body.app_password,
        site_url=body.site_url,
    )
    return {"stored": True, **card}


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8088"))
    uvicorn.run(app, host=host, port=port)
