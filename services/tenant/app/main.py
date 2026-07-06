import os
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "2.0.0")
app = FastAPI(title="govOS v2 Tenant Service", version=VERSION)


class CaseCreateRequest(BaseModel):
    tenant_id: str
    title: str
    status: str = "open"
    notes: str | None = None


CASE_STORE: dict[str, dict] = {}


@app.get(f"{API_PREFIX}/live")
def live():
    return {"status": "alive", "service": "tenant", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get(f"{API_PREFIX}/ready")
def ready():
    return {"status": "ready", "service": "tenant"}


@app.get(f"{API_PREFIX}/health")
def health():
    return {"status": "healthy", "service": "tenant", "version": VERSION, "case_count": len(CASE_STORE)}


@app.get(f"{API_PREFIX}/cases")
def list_cases():
    return {"cases": list(CASE_STORE.values())}


@app.post(f"{API_PREFIX}/cases", status_code=201)
def create_case(payload: CaseCreateRequest):
    case_id = str(uuid4())
    record = {
        "id": case_id,
        "tenant_id": payload.tenant_id,
        "title": payload.title,
        "status": payload.status,
        "notes": payload.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    CASE_STORE[case_id] = record
    return record


@app.get(f"{API_PREFIX}/cases/{{case_id}}")
def get_case(case_id: str):
    case = CASE_STORE.get(case_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource_not_found", "message": "Case was not found", "details": {"case_id": case_id}}},
        )
    return case
