import base64
import hashlib
import hmac
import html as _html
import json
import logging
import os
import secrets
import sqlite3
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests as _requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

_log = logging.getLogger(__name__)

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "2.0.0")
DB_PATH = os.environ.get("AUTH_DB_PATH", "/tmp/govos_v2_auth.db")
SIGNING_SECRET = os.environ.get("AUTH_SIGNING_SECRET", "dev-only-signing-secret-change-me")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")

# ── OAuth ─────────────────────────────────────────────────────────────────────
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
# Public URL of this auth service (used to build OAuth callback URIs registered with providers).
AUTH_PUBLIC_URL = os.environ.get("AUTH_PUBLIC_URL", "https://auth.12sgi.com")
# Console URL to redirect back to after successful sign-in (token appended as #token=...).
OAUTH_REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", "https://12sgi.com/king/")
# Comma-separated list of allowed GitHub logins and Google e-mail addresses.
OWNER_GITHUB_LOGINS: set[str] = set(filter(None, os.environ.get("OWNER_GITHUB_LOGINS", "jimlangford").split(",")))
OWNER_GOOGLE_EMAILS: set[str] = set(filter(None, os.environ.get("OWNER_GOOGLE_EMAILS", "").split(",")))
# CORS: allow requests from the console origins.
_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "https://jimlangford.github.io,https://12sgi.com").split(",")
    if o.strip()
]

app = FastAPI(title="govOS v2 Auth Service", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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


ALLOWED_PROVIDERS = {"passkey", "google", "apple", "microsoft", "magic_link", "github"}


# ── OAuth CSRF state helpers ──────────────────────────────────────────────────

def _make_oauth_state(provider: str) -> str:
    """Return a signed state token for CSRF protection. Stateless — no DB needed."""
    nonce = secrets.token_urlsafe(16)
    sig = hmac.new(
        SIGNING_SECRET.encode(), f"{provider}:{nonce}".encode(), hashlib.sha256
    ).hexdigest()[:16]
    return f"{provider}.{nonce}.{sig}"


def _verify_oauth_state(state: str, provider: str) -> bool:
    try:
        p, nonce, sig = state.split(".", 2)
    except ValueError:
        return False
    if p != provider:
        return False
    expected = hmac.new(
        SIGNING_SECRET.encode(), f"{provider}:{nonce}".encode(), hashlib.sha256
    ).hexdigest()[:16]
    return hmac.compare_digest(sig, expected)


def _error_page(msg: str, *, log_detail: str = "") -> HTMLResponse:
    if log_detail:
        _log.warning("OAuth error: %s | detail: %s", msg, log_detail)
    safe = _html.escape(msg)
    back = _html.escape(OAUTH_REDIRECT_BASE)
    body = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>Auth error · 12sgi</title>"
        "<style>body{font-family:system-ui,sans-serif;padding:40px;max-width:480px;margin:auto}"
        "h2{color:#c0322c}a{color:#1259a3}</style></head><body>"
        f"<h2>Authentication error</h2><p>{safe}</p>"
        f"<p><a href='{back}'>&#8592; Back to console</a></p>"
        "</body></html>"
    )
    return HTMLResponse(content=body, status_code=400)


def _issue_and_store_session(subject: str, provider: str, email: str) -> str:
    """Issue a JWT and persist the session row, returning the raw token."""
    issued_at = _now_utc()
    expires_at = issued_at + timedelta(hours=8)
    expires_at_ts = int(expires_at.timestamp())
    token = _issue_token(subject, provider, expires_at_ts)
    with _db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions
              (token, provider, subject, email, issued_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token, provider, subject, email, issued_at.isoformat(), expires_at_ts),
        )
        conn.commit()
    return token


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


# ── GitHub OAuth ──────────────────────────────────────────────────────────────

@app.get(f"{API_PREFIX}/auth/github")
def oauth_github_start():
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=501, detail={"error": {"code": "not_configured", "message": "GitHub OAuth is not configured on this server"}})
    state = _make_oauth_state("github")
    callback_uri = f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/github/callback"
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": callback_uri,
        "scope": "read:user user:email",
        "state": state,
    }
    return RedirectResponse(url="https://github.com/login/oauth/authorize?" + urllib.parse.urlencode(params))


@app.get(f"{API_PREFIX}/auth/github/callback")
def oauth_github_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        # "error" is a fixed OAuth error code from GitHub (e.g. "access_denied") — safe to show.
        return _error_page("GitHub sign-in was not completed.", log_detail=f"provider_error={error}")
    if not code:
        return _error_page("No authorization code received from GitHub.")
    if not _verify_oauth_state(state, "github"):
        return _error_page("Invalid OAuth state — please try signing in again.")

    callback_uri = f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/github/callback"
    try:
        resp = _requests.post(
            "https://github.com/login/oauth/access_token",
            data={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET, "code": code, "redirect_uri": callback_uri},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        gh_access_token = resp.json().get("access_token", "")
        if not gh_access_token:
            return _error_page("GitHub did not return an access token.")
    except Exception as exc:
        return _error_page("Could not complete sign-in with GitHub — please try again.", log_detail=str(exc))

    try:
        user_resp = _requests.get(
            "https://api.github.com/user",
            headers={"Authorization": "token " + gh_access_token, "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        user_resp.raise_for_status()
        gh_user = user_resp.json()
        login = gh_user.get("login", "")
        email = gh_user.get("email") or ""
    except Exception as exc:
        return _error_page("Could not retrieve GitHub account information.", log_detail=str(exc))

    if login not in OWNER_GITHUB_LOGINS:
        return _error_page("This GitHub account is not authorised for owner access.")

    token = _issue_and_store_session(f"github:{login}", "github", email)
    redirect_url = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/#token={urllib.parse.quote(token, safe='')}"
    return RedirectResponse(url=redirect_url)


# ── Google OAuth ──────────────────────────────────────────────────────────────

@app.get(f"{API_PREFIX}/auth/google")
def oauth_google_start():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail={"error": {"code": "not_configured", "message": "Google OAuth is not configured on this server"}})
    state = _make_oauth_state("google")
    callback_uri = f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/google/callback"
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": callback_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
    }
    return RedirectResponse(url="https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params))


@app.get(f"{API_PREFIX}/auth/google/callback")
def oauth_google_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return _error_page("Google sign-in was not completed.", log_detail=f"provider_error={error}")
    if not code:
        return _error_page("No authorization code received from Google.")
    if not _verify_oauth_state(state, "google"):
        return _error_page("Invalid OAuth state — please try signing in again.")

    callback_uri = f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/google/callback"
    try:
        resp = _requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": callback_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except Exception as exc:
        return _error_page("Could not complete sign-in with Google — please try again.", log_detail=str(exc))

    id_token_raw = token_data.get("id_token", "")
    try:
        # Decode without verification — we trust Google's signed redirect.
        payload_b64 = id_token_raw.split(".")[1]
        # Restore standard base64 padding.
        padding = (4 - len(payload_b64) % 4) % 4
        id_payload = json.loads(base64.b64decode(payload_b64 + "=" * padding).decode("utf-8"))
        email = id_payload.get("email", "")
        sub = id_payload.get("sub", "")
    except Exception as exc:
        return _error_page("Could not verify Google account — please try again.", log_detail=str(exc))

    if not OWNER_GOOGLE_EMAILS or email not in OWNER_GOOGLE_EMAILS:
        return _error_page("This Google account is not authorised for owner access.")

    token = _issue_and_store_session(f"google:{sub}", "google", email)
    redirect_url = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/#token={urllib.parse.quote(token, safe='')}"
    return RedirectResponse(url=redirect_url)
