"""WordPress entitlement bridge and identity linker.

PUBLIC authority:
- WordPress + WooCommerce (via Jetpack-capable API path) define paid access.

PRIVATE authority:
- QUAD OS uses mapped tier/capability assertions only.

BRIDGE boundary:
- only identity + entitlement assertions cross systems.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from watchers import tier_access

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = Path(os.environ.get("ENTITLEMENT_MAP_PATH", str(ROOT / "config" / "entitlement_map.json")))
DB_PATH = Path(os.environ.get("ENTITLEMENT_DB_PATH", "/tmp/govos_v2_entitlements.db"))

JETPACK_TOKEN = os.environ.get("JETPACK_TOKEN", "").strip()
JETPACK_SITE_ID = os.environ.get("JETPACK_SITE_ID", "").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(value: str) -> str:
    v = str(value or "").strip().lower()
    if not v:
        return ""
    return "sha256:" + hashlib.sha256(v.encode("utf-8")).hexdigest()[:16]


def _load_map() -> dict:
    try:
        with open(MAP_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {
            "default_tier": "free",
            "woo_product_to_tier": {},
            "woo_status_to_tier": {"active": "pro"},
            "wordpress_role_to_tier": {},
        }


@contextmanager
def _db(path: Path = DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS identity_links (
                provider TEXT NOT NULL,
                subject TEXT NOT NULL,
                email TEXT,
                wordpress_user_id TEXT,
                woocommerce_customer_id TEXT,
                tier TEXT,
                linked_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (provider, subject)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entitlement_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                provider TEXT,
                subject_hash TEXT,
                email_hash TEXT,
                verified INTEGER NOT NULL,
                tier TEXT,
                source TEXT,
                reason TEXT,
                details_json TEXT
            )
            """
        )
        conn.commit()


def _audit(*, provider: str, subject: str, email: str, verified: bool, tier: str, source: str, reason: str, details: dict | None = None) -> None:
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO entitlement_audit (ts, provider, subject_hash, email_hash, verified, tier, source, reason, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now_iso(),
                provider,
                _redact(subject),
                _redact(email),
                1 if verified else 0,
                tier,
                source,
                reason,
                json.dumps(details or {}, separators=(",", ":")),
            ),
        )
        conn.commit()


def _http_get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _map_tier(raw: dict, mapping: dict) -> str:
    default_tier = str(mapping.get("default_tier") or "free")
    products = mapping.get("woo_product_to_tier") or {}
    statuses = mapping.get("woo_status_to_tier") or {}
    roles = mapping.get("wordpress_role_to_tier") or {}

    for product in raw.get("products") or []:
        tier = products.get(str(product).strip())
        if tier:
            return str(tier)

    status = str(raw.get("subscription_status") or "").strip().lower()
    if status:
        tier = statuses.get(status)
        if tier:
            return str(tier)

    wp_role = str(raw.get("wp_role") or "").strip().lower()
    if wp_role:
        tier = roles.get(wp_role)
        if tier:
            return str(tier)

    return default_tier


def _fetch_wordpress_profile(email: str) -> dict:
    """Fetch a slim WordPress profile via Jetpack-capable API path.

    This is best-effort and intentionally defensive because endpoint availability differs between
    WordPress.com and Jetpack-connected installs.
    """
    if not (JETPACK_TOKEN and JETPACK_SITE_ID and email):
        return {}

    encoded_site = urllib.parse.quote(JETPACK_SITE_ID, safe="")
    encoded_email = urllib.parse.quote(email, safe="")
    # Users endpoint is widely available on WP.com API; include email search as identity bridge.
    users_url = f"https://public-api.wordpress.com/rest/v1.1/sites/{encoded_site}/users/?search={encoded_email}"
    data = _http_get_json(users_url, JETPACK_TOKEN)
    users = data.get("users") if isinstance(data, dict) else None
    if not isinstance(users, list):
        return {}

    matched = None
    for user in users:
        if str((user or {}).get("email") or "").strip().lower() == email.strip().lower():
            matched = user or {}
            break
    if not matched:
        return {}

    roles = matched.get("roles") or []
    wp_role = ""
    if isinstance(roles, list) and roles:
        wp_role = str(roles[0] or "").strip().lower()

    return {
        "wordpress_user_id": str(matched.get("ID") or ""),
        "wp_role": wp_role,
        # Woo product/status can be supplied by a separate sync process through env to avoid
        # exposing Woo internals here; bridge consumes assertions only.
        "subscription_status": str(os.environ.get("WP_BRIDGE_SUBSCRIPTION_STATUS", "")).strip().lower(),
        "products": [
            p.strip()
            for p in os.environ.get("WP_BRIDGE_PRODUCTS", "").split(",")
            if p.strip()
        ],
        "woocommerce_customer_id": str(os.environ.get("WP_BRIDGE_CUSTOMER_ID", "")).strip(),
    }


