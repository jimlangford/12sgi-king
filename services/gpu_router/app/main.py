# gpu-router v3 — multi-engine state orchestrator, single host.
#
# ENGINES:
#   ollama    → Ollama (or llama.cpp) LLM inference; GPU-bound; serialised.
#   voice     → espeak-ng text-to-speech; CPU-bound; serialised on a CPU worker.
#   embedding → Ollama /api/embeddings; lighter GPU call; serialised on CPU worker.
#   comfyui   → ComfyUI image/video render; GPU-bound; future (shares GPU worker).
#
# CLIENTS:  govOS core, Maui tenant, Studio / Element LOTUS, Civic Signal,
#           Workboard, reports — each submits jobs by client_id + job_type.
#
# How it works:
#   POST /api/v2/gpu/infer  → enqueue job by job_type, block until done (or timeout).
#   GET  /api/v2/gpu/queue  → list pending / running jobs (owner only).
#   GET  /api/v2/gpu/usage  → per-client usage stats.
#   GET  /api/v2/gpu/events → recent event bus entries (engine start/done/error).
#   GET  /api/v2/gpu/ready|live|health  → standard govOS health surface.
#
# Workers:
#   GPU worker  — serialises ollama + comfyui calls (one GPU job at a time).
#   CPU worker  — serialises voice + embedding calls (runs concurrently with GPU).
#
# Priority:
#   Jobs from higher-priority clients are pulled first within each worker lane.
#   Priority is configured via CLIENT_PRIORITIES env (see below).
#   Ties broken by arrival order (FIFO within a tier).
#
# Queue persistence:
#   SQLite at GPU_ROUTER_DB_PATH.  A restart drains pending jobs in priority
#   order; any job still in state "running" at startup is reset to "pending" so
#   it can be retried.

import base64
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error, request
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel
from services.authz import audit_auth_event, enforce_tenant_scope, require_claims
from services.job_envelope import build_job_envelope, normalise_envelope, sync_envelope_state, transition_job_envelope
from services.service_metadata import with_service_metadata

API_PREFIX = "/api/v2"
SERVICE_NAME = "gpu-router"
VERSION = os.environ.get("VERSION", "3.0.0")
DB_PATH = os.environ.get("GPU_ROUTER_DB_PATH", "/tmp/govos_v2_gpu_router.db")
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GPU_PROFILE_PATH = os.path.join(REPO_ROOT, "config", "gpu_profiles", "rtx4070_8gb.json")
WORKFLOW_INVENTORY_PATH = os.path.join(REPO_ROOT, "config", "media_workflow_inventory.v2.json")

# Ollama (or llama.cpp) base URL — internal Docker network name.
GPU_RUNTIME_URL = os.environ.get("GPU_RUNTIME_URL", "http://gpu-runtime:11434")

# Auth introspection so callers must hold a valid owner token.
AUTH_INTROSPECTION_URL = os.environ.get("AUTH_INTROSPECTION_URL", "http://localhost:8101/api/v2/auth/introspect")
AUTH_READY_URL = os.environ.get("AUTH_READY_URL", "http://localhost:8101/api/v2/ready")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
REQUEST_TIMEOUT = float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "3"))

# How long to wait for Ollama to finish a job (seconds).
INFER_TIMEOUT = float(os.environ.get("GPU_INFER_TIMEOUT", "120"))
JOB_LEASE_SECONDS = float(os.environ.get("GPU_JOB_LEASE_SECONDS", str(max(INFER_TIMEOUT + 30, 150))))
RETRY_BACKOFF_SECONDS = float(os.environ.get("GPU_RETRY_BACKOFF_SECONDS", "2"))
MAX_RETRIES = max(0, int(os.environ.get("GPU_MAX_RETRIES", "2")))
DEFAULT_MAX_ATTEMPTS = MAX_RETRIES + 1
TENANT_CONCURRENCY_LIMIT = max(1, int(os.environ.get("GPU_TENANT_CONCURRENCY_LIMIT", "1")))
MEDIA_TENANT_ID = "media"
_gpu_resident_signature: str | None = None
_gpu_resident_engine: str | None = None

# Job type → engine lane mapping.
#   GPU worker:  ollama, comfyui
#   CPU worker:  voice, embedding
GPU_LANES = {"ollama", "comfyui"}
CPU_LANES = {"voice", "embedding"}
ALL_JOB_TYPES = GPU_LANES | CPU_LANES

# espeak-ng voice synthesis defaults (overridable via options in the request).
VOICE_DEFAULT_LANG = os.environ.get("VOICE_DEFAULT_LANG", "haw")
VOICE_DEFAULT_RATE = int(os.environ.get("VOICE_DEFAULT_RATE", "130"))
VOICE_DEFAULT_PITCH = int(os.environ.get("VOICE_DEFAULT_PITCH", "50"))

# Per-client priority weights (lower number = higher priority).
# Override via env: GPU_CLIENT_PRIORITIES=govos-core:1,maui-tenant:2,studio:3,...
_DEFAULT_PRIORITIES = {
    "govos-core":     1,
    "maui-tenant":    2,
    "studio":         3,
    "civic-signal":   4,
    "workboard":      5,
    "reports":        6,
}

def _load_priorities() -> dict[str, int]:
    raw = os.environ.get("GPU_CLIENT_PRIORITIES", "")
    if not raw.strip():
        return dict(_DEFAULT_PRIORITIES)
    out: dict[str, int] = {}
    for part in raw.split(","):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            try:
                out[k.strip()] = int(v.strip())
            except ValueError:
                pass
    return out or dict(_DEFAULT_PRIORITIES)

CLIENT_PRIORITIES = _load_priorities()
DEFAULT_PRIORITY = max(CLIENT_PRIORITIES.values()) + 1  # unknown clients go last

app = FastAPI(title="govOS GPU Router v3", version=VERSION)

# ──────────────────────────────────────────────
# DB
# ──────────────────────────────────────────────

@contextmanager
def _db():
    # sqlite3.Connection.__exit__ only commits/rolls back -- it does not close the connection.
    # Same leak found+fixed across services/{ai,auth,tenant,documents,storage}/app/main.py
    # 2026-07-09; worst offender here since _worker_loop polls _db() in a `while True:` loop.
    # Transactional behavior at call sites is unchanged.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # busy_timeout (audit-quad-os 2026-07-10): gpu-router-v3 runs TWO concurrent SQLite writers
    # (GPU + CPU workers) plus the infer poller. Wait up to 30s for a lock instead of raising
    # 'database is locked' immediately, so transient write contention self-resolves rather than
    # surfacing as an error the worker loop has to swallow.
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
    finally:
        conn.close()

