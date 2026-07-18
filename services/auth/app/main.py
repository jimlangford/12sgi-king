import base64
import binascii
import hashlib
import hmac
import html as _html
import json
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import urllib.parse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from uuid import uuid4

import requests as _requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from services.service_metadata import with_service_metadata
from services.authz import DEFAULT_SCOPES_BY_ROLE, KNOWN_SCOPES, VALID_ROLES, audit_auth_event
from services.event_bus import publish_event as _publish_event
from services.auth.app.passkeys import (
    init_passkeys_db,
    PasskeyRegisterBeginRequest, PasskeyRegisterBeginResponse,
    PasskeyRegisterCompleteRequest, PasskeyRegisterCompleteResponse,
    PasskeySigninBeginRequest, PasskeySigninBeginResponse,
    PasskeySigninCompleteRequest, PasskeySigninCompleteResponse,
    passkey_register_begin, passkey_register_complete,
    passkey_signin_begin, passkey_signin_complete,
)

_log = logging.getLogger(__name__)

API_PREFIX = "/api/v2"
SERVICE_NAME = "auth"
VERSION = os.environ.get("VERSION", "2.0.0")
DB_PATH = os.environ.get("AUTH_DB_PATH", "/tmp/govos_v2_auth.db")
AUTH_ISSUER = os.environ.get("AUTH_ISSUER", "govos-auth")
AUTH_AUDIENCE = os.environ.get("AUTH_AUDIENCE", "govos-v2")
AUTH_TOKEN_TTL_SECONDS = max(300, int(os.environ.get("AUTH_TOKEN_TTL_SECONDS", "3600")))
SERVICE_ALLOWED_SCOPES = {
    scope.strip()
    for scope in os.environ.get(
        "AUTH_SERVICE_ALLOWED_SCOPES",
        "auth:introspect,tenant:read,tenant:write,documents:read,documents:write,storage:read,storage:write,ai:assist,gpu:infer,gpu:read",
    ).split(",")
    if scope.strip()
}
ALLOWED_WILDCARD_SCOPES = {
    scope.strip()
    for scope in os.environ.get("AUTH_ALLOWED_WILDCARD_SCOPES", "").split(",")
    if scope.strip()
}
AUTH_VERIFICATION_DIAGNOSTICS_ENABLED = os.environ.get("AUTH_VERIFICATION_DIAGNOSTICS_ENABLED", "").strip().lower() in {
    "1",
    "true",
    "yes",
}

_DEV_SIGNING_SECRET = "dev-only-signing-secret-change-me"
_DEV_SERVICE_TOKEN = "dev-internal-token"
SIGNING_SECRET = os.environ.get("AUTH_SIGNING_SECRET", _DEV_SIGNING_SECRET)
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", _DEV_SERVICE_TOKEN)

# Fail-closed on the well-known dev secrets (docs/architecture/V1_TO_V2_UPGRADE_MAP.md Section E:
# "make that structurally impossible (fail-to-start on default secret), not remembered" -- these
# values are published in this repo's own docker-compose.v2.yml comments, so a deploy that forgets
# to override them is an auth bypass, not a hardening detail). GOVOS_ALLOW_DEV_SECRETS is the
# explicit, visible opt-in for local/Tailscale-private dev (set by docker-compose.v2.yml) -- the
# service now refuses to boot on the default secret unless that flag is deliberately set, so
# "forgot to set a real secret" can no longer silently ship instead of loudly failing.
if not os.environ.get("GOVOS_ALLOW_DEV_SECRETS"):
    if SIGNING_SECRET == _DEV_SIGNING_SECRET:
        raise RuntimeError(
            "AUTH_SIGNING_SECRET is unset and defaulted to the published dev value -- refusing to "
            "start. Set a real AUTH_SIGNING_SECRET, or set GOVOS_ALLOW_DEV_SECRETS=1 for local/"
            "Tailscale-private dev only.")
    if INTERNAL_SERVICE_TOKEN == _DEV_SERVICE_TOKEN:
        raise RuntimeError(
            "INTERNAL_SERVICE_TOKEN is unset and defaulted to the published dev value -- refusing to "
            "start. Set a real INTERNAL_SERVICE_TOKEN, or set GOVOS_ALLOW_DEV_SECRETS=1 for local/"
            "Tailscale-private dev only.")

# ── OAuth ─────────────────────────────────────────────────────────────────────
def _csv_env_set(name: str, default: str = "", *, casefold: bool = False) -> set[str]:
    values: set[str] = set()
    for raw in os.environ.get(name, default).split(","):
        item = raw.strip()
        if not item:
            continue
        values.add(item.casefold() if casefold else item)
    return values


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
# Public URL of this auth service (used to build OAuth callback URIs registered with providers).
AUTH_PUBLIC_URL = os.environ.get("AUTH_PUBLIC_URL", "https://auth.12sgi.com")
# Console URL to redirect back to after successful sign-in (token appended as #token=...).
OAUTH_REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", "https://12sgi.com/king/")
# Comma-separated list of allowed GitHub logins and Google e-mail addresses.
OWNER_GITHUB_LOGINS = _csv_env_set("OWNER_GITHUB_LOGINS", "jimlangford", casefold=True)
OWNER_GOOGLE_EMAILS = _csv_env_set("OWNER_GOOGLE_EMAILS", casefold=True)
OWNER_MAGIC_EMAILS = _csv_env_set(
    "OWNER_MAGIC_EMAILS",
    ",".join(sorted(OWNER_GOOGLE_EMAILS)),
    casefold=True,
)
MAGIC_LINK_TTL_SECONDS = max(300, min(3600, int(os.environ.get("MAGIC_LINK_TTL_SECONDS", "900"))))
MAGIC_LINK_MIN_INTERVAL_SECONDS = max(
    0,
    min(900, int(os.environ.get("MAGIC_LINK_MIN_INTERVAL_SECONDS", "60"))),
)
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@12sgi.com").strip()
SMTP_STARTTLS = _bool_env("SMTP_STARTTLS", default=True)
SMTP_ALLOW_UNAUTHENTICATED = _bool_env("SMTP_ALLOW_UNAUTHENTICATED", default=False)
MAGIC_EMAIL_CONFIGURED = bool(
    SMTP_HOST
    and SMTP_FROM
    and ((SMTP_USER and SMTP_PASS) or SMTP_ALLOW_UNAUTHENTICATED)
    and OWNER_MAGIC_EMAILS
)
# Passkey registration requires an existing Owner session. The allowlist further constrains which
# owner e-mails may bind a credential and defaults only to explicitly configured Google owners.
OWNER_PASSKEY_EMAILS = _csv_env_set(
    "OWNER_PASSKEY_EMAILS",
    ",".join(sorted(OWNER_GOOGLE_EMAILS)),
    casefold=True,
)
# CORS: allow requests from the console origins.
_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "https://jimlangford.github.io,https://12sgi.com").split(",")
    if o.strip()
]

