"""services/connectors/registry.py — platform connector registry.

Provides:
  status_all()               → dict of platform → status card
  status(platform)           → single status card
  refresh(platform)          → attempt silent token refresh; returns True on success
  authorize_url(platform, …) → OAuth authorization URL (redirect to platform)
  store_callback_tokens(…)   → persist tokens received from OAuth callback

Each platform entry defines:
  client_id / client_secret env vars
  authorize_url template
  token_url for code→token and refresh→token exchanges
  default scopes

Fail-closed everywhere: missing credentials, network errors, or unexpected
API responses all leave the token in its current (or needs_auth) state and
return False / raise a descriptive exception.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

_log = logging.getLogger(__name__)

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

from services.connectors.token_store import (
    PLATFORMS,
    get_token,
    revoke_token,
    status_card,
    token_status,
    upsert_token,
)

# ── Platform definitions ──────────────────────────────────────────────────────
# Each entry describes the OAuth flow for one publishing platform.
# Credentials are read from environment variables (set in .env.v2 / docker secrets).
#
# wordpress uses Application Passwords (Basic Auth), not OAuth — the token_url
# is the WP REST API root and "refresh" is a no-op (app passwords don't expire).

_PLATFORM_META: dict[str, dict] = {
    "wordpress": {
        "icon": "🔵",
        "label": "WordPress",
        "auth_type": "app_password",   # Basic auth — no OAuth redirect needed
        "token_env": "WP_APP_PASSWORD",
        "user_env": "WP_APP_USER",
        "site_env": "WP_SITE_URL",
        "token_url": None,
        "authorize_template": None,
        "scopes": [],
    },
    "youtube": {
        "icon": "▶️",
        "label": "YouTube",
        "auth_type": "oauth2",
        "client_id_env": "YOUTUBE_CLIENT_ID",
        "client_secret_env": "YOUTUBE_CLIENT_SECRET",
        "authorize_template": (
            "https://accounts.google.com/o/oauth2/v2/auth"
            "?client_id={client_id}&redirect_uri={redirect_uri}"
            "&response_type=code&scope={scope}&access_type=offline&prompt=consent"
        ),
        "token_url": "https://oauth2.googleapis.com/token",
        "revoke_url": "https://oauth2.googleapis.com/revoke",
        "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
    },
    "tiktok": {
        "icon": "🎵",
        "label": "TikTok",
        "auth_type": "oauth2",
        "client_id_env": "TIKTOK_CLIENT_KEY",
        "client_secret_env": "TIKTOK_CLIENT_SECRET",
        "authorize_template": (
            "https://www.tiktok.com/v2/auth/authorize/"
            "?client_key={client_id}&redirect_uri={redirect_uri}"
            "&response_type=code&scope={scope}"
        ),
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
        "scopes": ["video.upload", "video.publish"],
    },
    "facebook": {
        "icon": "📘",
        "label": "Facebook / Meta",
        "auth_type": "oauth2",
        "client_id_env": "FACEBOOK_APP_ID",
        "client_secret_env": "FACEBOOK_APP_SECRET",
        "authorize_template": (
            "https://www.facebook.com/v19.0/dialog/oauth"
            "?client_id={client_id}&redirect_uri={redirect_uri}"
            "&response_type=code&scope={scope}"
        ),
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "scopes": ["pages_manage_posts", "pages_read_engagement"],
    },
    "linkedin": {
        "icon": "💼",
        "label": "LinkedIn",
        "auth_type": "oauth2",
        "client_id_env": "LINKEDIN_CLIENT_ID",
        "client_secret_env": "LINKEDIN_CLIENT_SECRET",
        "authorize_template": (
            "https://www.linkedin.com/oauth/v2/authorization"
            "?client_id={client_id}&redirect_uri={redirect_uri}"
            "&response_type=code&scope={scope}"
        ),
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "scopes": ["w_member_social", "r_liteprofile"],
    },
}


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


# ── Public API ────────────────────────────────────────────────────────────────

def status_all() -> dict[str, dict]:
    """Return a status card for every known platform."""
    return {p: status_card(p) for p in PLATFORMS}


def status(platform: str) -> dict:
    """Return the status card for one platform."""
    _assert_known(platform)
    return status_card(platform)


def refresh(platform: str) -> bool:
    """Attempt a silent token refresh for the given platform.

    Returns True if the token is now valid, False otherwise.
    WordPress app passwords never expire — this is always a no-op returning
    True if credentials are stored.
    """
    _assert_known(platform)
    meta = _PLATFORM_META[platform]

    if meta["auth_type"] == "app_password":
        # WordPress app passwords don't expire; if we have a token it's valid.
        return token_status(platform) in ("valid",)

    row = get_token(platform)
    if not row or not row.get("refresh_token"):
        _log.info("connector.refresh %s: no refresh token stored", platform)
        return False

    if not _REQUESTS_AVAILABLE:
        _log.warning("connector.refresh %s: requests library not available", platform)
        return False

    client_id = os.environ.get(meta["client_id_env"], "")
    client_secret = os.environ.get(meta["client_secret_env"], "")
    if not client_id or not client_secret:
        _log.warning("connector.refresh %s: missing client credentials", platform)
        return False

    token_url = meta["token_url"]
    try:
        resp = _requests.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": row["refresh_token"],
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except Exception as exc:
        _log.warning("connector.refresh %s: HTTP error: %s", platform, exc)
        return False

    access_token = data.get("access_token")
    if not access_token:
        _log.warning("connector.refresh %s: no access_token in response", platform)
        return False

    expires_in = data.get("expires_in")
    expires_at = (_now_ts() + int(expires_in)) if expires_in else None
    new_refresh = data.get("refresh_token") or row["refresh_token"]

    upsert_token(
        platform,
        access_token=access_token,
        refresh_token=new_refresh,
        expires_at=expires_at,
        scopes=row.get("scopes"),
        account_id=row.get("account_id"),
        account_label=row.get("account_label"),
    )
    _log.info("connector.refresh %s: success", platform)
    return True


def ensure_valid(platform: str) -> tuple[bool, str]:
    """Ensure a platform token is valid, refreshing silently if needed.

    Returns (is_valid, reason) where reason is one of:
      "valid"        — token is ready to use
      "refreshed"    — was refreshable; silent refresh succeeded
      "needs_auth"   — no token or refresh failed; owner must re-authorize
    """
    _assert_known(platform)
    s = token_status(platform)
    if s == "valid":
        return True, "valid"
    if s == "refreshable":
        ok = refresh(platform)
        if ok:
            return True, "refreshed"
        return False, "needs_auth"
    return False, "needs_auth"


def authorize_url(platform: str, redirect_uri: str, state: str = "") -> str:
    """Build the OAuth authorization URL for the platform.

    The caller (v2/app/main.py) redirects the browser to this URL.
    WordPress uses app passwords — this returns an empty string; the
    console should prompt for username + app-password instead.
    """
    _assert_known(platform)
    meta = _PLATFORM_META[platform]
    if meta["auth_type"] == "app_password":
        return ""

    client_id = os.environ.get(meta["client_id_env"], "")
    if not client_id:
        raise ValueError(f"Missing {meta['client_id_env']} — configure it in .env.v2")

    scope = "%20".join(meta["scopes"])
    url = meta["authorize_template"].format(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
    )
    if state:
        url += f"&state={state}"
    return url


def exchange_code(platform: str, code: str, redirect_uri: str) -> dict:
    """Exchange an authorization code for tokens and store them.

    Returns the stored status card on success, raises ValueError on failure.
    """
    _assert_known(platform)
    meta = _PLATFORM_META[platform]
    if meta["auth_type"] == "app_password":
        raise ValueError("WordPress uses app passwords, not authorization codes")

    if not _REQUESTS_AVAILABLE:
        raise RuntimeError("requests library not available")

    client_id = os.environ.get(meta["client_id_env"], "")
    client_secret = os.environ.get(meta["client_secret_env"], "")
    if not client_id or not client_secret:
        raise ValueError(f"Missing credentials for {platform}")

    resp = _requests.post(
        meta["token_url"],
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()

    access_token = data.get("access_token")
    if not access_token:
        raise ValueError(f"No access_token in response from {platform}: {data}")

    expires_in = data.get("expires_in")
    expires_at = (_now_ts() + int(expires_in)) if expires_in else None

    upsert_token(
        platform,
        access_token=access_token,
        refresh_token=data.get("refresh_token"),
        expires_at=expires_at,
        scopes=data.get("scope", "").split() if isinstance(data.get("scope"), str) else meta["scopes"],
    )
    return status_card(platform)


def store_app_password(
    platform: str = "wordpress",
    *,
    username: str,
    app_password: str,
    site_url: str | None = None,
) -> dict:
    """Store WordPress application-password credentials.

    app_password should be the raw application password (spaces OK; stored as-is).
    """
    if platform != "wordpress":
        raise ValueError("store_app_password is only for WordPress")
    import base64 as _b64
    # Store as Basic-auth credential: base64(username:password) in access_token field.
    credential = _b64.b64encode(f"{username}:{app_password}".encode()).decode()
    upsert_token(
        "wordpress",
        access_token=credential,
        refresh_token=None,
        expires_at=None,       # app passwords don't expire
        scopes=["posts:write"],
        account_id=username,
        account_label=site_url or os.environ.get("WP_SITE_URL", ""),
    )
    return status_card("wordpress")


def platform_meta(platform: str) -> dict:
    """Return display metadata (icon, label) for a platform."""
    _assert_known(platform)
    m = _PLATFORM_META[platform]
    return {
        "platform": platform,
        "icon": m["icon"],
        "label": m["label"],
        "auth_type": m["auth_type"],
    }


def all_platform_meta() -> list[dict]:
    return [platform_meta(p) for p in PLATFORMS]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _assert_known(platform: str) -> None:
    if platform not in _PLATFORM_META:
        raise ValueError(f"Unknown platform '{platform}'. Known: {list(_PLATFORM_META)}")
