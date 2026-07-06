import json
import os
import sqlite3
from datetime import datetime, timezone
from urllib import error, request
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field

API_PREFIX = "/api/v2"
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


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS objects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                download_url TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _error(status_code: int, code: str, message: str, details: dict | None = None):
    raise HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message, "details": details or {}}})


def _check_dependency_ready(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode() or "{}")
            return data.get("status") in {"ready", "healthy"}
    except Exception:
        return False


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


def _to_object(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
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
    return {"status": "alive", "service": "storage", "timestamp": _now_utc()}


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
        "service": "storage",
        "dependencies": {"database": db_ok, "auth": auth_ok},
    }


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
    return {"status": "healthy", "service": "storage", "version": VERSION, "object_count": count}


@app.post(f"{API_PREFIX}/storage/objects", status_code=201)
def create_object(payload: StorageObjectCreateRequest, authorization: str | None = Header(default=None)):
    user = _require_auth(authorization)
    object_id = str(uuid4())
    record = {
        "id": object_id,
        "name": payload.name,
        "content_type": payload.content_type,
        "size_bytes": payload.size_bytes,
        "created_at": _now_utc(),
        "download_url": f"{DOWNLOAD_BASE_URL}/{object_id}",
        "created_by": user.get("id", "unknown"),
    }

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO objects (id, name, content_type, size_bytes, created_at, download_url, created_by)
            VALUES (:id, :name, :content_type, :size_bytes, :created_at, :download_url, :created_by)
            """,
            record,
        )
        conn.commit()

    return record


@app.get(f"{API_PREFIX}/storage/objects")
def list_objects(authorization: str | None = Header(default=None)):
    _require_auth(authorization)
    with _db() as conn:
        rows = conn.execute("SELECT * FROM objects ORDER BY created_at DESC").fetchall()
    return {"objects": [_to_object(row) for row in rows]}


@app.get(f"{API_PREFIX}/storage/objects/{{object_id}}")
def get_object(object_id: str, authorization: str | None = Header(default=None)):
    _require_auth(authorization)
    with _db() as conn:
        row = conn.execute("SELECT * FROM objects WHERE id = ?", (object_id,)).fetchone()
    if not row:
        _error(404, "resource_not_found", "Object was not found", {"object_id": object_id})
    return _to_object(row)
