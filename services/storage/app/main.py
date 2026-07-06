import os
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "2.0.0")
DOWNLOAD_BASE_URL = os.environ.get("STORAGE_DOWNLOAD_BASE_URL", "https://storage.local/download")
app = FastAPI(title="govOS v2 Storage Service", version=VERSION)


class StorageObjectCreateRequest(BaseModel):
    name: str
    content_type: str
    size_bytes: int = Field(default=0, ge=0)


OBJECTS: dict[str, dict] = {}


@app.get(f"{API_PREFIX}/live")
def live():
    return {"status": "alive", "service": "storage", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get(f"{API_PREFIX}/ready")
def ready():
    return {"status": "ready", "service": "storage"}


@app.get(f"{API_PREFIX}/health")
def health():
    return {"status": "healthy", "service": "storage", "version": VERSION, "object_count": len(OBJECTS)}


@app.post(f"{API_PREFIX}/storage/objects", status_code=201)
def create_object(payload: StorageObjectCreateRequest):
    object_id = str(uuid4())
    record = {
        "id": object_id,
        "name": payload.name,
        "content_type": payload.content_type,
        "size_bytes": payload.size_bytes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "download_url": f"{DOWNLOAD_BASE_URL}/{object_id}",
    }
    OBJECTS[object_id] = record
    return record


@app.get(f"{API_PREFIX}/storage/objects")
def list_objects():
    return {"objects": list(OBJECTS.values())}


@app.get(f"{API_PREFIX}/storage/objects/{{object_id}}")
def get_object(object_id: str):
    obj = OBJECTS.get(object_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "resource_not_found", "message": "Object was not found", "details": {"object_id": object_id}}},
        )
    return obj
