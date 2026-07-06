import os
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "2.0.0")
app = FastAPI(title="govOS v2 Documents Service", version=VERSION)


class DocumentGenerateRequest(BaseModel):
    template_id: str
    case_id: str
    output_format: str
    fields: dict | None = None


DOCUMENTS: dict[str, dict] = {}
ALLOWED_FORMATS = {"pdf", "docx", "html"}


@app.get(f"{API_PREFIX}/live")
def live():
    return {"status": "alive", "service": "documents", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get(f"{API_PREFIX}/ready")
def ready():
    return {"status": "ready", "service": "documents"}


@app.get(f"{API_PREFIX}/health")
def health():
    return {"status": "healthy", "service": "documents", "version": VERSION, "document_count": len(DOCUMENTS)}


@app.post(f"{API_PREFIX}/documents/generate", status_code=201)
def generate_document(payload: DocumentGenerateRequest):
    if payload.output_format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_output_format",
                    "message": "Output format is not supported",
                    "details": {"output_format": payload.output_format},
                }
            },
        )

    doc_id = str(uuid4())
    record = {
        "id": doc_id,
        "template_id": payload.template_id,
        "case_id": payload.case_id,
        "output_format": payload.output_format,
        "status": "generated",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    DOCUMENTS[doc_id] = record
    return record


@app.get(f"{API_PREFIX}/documents/{{document_id}}")
def get_document(document_id: str):
    doc = DOCUMENTS.get(document_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource_not_found", "message": "Document was not found", "details": {"document_id": document_id}}},
        )
    return doc
