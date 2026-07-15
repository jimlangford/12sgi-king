"""
services/auth/app/passkeys.py — WebAuthn (FIDO2) passkey registration and authentication.

Implements registration + signin flows using py_webauthn for FIDO2 credential handling.
Credentials stored in SQLite with per-user credential registry.

Endpoints:
  POST /api/v2/auth/passkey/register/begin   → challenge for credential creation
  POST /api/v2/auth/passkey/register/complete → store verified credential
  POST /api/v2/auth/passkey/signin/begin      → challenge for credential assertion
  POST /api/v2/auth/passkey/signin/complete   → verify assertion, issue JWT
"""

import json
import os
import sqlite3
from base64 import b64decode, b64encode
from contextlib import contextmanager
from uuid import uuid4

from pydantic import BaseModel
from webauthn import (
    options_creation, credential_id_to_json, options_assertion, verify_registration_response,
    verify_assertion_response, generate_challenge
)
from webauthn.helpers.structs import (
    UserVerificationRequirement, ResidentKeyRequirement, AttestationConveyancePreference
)
from webauthn.helpers.base64url_to_bytes import base64url_to_bytes
from webauthn.helpers.bytes_to_base64url import bytes_to_base64url

RP_ID = os.environ.get("WEBAUTHN_RP_ID", "12sgi.com")
RP_NAME = "govOS v2"
ORIGIN = os.environ.get("WEBAUTHN_ORIGIN", "https://12sgi.com")
DB_PATH = os.environ.get("AUTH_DB_PATH", "/tmp/govos_v2_auth.db")

# Request/Response models
class PasskeyRegisterBeginRequest(BaseModel):
    user_id: str
    email: str
    display_name: str

class PasskeyRegisterBeginResponse(BaseModel):
    challenge: str
    user_id: str
    user_handle: str

class PasskeyRegisterCompleteRequest(BaseModel):
    user_id: str
    credential_id: str
    client_data_json: str
    attestation_object: str
    transports: list[str] = []

class PasskeyRegisterCompleteResponse(BaseModel):
    credential_id: str
    public_key: str
    sign_count: int

class PasskeySigninBeginRequest(BaseModel):
    email: str

class PasskeySigninBeginResponse(BaseModel):
    challenge: str
    allow_credentials: list[dict]

class PasskeySigninCompleteRequest(BaseModel):
    credential_id: str
    client_data_json: str
    authenticator_data: str
    signature: str
    user_handle: str

class PasskeySigninCompleteResponse(BaseModel):
    user_id: str
    email: str
    sign_count: int

# DB helpers
@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_passkeys_db():
    """Create passkey credential tables."""
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
                public_key TEXT NOT NULL,
                sign_count INTEGER NOT NULL DEFAULT 0,
                transports TEXT,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                FOREIGN KEY(user_id) REFERENCES passkey_users(user_id)
            )
        """)
        conn.commit()

def _store_challenge(user_id: str, challenge: str, challenge_type: str = "registration") -> None:
    """Store challenge temporarily (expires after 10 min)."""
    with _db() as conn:
        conn.execute("""
            INSERT INTO passkey_challenges (user_id, challenge, type, created_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (user_id, challenge, challenge_type))
        # Clean up old challenges
        conn.execute("DELETE FROM passkey_challenges WHERE datetime(created_at) < datetime('now', '-10 minutes')")
        conn.commit()

