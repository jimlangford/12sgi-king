"""
services/auth/app/passkeys.py — WebAuthn (FIDO2) passkey registration and authentication.

REWRITTEN 2026-07-15 (audit-quad-os): the original draft called a webauthn API that does not exist
(options_creation/options_assertion/generate_challenge/verify_assertion_response — none of these are
in the real installed library). Rewritten against the REAL, verified `webauthn==3.0.0` API
(generate_registration_options / verify_registration_response / generate_authentication_options /
verify_authentication_response / options_to_json), confirmed live against the auth container's actual
installed package before writing a single call. Also fixed two real bugs found in the draft:
  1. `passkey_challenges` was written to but never CREATEd — every registration/signin would have
     crashed with "no such table" on first real use.
  2. passkey_register_complete stored email="" / display_name="" (its own comment admitted the data
     was meant to come "from earlier registration" but never did) — signin_begin looks users up BY
     EMAIL, so this made every passkey-registered user permanently unable to sign in. Fixed by
     persisting email + display_name on the registration CHALLENGE row and reading them back in
     register_complete.

Endpoints (wired in main.py):
  POST /api/v2/auth/passkey/register/begin    -> full PublicKeyCredentialCreationOptions (as JSON the
                                                  browser passes straight to navigator.credentials.create)
  POST /api/v2/auth/passkey/register/complete -> verify + store credential
  POST /api/v2/auth/passkey/signin/begin      -> full PublicKeyCredentialRequestOptions
  POST /api/v2/auth/passkey/signin/complete   -> verify assertion, return user info (main.py issues the JWT)
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from uuid import uuid4

from pydantic import BaseModel
from webauthn import (
    generate_registration_options, verify_registration_response,
    generate_authentication_options, verify_authentication_response, options_to_json,
)
from webauthn.helpers.structs import (
    UserVerificationRequirement, PublicKeyCredentialDescriptor, AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

RP_ID = os.environ.get("WEBAUTHN_RP_ID", "12sgi.com")
RP_NAME = "govOS v2"
ORIGIN = os.environ.get("WEBAUTHN_ORIGIN", "https://12sgi.com")
DB_PATH = os.environ.get("AUTH_DB_PATH", "/tmp/govos_v2_auth.db")  # SAME path/env var as main.py's DB_PATH


# ── Request/Response models ────────────────────────────────────────────────────
class PasskeyRegisterBeginRequest(BaseModel):
    user_id: str
    email: str
    display_name: str

class PasskeyRegisterBeginResponse(BaseModel):
    options_json: str   # pass straight to: navigator.credentials.create({publicKey: JSON.parse(options_json)})
    user_id: str

class PasskeyRegisterCompleteRequest(BaseModel):
    user_id: str
    credential_json: str   # the raw JSON the browser returned from navigator.credentials.create()
    transports: list[str] = []

class PasskeyRegisterCompleteResponse(BaseModel):
    credential_id: str
    sign_count: int

class PasskeySigninBeginRequest(BaseModel):
    email: str

class PasskeySigninBeginResponse(BaseModel):
    options_json: str   # pass straight to: navigator.credentials.get({publicKey: JSON.parse(options_json)})
    user_id: str

class PasskeySigninCompleteRequest(BaseModel):
    user_id: str
    credential_json: str   # the raw JSON the browser returned from navigator.credentials.get()

class PasskeySigninCompleteResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    sign_count: int


# ── DB ──────────────────────────────────────────────────────────────────────────
@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()   # sqlite3.Connection's own context manager only commits; it never closes


def init_passkeys_db() -> None:
    """Create passkey tables. FIX (2026-07-15): passkey_challenges was previously never created."""
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS passkey_users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS passkey_credentials (
                credential_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                public_key BLOB NOT NULL,
                sign_count INTEGER NOT NULL DEFAULT 0,
                transports TEXT,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                FOREIGN KEY(user_id) REFERENCES passkey_users(user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS passkey_challenges (
                user_id TEXT NOT NULL,
                challenge BLOB NOT NULL,
                type TEXT NOT NULL,
                email TEXT,
                display_name TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def _store_challenge(user_id: str, challenge: bytes, challenge_type: str,
                      email: str = "", display_name: str = "") -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO passkey_challenges (user_id, challenge, type, email, display_name, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (user_id, challenge, challenge_type, email, display_name),
        )
        conn.execute("DELETE FROM passkey_challenges WHERE datetime(created_at) < datetime('now', '-10 minutes')")
        conn.commit()


def _get_challenge(user_id: str, challenge_type: str) -> sqlite3.Row | None:
    """Retrieve + consume (one-time use) the most recent unexpired challenge for this user+type."""
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM passkey_challenges WHERE user_id = ? AND type = ? "
            "AND datetime(created_at) > datetime('now', '-10 minutes') "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, challenge_type),
        ).fetchone()
        if row:
            conn.execute("DELETE FROM passkey_challenges WHERE user_id = ? AND type = ?", (user_id, challenge_type))
            conn.commit()
        return row


# ── Registration flow ────────────────────────────────────────────────────────────
def passkey_register_begin(req: PasskeyRegisterBeginRequest) -> PasskeyRegisterBeginResponse:
    with _db() as conn:
        existing = conn.execute(
            "SELECT credential_id FROM passkey_credentials WHERE user_id = ?", (req.user_id,)
        ).fetchall()
    exclude = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(r["credential_id"])) for r in existing]

    options = generate_registration_options(
        rp_id=RP_ID, rp_name=RP_NAME,
        user_id=req.user_id.encode("utf-8"),
        user_name=req.email, user_display_name=req.display_name,
        exclude_credentials=exclude or None,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    # Persist email/display_name on the challenge row so register_complete can create the user WITHOUT
    # blank fields (the exact bug this rewrite fixes — see module docstring).
    _store_challenge(req.user_id, options.challenge, "registration", req.email, req.display_name)

    return PasskeyRegisterBeginResponse(options_json=options_to_json(options), user_id=req.user_id)


def passkey_register_complete(req: PasskeyRegisterCompleteRequest) -> PasskeyRegisterCompleteResponse:
    chal_row = _get_challenge(req.user_id, "registration")
    if not chal_row:
        raise ValueError("Challenge expired or not found — start registration again")

    try:
        verified = verify_registration_response(
            credential=req.credential_json,
            expected_challenge=bytes(chal_row["challenge"]),
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
        )
    except Exception as e:
        raise ValueError(f"Credential verification failed: {e}")

    credential_id_b64 = bytes_to_base64url(verified.credential_id)
    with _db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO passkey_users (user_id, email, display_name, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (req.user_id, chal_row["email"], chal_row["display_name"]),
        )
        conn.execute(
            "INSERT INTO passkey_credentials "
            "(credential_id, user_id, public_key, sign_count, transports, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (credential_id_b64, req.user_id, verified.credential_public_key,
             verified.sign_count, json.dumps(req.transports)),
        )
        conn.commit()

    return PasskeyRegisterCompleteResponse(credential_id=credential_id_b64, sign_count=verified.sign_count)


# ── Signin flow ──────────────────────────────────────────────────────────────────
def passkey_signin_begin(req: PasskeySigninBeginRequest) -> PasskeySigninBeginResponse:
    with _db() as conn:
        user_row = conn.execute(
            "SELECT user_id FROM passkey_users WHERE email = ?", (req.email,)
        ).fetchone()
        if not user_row:
            raise ValueError("No passkey user found with this email")
        user_id = user_row["user_id"]
        cred_rows = conn.execute(
            "SELECT credential_id, transports FROM passkey_credentials WHERE user_id = ?", (user_id,)
        ).fetchall()
    if not cred_rows:
        raise ValueError("No passkey credentials registered for this user")

    allow_credentials = [
        PublicKeyCredentialDescriptor(
            id=base64url_to_bytes(r["credential_id"]),
            transports=json.loads(r["transports"] or "[]") or None,
        )
        for r in cred_rows
    ]
    options = generate_authentication_options(
        rp_id=RP_ID, allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    _store_challenge(user_id, options.challenge, "signin")

    return PasskeySigninBeginResponse(options_json=options_to_json(options), user_id=user_id)


def passkey_signin_complete(req: PasskeySigninCompleteRequest) -> PasskeySigninCompleteResponse:
    chal_row = _get_challenge(req.user_id, "signin")
    if not chal_row:
        raise ValueError("Challenge expired or not found — start signin again")

    credential = json.loads(req.credential_json)
    credential_id_b64 = credential.get("id") or credential.get("rawId")
    if not credential_id_b64:
        raise ValueError("Malformed credential — missing id")

    with _db() as conn:
        cred_row = conn.execute(
            "SELECT user_id, public_key, sign_count FROM passkey_credentials WHERE credential_id = ?",
            (credential_id_b64,),
        ).fetchone()
        if not cred_row or cred_row["user_id"] != req.user_id:
            raise ValueError("Credential not found for this user")
        user_row = conn.execute(
            "SELECT email, display_name FROM passkey_users WHERE user_id = ?", (req.user_id,)
        ).fetchone()

    try:
        verified = verify_authentication_response(
            credential=req.credential_json,
            expected_challenge=bytes(chal_row["challenge"]),
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=bytes(cred_row["public_key"]),
            credential_current_sign_count=cred_row["sign_count"],
        )
    except Exception as e:
        raise ValueError(f"Assertion verification failed: {e}")

    # Clone detection: the library ALREADY enforces new_sign_count > credential_current_sign_count
    # internally (raises on failure) when authenticators report a nonzero counter. We still persist
    # the new count so the next signin has a real baseline to check against.
    with _db() as conn:
        conn.execute(
            "UPDATE passkey_credentials SET sign_count = ?, last_used_at = datetime('now') "
            "WHERE credential_id = ?",
            (verified.new_sign_count, credential_id_b64),
        )
        conn.commit()

    return PasskeySigninCompleteResponse(
        user_id=req.user_id, email=user_row["email"], display_name=user_row["display_name"],
        sign_count=verified.new_sign_count,
    )
