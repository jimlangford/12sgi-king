import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "2.0.0")

app = FastAPI(title="govOS v2 Auth Service", version=VERSION)


class AuthSessionRequest(BaseModel):
    provider: str
    subject: str
    email: str | None = None


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: dict


ALLOWED_PROVIDERS = {"passkey", "google", "apple", "microsoft", "magic_link"}


@app.get(f"{API_PREFIX}/live")
def live():
    return {"status": "alive", "service": "auth", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get(f"{API_PREFIX}/ready")
def ready():
    return {"status": "ready", "service": "auth"}


@app.get(f"{API_PREFIX}/health")
def health():
    return {"status": "healthy", "service": "auth", "version": VERSION}


@app.get(f"{API_PREFIX}/auth/jwks")
def jwks():
    # Placeholder JWKS document for local integration; replace with managed keys in production.
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "local-dev-key-1",
                "use": "sig",
                "alg": "RS256",
                "n": "00",
                "e": "AQAB",
            }
        ]
    }


@app.post(f"{API_PREFIX}/auth/session", response_model=AuthSessionResponse)
def create_session(payload: AuthSessionRequest):
    if payload.provider not in ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_provider",
                    "message": "Provider is not supported",
                    "details": {"provider": payload.provider},
                }
            },
        )

    expires = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    token = secrets.token_urlsafe(32)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": expires,
        "user": {
            "id": payload.subject,
            "provider": payload.provider,
            "email": payload.email,
        },
    }
