import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib import error, parse, request
from uuid import uuid4

from fastapi import FastAPI, Header, Response
from pydantic import BaseModel

from services.authz import auth_error, enforce_resource_tenant, require_claims
from services.service_metadata import with_service_metadata
from services.v2_workboard import emit_workboard_job

API_PREFIX = "/api/v2"
SERVICE_NAME = "documents"
VERSION = os.environ.get("VERSION", "2.0.0")
DB_PATH = os.environ.get("DOCUMENTS_DB_PATH", "/tmp/govos_v2_documents.db")
AUTH_INTROSPECTION_URL = os.environ.get("AUTH_INTROSPECTION_URL", "http://localhost:8101/api/v2/auth/introspect")
AUTH_READY_URL = os.environ.get("AUTH_READY_URL", "http://localhost:8101/api/v2/ready")
TENANT_SERVICE_URL = os.environ.get("TENANT_SERVICE_URL", "http://localhost:8102")
TENANT_READY_URL = os.environ.get("TENANT_READY_URL", f"{TENANT_SERVICE_URL}/api/v2/ready")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
REQUEST_TIMEOUT = float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "3"))

app = FastAPI(title="govOS v2 Documents Service", version=VERSION)


class DocumentGenerateRequest(BaseModel):
    template_id: str
    case_id: str
    output_format: str
    fields: dict | None = None


ALLOWED_FORMATS = {"pdf", "docx", "html"}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    # sqlite3.Connection.__exit__ only commits/rolls back -- it does not close the connection.
    # Same leak found+fixed across services/{ai,auth,tenant}/app/main.py 2026-07-09; applied here
    # for consistency. Transactional behavior at call sites is unchanged.
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
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT '',
                case_id TEXT NOT NULL,
                output_format TEXT NOT NULL,
                fields_json TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
            """
        )
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''")
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


def _ensure_case_exists(case_id: str, authorization: str) -> dict:
    encoded_case_id = parse.quote(case_id, safe="")
    req = request.Request(
        f"{TENANT_SERVICE_URL}/api/v2/cases/{encoded_case_id}",
        headers={"Authorization": authorization},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                auth_error(503, "dependency_unavailable", "Tenant service unavailable", {"status": resp.status})
            return json.loads(resp.read().decode() or "{}")
    except error.HTTPError as exc:
        if exc.code == 404:
            auth_error(404, "resource_not_found", "Case was not found", {"case_id": case_id})
        if exc.code == 401:
            auth_error(401, "unauthorized", "Session is not active")
        auth_error(503, "dependency_unavailable", "Tenant service unavailable", {"status": exc.code})
    except Exception:
        auth_error(503, "dependency_unavailable", "Tenant service unavailable")


def _to_document(row: sqlite3.Row) -> dict:
    fields = row["fields_json"]
    return {
        "id": row["id"],
        "template_id": row["template_id"],
        "tenant_id": row["tenant_id"],
        "case_id": row["case_id"],
        "output_format": row["output_format"],
        "status": row["status"],
        "created_at": row["created_at"],
        "created_by": row["created_by"],
        "fields": json.loads(fields) if fields else None,
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
    tenant_ok = _check_dependency_ready(TENANT_READY_URL)
    is_ready = db_ok and auth_ok and tenant_ok

    response.status_code = 200 if is_ready else 503
    return with_service_metadata(
        {
            "status": "ready" if is_ready else "not-ready",
            "dependencies": {"database": db_ok, "auth": auth_ok, "tenant": tenant_ok},
        },
        SERVICE_NAME,
        VERSION,
    )


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    return with_service_metadata(
        {"status": "healthy", "document_count": count},
        SERVICE_NAME,
        VERSION,
    )


@app.post(f"{API_PREFIX}/documents/generate", status_code=201)
def generate_document(payload: DocumentGenerateRequest, authorization: str | None = Header(default=None)):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"documents:write"},
    )

    if payload.output_format not in ALLOWED_FORMATS:
        auth_error(400, "invalid_output_format", "Output format is not supported", {"output_format": payload.output_format})

    case = _ensure_case_exists(payload.case_id, authorization or "")
    case_tenant_id = case.get("tenant_id", "")
    enforce_resource_tenant(service_name=SERVICE_NAME, claims=claims, resource_tenant_id=case_tenant_id)

    doc_id = str(uuid4())
    record = {
        "id": doc_id,
        "template_id": payload.template_id,
        "tenant_id": case_tenant_id,
        "case_id": payload.case_id,
        "output_format": payload.output_format,
        "fields_json": json.dumps(payload.fields) if payload.fields else None,
        "status": "generated",
        "created_at": _now_utc(),
        "created_by": claims.get("sub", "unknown"),
    }
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO documents (id, template_id, tenant_id, case_id, output_format, fields_json, status, created_at, created_by)
            VALUES (:id, :template_id, :tenant_id, :case_id, :output_format, :fields_json, :status, :created_at, :created_by)
            """,
            record,
        )
        conn.commit()

    try:
        emit_workboard_job(
            source="govos-v2-documents",
            action="document.generated",
            event=f"V2 DOCUMENT QUEUED: {record['id']}",
            lane="creative",  # generated documents need human review before publish
            payload={
                "document_id": record["id"],
                "case_id": record["case_id"],
                "output_format": record["output_format"],
                "created_by": record["created_by"],
            },
        )
    except Exception:
        pass

    return {
        "id": record["id"],
        "template_id": record["template_id"],
        "tenant_id": record["tenant_id"],
        "case_id": record["case_id"],
        "output_format": record["output_format"],
        "status": record["status"],
        "created_at": record["created_at"],
        "created_by": record["created_by"],
        "fields": payload.fields,
    }


@app.get(f"{API_PREFIX}/documents/{{document_id}}")
def get_document(document_id: str, authorization: str | None = Header(default=None)):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"documents:read"},
    )
    with _db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not row:
        auth_error(404, "resource_not_found", "Document was not found", {"document_id": document_id})
    enforce_resource_tenant(service_name=SERVICE_NAME, claims=claims, resource_tenant_id=row["tenant_id"])
    return _to_document(row)
