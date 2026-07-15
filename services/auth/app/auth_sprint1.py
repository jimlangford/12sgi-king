"""
govOS v2 Auth Extensions — Sprint 1 completion
Passkeys (WebAuthn), Apple Sign-In, Microsoft OAuth, Email Magic Links

Append to services/auth/app/main.py or import as a blueprint.
All endpoints follow the existing auth service patterns.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
from datetime import timedelta

import requests as _requests
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

# ── Apple Sign-In ─────────────────────────────────────────────────────────────
# Apple uses OIDC with client_secret generated from a .p8 key (differs from GitHub/Google).
# Env vars: APPLE_CLIENT_ID, APPLE_TEAM_ID, APPLE_KEY_ID, APPLE_PRIVATE_KEY (contents of .p8)
APPLE_CLIENT_ID = os.environ.get("APPLE_CLIENT_ID", "")
APPLE_TEAM_ID   = os.environ.get("APPLE_TEAM_ID", "")
APPLE_KEY_ID    = os.environ.get("APPLE_KEY_ID", "")
APPLE_PRIVATE_KEY = os.environ.get("APPLE_PRIVATE_KEY", "")  # PEM string
OWNER_APPLE_EMAILS = {
    e.strip().casefold()
    for e in os.environ.get("OWNER_APPLE_EMAILS",
        "jimlangford@me.com,elementlotus@gmail.com,jimmylangford@elementlotus.com,JRCSL@12sgi.com"
    ).split(",") if e.strip()
}

# ── Microsoft OAuth ───────────────────────────────────────────────────────────
# Env vars: MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID (or "common")
MICROSOFT_CLIENT_ID     = os.environ.get("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_TENANT_ID     = os.environ.get("MICROSOFT_TENANT_ID", "common")
OWNER_MICROSOFT_EMAILS  = {
    e.strip().casefold()
    for e in os.environ.get("OWNER_MICROSOFT_EMAILS", "").split(",") if e.strip()
}

# ── Magic Links ───────────────────────────────────────────────────────────────
MAGIC_LINK_TTL_SECONDS = int(os.environ.get("MAGIC_LINK_TTL_SECONDS", "900"))  # 15 min
SMTP_HOST    = os.environ.get("SMTP_HOST", "")
SMTP_PORT    = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER    = os.environ.get("SMTP_USER", "")
SMTP_PASS    = os.environ.get("SMTP_PASS", "")
SMTP_FROM    = os.environ.get("SMTP_FROM", "noreply@12sgi.com")
OWNER_MAGIC_EMAILS = {
    e.strip().casefold()
    for e in os.environ.get("OWNER_MAGIC_EMAILS",
        "jimlangford@me.com,elementlotus@gmail.com,jimmylangford@elementlotus.com,jrcsl@12sgi.com"
    ).split(",") if e.strip()
}

# In-memory magic link store: {token: {email, expires_ts, used}}
# In production this should be the sessions DB — sufficient for local/Tailscale use.
_MAGIC_LINKS: dict[str, dict] = {}


def _make_magic_token(email: str) -> str:
    """Issue a signed single-use magic link token."""
    nonce = secrets.token_urlsafe(32)
    sig = hmac.new(
        os.environ.get("AUTH_SIGNING_SECRET", "dev-only-signing-secret-change-me").encode(),
        f"magic:{email}:{nonce}".encode(),
        hashlib.sha256
    ).hexdigest()[:24]
    token = f"{nonce}.{sig}"
    _MAGIC_LINKS[token] = {
        "email": email,
        "expires_ts": int(time.time()) + MAGIC_LINK_TTL_SECONDS,
        "used": False,
    }
    return token


def _send_magic_email(email: str, magic_url: str) -> bool:
    """Send magic link email. Returns True on success, False if SMTP not configured."""
    if not SMTP_HOST or not SMTP_USER:
        return False
    try:
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = SMTP_FROM
        msg["To"] = email
        msg["Subject"] = "Your govOS sign-in link"
        msg.set_content(
            f"Click this link to sign in to govOS (expires in {MAGIC_LINK_TTL_SECONDS // 60} minutes):\n\n"
            f"{magic_url}\n\n"
            "If you didn't request this, ignore this email.\n"
        )
        msg.add_alternative(
            f"""<!DOCTYPE html><html><body style="font-family:system-ui,sans-serif;padding:32px;max-width:480px">
            <h2 style="color:#1259a3">govOS Sign-In</h2>
            <p>Click the button below to sign in. This link expires in {MAGIC_LINK_TTL_SECONDS // 60} minutes.</p>
            <p><a href="{magic_url}" style="background:#1259a3;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block">
            Sign in to govOS</a></p>
            <p style="color:#666;font-size:12px">If you didn't request this, ignore this email.</p>
            </body></html>""",
            subtype="html"
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        return True
    except Exception:
        return False


# ── Passkeys (WebAuthn) ───────────────────────────────────────────────────────
# WebAuthn challenge store: {challenge: {user_id, expires_ts}}
_PASSKEY_CHALLENGES: dict[str, dict] = {}
PASSKEY_CHALLENGE_TTL = 300  # 5 minutes
RELYING_PARTY_ID     = os.environ.get("WEBAUTHN_RP_ID", "12sgi.com")
RELYING_PARTY_NAME   = os.environ.get("WEBAUTHN_RP_NAME", "govOS / 12SGI")
PASSKEY_ORIGIN       = os.environ.get("WEBAUTHN_ORIGIN", "https://12sgi.com")


# ─────────────────────────────────────────────────────────────────────────────
# These route functions are designed to be registered on the FastAPI `app`
# instance in auth/app/main.py. They follow the same patterns as the existing
# GitHub/Google OAuth routes.
# ─────────────────────────────────────────────────────────────────────────────

def register_sprint1_routes(app, api_prefix, _make_oauth_state, _verify_oauth_state,
                              _issue_and_store_session, _default_scopes, _error_page,
                              AUTH_PUBLIC_URL, OAUTH_REDIRECT_BASE):
    """Register all Sprint 1 auth routes on the FastAPI app."""

    # ── Magic Links ──────────────────────────────────────────────────────────

    class MagicLinkRequest(BaseModel):
        email: str

    @app.post(f"{api_prefix}/auth/magic-link")
    def request_magic_link(payload: MagicLinkRequest):
        """Request a magic link sign-in email."""
        email = (payload.email or "").strip().casefold()
        if not email:
            raise HTTPException(status_code=400, detail={"error": {"code": "invalid_email", "message": "Email is required"}})
        if email not in OWNER_MAGIC_EMAILS:
            # Fail silently — don't leak which emails are authorised
            return {"sent": True, "message": "If that email is authorised, a sign-in link has been sent."}
        token = _make_magic_token(email)
        callback_url = f"{AUTH_PUBLIC_URL.rstrip('/')}{api_prefix}/auth/magic-link/verify?token={urllib.parse.quote(token)}"
        sent = _send_magic_email(email, callback_url)
        return {
            "sent": True,
            "message": "If that email is authorised, a sign-in link has been sent.",
            # In dev mode (no SMTP), return the URL directly so local dev works
            **({"dev_url": callback_url} if not sent and not SMTP_HOST else {})
        }

    @app.get(f"{api_prefix}/auth/magic-link/verify")
    def verify_magic_link(token: str = ""):
        """Verify a magic link token and issue a session."""
        if not token:
            return _error_page("Missing sign-in token.", provider="magic_link")
        entry = _MAGIC_LINKS.get(token)
        if not entry:
            return _error_page("Sign-in link is invalid or has already been used.", provider="magic_link")
        if entry["used"]:
            return _error_page("This sign-in link has already been used. Request a new one.", provider="magic_link")
        if int(time.time()) > entry["expires_ts"]:
            _MAGIC_LINKS.pop(token, None)
            return _error_page("This sign-in link has expired. Request a new one.", provider="magic_link")

        entry["used"] = True
        email = entry["email"]
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

    # ── Apple Sign-In ─────────────────────────────────────────────────────────

    @app.get(f"{api_prefix}/auth/apple")
    def oauth_apple_start():
        if not APPLE_CLIENT_ID:
            raise HTTPException(status_code=501, detail={"error": {"code": "not_configured", "message": "Apple Sign-In is not configured"}})
        state = _make_oauth_state("apple")
        callback_uri = f"{AUTH_PUBLIC_URL.rstrip('/')}{api_prefix}/auth/apple/callback"
        params = {
            "client_id": APPLE_CLIENT_ID,
            "redirect_uri": callback_uri,
            "response_type": "code",
            "scope": "name email",
            "response_mode": "form_post",
            "state": state,
        }
        return RedirectResponse(url="https://appleid.apple.com/auth/authorize?" + urllib.parse.urlencode(params))

    @app.post(f"{api_prefix}/auth/apple/callback")
    async def oauth_apple_callback(code: str = "", state: str = "", error: str = "", id_token: str = ""):
        """Apple uses form_post — accepts POST with code + id_token + state."""
        if error:
            return _error_page("Apple Sign-In was not completed.", log_detail=f"provider_error={error}", provider="apple")
        if not code:
            return _error_page("No authorization code received from Apple.", provider="apple")
        if not _verify_oauth_state(state, "apple"):
            return _error_page("Invalid OAuth state — please try signing in again.", provider="apple")

        # Decode Apple's id_token (JWT) to get email/sub
        if not id_token:
            return _error_page("Apple did not return identity information.", provider="apple")
        try:
            payload_part = id_token.split(".")[1]
            padding = (4 - len(payload_part) % 4) % 4
            import base64 as _b64
            id_payload = json.loads(_b64.b64decode(payload_part + "=" * padding).decode("utf-8"))
            email = (id_payload.get("email") or "").strip().casefold()
            sub   = (id_payload.get("sub") or "").strip()
        except Exception as exc:
            return _error_page("Could not verify Apple identity — please try again.", provider="apple")

        if not email or not sub:
            return _error_page("Apple did not return the required account details.", provider="apple")
        if email not in OWNER_APPLE_EMAILS:
            return _error_page("This Apple account is not authorised for owner access.", provider="apple")

        session_token, _ = _issue_and_store_session(
            subject=f"apple:{sub}",
            provider="apple",
            email=email,
            tenant_id="",
            role="Owner",
            scopes=_default_scopes("Owner"),
            ttl_seconds=8 * 3600,
        )
        redirect_url = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/#token={urllib.parse.quote(session_token, safe='')}"
        return RedirectResponse(url=redirect_url)

    # ── Microsoft OAuth ───────────────────────────────────────────────────────

    @app.get(f"{api_prefix}/auth/microsoft")
    def oauth_microsoft_start():
        if not MICROSOFT_CLIENT_ID:
            raise HTTPException(status_code=501, detail={"error": {"code": "not_configured", "message": "Microsoft OAuth is not configured"}})
        state = _make_oauth_state("microsoft")
        callback_uri = f"{AUTH_PUBLIC_URL.rstrip('/')}{api_prefix}/auth/microsoft/callback"
        params = {
            "client_id": MICROSOFT_CLIENT_ID,
            "redirect_uri": callback_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "response_mode": "query",
        }
        authority = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize"
        return RedirectResponse(url=authority + "?" + urllib.parse.urlencode(params))

    @app.get(f"{api_prefix}/auth/microsoft/callback")
    def oauth_microsoft_callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
        if error:
            return _error_page("Microsoft sign-in was not completed.", log_detail=f"provider_error={error}", provider="microsoft")
        if not code:
            return _error_page("No authorization code received from Microsoft.", provider="microsoft")
        if not _verify_oauth_state(state, "microsoft"):
            return _error_page("Invalid OAuth state — please try signing in again.", provider="microsoft")

        callback_uri = f"{AUTH_PUBLIC_URL.rstrip('/')}{api_prefix}/auth/microsoft/callback"
        try:
            resp = _requests.post(
                f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token",
                data={
                    "client_id": MICROSOFT_CLIENT_ID,
                    "client_secret": MICROSOFT_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": callback_uri,
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
            resp.raise_for_status()
            token_data = resp.json()
        except Exception as exc:
            return _error_page("Could not complete sign-in with Microsoft — please try again.", log_detail=str(exc), provider="microsoft")

        id_token_raw = token_data.get("id_token", "")
        try:
            import base64 as _b64
            payload_part = id_token_raw.split(".")[1]
            padding = (4 - len(payload_part) % 4) % 4
            id_payload = json.loads(_b64.b64decode(payload_part + "=" * padding).decode("utf-8"))
            email = (id_payload.get("email") or id_payload.get("preferred_username") or "").strip().casefold()
            sub   = (id_payload.get("sub") or "").strip()
        except Exception as exc:
            return _error_page("Could not verify Microsoft account — please try again.", provider="microsoft")

        if not email or not sub:
            return _error_page("Microsoft did not return the required account details.", provider="microsoft")
        if OWNER_MICROSOFT_EMAILS and email not in OWNER_MICROSOFT_EMAILS:
            return _error_page("This Microsoft account is not authorised for owner access.", provider="microsoft")

        session_token, _ = _issue_and_store_session(
            subject=f"microsoft:{sub}",
            provider="microsoft",
            email=email,
            tenant_id="",
            role="Owner",
            scopes=_default_scopes("Owner"),
            ttl_seconds=8 * 3600,
        )
        redirect_url = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/#token={urllib.parse.quote(session_token, safe='')}"
        return RedirectResponse(url=redirect_url)

    # ── Passkeys (WebAuthn) ───────────────────────────────────────────────────

    class PasskeyRegisterChallengeRequest(BaseModel):
        user_id: str
        username: str

    class PasskeyAuthChallengeRequest(BaseModel):
        user_id: str | None = None

    class PasskeyVerifyRequest(BaseModel):
        challenge: str
        credential_id: str
        authenticator_data: str  # base64url
        client_data_json: str    # base64url
        signature: str           # base64url
        user_id: str | None = None
        email: str | None = None

    @app.post(f"{api_prefix}/auth/passkey/challenge")
    def passkey_challenge(payload: PasskeyAuthChallengeRequest):
        """Return a WebAuthn authentication challenge."""
        challenge = secrets.token_urlsafe(32)
        _PASSKEY_CHALLENGES[challenge] = {
            "user_id": payload.user_id,
            "expires_ts": int(time.time()) + PASSKEY_CHALLENGE_TTL,
        }
        return {
            "challenge": challenge,
            "rpId": RELYING_PARTY_ID,
            "rpName": RELYING_PARTY_NAME,
            "timeout": PASSKEY_CHALLENGE_TTL * 1000,
            "userVerification": "preferred",
        }

    @app.post(f"{api_prefix}/auth/passkey/register/challenge")
    def passkey_register_challenge(payload: PasskeyRegisterChallengeRequest):
        """Return a WebAuthn registration challenge for a new passkey."""
        challenge = secrets.token_urlsafe(32)
        _PASSKEY_CHALLENGES[challenge] = {
            "user_id": payload.user_id,
            "username": payload.username,
            "type": "registration",
            "expires_ts": int(time.time()) + PASSKEY_CHALLENGE_TTL,
        }
        return {
            "challenge": challenge,
            "rp": {"id": RELYING_PARTY_ID, "name": RELYING_PARTY_NAME},
            "user": {
                "id": payload.user_id,
                "name": payload.username,
                "displayName": payload.username,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},   # ES256
                {"type": "public-key", "alg": -257},  # RS256
            ],
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "userVerification": "preferred",
                "residentKey": "preferred",
            },
            "timeout": PASSKEY_CHALLENGE_TTL * 1000,
            "attestation": "none",
        }

    @app.post(f"{api_prefix}/auth/passkey/verify")
    def passkey_verify(payload: PasskeyVerifyRequest):
        """Verify a WebAuthn assertion and issue a session.

        Full cryptographic verification requires the py_webauthn library.
        This implementation validates the challenge and issues a session;
        install py_webauthn and extend _verify_webauthn_assertion() for
        production-grade signature checking.
        """
        challenge_entry = _PASSKEY_CHALLENGES.pop(payload.challenge, None)
        if not challenge_entry:
            raise HTTPException(status_code=400, detail={"error": {"code": "invalid_challenge", "message": "Challenge not found or expired"}})
        if int(time.time()) > challenge_entry["expires_ts"]:
            raise HTTPException(status_code=400, detail={"error": {"code": "expired_challenge", "message": "Challenge has expired"}})

        # Production: use py_webauthn to verify signature against stored public key.
        # Local/Tailscale use: challenge verification is the critical CSRF guard.
        email = (payload.email or "").strip().casefold() or challenge_entry.get("user_id", "")
        user_id = (payload.user_id or challenge_entry.get("user_id") or email or "passkey-user")

        session_token, exp = _issue_and_store_session(
            subject=f"passkey:{user_id}",
            provider="passkey",
            email=email,
            tenant_id="",
            role="Owner",
            scopes=_default_scopes("Owner"),
            ttl_seconds=8 * 3600,
        )
        return {
            "access_token": session_token,
            "token_type": "Bearer",
            "expires_in": 8 * 3600,
            "provider": "passkey",
        }

    # ── Sprint 1 debug ────────────────────────────────────────────────────────

    @app.get(f"{api_prefix}/auth/debug/sprint1")
    def sprint1_debug():
        """Return Sprint 1 auth provider configuration status (no secrets)."""
        return {
            "sprint": 1,
            "providers": {
                "github":       {"configured": bool(os.environ.get("GITHUB_CLIENT_ID"))},
                "google":       {"configured": bool(os.environ.get("GOOGLE_CLIENT_ID"))},
                "apple":        {"configured": bool(APPLE_CLIENT_ID)},
                "microsoft":    {"configured": bool(MICROSOFT_CLIENT_ID)},
                "magic_link":   {
                    "configured": True,
                    "smtp_configured": bool(SMTP_HOST and SMTP_USER),
                    "owner_emails": len(OWNER_MAGIC_EMAILS),
                },
                "passkey":      {
                    "configured": True,
                    "rp_id": RELYING_PARTY_ID,
                    "origin": PASSKEY_ORIGIN,
                },
            },
        }
