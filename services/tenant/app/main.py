import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib import error, parse, request
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from services.v2_workboard import emit_workboard_job

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "2.0.0")
DB_PATH = os.environ.get("TENANT_DB_PATH", "/tmp/govos_v2_tenant.db")
AUTH_INTROSPECTION_URL = os.environ.get("AUTH_INTROSPECTION_URL", "http://localhost:8101/api/v2/auth/introspect")
AUTH_READY_URL = os.environ.get("AUTH_READY_URL", "http://localhost:8101/api/v2/ready")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
REQUEST_TIMEOUT = float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "3"))

app = FastAPI(title="govOS v2 Tenant Service", version=VERSION)


class CaseCreateRequest(BaseModel):
    tenant_id: str
    title: str
    status: str = "open"
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


def _error(status_code: int, code: str, message: str, details: dict | None = None):
    raise HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message, "details": details or {}}})


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
    return {"status": "alive", "service": "tenant", "timestamp": _now_utc()}


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
    return {
        "status": "ready" if is_ready else "not-ready",
        "service": "tenant",
        "dependencies": {"database": db_ok, "auth": auth_ok},
    }


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    return {"status": "healthy", "service": "tenant", "version": VERSION, "case_count": count}


@app.get(f"{API_PREFIX}/cases")
def list_cases(authorization: str | None = Header(default=None)):
    _require_auth(authorization)
    with _db() as conn:
        rows = conn.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
    return {"cases": [_to_case(row) for row in rows]}


@app.post(f"{API_PREFIX}/cases", status_code=201)
def create_case(payload: CaseCreateRequest, authorization: str | None = Header(default=None)):
    user = _require_auth(authorization)

    case_id = str(uuid4())
    record = {
        "id": case_id,
        "tenant_id": payload.tenant_id,
        "title": payload.title,
        "status": payload.status,
        "notes": payload.notes,
        "created_at": _now_utc(),
        "created_by": user.get("id", "unknown"),
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

    return record


@app.get(f"{API_PREFIX}/cases/{{case_id}}")
def get_case(case_id: str, authorization: str | None = Header(default=None)):
    _require_auth(authorization)
    with _db() as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if not row:
        _error(404, "resource_not_found", "Case was not found", {"case_id": case_id})
    return _to_case(row)