app = FastAPI(
    title="govOS v2 Auth Service",
    version=VERSION,
    description="Owner authentication for govOS v2: GitHub/Google OAuth, Passkeys (WebAuthn), "
                "Magic Links, session issuance + introspection. All endpoints under /api/v2.",
    # Tier 1.7 (2026-07-15): expose Swagger UI + OpenAPI schema at the /api/v2 prefix (per the
    # continuation-guide spec), not the FastAPI default root paths.
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    openapi_url=f"{API_PREFIX}/openapi.json",
)

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
    tenant_id: str | None = None
    role: str = "Resident"
    scopes: list[str] | None = None
    audience: str | None = None
    expires_in: int | None = None


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    claims: dict
    user: dict


class AuthIntrospectionRequest(BaseModel):
    token: str


class AuthClaimsDiagnosticRequest(BaseModel):
    token: str | None = None


class MagicLinkRequest(BaseModel):
    email: str


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


def _error_page(msg: str, *, log_detail: str = "", provider: str = "oauth") -> HTMLResponse:
    if log_detail:
        _log.warning("OAuth error: %s | detail: %s", msg, log_detail)
    # Emit a failure event — message is safe to include (no credentials/tokens).
    _publish_event(
        event_type="auth.oauth.failed",
        producer="auth",
        payload={"provider": provider, "reason": msg},
    )
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