def _get_challenge(user_id: str) -> str | None:
    """Retrieve and validate challenge."""
    with _db() as conn:
        row = conn.execute("""
            SELECT challenge FROM passkey_challenges
            WHERE user_id = ? AND datetime(created_at) > datetime('now', '-10 minutes')
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM passkey_challenges WHERE user_id = ?", (user_id,))
            conn.commit()
            return row[0]
    return None

# Passkey registration flow
def passkey_register_begin(req: PasskeyRegisterBeginRequest) -> PasskeyRegisterBeginResponse:
    """Generate registration challenge."""
    challenge = generate_challenge()
    user_handle = bytes_to_base64url(uuid4().bytes)
    
    _store_challenge(req.user_id, challenge, "registration")
    
    return PasskeyRegisterBeginResponse(
        challenge=challenge,
        user_id=req.user_id,
        user_handle=user_handle
    )

def passkey_register_complete(req: PasskeyRegisterCompleteRequest) -> PasskeyRegisterCompleteResponse:
    """Verify credential and store in DB."""
    challenge = _get_challenge(req.user_id)
    if not challenge:
        raise ValueError("Challenge expired or not found")
    
    try:
        # Verify credential creation
        verified = verify_registration_response(
            credential=req.credential_id,
            client_data_json_bytes=b64decode(req.client_data_json),
            attestation_object_bytes=b64decode(req.attestation_object),
            expected_challenge=challenge.encode(),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID
        )
    except Exception as e:
        raise ValueError(f"Credential verification failed: {str(e)}")
    
    # Store credential
    with _db() as conn:
        # Create user if needed
        conn.execute("""
            INSERT OR IGNORE INTO passkey_users (user_id, email, display_name, created_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (req.user_id, "", ""))  # Email/display_name from earlier registration
        
        # Store credential
        conn.execute("""
            INSERT INTO passkey_credentials
            (credential_id, user_id, public_key, sign_count, transports, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (
            req.credential_id,
            req.user_id,
            json.dumps(verified.credential_public_key),  # Serialize public key
            verified.sign_count,
            json.dumps(req.transports)
        ))
        conn.commit()
    
    return PasskeyRegisterCompleteResponse(
        credential_id=req.credential_id,
        public_key=json.dumps(verified.credential_public_key),
        sign_count=verified.sign_count
    )

# Passkey signin flow
def passkey_signin_begin(req: PasskeySigninBeginRequest) -> PasskeySigninBeginResponse:
    """Generate signin challenge."""
    challenge = generate_challenge()
    
    # Get user's credentials
    with _db() as conn:
        user_row = conn.execute(
            "SELECT user_id FROM passkey_users WHERE email = ?",
            (req.email,)
        ).fetchone()
        
        if not user_row:
            raise ValueError("No passkey user found with this email")
        
        user_id = user_row[0]
        _store_challenge(user_id, challenge, "signin")
        
        cred_rows = conn.execute(
            "SELECT credential_id, transports FROM passkey_credentials WHERE user_id = ?",
            (user_id,)
        ).fetchall()
    
    allow_credentials = [
        {
            "type": "public-key",
            "id": b64encode(row["credential_id"].encode()).decode(),
            "transports": json.loads(row["transports"] or "[]")
        }
        for row in cred_rows
    ]
    
    return PasskeySigninBeginResponse(
        challenge=challenge,
        allow_credentials=allow_credentials
    )

def passkey_signin_complete(req: PasskeySigninCompleteRequest) -> PasskeySigninCompleteResponse:
    """Verify assertion and return user info."""
    # Decode user_handle to get user_id
    user_handle_bytes = b64decode(req.user_handle)
    
    # Get credential from DB
    with _db() as conn:
        cred_row = conn.execute(
            "SELECT user_id, public_key, sign_count FROM passkey_credentials WHERE credential_id = ?",
            (req.credential_id,)
        ).fetchone()
        
        if not cred_row:
            raise ValueError("Credential not found")
        
        user_id = cred_row["user_id"]
        public_key = json.loads(cred_row["public_key"])
        stored_sign_count = cred_row["sign_count"]
        
        user_row = conn.execute(
            "SELECT email FROM passkey_users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
    
    challenge = _get_challenge(user_id)
    if not challenge:
        raise ValueError("Challenge expired or not found")
    
    try:
        # Verify assertion
        verified = verify_assertion_response(
            credential_id=req.credential_id,
            client_data_json_bytes=b64decode(req.client_data_json),
            authenticator_data_bytes=b64decode(req.authenticator_data),
            signature=b64decode(req.signature),
            credential_public_key=public_key,
            expected_challenge=challenge.encode(),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID
        )
    except Exception as e:
        raise ValueError(f"Assertion verification failed: {str(e)}")
    
    # Check sign count (cloned credential detection)
    if verified.sign_count <= stored_sign_count:
        raise ValueError("Possible cloned credential detected (sign count mismatch)")
    
    # Update sign count
    with _db() as conn:
        conn.execute(
            "UPDATE passkey_credentials SET sign_count = ?, last_used_at = datetime('now') WHERE credential_id = ?",
            (verified.sign_count, req.credential_id)
        )
        conn.commit()
    
    return PasskeySigninCompleteResponse(
        user_id=user_id,
        email=user_row["email"],
        sign_count=verified.sign_count
    )
