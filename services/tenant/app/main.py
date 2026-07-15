import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib import request
from uuid import uuid4

from fastapi import FastAPI, Header, Response
from pydantic import BaseModel

from services.authz import auth_error, audit_auth_event, enforce_resource_tenant, enforce_tenant_scope, require_claims
from services.service_metadata import with_service_metadata
from services.v2_workboard import emit_workboard_job
from services.event_bus import publish_event as _publish_event

API_PREFIX = "/api/v2"
SERVICE_NAME = "tenant"
VERSION = os.environ.get("VERSION", "2.0.0")
DB_PATH = os.environ.get("TENANT_DB_PATH", "/tmp/govos_v2_tenant.db")
AUTH_INTROSPECTION_URL = os.environ.get("AUTH_INTROSPECTION_URL", "http://localhost:8101/api/v2/auth/introspect")
AUTH_READY_URL = os.environ.get("AUTH_READY_URL", "http://localhost:8101/api/v2/ready")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
REQUEST_TIMEOUT = float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "3"))

app = FastAPI(title="govOS v2 Tenant Service", version=VERSION)


CASE_STATUSES = {"open", "in_progress", "pending_review", "closed", "archived"}


class CaseCreateRequest(BaseModel):
    tenant_id: str
    title: str
    status: str = "open"
    notes: str | None = None


class CaseStatusUpdateRequest(BaseModel):
    status: str
    notes: str | None = None


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    # sqlite3.Connection.__exit__ only commits/rolls back -- it does not close the connection.
    # Same leak found+fixed across services/{ai,auth}/app/main.py 2026-07-09; applied here for
    # consistency. Transactional behavior at call sites is unchanged.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _check_dependency_ready(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode() or "{}")
            return data.get("status") in {"ready", "healthy"}
    except Exception:
        return False





def _to_case(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "title": row["title"],
        "status": row["status"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "created_by": row["created_by"],
    }


init_db()


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
    is_ready = db_ok and auth_ok
    response.status_code = 200 if is_ready else 503
    return with_service_metadata(
        {
            "status": "ready" if is_ready else "not-ready",
            "dependencies": {"database": db_ok, "auth": auth_ok},
        },
        SERVICE_NAME,
        VERSION,
    )


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    return with_service_metadata(
        {"status": "healthy", "case_count": count},
        SERVICE_NAME,
        VERSION,
    )


@app.get(f"{API_PREFIX}/cases")
def list_cases(authorization: str | None = Header(default=None), tenant_id: str | None = None):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"tenant:read"},
    )
    scope_tenant = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=tenant_id,
        owner_override_allowed=True,
    )
    if claims.get("role") == "Owner" and not scope_tenant:
        audit_auth_event(SERVICE_NAME, "owner_override", {"resource": "cases.list", "scope": "all_tenants"})
    with _db() as conn:
        if scope_tenant:
            rows = conn.execute("SELECT * FROM cases WHERE tenant_id = ? ORDER BY created_at DESC", (scope_tenant,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
    return {"cases": [_to_case(row) for row in rows]}


@app.post(f"{API_PREFIX}/cases", status_code=201)
def create_case(payload: CaseCreateRequest, authorization: str | None = Header(default=None)):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"tenant:write"},
    )
    tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=payload.tenant_id,
        owner_override_allowed=True,
    )

    case_id = str(uuid4())
    record = {
        "id": case_id,
        "tenant_id": tenant_id,
        "title": payload.title,
        "status": payload.status,
        "notes": payload.notes,
        "created_at": _now_utc(),
        "created_by": claims.get("sub", "unknown"),
    }

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO cases (id, tenant_id, title, status, notes, created_at, created_by)
            VALUES (:id, :tenant_id, :title, :status, :notes, :created_at, :created_by)
            """,
            record,
        )
        conn.commit()

    try:
        emit_workboard_job(
            source="govos-v2-tenant",
            action="case.created",
            event=f"V2 CASE QUEUED: {record['id']}",
            lane="engineering",  # case management is internal plumbing; self-heals
            payload={
                "case_id": record["id"],
                "tenant_id": record["tenant_id"],
                "created_by": record["created_by"],
            },
        )
    except Exception:
        pass

    _publish_event(
        event_type="case.created",
        producer="tenant",
        entity_id=case_id,
        payload={
            "tenant_id": tenant_id,
            "title": payload.title,
            "status": payload.status,
            "created_by": record["created_by"],
        },
    )

    return record


@app.get(f"{API_PREFIX}/cases/{{case_id}}")
def get_case(case_id: str, authorization: str | None = Header(default=None)):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"tenant:read"},
    )
    with _db() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if not row:
        auth_error(404, "resource_not_found", "Case was not found", {"case_id": case_id})
    enforce_resource_tenant(service_name=SERVICE_NAME, claims=claims, resource_tenant_id=row["tenant_id"])
    return _to_case(row)


@app.patch(f"{API_PREFIX}/cases/{{case_id}}/status")
def update_case_status(
    case_id: str,
    payload: CaseStatusUpdateRequest,
    authorization: str | None = Header(default=None),
):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"tenant:write"},
    )
    new_status = payload.status if payload.status in CASE_STATUSES else "open"
    with _db() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            auth_error(404, "resource_not_found", "Case was not found", {"case_id": case_id})
        enforce_resource_tenant(
            service_name=SERVICE_NAME, claims=claims, resource_tenant_id=row["tenant_id"]
        )
        previous_status = row["status"]
        if payload.notes is not None:
            conn.execute(
                "UPDATE cases SET status = ?, notes = ? WHERE id = ?",
                (new_status, payload.notes, case_id),
            )
        else:
            conn.execute(
                "UPDATE cases SET status = ? WHERE id = ?",
                (new_status, case_id),
            )
        conn.commit()
        updated_row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()

    _publish_event(
        event_type="case.status_changed",
        producer="tenant",
        entity_id=case_id,
        payload={
            "tenant_id": row["tenant_id"],
            "previous_status": previous_status,
            "new_status": new_status,
            "changed_by": claims.get("sub", "unknown"),
        },
    )

    return _to_case(updated_row)