def _issue_and_store_session(
    *,
    subject: str,
    provider: str,
    email: str,
    tenant_id: str,
    role: str,
    scopes: list[str],
    audience: str = AUTH_AUDIENCE,
    ttl_seconds: int = AUTH_TOKEN_TTL_SECONDS,
) -> tuple[str, int]:
    """Issue a JWT and persist the session row, returning the raw token."""
    issued_at = _now_utc()
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    expires_at_ts = int(expires_at.timestamp())
    token = _issue_token(
        subject=subject,
        provider=provider,
        tenant_id=tenant_id,
        role=role,
        scopes=scopes,
        audience=audience,
        expires_at=expires_at_ts,
    )
    with _db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions
              (token, provider, subject, email, tenant_id, role, scopes_json, issuer, audience, issued_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                provider,
                subject,
                email,
                tenant_id,
                role,
                json.dumps(scopes, separators=(",", ":")),
                AUTH_ISSUER,
                audience,
                issued_at.isoformat(),
                expires_at_ts,
            ),
        )
        conn.commit()
    # Emit auth event — never raises; never includes token/secret values.
    _publish_event(
        event_type="auth.session.created",
        producer="auth",
        entity_id=_redact_claim_identifier(subject),
        payload={
            "provider": provider,
            "role": role,
            "tenant_id": tenant_id or None,
            "scopes": scopes,
        },
    )
    return token, expires_at_ts


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def _db():
    # sqlite3.Connection.__exit__ only commits/rolls back -- it does not close the connection, so
    # every `with _db() as conn:` call site was leaking one open handle (services/ai/app/main.py
    # had the identical bug, found + fixed 2026-07-09 via tests/v2/test_v2_hardening.py). Same fix
    # applied here for consistency; transactional behavior at call sites is unchanged.
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
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                subject TEXT NOT NULL,
                email TEXT,
                tenant_id TEXT,
                role TEXT NOT NULL DEFAULT 'Resident',
                scopes_json TEXT,
                issuer TEXT NOT NULL DEFAULT 'govos-auth',
                audience TEXT NOT NULL DEFAULT 'govos-v2',
                issued_at TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS magic_links (
                token_hash TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_magic_links_email_created
            ON magic_links (email, created_at DESC)
            """
        )
        for ddl in (
            "ALTER TABLE sessions ADD COLUMN tenant_id TEXT",
            "ALTER TABLE sessions ADD COLUMN role TEXT NOT NULL DEFAULT 'Resident'",
            "ALTER TABLE sessions ADD COLUMN scopes_json TEXT",
            "ALTER TABLE sessions ADD COLUMN issuer TEXT NOT NULL DEFAULT 'govos-auth'",
            "ALTER TABLE sessions ADD COLUMN audience TEXT NOT NULL DEFAULT 'govos-v2'",
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass
        conn.commit()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _normalise_scopes(scopes: list[str] | None) -> list[str]:
    items = sorted({str(scope).strip() for scope in (scopes or []) if str(scope).strip()})
    return items


def _default_scopes(role: str) -> list[str]:
    return sorted(DEFAULT_SCOPES_BY_ROLE.get(role, set()))


def _resolve_scopes(role: str, requested_scopes: list[str] | None) -> list[str]:
    requested = set(_normalise_scopes(requested_scopes))
    wildcard_scopes = sorted(scope for scope in requested if "*" in scope and scope not in ALLOWED_WILDCARD_SCOPES)
    if wildcard_scopes:
        audit_auth_event("auth", "wildcard_scope_blocked", {"role": role, "requested_scopes": wildcard_scopes})
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "invalid_scope", "message": "Wildcard scopes require explicit allowlisting", "details": {"blocked_scopes": wildcard_scopes}}},
        )
    unknown_scopes = sorted(scope for scope in requested if scope not in KNOWN_SCOPES and "*" not in scope)
    if unknown_scopes:
        audit_auth_event("auth", "legacy_claim_pattern_rejected", {"reason": "undefined_scopes", "requested_scopes": unknown_scopes})
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "invalid_scope", "message": "Requested scopes are undefined", "details": {"undefined_scopes": unknown_scopes}}},
        )
    allowed = set(DEFAULT_SCOPES_BY_ROLE.get(role, set()))
    if role == "Service":
        allowed = set(SERVICE_ALLOWED_SCOPES)
        if not requested:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "invalid_scope", "message": "Service role requires explicit scopes", "details": {}}},
            )
        if not requested.issubset(allowed):
            disallowed = sorted(requested - allowed)
            audit_auth_event("auth", "role_escalation_attempt", {"role": role, "requested_scopes": sorted(requested)})
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "invalid_scope", "message": "Service scopes are not allowlisted", "details": {"disallowed_scopes": disallowed}}},
            )
        return sorted(requested)
    if not requested:
        return sorted(allowed)
    if not requested.issubset(allowed):
        disallowed = sorted(requested - allowed)
        audit_auth_event("auth", "role_escalation_attempt", {"role": role, "requested_scopes": sorted(requested)})
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "invalid_scope", "message": "Requested scopes exceed role permissions", "details": {"disallowed_scopes": disallowed}}},
        )
    return sorted(requested)


def _decode_and_verify_token(token: str) -> tuple[dict, dict]:
    try:
        header_part, payload_part, sig_part = token.split(".")
    except ValueError:
        audit_auth_event("auth", "malformed_token", {})
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Malformed token", "details": {}}})

    unsigned = f"{header_part}.{payload_part}".encode()
    expected_sig = _b64url(hmac.new(SIGNING_SECRET.encode(), unsigned, hashlib.sha256).digest())
    if not secrets.compare_digest(expected_sig, sig_part):
        audit_auth_event("auth", "malformed_token", {"reason": "invalid_signature"})
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Malformed token", "details": {}}})

    try:
        header = json.loads(_b64url_decode(header_part).decode("utf-8"))
        claims = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
        audit_auth_event("auth", "malformed_token", {"reason": "decode_error"})
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Malformed token", "details": {}}})

    now_ts = int(_now_utc().timestamp())
    if int(claims.get("exp", 0)) <= now_ts:
        audit_auth_event("auth", "expired_token", {"sub": claims.get("sub", "")})
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Session is not active", "details": {}}})
    if claims.get("iss") != AUTH_ISSUER:
        audit_auth_event("auth", "denied_access", {"reason": "wrong_issuer", "iss": claims.get("iss")})
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Session is not active", "details": {}}})
    if claims.get("aud") != AUTH_AUDIENCE:
        audit_auth_event("auth", "denied_access", {"reason": "wrong_audience", "aud": claims.get("aud")})
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized", "message": "Session is not active", "details": {}}})
    return header, claims


def _issue_token(
    *,
    subject: str,
    provider: str,
    tenant_id: str,
    role: str,
    scopes: list[str],
    audience: str,
    expires_at: int,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": AUTH_ISSUER,
        "aud": audience,
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "scopes": scopes,
        "provider": provider,
        "exp": expires_at,
        "jti": secrets.token_urlsafe(16),
    }
    header_part = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_part = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    unsigned = f"{header_part}.{payload_part}".encode()
    sig = hmac.new(SIGNING_SECRET.encode(), unsigned, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_b64url(sig)}"


def _redact_claim_identifier(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _session_for_token(token: str) -> sqlite3.Row | None:
    with _db() as conn:
        return conn.execute(
            """
            SELECT token, provider, subject, email, tenant_id, role, scopes_json, issuer, audience, issued_at, expires_at
            FROM sessions
            WHERE token = ?
            """,
            (token,),
        ).fetchone()


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalise_email(raw: str) -> str:
    email = str(raw or "").strip().casefold()
    return email if _EMAIL_PATTERN.fullmatch(email) else ""


def _magic_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_magic_link(email: str) -> tuple[str, int] | None:
    """Persist a hashed, single-use token unless this address is rate limited."""
    now = int(_now_utc().timestamp())
    token = secrets.token_urlsafe(32)
    token_hash = _magic_token_hash(token)
    expires_at = now + MAGIC_LINK_TTL_SECONDS
    with _db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        recent = conn.execute(
            "SELECT created_at FROM magic_links WHERE email = ? ORDER BY created_at DESC LIMIT 1",
            (email,),
        ).fetchone()
        if recent and now - int(recent["created_at"]) < MAGIC_LINK_MIN_INTERVAL_SECONDS:
            conn.commit()
            return None
        conn.execute(
            "UPDATE magic_links SET used_at = ? WHERE email = ? AND used_at IS NULL",
            (now, email),
        )
        conn.execute(
            """
            INSERT INTO magic_links (token_hash, email, created_at, expires_at, used_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (token_hash, email, now, expires_at),
        )
        conn.execute(
            "DELETE FROM magic_links WHERE expires_at < ? OR (used_at IS NOT NULL AND used_at < ?)",
            (now - 86400, now - 86400),
        )
        conn.commit()
    return token, expires_at


def _consume_magic_link(token: str) -> tuple[str, str]:
    """Atomically consume a magic link and return (status, email)."""
    if not token or len(token) > 512:
        return "invalid", ""
    now = int(_now_utc().timestamp())
    token_hash = _magic_token_hash(token)
    with _db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT email, expires_at, used_at FROM magic_links WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        if not row:
            conn.commit()
            return "invalid", ""
        if row["used_at"] is not None:
            conn.commit()
            return "used", ""
        if int(row["expires_at"]) < now:
            conn.execute(
                "UPDATE magic_links SET used_at = ? WHERE token_hash = ? AND used_at IS NULL",
                (now, token_hash),
            )
            conn.commit()
            return "expired", ""
        updated = conn.execute(
            """
            UPDATE magic_links SET used_at = ?
            WHERE token_hash = ? AND used_at IS NULL AND expires_at >= ?
            """,
            (now, token_hash, now),
        ).rowcount
        conn.commit()
    if updated != 1:
        return "used", ""
    return "ok", str(row["email"])


def _send_magic_email(email: str, magic_url: str) -> bool:
    if not MAGIC_EMAIL_CONFIGURED:
        return False
    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = email
    message["Subject"] = "Your 12SGI sign-in link"
    minutes = max(1, MAGIC_LINK_TTL_SECONDS // 60)
    message.set_content(
        f"Use this link to sign in to 12SGI. It expires in {minutes} minutes:\n\n"
        f"{magic_url}\n\n"
        "If you did not request this link, you can ignore this email.\n"
    )
    safe_url = _html.escape(magic_url, quote=True)
    message.add_alternative(
        "<!DOCTYPE html><html><body style='font-family:system-ui,sans-serif;padding:32px;max-width:480px'>"
        "<h2 style='color:#1259a3'>12SGI Sign-In</h2>"
        f"<p>This link expires in {minutes} minutes.</p>"
        f"<p><a href='{safe_url}' style='background:#1259a3;color:#fff;padding:12px 24px;"
        "border-radius:6px;text-decoration:none;display:inline-block'>Sign in to 12SGI</a></p>"
        "<p style='color:#666;font-size:12px'>If you did not request this link, ignore this email.</p>"
        "</body></html>",
        subtype="html",
    )
    try:
        if SMTP_PORT == 465:
            smtp_client = smtplib.SMTP_SSL(
                SMTP_HOST,
                SMTP_PORT,
                timeout=15,
                context=ssl.create_default_context(),
            )
        else:
            smtp_client = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        with smtp_client as smtp:
            if SMTP_PORT != 465 and SMTP_STARTTLS:
                smtp.starttls(context=ssl.create_default_context())
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(message)
        return True
    except Exception as exc:
        _log.error("Magic-link email delivery failed: %s", type(exc).__name__)
        return False


init_db()
init_passkeys_db()


@app.get(f"{API_PREFIX}/live")
def live():
    return with_service_metadata(
        {"status": "alive", "timestamp": _now_utc().isoformat()},
        SERVICE_NAME,
        VERSION,
    )


@app.get(f"{API_PREFIX}/ready")
def ready():
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
        return with_service_metadata(
            {"status": "ready", "db_path": DB_PATH},
            SERVICE_NAME,
            VERSION,
        )
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "dependency_not_ready", "message": "Auth database unavailable", "details": {"reason": str(exc)}}},
        )


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    return with_service_metadata(
        {"status": "healthy", "session_count": count},
        SERVICE_NAME,
        VERSION,
    )


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


