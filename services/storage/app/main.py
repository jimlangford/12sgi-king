import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib import request
from uuid import uuid4

from fastapi import FastAPI, Header, Response
from pydantic import BaseModel, Field

from services.authz import auth_error, enforce_resource_tenant, enforce_tenant_scope, require_claims
from services.service_metadata import with_service_metadata
from services.v2_workboard import emit_workboard_job

API_PREFIX = "/api/v2"
SERVICE_NAME = "storage"
VERSION = os.environ.get("VERSION", "2.0.0")
DOWNLOAD_BASE_URL = os.environ.get("STORAGE_DOWNLOAD_BASE_URL", "https://storage.local/download")
DB_PATH = os.environ.get("STORAGE_DB_PATH", "/tmp/govos_v2_storage.db")
AUTH_INTROSPECTION_URL = os.environ.get("AUTH_INTROSPECTION_URL", "http://localhost:8101/api/v2/auth/introspect")
AUTH_READY_URL = os.environ.get("AUTH_READY_URL", "http://localhost:8101/api/v2/ready")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
REQUEST_TIMEOUT = float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "3"))

app = FastAPI(title="govOS v2 Storage Service", version=VERSION)


class StorageObjectCreateRequest(BaseModel):
    name: str
    content_type: str
    size_bytes: int = Field(default=0, ge=0)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    # sqlite3.Connection.__exit__ only commits/rolls back -- it does not close the connection.
    # Same leak found+fixed across services/{ai,auth,tenant,documents}/app/main.py 2026-07-09;
    # applied here for consistency. Transactional behavior at call sites is unchanged.
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
            CREATE TABLE IF NOT EXISTS objects (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                download_url TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
            """
        )
        try:
            conn.execute("ALTER TABLE objects ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass
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


def _to_object(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "name": row["name"],
        "content_type": row["content_type"],
        "size_bytes": row["size_bytes"],
        "created_at": row["created_at"],
        "download_url": row["download_url"],
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
        count = conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
    return with_service_metadata(
        {"status": "healthy", "object_count": count},
        SERVICE_NAME,
        VERSION,
    )


@app.post(f"{API_PREFIX}/storage/objects", status_code=201)
def create_object(payload: StorageObjectCreateRequest, authorization: str | None = Header(default=None)):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"storage:write"},
    )
    tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=None,
        owner_override_allowed=False,
    ) or "owner"
    object_id = str(uuid4())
    record = {
        "id": object_id,
        "tenant_id": tenant_id,
        "name": payload.name,
        "content_type": payload.content_type,
        "size_bytes": payload.size_bytes,
        "created_at": _now_utc(),
        "download_url": f"{DOWNLOAD_BASE_URL}/{object_id}",
        "created_by": claims.get("sub", "unknown"),
    }

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO objects (id, tenant_id, name, content_type, size_bytes, created_at, download_url, created_by)
            VALUES (:id, :tenant_id, :name, :content_type, :size_bytes, :created_at, :download_url, :created_by)
            """,
            record,
        )
        conn.commit()

    try:
        emit_workboard_job(
            source="govos-v2-storage",
            action="storage.object.created",
            event=f"V2 STORAGE OBJECT QUEUED: {record['id']}",
            lane="engineering",  # file upload is internal plumbing; self-heals
            payload={
                "object_id": record["id"],
                "name": record["name"],
                "content_type": record["content_type"],
                "created_by": record["created_by"],
            },
        )
    except Exception:
        pass

    return record


@app.get(f"{API_PREFIX}/storage/objects")
def list_objects(authorization: str | None = Header(default=None)):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"storage:read"},
    )
    tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=None,
        owner_override_allowed=False,
    )
    with _db() as conn:
        if tenant_id:
            rows = conn.execute("SELECT * FROM objects WHERE tenant_id = ? ORDER BY created_at DESC", (tenant_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM objects ORDER BY created_at DESC").fetchall()
    return {"objects": [_to_object(row) for row in rows]}


@app.get(f"{API_PREFIX}/storage/objects/{{object_id}}")
def get_object(object_id: str, authorization: str | None = Header(default=None)):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"storage:read"},
    )
    with _db() as conn:
        row = conn.execute("SELECT * FROM objects WHERE id = ?", (object_id,)).fetchone()
    if not row:
        auth_error(404, "resource_not_found", "Object was not found", {"object_id": object_id})
    enforce_resource_tenant(service_name=SERVICE_NAME, claims=claims, resource_tenant_id=row["tenant_id"])
    return _to_object(row)
