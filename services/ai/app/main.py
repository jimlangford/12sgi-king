import os
from datetime import datetime, timezone
from fastapi import FastAPI
from pydantic import BaseModel

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "2.0.0")
app = FastAPI(title="govOS v2 AI Service", version=VERSION)


class AiAssistRequest(BaseModel):
    case_id: str
    prompt: str
    context: dict | None = None


@app.get(f"{API_PREFIX}/live")
def live():
    return {"status": "alive", "service": "ai", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get(f"{API_PREFIX}/ready")
def ready():
    return {"status": "ready", "service": "ai"}


@app.get(f"{API_PREFIX}/health")
def health():
    return {"status": "healthy", "service": "ai", "version": VERSION}


@app.post(f"{API_PREFIX}/ai/assist")
def assist(payload: AiAssistRequest):
    prompt = payload.prompt.strip()
    summary = (
        f"Suggested next step for case {payload.case_id}: gather timeline facts, "
        f"organize evidence, and generate a draft document."
    )
    if prompt:
        summary = f"Assistant reviewed your prompt and prepared next actions for case {payload.case_id}."

    return {
        "case_id": payload.case_id,
        "summary": summary,
        "actions": [
            "Review latest timeline events",
            "Generate notice draft from template",
            "Upload supporting files to evidence storage",
        ],
    }