def _require_service_trust(x_service_token: str | None) -> None:
    if not x_service_token or not secrets.compare_digest(x_service_token, INTERNAL_SERVICE_TOKEN):
        audit_auth_event("auth", "service_auth_failure", {"reason": "invalid_service_token"})
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


# Compatibility aliases for the Tier 1 draft paths. Both use the durable hashed-token flow below.
@app.post(f"{API_PREFIX}/auth/magiclink/request")
def magiclink_request_endpoint(payload: MagicLinkRequest):
    return request_magic_link(payload)


@app.get(f"{API_PREFIX}/auth/magiclink/claim")
def magiclink_claim_endpoint(token: str = "", email: str = ""):
    del email
    return verify_magic_link(token)


@app.post(f"{API_PREFIX}/auth/passkey/register/begin", response_model=PasskeyRegisterBeginResponse)
def passkey_register_begin_endpoint(
    payload: PasskeyRegisterBeginRequest,
    authorization: str | None = Header(default=None),
):
    _require_owner(authorization)
    if payload.email.casefold() not in OWNER_PASSKEY_EMAILS:
        raise HTTPException(status_code=403, detail={"error": {"code": "not_authorised", "message": "This email is not authorised for passkey registration"}})
    try:
        return passkey_register_begin(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": {"code": "passkey_register_begin_failed", "message": str(exc)}})


@app.post(f"{API_PREFIX}/auth/passkey/register/complete", response_model=PasskeyRegisterCompleteResponse)
def passkey_register_complete_endpoint(
    payload: PasskeyRegisterCompleteRequest,
    authorization: str | None = Header(default=None),
):
    _require_owner(authorization)
    try:
        result = passkey_register_complete(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": {"code": "passkey_register_complete_failed", "message": str(exc)}})
    _publish_event(
        event_type="auth.passkey.registered", producer="auth",
        entity_id=_redact_claim_identifier(f"passkey:{payload.user_id}"),
        payload={"credential_id": result.credential_id},
    )
    return result


@app.post(f"{API_PREFIX}/auth/passkey/signin/begin", response_model=PasskeySigninBeginResponse)
def passkey_signin_begin_endpoint(payload: PasskeySigninBeginRequest):
    try:
        return passkey_signin_begin(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": {"code": "passkey_signin_begin_failed", "message": str(exc)}})


@app.post(f"{API_PREFIX}/auth/passkey/signin/complete", response_model=AuthSessionResponse)
def passkey_signin_complete_endpoint(payload: PasskeySigninCompleteRequest):
    try:
        result = passkey_signin_complete(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": {"code": "passkey_signin_complete_failed", "message": str(exc)}})

    # Gate the SESSION's role, not just registration — defense in depth, matches OAuth callbacks:
    # registration already required an allowlisted email, but re-check here too so a future bug in
    # register_begin's gate can never silently grant Owner via a stale/leftover credential.
    if result.email.casefold() not in OWNER_PASSKEY_EMAILS:
        raise HTTPException(status_code=403, detail={"error": {"code": "not_authorised", "message": "This account is not authorised for owner access"}})

    subject = f"passkey:{result.user_id}"
    role = "Owner"
    scopes = _default_scopes(role)
    ttl = 8 * 3600
    token, exp = _issue_and_store_session(
        subject=subject, provider="passkey", email=result.email,
        tenant_id="", role=role, scopes=scopes, ttl_seconds=ttl,
    )
    audit_auth_event("auth", "passkey_signin", details={"subject": _redact_claim_identifier(subject), "role": role})
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": ttl,
        "claims": {"sub": subject, "tenant_id": "", "role": role, "scopes": scopes,
                    "exp": exp, "iss": AUTH_ISSUER, "aud": AUTH_AUDIENCE},
        "user": {"id": subject, "provider": "passkey", "email": result.email, "tenant_id": "",
                  "role": role, "scopes": scopes},
    }


@app.post(f"{API_PREFIX}/auth/session", response_model=AuthSessionResponse)
def create_session(
    payload: AuthSessionRequest,
    x_service_token: str | None = Header(default=None),
):
    _require_service_trust(x_service_token)
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

    role = (payload.role or "Resident").strip()
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "invalid_role", "message": "Role is not supported", "details": {"role": role}}},
        )
    if role == "Service" and payload.provider != "magic_link":
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "invalid_provider", "message": "Service role requires magic_link provider", "details": {}}},
        )
    tenant_id = (payload.tenant_id or "").strip()
    if role not in {"Owner", "Service"} and not tenant_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "missing_tenant_claim", "message": "tenant_id is required for this role", "details": {"role": role}}},
        )
    scopes = _resolve_scopes(role, payload.scopes)
    ttl = payload.expires_in if payload.expires_in is not None else AUTH_TOKEN_TTL_SECONDS
    ttl = max(300, min(int(ttl), 8 * 3600))
    audience = (payload.audience or AUTH_AUDIENCE).strip() or AUTH_AUDIENCE
    token, exp = _issue_and_store_session(
        subject=payload.subject,
        provider=payload.provider,
        email=payload.email or "",
        tenant_id=tenant_id,
        role=role,
        scopes=scopes,
        audience=audience,
        ttl_seconds=ttl,
    )

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": ttl,
        "claims": {
            "sub": payload.subject,
            "tenant_id": tenant_id,
            "role": role,
            "scopes": scopes,
            "exp": exp,
            "iss": AUTH_ISSUER,
            "aud": audience,
        },
        "user": {
            "id": payload.subject,
            "provider": payload.provider,
            "email": payload.email,
            "tenant_id": tenant_id,
            "role": role,
            "scopes": scopes,
        },
    }


