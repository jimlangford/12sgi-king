"""
12 Stones v2 Local Owner Node — main API entry point.

Runs inside Docker on the owner machine. Accessible only via
localhost or through the Tailscale private network (12sgi-v2).
Never exposed to the public internet without explicit review.
"""
from fastapi import FastAPI
import uvicorn
import os
from pathlib import Path

app = FastAPI(title="12 Stones v2 Local Owner Node")


def read_secret(name: str) -> str | None:
    """Read a Docker secret from /run/secrets/<name>."""
    p = Path(f"/run/secrets/{name}")
    if p.exists():
        return p.read_text().strip() or None
    return None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "12sgi-v2",
        "mode": "local-owner-tailscale",
        "env": os.getenv("APP_ENV", "local"),
    }


@app.get("/")
def root():
    return {
        "message": "12 Stones v2 local owner node is running.",
        "access": "Localhost or Tailscale only.",
        "docs": "/docs",
    }


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8088"))
    uvicorn.run(app, host=host, port=port)