def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gpu_jobs (
                id          TEXT PRIMARY KEY,
                tenant_id   TEXT NOT NULL DEFAULT '',
                client_id   TEXT NOT NULL,
                priority    INTEGER NOT NULL,
                job_type    TEXT NOT NULL DEFAULT 'ollama',
                model       TEXT NOT NULL,
                prompt      TEXT NOT NULL,
                options_json TEXT,
                idempotency_key TEXT,
                status      TEXT NOT NULL DEFAULT 'pending',
                result_json TEXT,
                error       TEXT,
                created_at  TEXT NOT NULL,
                started_at  TEXT,
                available_at TEXT,
                lease_expires_at TEXT,
                finished_at TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                worker_name TEXT,
                claim_token TEXT,
                created_by  TEXT NOT NULL,
                job_envelope_json TEXT
            )
            """
        )
        # Add job_type column to existing databases that pre-date v3.
        try:
            conn.execute("ALTER TABLE gpu_jobs ADD COLUMN job_type TEXT NOT NULL DEFAULT 'ollama'")
        except sqlite3.OperationalError:
            pass  # column already exists
        for ddl in (
            "ALTER TABLE gpu_jobs ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE gpu_jobs ADD COLUMN idempotency_key TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN available_at TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN lease_expires_at TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0",
            f"ALTER TABLE gpu_jobs ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT {DEFAULT_MAX_ATTEMPTS}",
            "ALTER TABLE gpu_jobs ADD COLUMN worker_name TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN claim_token TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN job_envelope_json TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN capability TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN media_job_type TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN media_state TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN workflow_id TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN workflow_profile TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN resolution TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN frame_count INTEGER",
            "ALTER TABLE gpu_jobs ADD COLUMN adapter_set TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN lora_set TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN model_residency INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE gpu_jobs ADD COLUMN vram_required_mb INTEGER",
            "ALTER TABLE gpu_jobs ADD COLUMN approval_required INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE gpu_jobs ADD COLUMN qc_required INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE gpu_jobs ADD COLUMN publish_eligible INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE gpu_jobs ADD COLUMN selected_engine TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN evidence_json TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN dependencies_json TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN published_at TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN output_hash TEXT",
            "ALTER TABLE gpu_jobs ADD COLUMN provenance_hash TEXT",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass
        conn.execute(
            "UPDATE gpu_jobs SET tenant_id = client_id WHERE tenant_id IS NULL OR tenant_id = ''"
        )
        conn.execute(
            "UPDATE gpu_jobs SET available_at = created_at WHERE available_at IS NULL"
        )
        conn.execute(
            "UPDATE gpu_jobs SET media_state = status WHERE tenant_id = ? AND (media_state IS NULL OR media_state = '')",
            (MEDIA_TENANT_ID,),
        )
        conn.execute(
            "UPDATE gpu_jobs SET max_attempts = ? WHERE max_attempts IS NULL OR max_attempts < 1",
            (DEFAULT_MAX_ATTEMPTS,),
        )
        rows = conn.execute(
            "SELECT id, tenant_id, client_id, job_type, status FROM gpu_jobs WHERE job_envelope_json IS NULL OR job_envelope_json = ''"
        ).fetchall()
        for row in rows:
            try:
                envelope = build_job_envelope(
                    domain="gpu-router",
                    service=SERVICE_NAME,
                    action="gpu.infer",
                    state="pending",
                    payload={"tenant_id": row["tenant_id"], "client_id": row["client_id"], "job_type": row["job_type"]},
                    lane=row["job_type"] or "ollama",
                    entity_id=row["id"],
                    correlation_id=row["id"],
                )
                status = (row["status"] or "pending").strip().lower()
                if status != "pending":
                    envelope = transition_job_envelope(envelope, status)
                conn.execute(
                    "UPDATE gpu_jobs SET job_envelope_json=? WHERE id=?",
                    (json.dumps(envelope, separators=(",", ":")), row["id"]),
                )
            except Exception:
                continue
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS gpu_jobs_tenant_idempotency_idx
            ON gpu_jobs (tenant_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gpu_events (
                id          TEXT PRIMARY KEY,
                event_type  TEXT NOT NULL,
                engine      TEXT NOT NULL,
                job_id      TEXT,
                detail_json TEXT,
                ts          TEXT NOT NULL
            )
            """
        )
        conn.commit()

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_after(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _parse_utc(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _normalise_tenant_id(value: str | None, client_id: str) -> str:
    tenant_id = (value or "").strip()
    return tenant_id or client_id


def _normalise_idempotency_key(value: str | None) -> str | None:
    key = (value or "").strip()
    return key or None


def _options_json(options: dict | None) -> str | None:
    if not options:
        return None
    return json.dumps(options, sort_keys=True, separators=(",", ":"))


def _canonical_media_profile() -> dict[str, Any]:
    try:
        with open(os.path.join(REPO_ROOT, "config", "canonical_job_contract.v2.json"), encoding="utf-8") as handle:
            data = json.load(handle)
        profile = ((data or {}).get("tenant_state_profiles") or {}).get("media") or {}
        return profile if isinstance(profile, dict) else {}
    except Exception:
        return {}


def _media_job_profiles() -> dict[str, Any]:
    profiles = _canonical_media_profile().get("job_type_profiles") or {}
    return profiles if isinstance(profiles, dict) else {}


def _media_transition_graphs() -> dict[str, Any]:
    graphs = _canonical_media_profile().get("transitions_by_job_type") or {}
    return graphs if isinstance(graphs, dict) else {}


def _media_capability_routing() -> dict[str, Any]:
    routing = _canonical_media_profile().get("capability_routing") or {}
    return routing if isinstance(routing, dict) else {}


def _load_gpu_profile() -> dict[str, Any]:
    try:
        with open(GPU_PROFILE_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_media_workflow_inventory() -> list[dict[str, Any]]:
    try:
        with open(WORKFLOW_INVENTORY_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        rows = (data or {}).get("workflows") or []
        return [row for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _workflow_by_id(workflow_id: str | None) -> dict[str, Any] | None:
    wanted = (workflow_id or "").strip()
    if not wanted:
        return None
    for row in _load_media_workflow_inventory():
        if str(row.get("workflow_id") or "").strip() == wanted:
            return row
    return None


def _media_job_signature(job: sqlite3.Row) -> str:
    adapter_set = (job["adapter_set"] or "").strip()
    lora_set = (job["lora_set"] or "").strip()
    return "|".join(
        [
            str(job["selected_engine"] or ""),
            str(job["workflow_profile"] or ""),
            str(job["resolution"] or ""),
            str(job["frame_count"] or ""),
            adapter_set,
            lora_set,
            "resident" if int(job["model_residency"] or 0) else "cold",
        ]
    )


def _parse_json_array(value: str | None) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _parse_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _hash_evidence(evidence: dict[str, Any]) -> str:
    payload = json.dumps(evidence or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _media_transition_is_allowed(job_type: str, from_state: str | None, to_state: str) -> bool:
    graph = _media_transition_graphs().get(job_type) or {}
    allowed = graph.get("allowed_transitions") or {}
    source = (from_state or "").strip().lower()
    target = (to_state or "").strip().lower()
    if not source:
        initial = str(graph.get("initial") or "").strip().lower()
        return target == initial
    next_states = allowed.get(source) or []
    return target in {str(item).strip().lower() for item in next_states}


def _media_required_inputs(job_type: str) -> set[str]:
    profile = _media_job_profiles().get(job_type) or {}
    req = profile.get("required_inputs") or []
    return {str(item).strip() for item in req if str(item).strip()}


def _media_completion_evidence(job_type: str) -> set[str]:
    profile = _media_job_profiles().get(job_type) or {}
    req = profile.get("completion_evidence") or []
    return {str(item).strip() for item in req if str(item).strip()}


def _media_qc_required(job_type: str) -> bool:
    profile = _media_job_profiles().get(job_type) or {}
    return str(profile.get("publish_eligibility") or "").strip().lower() == "approval_and_qc"


def _media_approval_required(job_type: str) -> bool:
    profile = _media_job_profiles().get(job_type) or {}
    return bool(profile.get("approval_required"))


def _select_engine_for_capability(capability: str | None) -> str | None:
    route = _media_capability_routing().get((capability or "").strip()) or {}
    preferred = str(route.get("preferred") or "").strip()
    fallback = str(route.get("fallback") or "").strip()
    return preferred or fallback or None


def _job_type_for_media_capability(capability: str | None) -> str:
    cap = (capability or "").strip().lower()
    if cap in {"image_generation", "short_video_generation", "long_video_generation", "upscale"}:
        return "comfyui"
    if cap in {"audio_generation", "voice_generation"}:
        return "voice"
    if cap in {"quality_check", "publishing"}:
        return "embedding"
    return "comfyui"


def _gpu_profile_allows_vram(vram_required_mb: int | None) -> bool:
    if not vram_required_mb:
        return True
    profile = _load_gpu_profile()
    safe_limit = profile.get("vram_safe_limit_mb")
    if not isinstance(safe_limit, int):
        return True
    return int(vram_required_mb) <= safe_limit

def _decode_envelope(blob: str | None) -> dict | None:
    if not blob:
        return None
    try:
        value = json.loads(blob)
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _envelope_for_row(job: sqlite3.Row, *, fallback_state: str = "pending") -> dict:
    status_state = (job["status"] or fallback_state or "pending").strip().lower()
    existing = _decode_envelope(job["job_envelope_json"])
    if existing:
        normalised = normalise_envelope(existing, domain="gpu-router", fallback_state=status_state)
        if normalised.get("state") != status_state:
            _log_event(
                "guardian.state_mismatch",
                "gpu-router",
                job["id"],
                {"status": status_state, "envelope_state": normalised.get("state")},
            )
            normalised = sync_envelope_state(
                normalised,
                status_state,
                actor="guardian",
                engine="gpu-router",
                reason="status_envelope_mismatch",
            )
        return normalised
    envelope = build_job_envelope(
        domain="gpu-router",
        service=SERVICE_NAME,
        action="gpu.infer",
        state="pending",
        payload={"tenant_id": job["tenant_id"], "client_id": job["client_id"], "job_type": job["job_type"]},
        lane=job["job_type"] or "ollama",
        entity_id=job["id"],
        correlation_id=job["id"],
    )
    target_state = status_state
    if target_state != "pending":
        try:
            envelope = transition_job_envelope(envelope, target_state)
        except ValueError:
            pass
    return envelope


def _media_transition(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    to_state: str,
    *,
    actor: str,
    reason: str,
    evidence: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    def emit(event_type: str, engine: str, detail: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO gpu_events (id, event_type, engine, job_id, detail_json, ts) VALUES (?,?,?,?,?,?)",
            (str(uuid4()), event_type, engine, job["id"], json.dumps(detail or {}), _now_utc()),
        )

    target = (to_state or "").strip().lower()
    if not target:
        return False, "missing_target_state"
    tenant_id = (job["tenant_id"] or "").strip().lower()
    if tenant_id != MEDIA_TENANT_ID:
        emit(
            "guardian.illegal_transition",
            "gpu-router",
            {
                "tenant": tenant_id or "",
                "job_id": job["id"],
                "previous_state": job["media_state"] or "",
                "requested_state": target,
                "reason": "tenant_not_media",
            },
        )
        return False, "tenant_not_media"
    job_type = (job["media_job_type"] or "").strip()
    if job_type not in _media_job_profiles():
        emit(
            "guardian.illegal_transition",
            "gpu-router",
            {
                "tenant": MEDIA_TENANT_ID,
                "job_id": job["id"],
                "previous_state": job["media_state"] or "",
                "requested_state": target,
                "reason": "unknown_media_job_type",
            },
        )
        return False, "unknown_media_job_type"
    current = (job["media_state"] or "").strip().lower()
    if current == target:
        return True, "duplicate_suppressed"
    if not _media_transition_is_allowed(job_type, current, target):
        emit(
            "guardian.illegal_transition",
            "gpu-router",
            {
                "tenant": MEDIA_TENANT_ID,
                "job_id": job["id"],
                "previous_state": current,
                "requested_state": target,
                "reason": "illegal_transition",
            },
        )
        return False, "illegal_transition"
    dependencies = _parse_json_array(job["dependencies_json"])
    if dependencies:
        placeholders = ",".join("?" for _ in dependencies)
        dep_rows = conn.execute(
            f"SELECT id, media_state FROM gpu_jobs WHERE id IN ({placeholders})",
            list(dependencies),
        ).fetchall()
        completed = {"published", "approved", "qc_passed", "done"}
        unresolved = [row["id"] for row in dep_rows if (row["media_state"] or "").strip().lower() not in completed]
        if unresolved:
            emit(
                "guardian.illegal_transition",
                "gpu-router",
                {
                    "tenant": MEDIA_TENANT_ID,
                    "job_id": job["id"],
                    "previous_state": current,
                    "requested_state": target,
                    "reason": "dependencies_incomplete",
                    "dependencies": unresolved,
                },
            )
            return False, "dependencies_incomplete"
    evidence_payload = evidence or _parse_json_dict(job["evidence_json"])
    if target in {"rendered", "published"}:
        missing = [field for field in _media_completion_evidence(job_type) if not evidence_payload.get(field)]
        if missing:
            emit(
                "guardian.illegal_transition",
                "gpu-router",
                {
                    "tenant": MEDIA_TENANT_ID,
                    "job_id": job["id"],
                    "previous_state": current,
                    "requested_state": target,
                    "reason": "missing_evidence",
                    "missing": missing,
                },
            )
            return False, "missing_evidence"
    if target in {"publish_ready", "publishing", "published"} and _media_qc_required(job_type):
        if current not in {"qc_passed", "approval_pending", "approved", "publish_ready", "publishing"}:
            emit(
                "guardian.illegal_transition",
                "gpu-router",
                {
                    "tenant": MEDIA_TENANT_ID,
                    "job_id": job["id"],
                    "previous_state": current,
                    "requested_state": target,
                    "reason": "qc_and_approval_required",
                },
            )
            return False, "qc_and_approval_required"
    if target in {"publishing", "published"} and _media_approval_required(job_type):
        approved = current in {"approved", "publish_ready", "publishing"}
        if not approved:
            emit(
                "guardian.illegal_transition",
                "gpu-router",
                {
                    "tenant": MEDIA_TENANT_ID,
                    "job_id": job["id"],
                    "previous_state": current,
                    "requested_state": target,
                    "reason": "approval_required",
                },
            )
            return False, "approval_required"
    if job["vram_required_mb"] and not _gpu_profile_allows_vram(int(job["vram_required_mb"])):
        emit(
            "guardian.illegal_transition",
            "gpu-router",
            {
                "tenant": MEDIA_TENANT_ID,
                "job_id": job["id"],
                "previous_state": current,
                "requested_state": target,
                "reason": "gpu_profile_exceeded",
            },
        )
        return False, "gpu_profile_exceeded"
    envelope = _envelope_for_row(job, fallback_state=(job["status"] or "pending"))
    next_envelope = transition_job_envelope(
        envelope,
        target if target in {"pending", "running", "done", "error", "timeout"} else envelope.get("state") or "pending",
        actor=actor,
        engine=str(job["selected_engine"] or job["job_type"] or "gpu-router"),
        reason=reason,
        evidence_hash=_hash_evidence(evidence_payload),
        metadata_update={"media_state": target},
    )
    conn.execute(
        """
        UPDATE gpu_jobs
        SET media_state=?,
            evidence_json=?,
            publish_eligible=?,
            published_at=CASE WHEN ?='published' THEN ? ELSE published_at END,
            output_hash=COALESCE(?, output_hash),
            provenance_hash=COALESCE(?, provenance_hash),
            job_envelope_json=?
        WHERE id=?
        """,
        (
            target,
            json.dumps(evidence_payload, sort_keys=True, separators=(",", ":")) if evidence_payload else None,
            1 if target in {"publish_ready", "publishing", "published"} else int(job["publish_eligible"] or 0),
            target,
            _now_utc(),
            evidence_payload.get("output_hash") if evidence_payload else None,
            evidence_payload.get("provenance_hash") if evidence_payload else None,
            json.dumps(next_envelope, separators=(",", ":")),
            job["id"],
        ),
    )
    emit(
        "media.transition",
        str(job["selected_engine"] or "gpu-router"),
        {"tenant": MEDIA_TENANT_ID, "from_state": current, "to_state": target, "reason": reason},
    )
    return True, "ok"


def _advance_media_to_ready_queue(conn: sqlite3.Connection, job_id: str) -> None:
    row = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return
    if (row["tenant_id"] or "").strip().lower() != MEDIA_TENANT_ID or not row["media_job_type"]:
        return
    for state in ("script_ready", "prompt_ready", "reference_ready", "queued"):
        latest = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
        if not latest:
            return
        current = (latest["media_state"] or "").strip().lower()
        if current == state:
            continue
        if _media_transition_is_allowed(str(latest["media_job_type"] or ""), current, state):
            _media_transition(conn, latest, state, actor="gpu-router", reason="queue_preparation")


def _recover_abandoned_jobs(conn: sqlite3.Connection) -> list[dict[str, str]]:
    now = datetime.now(timezone.utc)
    rows = conn.execute(
        """
        SELECT id, tenant_id, job_type, client_id, attempt_count, max_attempts, lease_expires_at
             , status, job_envelope_json
        FROM gpu_jobs
        WHERE status = 'running'
          AND lease_expires_at IS NOT NULL
        """
    ).fetchall()
    recovered: list[dict[str, str]] = []
    for row in rows:
        lease_expires = _parse_utc(row["lease_expires_at"])
        if not lease_expires or lease_expires > now:
            continue
        retryable = row["attempt_count"] < row["max_attempts"]
        if retryable:
            next_envelope = transition_job_envelope(
                _envelope_for_row(row),
                "pending",
                metadata_update={"recovery": "lease-expired"},
            )
            conn.execute(
                """
                UPDATE gpu_jobs
                SET status='pending',
                    media_state=CASE WHEN tenant_id=? AND media_job_type IS NOT NULL THEN 'queued' ELSE media_state END,
                    started_at=NULL,
                    available_at=?,
                    lease_expires_at=NULL,
                    claim_token=NULL,
                    worker_name=NULL,
                    error=?,
                    job_envelope_json=?
                WHERE id=? AND status='running'
                """,
                (
                    MEDIA_TENANT_ID,
                    _utc_after(RETRY_BACKOFF_SECONDS),
                    "Recovered abandoned job after worker lease expiry",
                    json.dumps(next_envelope, separators=(",", ":")),
                    row["id"],
                ),
            )
            recovered.append({"job_id": row["id"], "event_type": "job.recovered", "job_type": row["job_type"]})
        else:
            next_envelope = transition_job_envelope(
                _envelope_for_row(row),
                "timeout",
                metadata_update={"recovery": "lease-expired"},
            )
            conn.execute(
                """
                UPDATE gpu_jobs
                SET status='timeout',
                    media_state=CASE WHEN tenant_id=? AND media_job_type IS NOT NULL THEN 'timeout' ELSE media_state END,
                    finished_at=?,
                    lease_expires_at=NULL,
                    claim_token=NULL,
                    worker_name=NULL,
                    error=?,
                    job_envelope_json=?
                WHERE id=? AND status='running'
                """,
                (
                    MEDIA_TENANT_ID,
                    _now_utc(),
                    "Job exceeded retry limit after worker lease expiry",
                    json.dumps(next_envelope, separators=(",", ":")),
                    row["id"],
                ),
            )
            recovered.append({"job_id": row["id"], "event_type": "job.timeout", "job_type": row["job_type"]})
    return recovered


def _log_event(event_type: str, engine: str, job_id: str | None = None, detail: dict | None = None) -> None:
    """Append an event to the gpu_events bus.  Never raises — event loss is acceptable."""
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO gpu_events (id, event_type, engine, job_id, detail_json, ts) VALUES (?,?,?,?,?,?)",
                (str(uuid4()), event_type, engine, job_id, json.dumps(detail or {}), _now_utc()),
            )
            conn.commit()
    except Exception:
        pass

# ──────────────────────────────────────────────
# Queue workers — one GPU worker, one CPU worker
# ──────────────────────────────────────────────

_gpu_worker_lock = threading.Lock()   # serialise GPU (Ollama) calls
_cpu_worker_lock = threading.Lock()   # serialise CPU (voice/embedding) calls
_gpu_wakeup = threading.Event()       # signal GPU worker when a job is enqueued
_cpu_wakeup = threading.Event()       # signal CPU worker when a job is enqueued

def _find_idempotent_job(
    conn: sqlite3.Connection,
    tenant_id: str,
    idempotency_key: str | None,
) -> sqlite3.Row | None:
    if not idempotency_key:
        return None
    return conn.execute(
        """
        SELECT * FROM gpu_jobs
        WHERE tenant_id = ? AND idempotency_key = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (tenant_id, idempotency_key),
    ).fetchone()


def _claim_next_pending_job(conn: sqlite3.Connection, lanes: set[str], worker_name: str) -> sqlite3.Row | None:
    global _gpu_resident_engine
    placeholders = ",".join("?" for _ in lanes)
    now = _now_utc()
    claim_token = str(uuid4())
    conn.execute("BEGIN IMMEDIATE")
    recovered = _recover_abandoned_jobs(conn)
    candidates = conn.execute(
        f"""
        SELECT * FROM gpu_jobs AS j
        WHERE j.status = 'pending'
          AND j.job_type IN ({placeholders})
          AND (j.available_at IS NULL OR j.available_at <= ?)
          AND (
                SELECT COUNT(*)
                FROM gpu_jobs AS active
                WHERE active.tenant_id = j.tenant_id
                  AND active.status = 'running'
              ) < ?
        ORDER BY j.priority ASC, j.created_at ASC
        """,
        [*list(lanes), now, TENANT_CONCURRENCY_LIMIT],
    ).fetchall()
    job = None
    if candidates:
        if "comfyui" in lanes:
            grouped: dict[str, int] = {}
            for row in candidates:
                if (row["tenant_id"] or "").strip().lower() != MEDIA_TENANT_ID:
                    continue
                sig = _media_job_signature(row)
                grouped[sig] = grouped.get(sig, 0) + 1
            scored: list[tuple[int, int, str, sqlite3.Row]] = []
            for row in candidates:
                engine = str(row["selected_engine"] or row["job_type"] or "")
                sig = _media_job_signature(row)
                resident_bonus = 0 if _gpu_resident_engine and engine == _gpu_resident_engine else 1
                batch_size = grouped.get(sig, 1)
                scored.append((resident_bonus, -batch_size, str(row["created_at"] or ""), row))
            scored.sort(key=lambda item: (item[0], item[1], item[2], item[3]["priority"]))
            job = scored[0][3]
        else:
            job = candidates[0]
    if not job:
        conn.commit()
        for event in recovered:
            _log_event(event["event_type"], event["job_type"], event["job_id"])
        return None
    started_at = _now_utc()
    running_envelope = transition_job_envelope(
        _envelope_for_row(job),
        "running",
        metadata_update={"worker_name": worker_name},
    )
    cursor = conn.execute(
        """
        UPDATE gpu_jobs
        SET status='running',
            started_at=?,
            lease_expires_at=?,
            claim_token=?,
            worker_name=?,
            job_envelope_json=?,
            attempt_count=attempt_count + 1,
            available_at=NULL
        WHERE id=? AND status='pending'
        """,
        (
            started_at,
            _utc_after(JOB_LEASE_SECONDS),
            claim_token,
            worker_name,
            json.dumps(running_envelope, separators=(",", ":")),
            job["id"],
        ),
    )
    if (job["tenant_id"] or "").strip().lower() == MEDIA_TENANT_ID and job["media_job_type"]:
        conn.execute(
            "UPDATE gpu_jobs SET media_state='rendering' WHERE id=?",
            (job["id"],),
        )
    conn.commit()
    for event in recovered:
        _log_event(event["event_type"], event["job_type"], event["job_id"])
    if cursor.rowcount != 1:
        return None
    claimed = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job["id"],)).fetchone()
    if claimed:
        _gpu_resident_engine = str(claimed["selected_engine"] or claimed["job_type"] or "")
    return claimed


def _call_ollama(model: str, prompt: str, options: dict | None) -> dict[str, Any]:
    payload = {"model": model, "prompt": prompt, "stream": False}
    if options:
        payload["options"] = options
    data = json.dumps(payload).encode()
    req = request.Request(
        f"{GPU_RUNTIME_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=INFER_TIMEOUT) as resp:
        return json.loads(resp.read().decode() or "{}")


def _call_embedding(model: str, prompt: str, options: dict | None) -> dict[str, Any]:
    """Generate a text embedding vector via Ollama /api/embeddings."""
    payload = {"model": model or "nomic-embed-text", "prompt": prompt}
    data = json.dumps(payload).encode()
    req = request.Request(
        f"{GPU_RUNTIME_URL}/api/embeddings",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=INFER_TIMEOUT) as resp:
        return json.loads(resp.read().decode() or "{}")


_VOICE_LANGS_CACHE: set[str] | None = None


def _voice_langs() -> set[str]:
    """The set of espeak-ng voice names actually installed, queried once and cached. Used to
    validate the requested `lang` so it can't smuggle an espeak flag. Falls back to a small
    known-safe set (the ones this stack ships: Hawaiian + English) if the query fails."""
    global _VOICE_LANGS_CACHE
    if _VOICE_LANGS_CACHE is None:
        langs: set[str] = set()
        try:
            out = subprocess.run(["espeak-ng", "--voices"], capture_output=True,
                                  stdin=subprocess.DEVNULL, timeout=10)
            for line in out.stdout.decode(errors="replace").splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    langs.add(parts[1])          # column 2 = voice name
        except Exception:
            pass
        _VOICE_LANGS_CACHE = langs or {"haw", "en-us", "en-gb", "en"}
    return _VOICE_LANGS_CACHE


def _call_voice(model: str, prompt: str, options: dict | None) -> dict[str, Any]:
    """Synthesise speech from *prompt* using espeak-ng.

    model   = voice/language tag, e.g. "haw" (Hawaiian), "en-us", "en-gb".
    options = {"rate": int, "pitch": int} — espeak-ng -s / -p flags.

    Returns {"audio_b64": <base64 WAV>, "duration_s": float, "engine": "espeak-ng"}.
    Falls back to a dict with "error" key if espeak-ng is not installed.
    """
    if not shutil.which("espeak-ng"):
        return {"error": "espeak-ng not found on PATH; install it in the container image"}

    opts = options or {}
    lang = model or VOICE_DEFAULT_LANG
    rate = int(opts.get("rate", VOICE_DEFAULT_RATE))
    pitch = int(opts.get("pitch", VOICE_DEFAULT_PITCH))
    text = (prompt or "").strip()
    if not text:
        return {"error": "empty text — nothing to synthesise"}

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        # "--" ends espeak-ng option parsing so a prompt/lang beginning with '-' is spoken as TEXT,
        # not interpreted as an espeak flag (e.g. --phonout=<path> or -f <file>/--stdin, which an
        # authenticated caller could otherwise use to write to an arbitrary path or hang the shared
        # CPU worker to the 60s timeout = voice+embedding lane DoS). argv form + no shell already
        # blocks shell RCE; this closes the residual espeak-own-flag argument-injection surface.
        # lang is validated against the installed-voice allowlist so it can't smuggle a flag either.
        if lang not in _voice_langs():
            return {"error": f"unknown voice '{lang}'; install it or pick an available voice"}
        result = subprocess.run(
            ["espeak-ng", "-v", lang, "-s", str(rate), "-p", str(pitch), "-w", tmp_path, "--", text],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
        )
        if result.returncode != 0:
            err = result.stderr.decode(errors="replace").strip()
            return {"error": f"espeak-ng exited {result.returncode}: {err}"}
        with open(tmp_path, "rb") as f:
            wav_bytes = f.read()
        if not wav_bytes:
            return {"error": "espeak-ng produced an empty WAV file"}
        # WAV frame rate is 22050 Hz, 16-bit mono — approximate duration from file size.
        header_bytes = 44
        frame_bytes = max(1, len(wav_bytes) - header_bytes)
        duration_s = round(frame_bytes / (22050 * 2), 2)
        return {
            "audio_b64": base64.b64encode(wav_bytes).decode(),
            "duration_s": duration_s,
            "engine": "espeak-ng",
            "voice": lang,
            "rate": rate,
            "pitch": pitch,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _run_job(job: sqlite3.Row) -> tuple[str, dict | None, str | None]:
    """Dispatch one job to the correct engine.  Returns (status, result, error)."""
    job_type = job["job_type"] or "ollama"
    model = job["model"]
    prompt = job["prompt"]
    options = json.loads(job["options_json"]) if job["options_json"] else None
    try:
        if job_type == "ollama":
            result = _call_ollama(model, prompt, options)
        elif job_type == "embedding":
            result = _call_embedding(model, prompt, options)
        elif job_type == "voice":
            result = _call_voice(model, prompt, options)
            if "error" in result:
                return "error", None, result["error"]
        else:
            return "error", None, f"unknown job_type '{job_type}'"
        return "done", result, None
    except Exception as exc:
        return "error", None, str(exc)


def _persist_job_outcome(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    status: str,
    result: dict | None,
    err: str | None,
) -> str:
    attempt_count = job["attempt_count"]
    max_attempts = job["max_attempts"] or DEFAULT_MAX_ATTEMPTS
    should_retry = status == "error" and attempt_count < max_attempts
    is_media = (job["tenant_id"] or "").strip().lower() == MEDIA_TENANT_ID and bool(job["media_job_type"])
    base_envelope = _envelope_for_row(job, fallback_state="running")
    if should_retry:
        if is_media:
            _media_transition(conn, job, "queued", actor="gpu-router", reason="retry_backoff")
        next_envelope = transition_job_envelope(
            base_envelope,
            "pending",
            metadata_update={"retry_backoff_seconds": RETRY_BACKOFF_SECONDS},
        )
        cursor = conn.execute(
            """
            UPDATE gpu_jobs
            SET status='pending',
                result_json=NULL,
                error=?,
                finished_at=NULL,
                started_at=NULL,
                available_at=?,
                lease_expires_at=NULL,
                claim_token=NULL,
                worker_name=NULL,
                job_envelope_json=?
            WHERE id=? AND status='running' AND claim_token=?
            """,
            (
                err,
                _utc_after(RETRY_BACKOFF_SECONDS),
                json.dumps(next_envelope, separators=(",", ":")),
                job["id"],
                job["claim_token"],
            ),
        )
        return "retry" if cursor.rowcount == 1 else "stale"
    if is_media and status == "done":
        evidence = _parse_json_dict(job["evidence_json"])
        payload = result or {}
        if payload.get("response"):
            evidence.setdefault("artifact_uri", f"gpu://{job['id']}")
        evidence.setdefault("output_hash", hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest())
        evidence.setdefault("provenance_hash", hashlib.sha256(f"{job['id']}:{job['selected_engine'] or job['job_type']}".encode("utf-8")).hexdigest())
        _media_transition(conn, job, "rendered", actor="gpu-router", reason="render_complete", evidence=evidence)
        latest = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job["id"],)).fetchone()
        if latest:
            job = latest
        _media_transition(conn, job, "qc_pending", actor="gpu-router", reason="queue_qc", evidence=evidence)
    if is_media and status in {"error", "timeout"}:
        _media_transition(conn, job, "failed" if status == "error" else "timeout", actor="gpu-router", reason="worker_failure")
        latest = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job["id"],)).fetchone()
        if latest:
            job = latest
    next_envelope = transition_job_envelope(
        base_envelope,
        status,
        metadata_update={"error": err or ""},
    )
    cursor = conn.execute(
        """
        UPDATE gpu_jobs
        SET status=?,
            result_json=?,
            error=?,
            finished_at=?,
            lease_expires_at=NULL,
            claim_token=NULL,
            worker_name=NULL,
            job_envelope_json=?
        WHERE id=? AND status='running' AND claim_token=?
        """,
        (
            status,
            json.dumps(result) if result else None,
            err,
            _now_utc(),
            json.dumps(next_envelope, separators=(",", ":")),
            job["id"],
            job["claim_token"],
        ),
    )
    return status if cursor.rowcount == 1 else "stale"


def _build_infer_response(row: sqlite3.Row, job_type: str, model: str) -> dict[str, Any]:
    result = json.loads(row["result_json"] or "{}")
    resp: dict[str, Any] = {
        "job_id": row["id"],
        "tenant_id": row["tenant_id"],
        "job_type": job_type,
        "client_id": row["client_id"],
        "model": model,
        "done": True,
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }
    if row["idempotency_key"]:
        resp["idempotency_key"] = row["idempotency_key"]
    if row["media_state"]:
        resp["media_state"] = row["media_state"]
        resp["media_job_type"] = row["media_job_type"]
        resp["capability"] = row["capability"]
        resp["selected_engine"] = row["selected_engine"]
        if row["output_hash"]:
            resp["output_hash"] = row["output_hash"]
        if row["provenance_hash"]:
            resp["provenance_hash"] = row["provenance_hash"]
    if job_type == "voice":
        resp["audio_b64"] = result.get("audio_b64", "")
        resp["duration_s"] = result.get("duration_s")
        resp["engine"] = result.get("engine", "espeak-ng")
    elif job_type == "embedding":
        resp["embedding"] = result.get("embedding", [])
    else:
        resp["response"] = result.get("response", "")
    return resp


def _worker_loop(worker_name: str, lanes: set[str], lock: threading.Lock, wakeup: threading.Event) -> None:
    """Generic worker loop for a set of engine lanes.

    Hardened (audit-quad-os 2026-07-10): the whole inner body is wrapped in try/except so a
    transient sqlite3.OperationalError('database is locked') — now more likely because this branch
    runs TWO concurrent SQLite writers (the GPU and CPU workers) plus the infer poller — can no
    longer propagate out and permanently kill the worker thread (there is no supervisor to restart
    it), which would silently stall a whole engine lane. On error we log and continue; _db()'s
    connections also carry PRAGMA busy_timeout to absorb the contention in the first place.
    """
    while True:
        wakeup.wait(timeout=5)
        wakeup.clear()
        try:
            with lock:
                while True:
                    with _db() as conn:
                        job = _claim_next_pending_job(conn, lanes, worker_name)
                        if not job:
                            break

                    job_id = job["id"]
                    engine = job["job_type"] or "ollama"
                    _log_event("job.start", engine, job_id, {"client_id": job["client_id"]})

                    status, result, err = _run_job(job)

                    with _db() as conn:
                        outcome = _persist_job_outcome(conn, job, status, result, err)
                        conn.commit()

                    _log_event(
                        f"job.{outcome}", engine, job_id,
                        {"client_id": job["client_id"], "error": err} if err else {"client_id": job["client_id"]},
                    )
                    if outcome == "retry":
                        wakeup.set()
        except Exception as exc:
            # Never let a worker die: log via the event bus (best-effort) and loop again.
            try:
                _log_event("worker.error", worker_name, None, {"error": str(exc)[:300]})
            except Exception:
                pass


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

def _error(status_code: int, code: str, message: str, details: dict | None = None):
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )

def _require_auth(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        _error(401, "unauthorized", "Missing or invalid bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = json.dumps({"token": token}).encode()
    req = request.Request(
        AUTH_INTROSPECTION_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Service-Token": INTERNAL_SERVICE_TOKEN,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode() or "{}")
    except error.HTTPError as exc:
        if exc.code == 403:
            _error(503, "dependency_denied", "Auth service rejected service trust")
        _error(503, "dependency_unavailable", "Auth service unavailable", {"status": exc.code})
    except Exception:
        _error(503, "dependency_unavailable", "Auth service unavailable")
    if not data.get("active"):
        _error(401, "unauthorized", "Session is not active")
    return data.get("user") or {}


def _check_dependency_ready(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode() or "{}")
            return data.get("status") in {"ready", "healthy"}
    except Exception:
        return False


def _ollama_ready() -> bool:
    try:
        with request.urlopen(f"{GPU_RUNTIME_URL}/api/tags", timeout=REQUEST_TIMEOUT) as resp:
            return resp.status == 200
    except Exception:
        return False


# ──────────────────────────────────────────────
# Request / response models
# ──────────────────────────────────────────────

class InferRequest(BaseModel):
    client_id: str           # e.g. "govos-core", "studio", "workboard"
    tenant_id: str | None = None
    model: str               # Ollama model name e.g. "llama3"; or voice tag e.g. "haw"
    prompt: str              # LLM prompt or text to synthesise (voice lane)
    options: dict | None = None  # Ollama options (temperature, …) or voice options (rate, pitch)
    job_type: str = "ollama"     # "ollama" | "voice" | "embedding" | "comfyui"
    media_job_type: str | None = None
    capability: str | None = None
    workflow_id: str | None = None
    workflow_profile: str | None = None
    resolution: str | None = None
    frame_count: int | None = None
    adapter_set: list[str] | None = None
    lora_set: list[str] | None = None
    model_residency: bool | None = None
    vram_required_mb: int | None = None
    evidence: dict | None = None
    dependencies: list[str] | None = None


class MediaTransitionRequest(BaseModel):
    to_state: str
    actor: str | None = None
    reason: str | None = None
    evidence: dict | None = None


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get(f"{API_PREFIX}/live")
def live():
    return with_service_metadata(
        {"status": "alive", "timestamp": _now_utc()},
        SERVICE_NAME,
        VERSION,
    )


@app.get(f"{API_PREFIX}/ready")
def ready(response: Response):
    db_ok = True
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        db_ok = False

    auth_ok = _check_dependency_ready(AUTH_READY_URL)
    runtime_ok = _ollama_ready()
    voice_ok = bool(shutil.which("espeak-ng"))
    # voice lane is best-effort — router is ready as long as DB + auth + GPU runtime are up.
    is_ready = db_ok and auth_ok and runtime_ok

    response.status_code = 200 if is_ready else 503
    return with_service_metadata(
        {
            "status": "ready" if is_ready else "not-ready",
            "dependencies": {
                "database": db_ok,
                "auth": auth_ok,
                "gpu_runtime": runtime_ok,
                "voice_engine": voice_ok,
            },
        },
        SERVICE_NAME,
        VERSION,
    )


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM gpu_jobs").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM gpu_jobs WHERE status='pending'").fetchone()[0]
        running = conn.execute("SELECT COUNT(*) FROM gpu_jobs WHERE status='running'").fetchone()[0]
        # Per-lane pending/running counts.
        lane_rows = conn.execute(
            """
            SELECT job_type,
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running
            FROM gpu_jobs
            WHERE status IN ('pending','running')
            GROUP BY job_type
            """
        ).fetchall()
    lanes = {r["job_type"]: {"pending": r["pending"], "running": r["running"]} for r in lane_rows}
    return with_service_metadata(
        {
            "status": "healthy",
            "jobs": {"total": total, "pending": pending, "running": running},
            "lanes": lanes,
            "engines": {
                "gpu": list(GPU_LANES),
                "cpu": list(CPU_LANES),
            },
            "voice_engine": "espeak-ng" if shutil.which("espeak-ng") else "unavailable",
            "priorities": CLIENT_PRIORITIES,
            "tenant_concurrency_limit": TENANT_CONCURRENCY_LIMIT,
        },
        SERVICE_NAME,
        VERSION,
    )


@app.post(f"{API_PREFIX}/gpu/infer")
def infer(
    payload: InferRequest,
    authorization: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
):
    """Enqueue a job and block until it completes (or times out).

    job_type controls which engine lane handles the job:
      "ollama"    — LLM inference via Ollama (GPU).
      "voice"     — Text-to-speech via espeak-ng (CPU).  model = voice lang, e.g. "haw".
      "embedding" — Text embeddings via Ollama (CPU-light).
    """
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"gpu:infer"},
    )

    job_type = payload.job_type if payload.job_type in ALL_JOB_TYPES else "ollama"
    priority = CLIENT_PRIORITIES.get(payload.client_id, DEFAULT_PRIORITY)
    requested_tenant_id = payload.tenant_id or x_tenant_id
    tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=requested_tenant_id,
        owner_override_allowed=True,
    ) or payload.client_id
    if payload.tenant_id and x_tenant_id and payload.tenant_id.strip() != x_tenant_id.strip():
        _error(400, "tenant_mismatch", "Tenant header does not match request body")
    idempotency_key = _normalise_idempotency_key(x_idempotency_key)
    media_job_type = (payload.media_job_type or "").strip()
    capability = (payload.capability or "").strip()
    workflow_id = (payload.workflow_id or "").strip() or None
    workflow_profile = (payload.workflow_profile or "").strip() or None
    resolution = (payload.resolution or "").strip() or None
    frame_count = payload.frame_count
    adapter_set = payload.adapter_set or []
    lora_set = payload.lora_set or []
    model_residency = bool(payload.model_residency) if payload.model_residency is not None else False
    evidence = payload.evidence or {}
    dependencies = payload.dependencies or []
    vram_required_mb = payload.vram_required_mb
    selected_engine = payload.model
    if tenant_id.strip().lower() == MEDIA_TENANT_ID:
        if not media_job_type or media_job_type not in _media_job_profiles():
            _error(422, "unknown_media_job_type", "Media job type is required and must be registered")
        if not capability:
            profile = _media_job_profiles().get(media_job_type) or {}
            capability = str(profile.get("preferred_capability") or "").strip()
        if not capability:
            _error(422, "missing_capability", "Media capability is required")
        selected_engine = _select_engine_for_capability(capability) or selected_engine
        if not selected_engine:
            _error(422, "capability_unroutable", "Capability route has no engine")
        workflow = _workflow_by_id(workflow_id) if workflow_id else None
        if workflow and not workflow_profile:
            workflow_profile = workflow.get("workflow_id")
        required_inputs = _media_required_inputs(media_job_type)
        missing_inputs = []
        input_map = {
            "prompt": payload.prompt,
            "workflow_id": workflow_id,
            "capability": capability,
            "reference_image": (payload.options or {}).get("reference_image"),
            "source_artifact": (payload.options or {}).get("source_artifact"),
            "scene_id": (payload.options or {}).get("scene_id"),
            "shot_id": (payload.options or {}).get("shot_id"),
            "script": (payload.options or {}).get("script"),
            "voice_profile": (payload.options or {}).get("voice_profile"),
            "qc_profile": (payload.options or {}).get("qc_profile"),
            "approved_assets": (payload.options or {}).get("approved_assets"),
            "manifest": (payload.options or {}).get("manifest"),
            "publish_manifest": (payload.options or {}).get("publish_manifest"),
            "lora_set": lora_set,
            "adapter_set": adapter_set,
        }
        for field in required_inputs:
            if not input_map.get(field):
                missing_inputs.append(field)
        if missing_inputs:
            _error(422, "missing_required_inputs", "Media job missing required inputs", {"missing": missing_inputs})
        if not _gpu_profile_allows_vram(vram_required_mb):
            _error(422, "gpu_profile_exceeded", "Workflow exceeds safe VRAM profile", {"safe_limit_mb": _load_gpu_profile().get("vram_safe_limit_mb")})
        if not _media_transition_is_allowed(media_job_type, "", "planned"):
            _error(422, "invalid_media_initial_state", "Media profile has no legal initial state")
        job_type = _job_type_for_media_capability(capability)
    options_payload = dict(payload.options or {})
    if capability:
        options_payload["capability"] = capability
    if workflow_id:
        options_payload["workflow_id"] = workflow_id
    if selected_engine and tenant_id.strip().lower() == MEDIA_TENANT_ID:
        options_payload["selected_engine"] = selected_engine
    options_json = _options_json(options_payload)
    pending_envelope = build_job_envelope(
        domain="gpu-router",
        service=SERVICE_NAME,
        action="gpu.infer",
        state="pending",
        payload={"tenant_id": tenant_id, "client_id": payload.client_id, "job_type": job_type, "media_job_type": media_job_type, "capability": capability},
        lane=job_type,
    )
    job_id: str | None = None

    with _db() as conn:
        existing = _find_idempotent_job(conn, tenant_id, idempotency_key)
        if existing:
            same_payload = (
                existing["client_id"] == payload.client_id
                and existing["job_type"] == job_type
                and existing["model"] == payload.model
                and existing["prompt"] == payload.prompt
                and (existing["options_json"] or None) == options_json
            )
            if not same_payload:
                _error(409, "idempotency_conflict", "Idempotency key is already bound to a different request", {"job_id": existing["id"]})
            job_id = existing["id"]
        else:
            job_id = str(uuid4())
            try:
                conn.execute(
                    """
                    INSERT INTO gpu_jobs
                        (id, tenant_id, client_id, priority, job_type, model, prompt, options_json,
                         idempotency_key, status, created_at, available_at, max_attempts, created_by, job_envelope_json,
                         capability, media_job_type, media_state, workflow_id, workflow_profile, resolution, frame_count,
                         adapter_set, lora_set, model_residency, vram_required_mb, approval_required, qc_required,
                         publish_eligible, selected_engine, evidence_json, dependencies_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        tenant_id,
                        payload.client_id,
                        priority,
                        job_type,
                        payload.model,
                        payload.prompt,
                        options_json,
                        idempotency_key,
                        "pending",
                        _now_utc(),
                        _now_utc(),
                        DEFAULT_MAX_ATTEMPTS,
                        claims.get("sub", "unknown"),
                        json.dumps({**pending_envelope, "entity_id": job_id, "correlation_id": job_id}, separators=(",", ":")),
                        capability or None,
                        media_job_type or None,
                        "planned" if tenant_id.strip().lower() == MEDIA_TENANT_ID and media_job_type else None,
                        workflow_id,
                        workflow_profile,
                        resolution,
                        frame_count,
                        json.dumps(adapter_set, sort_keys=True) if adapter_set else None,
                        json.dumps(lora_set, sort_keys=True) if lora_set else None,
                        1 if model_residency else 0,
                        vram_required_mb,
                        1 if _media_approval_required(media_job_type) else 0,
                        1 if _media_qc_required(media_job_type) else 0,
                        0,
                        selected_engine,
                        json.dumps(evidence, sort_keys=True) if evidence else None,
                        json.dumps(dependencies, sort_keys=True) if dependencies else None,
                    ),
                )
            except sqlite3.IntegrityError:
                existing = _find_idempotent_job(conn, tenant_id, idempotency_key)
                if not existing:
                    raise
                job_id = existing["id"]
        if tenant_id.strip().lower() == MEDIA_TENANT_ID and media_job_type:
            _advance_media_to_ready_queue(conn, job_id)
        conn.commit()

    row = None
    with _db() as conn:
        row = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
    if row and row["status"] == "pending" and row["attempt_count"] == 0:
        _log_event("job.queued", job_type, job_id, {"client_id": payload.client_id, "tenant_id": tenant_id})

    # Wake the right worker.
    if job_type in CPU_LANES:
        _cpu_wakeup.set()
    else:
        _gpu_wakeup.set()

    # Poll until done or timeout.
    deadline = time.monotonic() + INFER_TIMEOUT
    while time.monotonic() < deadline:
        with _db() as conn:
            row = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
        if row and row["status"] == "done":
            return _build_infer_response(row, job_type, payload.model)
        if row and row["status"] == "error":
            engine_label = "CPU" if job_type in CPU_LANES else "GPU"
            _error(502, f"{job_type}_error", f"{engine_label} error: {row['error']}", {"job_id": job_id})
        if row and row["status"] == "timeout":
            _error(504, "job_timeout", row["error"] or "Job exceeded the allowed runtime", {"job_id": job_id})
        time.sleep(0.5)

    _log_event("request.timeout", job_type, job_id, {"client_id": payload.client_id, "tenant_id": tenant_id})
    _error(504, "infer_timeout", "Job did not complete within the allowed wait window", {"job_id": job_id})


@app.get(f"{API_PREFIX}/gpu/queue")
def queue_status(authorization: str | None = Header(default=None), tenant_id: str | None = None):
    """List pending and running jobs (owner/internal use)."""
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"gpu:read"},
    )
    scoped_tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=tenant_id,
        owner_override_allowed=True,
    )
    if claims.get("role") == "Owner" and not scoped_tenant_id:
        audit_auth_event(SERVICE_NAME, "owner_override", {"resource": "gpu.queue", "scope": "all_tenants"})
    with _db() as conn:
        if scoped_tenant_id:
            rows = conn.execute(
                """
                SELECT id, tenant_id, client_id, priority, job_type, model, status, created_at, started_at, attempt_count
                FROM gpu_jobs
                WHERE status IN ('pending', 'running') AND tenant_id = ?
                ORDER BY priority ASC, created_at ASC
                """,
                (scoped_tenant_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, tenant_id, client_id, priority, job_type, model, status, created_at, started_at, attempt_count
                FROM gpu_jobs
                WHERE status IN ('pending', 'running')
                ORDER BY priority ASC, created_at ASC
                """
            ).fetchall()
    return {"queue": [dict(r) for r in rows]}


@app.get(f"{API_PREFIX}/gpu/usage")
def usage(authorization: str | None = Header(default=None), tenant_id: str | None = None):
    """Per-client job counts."""
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"gpu:read"},
    )
    scoped_tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=tenant_id,
        owner_override_allowed=True,
    )
    if claims.get("role") == "Owner" and not scoped_tenant_id:
        audit_auth_event(SERVICE_NAME, "owner_override", {"resource": "gpu.usage", "scope": "all_tenants"})
    with _db() as conn:
        params: list[Any] = []
        tenant_clause = ""
        if scoped_tenant_id:
            tenant_clause = "WHERE tenant_id = ?"
            params.append(scoped_tenant_id)
        rows = conn.execute(
            f"""
            SELECT tenant_id,
                   client_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status='done'    THEN 1 ELSE 0 END) AS done,
                   SUM(CASE WHEN status='error'   THEN 1 ELSE 0 END) AS errors,
                   SUM(CASE WHEN status='timeout' THEN 1 ELSE 0 END) AS timeouts,
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running
            FROM gpu_jobs
            {tenant_clause}
            GROUP BY tenant_id, client_id
            ORDER BY tenant_id, client_id
            """,
            params,
        ).fetchall()
    return {"usage": [dict(r) for r in rows]}


@app.get(f"{API_PREFIX}/gpu/events")
def events(authorization: str | None = Header(default=None), limit: int = 50, tenant_id: str | None = None):
    """Recent events from the engine event bus (job start / done / error)."""
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"gpu:read"},
    )
    scoped_tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=tenant_id,
        owner_override_allowed=True,
    )
    if claims.get("role") == "Owner" and not scoped_tenant_id:
        audit_auth_event(SERVICE_NAME, "owner_override", {"resource": "gpu.events", "scope": "all_tenants"})
    limit = min(max(1, limit), 500)
    with _db() as conn:
        if scoped_tenant_id:
            rows = conn.execute(
                """
                SELECT e.id, e.event_type, e.engine, e.job_id, e.detail_json, e.ts
                FROM gpu_events AS e
                JOIN gpu_jobs AS j ON j.id = e.job_id
                WHERE j.tenant_id = ?
                ORDER BY e.ts DESC
                LIMIT ?
                """,
                (scoped_tenant_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, event_type, engine, job_id, detail_json, ts FROM gpu_events ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return {
        "events": [
            {**dict(r), "detail": json.loads(r["detail_json"] or "{}")}
            for r in rows
        ]
    }


@app.post(f"{API_PREFIX}/gpu/media/jobs/{{job_id}}/transition")
def media_transition(
    job_id: str,
    payload: MediaTransitionRequest,
    authorization: str | None = Header(default=None),
):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"gpu:infer"},
    )
    actor = payload.actor or claims.get("sub") or "owner"
    reason = payload.reason or "manual_transition"
    with _db() as conn:
        row = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            _error(404, "job_not_found", "Job not found")
        ok, code = _media_transition(conn, row, payload.to_state, actor=actor, reason=reason, evidence=payload.evidence or {})
        conn.commit()
        if not ok:
            _error(409, "illegal_transition", "Media transition rejected", {"reason": code})
        fresh = conn.execute("SELECT id, tenant_id, media_job_type, media_state, publish_eligible, output_hash, provenance_hash FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
    return dict(fresh)


@app.get(f"{API_PREFIX}/gpu/media/workflows")
def media_workflows(authorization: str | None = Header(default=None)):
    require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"gpu:read"},
    )
    return {"tenant": MEDIA_TENANT_ID, "workflows": _load_media_workflow_inventory()}


@app.get(f"{API_PREFIX}/gpu/media/overview")
def media_overview(authorization: str | None = Header(default=None)):
    require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"gpu:read"},
    )
    with _db() as conn:
        active = conn.execute(
            """
            SELECT id, media_job_type, media_state, selected_engine, workflow_profile, resolution, frame_count, created_at
            FROM gpu_jobs
            WHERE tenant_id=? AND status IN ('pending','running')
            ORDER BY created_at ASC
            LIMIT 50
            """,
            (MEDIA_TENANT_ID,),
        ).fetchall()
        by_state_rows = conn.execute(
            "SELECT media_state, COUNT(*) AS count FROM gpu_jobs WHERE tenant_id=? GROUP BY media_state",
            (MEDIA_TENANT_ID,),
        ).fetchall()
        current = conn.execute(
            """
            SELECT id, selected_engine, model, media_state
            FROM gpu_jobs
            WHERE tenant_id=? AND status='running'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (MEDIA_TENANT_ID,),
        ).fetchone()
        events_rows = conn.execute(
            """
            SELECT e.event_type, e.ts, e.job_id, e.detail_json
            FROM gpu_events e
            JOIN gpu_jobs j ON j.id=e.job_id
            WHERE j.tenant_id=? AND (e.event_type='media.transition' OR e.event_type='guardian.illegal_transition')
            ORDER BY e.ts DESC
            LIMIT 30
            """,
            (MEDIA_TENANT_ID,),
        ).fetchall()
        next_batch_rows = conn.execute(
            """
            SELECT selected_engine, workflow_profile, resolution, frame_count, adapter_set, lora_set, model_residency, COUNT(*) AS count, MIN(created_at) AS oldest
            FROM gpu_jobs
            WHERE tenant_id=? AND status='pending'
            GROUP BY selected_engine, workflow_profile, resolution, frame_count, adapter_set, lora_set, model_residency
            ORDER BY count DESC, oldest ASC
            LIMIT 1
            """,
            (MEDIA_TENANT_ID,),
        ).fetchall()
    profile = _load_gpu_profile()
    vram_used = None
    vram_total = profile.get("vram_total_mb")
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            text=True,
            timeout=3,
        ).strip()
        used_raw, total_raw = [int(x.strip()) for x in out.split(",")[:2]]
        vram_used = used_raw
        vram_total = total_raw
    except Exception:
        pass
    states = {str(row["media_state"] or "unknown"): int(row["count"] or 0) for row in by_state_rows}
    active_list = [dict(row) for row in active]
    next_batch = dict(next_batch_rows[0]) if next_batch_rows else {}
    qc_queue = states.get("qc_pending", 0)
    approval_queue = states.get("approval_pending", 0)
    publish_queue = states.get("publish_ready", 0) + states.get("publishing", 0)
    return {
        "tenant": MEDIA_TENANT_ID,
        "active_productions": len(active_list),
        "scenes_by_state": states,
        "shots_queued": states.get("queued", 0),
        "current_render": dict(current) if current else None,
        "loaded_model": (_gpu_resident_engine or (current["selected_engine"] if current else None)),
        "vram_usage": {"used_mb": vram_used, "total_mb": vram_total, "safe_limit_mb": profile.get("vram_safe_limit_mb")},
        "next_compatible_batch": next_batch,
        "qc_queue": qc_queue,
        "approval_queue": approval_queue,
        "publish_queue": publish_queue,
        "recent_media_transitions": [
            {**dict(row), "detail": _parse_json_dict(row["detail_json"])}
            for row in events_rows
        ],
        "active_jobs": active_list,
    }


# ──────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────

init_db()
with _db() as _startup_conn:
    _startup_recovered = _recover_abandoned_jobs(_startup_conn)
    _startup_conn.commit()
for _event in _startup_recovered:
    _log_event(_event["event_type"], _event["job_type"], _event["job_id"])

# GPU worker: handles ollama + comfyui lanes.
_gpu_thread = threading.Thread(
    target=_worker_loop,
    args=("gpu-worker", GPU_LANES, _gpu_worker_lock, _gpu_wakeup),
    daemon=True,
)
_gpu_thread.start()

# CPU worker: handles voice + embedding lanes concurrently with GPU work.
_cpu_thread = threading.Thread(
    target=_worker_loop,
    args=("cpu-worker", CPU_LANES, _cpu_worker_lock, _cpu_wakeup),
    daemon=True,
)
_cpu_thread.start()