@app.post(f"{API_PREFIX}/auth/introspect")
def introspect_session(payload: AuthIntrospectionRequest, x_service_token: str | None = Header(default=None)):
    _require_service_trust(x_service_token)

    try:
        _, jwt_claims = _decode_and_verify_token(payload.token)
    except HTTPException:
        return {"active": False}

    row = _session_for_token(payload.token)
    if not row:
        audit_auth_event("auth", "denied_access", {"reason": "session_not_found"})
        return {"active": False}
    if int(row["expires_at"]) <= int(_now_utc().timestamp()):
        audit_auth_event("auth", "expired_token", {"sub": row["subject"]})
        return {"active": False}
    if jwt_claims.get("sub") != row["subject"]:
        audit_auth_event("auth", "malformed_token", {"reason": "subject_mismatch"})
        return {"active": False}
    if (jwt_claims.get("tenant_id") or "") != (row["tenant_id"] or ""):
        audit_auth_event("auth", "tenant_mismatch", {"reason": "jwt_session_mismatch"})
        return {"active": False}
    if jwt_claims.get("role") != (row["role"] or "Resident"):
        audit_auth_event("auth", "role_escalation_attempt", {"reason": "jwt_session_mismatch"})
        return {"active": False}
    if (jwt_claims.get("iss") or "") != (row["issuer"] or AUTH_ISSUER):
        audit_auth_event("auth", "denied_access", {"reason": "issuer_mismatch"})
        return {"active": False}
    if (jwt_claims.get("aud") or "") != (row["audience"] or AUTH_AUDIENCE):
        audit_auth_event("auth", "denied_access", {"reason": "audience_mismatch"})
        return {"active": False}

    try:
        stored_scopes = json.loads(row["scopes_json"] or "[]")
    except json.JSONDecodeError:
        stored_scopes = []
    if sorted(stored_scopes) != sorted(jwt_claims.get("scopes") or []):
        audit_auth_event("auth", "role_escalation_attempt", {"reason": "scope_mismatch"})
        return {"active": False}
    role = row["role"] or "Resident"
    tenant_id = (row["tenant_id"] or "").strip()
    if role == "Resident":
        disallowed = {"tenant:write", "documents:write", "storage:write", "gpu:read", "ops:owner"}
        if disallowed.intersection(set(stored_scopes)):
            audit_auth_event("auth", "role_escalation_attempt", {"role": role, "scopes": stored_scopes})
            return {"active": False, "reason": "scope_role_violation"}

    return {
        "active": True,
        "claims": {
            "sub": row["subject"],
            "tenant_id": tenant_id,
            "role": role,
            "scopes": stored_scopes,
            "exp": row["expires_at"],
            "iss": row["issuer"] or AUTH_ISSUER,
            "aud": row["audience"] or AUTH_AUDIENCE,
            "provider": row["provider"],
        },
        "user": {
            "id": row["subject"],
            "provider": row["provider"],
            "email": row["email"],
            "tenant_id": tenant_id,
            "role": role,
            "scopes": stored_scopes,
        },
        "exp": row["expires_at"],
    }