def get_identity_link(provider: str, subject: str) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            """
            SELECT provider, subject, email, wordpress_user_id, woocommerce_customer_id, tier, linked_at, updated_at
            FROM identity_links
            WHERE provider = ? AND subject = ?
            """,
            (provider, subject),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_latest_entitlement_audit(provider: str, subject: str, email: str = "") -> dict | None:
    subject_hash = _redact(subject)
    email_hash = _redact(email)
    with _db() as conn:
        row = conn.execute(
            """
            SELECT ts, verified, tier, source, reason
            FROM entitlement_audit
            WHERE provider = ?
              AND (
                (? != '' AND subject_hash = ?)
                OR (? != '' AND email_hash = ?)
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (provider, subject_hash, subject_hash, email_hash, email_hash),
        ).fetchone()
    if row is None:
        return None
    return {
        "ts": row["ts"],
        "verified": bool(row["verified"]),
        "tier": str(row["tier"] or "free"),
        "source": str(row["source"] or ""),
        "reason": str(row["reason"] or ""),
    }


def bind_identity(*, provider: str, subject: str, email: str) -> dict:
    mapping = _load_map()
    profile = _fetch_wordpress_profile(email)
    tier = _map_tier(profile, mapping)

    existing = get_identity_link(provider, subject)
    wordpress_user_id = str(profile.get("wordpress_user_id") or (existing or {}).get("wordpress_user_id") or "")
    woocommerce_customer_id = str(profile.get("woocommerce_customer_id") or (existing or {}).get("woocommerce_customer_id") or "")

    now = _now_iso()
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO identity_links
              (provider, subject, email, wordpress_user_id, woocommerce_customer_id, tier, linked_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, subject) DO UPDATE SET
              email=excluded.email,
              wordpress_user_id=COALESCE(NULLIF(excluded.wordpress_user_id, ''), identity_links.wordpress_user_id),
              woocommerce_customer_id=COALESCE(NULLIF(excluded.woocommerce_customer_id, ''), identity_links.woocommerce_customer_id),
              tier=excluded.tier,
              updated_at=excluded.updated_at
            """,
            (
                provider,
                subject,
                email.strip().lower(),
                wordpress_user_id,
                woocommerce_customer_id,
                tier,
                now,
                now,
            ),
        )
        conn.commit()

    verified = bool(profile)
    reason = "wordpress_verified" if verified else "wordpress_unverified"
    source = "jetpack" if verified else "unverified"
    _audit(
        provider=provider,
        subject=subject,
        email=email,
        verified=verified,
        tier=tier,
        source=source,
        reason=reason,
        details={"has_wordpress_user_id": bool(wordpress_user_id), "has_woocommerce_customer_id": bool(woocommerce_customer_id)},
    )

    return {
        "provider": provider,
        "subject": subject,
        "email": email.strip().lower(),
        "wordpress_user_id": wordpress_user_id,
        "woocommerce_customer_id": woocommerce_customer_id,
        "verified": verified,
        "tier": tier,
        "capabilities": tier_access.capabilities(tier),
        "source": source,
        "reason": reason,
    }


def resolve_identity_entitlement(*, provider: str, subject: str, email: str) -> dict:
    """Resolve entitlement assertions for protected requests.

    Fail-closed semantics:
    - if WordPress verification cannot be performed, `verified` is false.
    - callers can reject access when `verified` is false for protected capabilities.
    """
    if not subject:
        return {"verified": False, "tier": "free", "capabilities": [], "source": "invalid", "reason": "missing_subject"}

    linked = get_identity_link(provider, subject)
    if linked:
        tier = str(linked.get("tier") or "free")
        verified = bool(linked.get("wordpress_user_id") or linked.get("woocommerce_customer_id"))
        source = "identity_link"
        reason = "cached_link"
        _audit(
            provider=provider,
            subject=subject,
            email=email,
            verified=verified,
            tier=tier,
            source=source,
            reason=reason,
        )
        return {
            "verified": verified,
            "tier": tier,
            "capabilities": tier_access.capabilities(tier),
            "source": source,
            "reason": reason,
            "wordpress_user_id": linked.get("wordpress_user_id") or "",
            "woocommerce_customer_id": linked.get("woocommerce_customer_id") or "",
        }

    return bind_identity(provider=provider, subject=subject, email=email)


init_db()
