"""
services/auth/app/magiclinks.py — passwordless email sign-in (Magic Links), Tier 1.4.

Flow:
  POST /api/v2/auth/magiclink/request  {email}  -> if the email is an allowlisted owner AND SMTP is
        configured, emails a one-time 15-minute link. Response is ALWAYS {"status":"check_email"} —
        never reveals whether an email is allowlisted (enumeration-safe).
  GET  /api/v2/auth/magiclink/claim?token=..&email=..  -> verifies the one-time token, then redirects
        the browser to OAUTH_REDIRECT_BASE#token=<jwt>. main.py mints the JWT (single source of session
        issuance); this module only verifies the link and reports the email back.

BUILT 2026-07-15 (audit-quad-os) against the same real patterns as the existing GitHub/Google OAuth +
Passkeys: fail-closed owner allowlist, DB path shared with main.py, SMTP config read at call time so a
missing credential returns a clean 501 instead of crashing (mirrors how burst-pricing/uipa_autosend stay
inert until the owner fills the secret). Fixes over the draft in TIER_1_CONTINUATION.md:
  - endpoints take a Pydantic model, not a raw `str` body param (FastAPI treats a bare `str` param as a
    QUERY param, so the draft's POST body would never have bound);
  - token is single-use AND time-checked (delete-on-claim) — the draft deleted only on the happy path;
  - the token row is looked up by (token, email) BOTH, so a token can't be replayed against a different
    email.
"""
import os
import secrets
import smtplib
import sqlite3
import urllib.parse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from pydantic import BaseModel

DB_PATH = os.environ.get("AUTH_DB_PATH", "/tmp/govos_v2_auth.db")   # SAME as main.py
TOKEN_TTL_MINUTES = 15


def _cfg():
    """Read SMTP + link config at call time (so an owner filling secrets doesn't need a code change)."""
    return {
        "smtp_host": os.environ.get("SMTP_HOST", ""),
        "smtp_port": int(os.environ.get("SMTP_PORT", "587") or "587"),
        "smtp_user": os.environ.get("SMTP_USER", ""),
        "smtp_pass": os.environ.get("SMTP_PASS", ""),
        "smtp_from": os.environ.get("SMTP_FROM", "noreply@12sgi.com"),
        "auth_public_url": os.environ.get("AUTH_PUBLIC_URL", "https://auth.12sgi.com"),
    }


def smtp_configured() -> bool:
    c = _cfg()
    return bool(c["smtp_host"] and c["smtp_user"] and c["smtp_pass"])


class MagicLinkRequest(BaseModel):
    email: str


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_magiclinks_db() -> None:
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS magic_link_tokens (
                token TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        conn.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def send_magic_link(email: str) -> None:
    """Create a one-time token and email the claim link. Assumes the caller already checked the
    allowlist + smtp_configured(). Raises on SMTP failure so the endpoint can surface a 503."""
    c = _cfg()
    token = secrets.token_urlsafe(32)
    now = _now()
    with _db() as conn:
        conn.execute("DELETE FROM magic_link_tokens WHERE datetime(expires_at) < datetime('now')")
        conn.execute(
            "INSERT INTO magic_link_tokens (token, email, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, email, now.isoformat(), (now + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat()),
        )
        conn.commit()

    claim_url = (f"{c['auth_public_url'].rstrip('/')}/api/v2/auth/magiclink/claim"
                 f"?token={urllib.parse.quote(token)}&email={urllib.parse.quote(email)}")
    body = (f"Click here to sign in to govOS:\n\n{claim_url}\n\n"
            f"This link expires in {TOKEN_TTL_MINUTES} minutes and can be used once.\n"
            f"If you did not request this, you can ignore this email.")
    msg = MIMEText(body, "plain")
    msg["From"] = c["smtp_from"]
    msg["To"] = email
    msg["Subject"] = "Your govOS Sign-In Link"

    with smtplib.SMTP(c["smtp_host"], c["smtp_port"], timeout=15) as server:
        server.starttls()
        server.login(c["smtp_user"], c["smtp_pass"])
        server.send_message(msg)


def claim_token(token: str, email: str) -> str | None:
    """Verify + consume a magic-link token. Returns the email on success, None on any failure
    (not found / wrong email / expired). Single-use: the row is deleted whether or not it was valid,
    so a token can never be replayed."""
    with _db() as conn:
        row = conn.execute(
            "SELECT token, email, expires_at FROM magic_link_tokens WHERE token = ? AND email = ?",
            (token, email),
        ).fetchone()
        # consume unconditionally (defense against timing/replay) if the token string exists at all
        conn.execute("DELETE FROM magic_link_tokens WHERE token = ?", (token,))
        conn.commit()
    if not row:
        return None
    try:
        if datetime.fromisoformat(row["expires_at"]) < _now():
            return None
    except (ValueError, TypeError):
        return None
    return row["email"]