def _require_owner(authorization: str | None) -> dict:
    """Verify the caller presents an ACTIVE Owner session; return the owner's JWT claims.

    Mirrors the owner-gate the diagnostics endpoint already uses: bearer present -> token verifies
    -> a stored session exists with role Owner and is not expired -> the JWT claim role is Owner.
    Raises 401 (missing / inactive session) or 403 (not Owner), exactly like the rest of the service.
    """
    if not authorization or not authorization.startswith("Bearer "):
        audit_auth_event("auth", "denied_access", {"reason": "missing_bearer"})
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Missing or invalid bearer token", "details": {}}},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        _, claims = _decode_and_verify_token(token)
    except HTTPException:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Session is not active", "details": {}}},
        )
    session = _session_for_token(token)
    if not session or (session["role"] or "") != "Owner":
        audit_auth_event("auth", "denied_access", {"reason": "owner_required"})
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "forbidden", "message": "Owner role required", "details": {}}},
        )
    if int(session["expires_at"]) <= int(_now_utc().timestamp()):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Session is not active", "details": {}}},
        )
    if claims.get("role") != "Owner":
        audit_auth_event("auth", "denied_access", {"reason": "owner_claim_required"})
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "forbidden", "message": "Owner role required", "details": {}}},
        )
    return claims


@app.get(f"{API_PREFIX}/auth/owner/allowlist")
def get_owner_allowlist(authorization: str | None = Header(default=None)):
    """Owner-only, READ-ONLY: the current owner-authentication allowlists (Tier 1.6).

    Returns the GitHub logins and Google / passkey / magic-link e-mail addresses permitted to
    authenticate as Owner, as loaded from the OWNER_* environment variables at startup. This
    endpoint never mutates the allowlists — runtime mutation is a separate, deliberate design
    decision (a persistent override store + hot-reload + a safeguard so the env-configured owner
    can never be locked out). The Admin Console reads this to display the live allowlists.
    """
    _require_owner(authorization)
    return {
        "github_logins": sorted(OWNER_GITHUB_LOGINS),
        "google_emails": sorted(OWNER_GOOGLE_EMAILS),
        "passkey_emails": sorted(OWNER_PASSKEY_EMAILS),
        "magic_emails": sorted(OWNER_MAGIC_EMAILS),
        "source": "environment (OWNER_* vars, loaded at startup)",
        "mutable_at_runtime": False,
    }


