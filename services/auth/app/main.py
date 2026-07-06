import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "2.0.0")
DB_PATH = os.environ.get("AUTH_DB_PATH", "/tmp/govos_v2_auth.db")
SIGNING_SECRET = os.environ.get("AUTH_SIGNING_SECRET", "dev-only-signing-secret-change-me")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")

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


class AuthIntrospectionRequest(BaseModel):
    token: str


ALLOWED_PROVIDERS = {"passkey", "google", "apple", "microsoft", "magic_link"}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                subject TEXT NOT NULL,
                email TEXT,
                issued_at TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _issue_token(subject: str, provider: str, expires_at: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": "govos-auth",
        "sub": subject,
        "provider": provider,
        "exp": expires_at,
        "jti": secrets.token_urlsafe(16),
    }
    header_part = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_part = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    unsigned = f"{header_part}.{payload_part}".encode()
    sig = hmac.new(SIGNING_SECRET.encode(), unsigned, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_b64url(sig)}"


def _session_for_token(token: str) -> sqlite3.Row | None:
    now_ts = int(_now_utc().timestamp())
    with _db() as conn:
        row = conn.execute(
            """
            SELECT token, provider, subject, email, issued_at, expires_at
            FROM sessions
            WHERE token = ? AND expires_at > ?
            """,
            (token, now_ts),
        ).fetchone()
    return row


init_db()


@app.get(f"{API_PREFIX}/live")
def live():
    return {"status": "alive", "service": "auth", "timestamp": _now_utc().isoformat()}


@app.get(f"{API_PREFIX}/ready")
def ready():
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ready", "service": "auth", "db_path": DB_PATH}
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "dependency_not_ready", "message": "Auth database unavailable", "details": {"reason": str(exc)}}},
        )


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    return {"status": "healthy", "service": "auth", "version": VERSION, "session_count": count}


@app.get(f"{API_PREFIX}/auth/jwks")
def jwks():
    return {
        "keys": [
            {
                "kty": "oct",
                "kid": "local-hs256-key-1",
                "use": "sig",
                "alg": "HS256",
                "k": "***redacted***",
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

    issued_at = _now_utc()
    expires_at = issued_at + timedelta(hours=1)
    expires_at_ts = int(expires_at.timestamp())
    token = _issue_token(payload.subject, payload.provider, expires_at_ts)

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO sessions (token, provider, subject, email, issued_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token, payload.provider, payload.subject, payload.email, issued_at.isoformat(), expires_at_ts),
        )
        conn.commit()

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "user": {
            "id": payload.subject,
            "provider": payload.provider,
            "email": payload.email,
        },
    }


@app.post(f"{API_PREFIX}/auth/introspect")
def introspect_session(payload: AuthIntrospectionRequest, x_service_token: str | None = Header(default=None)):
    if not x_service_token or not secrets.compare_digest(x_service_token, INTERNAL_SERVICE_TOKEN):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "forbidden",
                    "message": "Service trust token is invalid",
                    "details": {},
                }
            },
        )

    row = _session_for_token(payload.token)
    if not row:
        return {"active": False}

    return {
        "active": True,
        "user": {
            "id": row["subject"],
            "provider": row["provider"],
            "email": row["email"],
        },
        "exp": row["expires_at"],
    }
