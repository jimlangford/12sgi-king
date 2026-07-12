"""services/connectors/token_store.py — SQLite-backed per-platform OAuth token store.

Stores access tokens, refresh tokens, expiry, and scopes for each publishing
platform (wordpress, youtube, tiktok, facebook, linkedin).  The store is
local-only (never synced to GitHub or any cloud surface) and lives alongside
the other v2 databases in the DATA_DIR volume.

Token status semantics
  valid        — access token present, not expired (or no expiry set)
  refreshable  — access token expired but refresh token present
  needs_auth   — no token at all, or both expired with no refresh token
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

_DB_PATH = Path(os.environ.get("CONNECTOR_TOKEN_DB", "/tmp/govos_v2_connectors.db"))

TokenStatus = Literal["valid", "refreshable", "needs_auth"]

PLATFORMS = ("wordpress", "youtube", "tiktok", "facebook", "linkedin")


# ── DB bootstrap ──────────────────────────────────────────────────────────────

def _init_db(path: Path = _DB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS platform_tokens (
                platform       TEXT PRIMARY KEY,
                access_token   TEXT,
                refresh_token  TEXT,
                expires_at     INTEGER,
                scopes_json    TEXT DEFAULT '[]',
                account_id     TEXT,
                account_label  TEXT,
                updated_at     INTEGER NOT NULL
            )
        """)
        conn.commit()


_init_db()


@contextmanager
def _db(path: Path = _DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── Token CRUD ────────────────────────────────────────────────────────────────

def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def upsert_token(
    platform: str,
    *,
    access_token: str,
    refresh_token: str | None = None,
    expires_at: int | None = None,
    scopes: list[str] | None = None,
    account_id: str | None = None,
    account_label: str | None = None,
    db_path: Path = _DB_PATH,
) -> None:
    """Store or replace the OAuth tokens for a platform."""
    with _db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO platform_tokens
                (platform, access_token, refresh_token, expires_at, scopes_json,
                 account_id, account_label, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform) DO UPDATE SET
                access_token  = excluded.access_token,
                refresh_token = COALESCE(excluded.refresh_token, refresh_token),
                expires_at    = excluded.expires_at,
                scopes_json   = excluded.scopes_json,
                account_id    = COALESCE(excluded.account_id, account_id),
                account_label = COALESCE(excluded.account_label, account_label),
                updated_at    = excluded.updated_at
            """,
            (
                platform,
                access_token,
                refresh_token,
                expires_at,
                json.dumps(scopes or []),
                account_id,
                account_label,
                _now_ts(),
            ),
        )
        conn.commit()


def get_token(platform: str, db_path: Path = _DB_PATH) -> dict | None:
    """Return the stored token row for a platform, or None if not present."""
    with _db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM platform_tokens WHERE platform = ?", (platform,)
        ).fetchone()
    if row is None:
        return None
    return {
        "platform": row["platform"],
        "access_token": row["access_token"],
        "refresh_token": row["refresh_token"],
        "expires_at": row["expires_at"],
        "scopes": json.loads(row["scopes_json"] or "[]"),
        "account_id": row["account_id"],
        "account_label": row["account_label"],
        "updated_at": row["updated_at"],
    }


def revoke_token(platform: str, db_path: Path = _DB_PATH) -> None:
    """Remove all stored tokens for a platform (forces re-auth)."""
    with _db(db_path) as conn:
        conn.execute("DELETE FROM platform_tokens WHERE platform = ?", (platform,))
        conn.commit()


# ── Status helpers ────────────────────────────────────────────────────────────

def token_status(platform: str, db_path: Path = _DB_PATH) -> TokenStatus:
    """Return the current token status for a platform."""
    row = get_token(platform, db_path=db_path)
    if row is None or not row.get("access_token"):
        return "needs_auth"
    expires_at = row.get("expires_at")
    now = _now_ts()
    # No expiry set → treat as valid (e.g. WordPress app passwords never expire).
    if expires_at is None or expires_at > now:
        return "valid"
    # Expired — do we have a refresh token?
    if row.get("refresh_token"):
        return "refreshable"
    return "needs_auth"


def status_card(platform: str, db_path: Path = _DB_PATH) -> dict:
    """Return a full status card for a platform suitable for the console UI."""
    row = get_token(platform, db_path=db_path)
    status = token_status(platform, db_path=db_path)
    now = _now_ts()
    expires_at = (row or {}).get("expires_at")
    return {
        "platform": platform,
        "status": status,
        "account_id": (row or {}).get("account_id"),
        "account_label": (row or {}).get("account_label"),
        "expires_at": expires_at,
        "expires_in_seconds": max(0, expires_at - now) if expires_at else None,
        "has_refresh_token": bool((row or {}).get("refresh_token")),
        "scopes": (row or {}).get("scopes") or [],
        "updated_at": (row or {}).get("updated_at"),
    }