@app.post(f"{API_PREFIX}/auth/diagnostics/claims")
def diagnostic_claims(
    payload: AuthClaimsDiagnosticRequest,
    authorization: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
):
    if not AUTH_VERIFICATION_DIAGNOSTICS_ENABLED:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Endpoint not found", "details": {}}},
        )
    if not authorization or not authorization.startswith("Bearer "):
        audit_auth_event("auth", "denied_access", {"reason": "missing_bearer"})
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Missing or invalid bearer token", "details": {}}},
        )

    owner_token = authorization.split(" ", 1)[1].strip()
    try:
        _, owner_claims = _decode_and_verify_token(owner_token)
    except HTTPException:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Session is not active", "details": {}}},
        )
    owner_session = _session_for_token(owner_token)
    if not owner_session or (owner_session["role"] or "") != "Owner":
        audit_auth_event("auth", "denied_access", {"reason": "owner_required"})
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "forbidden", "message": "Owner role required", "details": {}}},
        )
    if int(owner_session["expires_at"]) <= int(_now_utc().timestamp()):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Session is not active", "details": {}}},
        )
    if owner_claims.get("role") != "Owner":
        audit_auth_event("auth", "denied_access", {"reason": "owner_claim_required"})
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "forbidden", "message": "Owner role required", "details": {}}},
        )

    target_token = (payload.token or owner_token).strip()
    audit_event_id = str(uuid4())
    request_id = (x_request_id or "").strip() or str(uuid4())
    decision = "denied"
    safe_claims: dict = {
        "sub": "",
        "tenant_id": "",
        "role": "",
        "scopes": [],
        "exp": None,
        "iss": "",
        "aud": "",
    }

    try:
        _, jwt_claims = _decode_and_verify_token(target_token)
        row = _session_for_token(target_token)
        if row and int(row["expires_at"]) > int(_now_utc().timestamp()):
            decision = "accepted"
            safe_claims = {
                "sub": row["subject"] or jwt_claims.get("sub") or "",
                "tenant_id": (row["tenant_id"] or "").strip() or (jwt_claims.get("tenant_id") or ""),
                "role": row["role"] or jwt_claims.get("role") or "",
                "scopes": json.loads(row["scopes_json"] or "[]"),
                "exp": row["expires_at"],
                "iss": row["issuer"] or jwt_claims.get("iss") or AUTH_ISSUER,
                "aud": row["audience"] or jwt_claims.get("aud") or AUTH_AUDIENCE,
            }
    except Exception:
        decision = "denied"

    diagnostic = {
        "subject": _redact_claim_identifier(safe_claims.get("sub") or ""),
        "role": safe_claims.get("role") or "",
        "tenant_id": _redact_claim_identifier(safe_claims.get("tenant_id") or ""),
        "accepted_scopes": sorted({str(scope) for scope in (safe_claims.get("scopes") or []) if str(scope).strip()}),
        "issuer": safe_claims.get("iss") or "",
        "audience": safe_claims.get("aud") or "",
        "expires_at": safe_claims.get("exp"),
        "authorization_decision": decision,
        "audit_event_id": audit_event_id,
        "request_id": request_id,
    }
    audit_auth_event(
        "auth",
        "diagnostic_claim_snapshot",
        {
            "audit_event_id": audit_event_id,
            "request_id": request_id,
            "authorization_decision": decision,
            "role": diagnostic["role"],
        },
    )
    return diagnostic


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
        return _error_page("GitHub sign-in was not completed.", log_detail=f"provider_error={error}", provider="github")
    if not code:
        return _error_page("No authorization code received from GitHub.", provider="github")
    if not _verify_oauth_state(state, "github"):
        return _error_page("Invalid OAuth state — please try signing in again.", provider="github")

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
            return _error_page("GitHub did not return an access token.", provider="github")
    except Exception as exc:
        return _error_page("Could not complete sign-in with GitHub — please try again.", log_detail=str(exc), provider="github")

    try:
        user_resp = _requests.get(
            "https://api.github.com/user",
            headers={"Authorization": "token " + gh_access_token, "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        user_resp.raise_for_status()
        gh_user = user_resp.json()
        login = (gh_user.get("login") or "").strip()
        email = (gh_user.get("email") or "").strip()
    except Exception as exc:
        return _error_page("Could not retrieve GitHub account information.", log_detail=str(exc), provider="github")

    if not login or login.casefold() not in OWNER_GITHUB_LOGINS:
        return _error_page("This GitHub account is not authorised for owner access.", provider="github")

    token, _ = _issue_and_store_session(
        subject=f"github:{login}",
        provider="github",
        email=email,
        tenant_id="",
        role="Owner",
        scopes=_default_scopes("Owner"),
        ttl_seconds=8 * 3600,
    )
    redirect_url = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/#token={urllib.parse.quote(token, safe='')}"
    return RedirectResponse(url=redirect_url)


# ── Owner sign-in providers ──────────────────────────────────────────────────

@app.get(f"{API_PREFIX}/auth/providers")
def owner_auth_providers():
    """Return public, non-secret sign-in capabilities for WordPress and Studio."""
    return {
        "google": {
            "available": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and OWNER_GOOGLE_EMAILS),
            "start_url": f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/google",
            "callback_uri": f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/google/callback",
        },
        "magic_email": {
            "available": MAGIC_EMAIL_CONFIGURED,
            "request_url": f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/magic-link",
            "verify_url": f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/magic-link/verify",
            "ttl_seconds": MAGIC_LINK_TTL_SECONDS,
        },
        "redirect_base": OAUTH_REDIRECT_BASE,
    }


_MAGIC_LINK_ACCEPTED = {
    "accepted": True,
    "message": "If that email is authorized, a sign-in link has been sent.",
}


@app.post(f"{API_PREFIX}/auth/magic-link")
def request_magic_link(payload: MagicLinkRequest):
    """Send an allowlisted owner a durable, single-use sign-in link."""
    if not MAGIC_EMAIL_CONFIGURED:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "provider_not_ready",
                    "message": "Magic email sign-in is not configured",
                }
            },
        )
    email = _normalise_email(payload.email)
    if not email:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "invalid_email", "message": "A valid email address is required"}},
        )
    if email not in OWNER_MAGIC_EMAILS:
        audit_auth_event("auth", "magic_link_requested", {"authorized": False})
        return JSONResponse(status_code=202, content=_MAGIC_LINK_ACCEPTED)

    issued = _create_magic_link(email)
    if not issued:
        audit_auth_event("auth", "magic_link_rate_limited", {"email": _redact_claim_identifier(email)})
        return JSONResponse(status_code=202, content=_MAGIC_LINK_ACCEPTED)
    token, _ = issued
    callback_url = (
        f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/magic-link/verify?"
        + urllib.parse.urlencode({"token": token})
    )
    delivered = _send_magic_email(email, callback_url)
    if not delivered:
        now = int(_now_utc().timestamp())
        with _db() as conn:
            conn.execute(
                "UPDATE magic_links SET used_at = ? WHERE token_hash = ? AND used_at IS NULL",
                (now, _magic_token_hash(token)),
            )
            conn.commit()
    audit_auth_event(
        "auth",
        "magic_link_requested",
        {"authorized": True, "delivered": delivered, "email": _redact_claim_identifier(email)},
    )
    return JSONResponse(status_code=202, content=_MAGIC_LINK_ACCEPTED)


@app.get(f"{API_PREFIX}/auth/magic-link/verify")
def verify_magic_link(token: str = ""):
    """Consume a magic link and issue an eight-hour owner session."""
    status, email = _consume_magic_link(token)
    if status == "expired":
        return _error_page("This sign-in link has expired. Request a new one.", provider="magic_link")
    if status != "ok":
        return _error_page("This sign-in link is invalid or has already been used.", provider="magic_link")
    if email not in OWNER_MAGIC_EMAILS:
        return _error_page("This email is no longer authorized for owner access.", provider="magic_link")
    session_token, _ = _issue_and_store_session(
        subject=f"magic:{email}",
        provider="magic_link",
        email=email,
        tenant_id="",
        role="Owner",
        scopes=_default_scopes("Owner"),
        ttl_seconds=8 * 3600,
    )
    redirect_url = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/#token={urllib.parse.quote(session_token, safe='')}"
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
        return _error_page("Google sign-in was not completed.", log_detail=f"provider_error={error}", provider="google")
    if not code:
        return _error_page("No authorization code received from Google.", provider="google")
    if not _verify_oauth_state(state, "google"):
        return _error_page("Invalid OAuth state — please try signing in again.", provider="google")

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
        return _error_page("Could not complete sign-in with Google — please try again.", log_detail=str(exc), provider="google")

    id_token_raw = token_data.get("id_token", "")
    if not id_token_raw:
        return _error_page("Google did not return identity information.", provider="google")
    try:
        verify_resp = _requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token_raw},
            timeout=10,
        )
        verify_resp.raise_for_status()
        id_payload = verify_resp.json()
        email = (id_payload.get("email") or "").strip()
        sub = (id_payload.get("sub") or "").strip()
        aud = (id_payload.get("aud") or "").strip()
        issuer = (id_payload.get("iss") or "").strip()
        email_verified = id_payload.get("email_verified")
        token_exp = int(id_payload.get("exp") or 0)
    except Exception as exc:
        return _error_page("Could not verify Google account — please try again.", log_detail=str(exc), provider="google")

    if not email or not sub:
        return _error_page("Google did not return the required account details.", provider="google")
    if aud != GOOGLE_CLIENT_ID:
        return _error_page("Google sign-in did not match this configured app.", provider="google")
    if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
        return _error_page("Google sign-in was issued by an unexpected authority.", provider="google")
    if email_verified is not True and str(email_verified).strip().lower() != "true":
        return _error_page("This Google account e-mail is not verified.", provider="google")
    if token_exp and token_exp <= int(_now_utc().timestamp()):
        return _error_page("Google sign-in expired before it could be completed.", provider="google")
    if not OWNER_GOOGLE_EMAILS or email.casefold() not in OWNER_GOOGLE_EMAILS:
        return _error_page("This Google account is not authorised for owner access.", provider="google")

    token, _ = _issue_and_store_session(
        subject=f"google:{sub}",
        provider="google",
        email=email,
        tenant_id="",
        role="Owner",
        scopes=_default_scopes("Owner"),
        ttl_seconds=8 * 3600,
    )
    redirect_url = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/#token={urllib.parse.quote(token, safe='')}"
    return RedirectResponse(url=redirect_url)


# ── OAuth configuration debug ─────────────────────────────────────────────────

@app.get(f"{API_PREFIX}/auth/debug")
def oauth_debug():
    """Return non-sensitive OAuth configuration status for debugging.

    No authentication is required because this endpoint is intentionally useful
    when sign-in is broken and no valid token exists yet.  It never exposes
    client secrets, signing keys, or the actual allowlist values.
    """
    return {
        "github": {
            "configured": bool(GITHUB_CLIENT_ID),
            "callback_uri": f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/github/callback",
        },
        "google": {
            "configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and OWNER_GOOGLE_EMAILS),
            "callback_uri": f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/google/callback",
        },
        "magic_email": {
            "configured": MAGIC_EMAIL_CONFIGURED,
            "smtp_configured": MAGIC_EMAIL_CONFIGURED,
            "ttl_seconds": MAGIC_LINK_TTL_SECONDS,
        },
        "redirect_base": OAUTH_REDIRECT_BASE,
        "owner_github_login_count": len(OWNER_GITHUB_LOGINS),
        "owner_google_email_count": len(OWNER_GOOGLE_EMAILS),
        "owner_magic_email_count": len(OWNER_MAGIC_EMAILS),
    }


# ── Silent token renewal ──────────────────────────────────────────────────────

class RenewRequest(BaseModel):
    """Renew an existing valid owner token without a full OAuth round-trip.

    The caller presents their current owner token.  If it is valid and
    carries the Owner role, a fresh token is issued with the same subject,
    provider, role, and scopes, resetting the expiry clock.  This keeps
    the Owner Console session alive without interrupting the owner's work.

    If the token is already expired the caller must complete a full OAuth
    redirect — there is no silent renewal path for expired tokens.
    """
    token: str


@app.post(f"{API_PREFIX}/auth/renew", response_model=AuthSessionResponse)
def renew_owner_token(payload: RenewRequest):
    """Silently renew a valid owner token.

    * Existing token must be valid (not expired) and have role == Owner.
    * Returns a new token with a fresh 8-hour expiry.
    * The old token remains valid until its original expiry — the caller
      should replace it in localStorage (king.ownerToken) with the new one.
    * If the token is expired: returns 401 — the console must redirect to OAuth.
    """
    token = (payload.token or "").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "token required"}},
        )

    try:
        _, claims = _decode_and_verify_token(token)
    except HTTPException:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Token expired or invalid — please sign in again"}},
        )

    if claims.get("role") != "Owner":
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "forbidden", "message": "Owner role required"}},
        )

    row = _session_for_token(token)
    if not row or int(row["expires_at"]) <= int(_now_utc().timestamp()):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "unauthorized", "message": "Session expired — please sign in again"}},
        )

    # Issue a fresh token, identical claims, new expiry.
    new_token, exp = _issue_and_store_session(
        subject=row["subject"] or claims["sub"],
        provider=row["provider"] or claims.get("provider", "unknown"),
        email=row["email"] or "",
        tenant_id=row["tenant_id"] or "",
        role="Owner",
        scopes=json.loads(row["scopes_json"] or "[]"),
        ttl_seconds=8 * 3600,
    )
    audit_auth_event("auth", "token_renewed", {"sub": _redact_claim_identifier(claims["sub"])})
    return {
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in": 8 * 3600,
        "claims": {
            "sub": claims["sub"],
            "role": "Owner",
            "exp": exp,
        },
    }
