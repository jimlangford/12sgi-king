import json
import logging
import os
from datetime import datetime, timezone
from urllib import error, request

from fastapi import HTTPException

OWNER_ROLE = "Owner"
VALID_ROLES = {"Owner", "Municipality", "Partner", "Resident", "Service"}
KNOWN_SCOPES = {
    "tenant:read",
    "tenant:write",
    "documents:read",
    "documents:write",
    "storage:read",
    "storage:write",
    "ai:assist",
    "gpu:infer",
    "gpu:read",
    "ops:owner",
    "auth:introspect",
}
ALLOWED_WILDCARD_SCOPES = {
    scope.strip()
    for scope in os.environ.get("GOVOS_ALLOWED_WILDCARD_SCOPES", "").split(",")
    if scope.strip()
}

DEFAULT_SCOPES_BY_ROLE = {
    "Owner": {
        "tenant:read",
        "tenant:write",
        "documents:read",
        "documents:write",
        "storage:read",
        "storage:write",
        "ai:assist",
        "gpu:infer",
        "gpu:read",
        "ops:owner",
    },
    "Municipality": {
        "tenant:read",
        "tenant:write",
        "documents:read",
        "documents:write",
        "storage:read",
        "storage:write",
        "ai:assist",
        "gpu:infer",
        "gpu:read",
    },
    "Partner": {
        "tenant:read",
        "documents:read",
        "documents:write",
        "storage:read",
        "storage:write",
        "ai:assist",
        "gpu:infer",
    },
    "Resident": {
        "tenant:read",
        "documents:read",
        "storage:read",
        "ai:assist",
        "gpu:infer",
    },
    "Service": set(),
}

_log = logging.getLogger(__name__)


def auth_error(status_code: int, code: str, message: str, details: dict | None = None):
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


def audit_auth_event(service: str, event_type: str, details: dict | None = None):
    _log.warning(
        "auth_audit %s",
        json.dumps(
            {
                "service": service,
                "event_type": event_type,
                "ts": datetime.now(timezone.utc).isoformat(),
                "details": details or {},
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
    )


def _normalise_claims(raw: dict | None) -> dict:
    claims = dict(raw or {})
    role = str(claims.get("role") or "Resident")
    scopes_raw = claims.get("scopes")
    if isinstance(scopes_raw, list):
        scopes = [str(s) for s in scopes_raw if s]
    else:
        scopes = []
    out = {
        "sub": str(claims.get("sub") or ""),
        "tenant_id": str(claims.get("tenant_id") or "").strip(),
        "role": role,
        "scopes": scopes,
        "exp": claims.get("exp"),
        "iss": claims.get("iss"),
        "aud": claims.get("aud"),
        "provider": str(claims.get("provider") or ""),
        "entitlement_tier": str(claims.get("entitlement_tier") or "free"),
        "entitlement_verified": bool(claims.get("entitlement_verified")),
        "entitlement_capabilities": [str(v) for v in (claims.get("entitlement_capabilities") or []) if str(v).strip()],
        "entitlement_source": str(claims.get("entitlement_source") or ""),
    }
    return out


def require_claims(
    *,
    service_name: str,
    authorization: str | None,
    introspection_url: str,
    internal_service_token: str,
    request_timeout: float,
    required_scopes: set[str] | None = None,
    required_capabilities: set[str] | None = None,
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        audit_auth_event(service_name, "denied_access", {"reason": "missing_bearer"})
        auth_error(401, "unauthorized", "Missing or invalid bearer token")

    token = authorization.split(" ", 1)[1].strip()
    payload = json.dumps({"token": token}).encode()
    req = request.Request(
        introspection_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Service-Token": internal_service_token,
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=request_timeout) as resp:
            data = json.loads(resp.read().decode() or "{}")
    except error.HTTPError as exc:
        if exc.code == 403:
            audit_auth_event(service_name, "service_auth_failure", {"status": 403})
            auth_error(503, "dependency_denied", "Auth service rejected service trust")
        audit_auth_event(service_name, "service_auth_failure", {"status": exc.code})
        auth_error(503, "dependency_unavailable", "Auth service unavailable", {"status": exc.code})
    except Exception:
        audit_auth_event(service_name, "service_auth_failure", {"status": "unreachable"})
        auth_error(503, "dependency_unavailable", "Auth service unavailable")

    if not data.get("active"):
        audit_auth_event(service_name, "denied_access", {"reason": data.get("reason", "inactive_token")})
        auth_error(401, "unauthorized", "Session is not active")

    claims = _normalise_claims(data.get("claims"))
    missing_claims: list[str] = []
    if not claims.get("sub"):
        missing_claims.append("sub")
    if not claims.get("role"):
        missing_claims.append("role")
    if not claims.get("scopes"):
        missing_claims.append("scopes")
    if claims.get("exp") in (None, ""):
        missing_claims.append("exp")
    if not claims.get("iss"):
        missing_claims.append("iss")
    if not claims.get("aud"):
        missing_claims.append("aud")
    if missing_claims:
        audit_auth_event(
            service_name,
            "legacy_claim_pattern_rejected",
            {"reason": "missing_required_claims", "missing": sorted(set(missing_claims))},
        )
        auth_error(401, "unauthorized", "Session claims are incomplete", {"missing": sorted(set(missing_claims))})
    if claims["role"] not in VALID_ROLES:
        audit_auth_event(service_name, "legacy_claim_pattern_rejected", {"reason": "invalid_role", "role": claims["role"]})
        auth_error(403, "forbidden", "Role is not allowed")
    if claims["role"] not in {OWNER_ROLE, "Service"} and not claims.get("tenant_id"):
        audit_auth_event(
            service_name,
            "legacy_claim_pattern_rejected",
            {"reason": "missing_tenant_claim", "role": claims["role"]},
        )
        auth_error(403, "forbidden", "Missing tenant claim")

    scope_values = set(claims.get("scopes") or [])
    wildcard_scopes = sorted(scope for scope in scope_values if "*" in scope and scope not in ALLOWED_WILDCARD_SCOPES)
    if wildcard_scopes:
        audit_auth_event(
            service_name,
            "legacy_claim_pattern_rejected",
            {"reason": "wildcard_scope_blocked", "scopes": wildcard_scopes},
        )
        auth_error(403, "forbidden", "Wildcard scopes are not allowed", {"blocked_scopes": wildcard_scopes})
    undefined_scopes = sorted(scope for scope in scope_values if scope not in KNOWN_SCOPES and "*" not in scope)
    if undefined_scopes:
        audit_auth_event(
            service_name,
            "legacy_claim_pattern_rejected",
            {"reason": "undefined_scopes", "scopes": undefined_scopes},
        )
        auth_error(403, "forbidden", "Undefined scopes are not allowed", {"undefined_scopes": undefined_scopes})

    needed = required_scopes or set()
    role = claims["role"]
    scopes = scope_values
    if role != OWNER_ROLE:
        if needed - scopes:
            audit_auth_event(
                service_name,
                "denied_access",
                {"reason": "missing_scope", "required": sorted(needed), "scopes": sorted(scopes)},
            )
            auth_error(403, "forbidden", "Insufficient scope", {"required_scopes": sorted(needed)})

    capabilities_needed = required_capabilities or set()
    if capabilities_needed and role not in {OWNER_ROLE, "Service"}:
        provider = (claims.get("provider") or "").strip().lower()
        entitlement_verified = bool(claims.get("entitlement_verified"))
        if provider == "google" and not entitlement_verified:
            audit_auth_event(
                service_name,
                "denied_access",
                {"reason": "entitlement_unverified", "provider": provider, "entitlement_source": claims.get("entitlement_source", "")},
            )
            auth_error(403, "forbidden", "Entitlement could not be verified", {"required_capabilities": sorted(capabilities_needed)})
        if provider != "google" and not entitlement_verified:
            return claims
        ent_caps = set(claims.get("entitlement_capabilities") or [])
        if capabilities_needed - ent_caps:
            audit_auth_event(
                service_name,
                "denied_access",
                {
                    "reason": "missing_capability",
                    "required_capabilities": sorted(capabilities_needed),
                    "capabilities": sorted(ent_caps),
                    "entitlement_tier": claims.get("entitlement_tier", "free"),
                },
            )
            auth_error(403, "forbidden", "Insufficient entitlement capability", {"required_capabilities": sorted(capabilities_needed)})
    return claims


def enforce_tenant_scope(
    *,
    service_name: str,
    claims: dict,
    requested_tenant_id: str | None,
    owner_override_allowed: bool = True,
) -> str:
    role = claims.get("role")
    claim_tenant = str(claims.get("tenant_id") or "").strip()
    requested = str(requested_tenant_id or "").strip()

    if role == OWNER_ROLE:
        if requested and owner_override_allowed:
            audit_auth_event(service_name, "owner_override", {"tenant_id": requested})
            return requested
        if requested and not owner_override_allowed:
            audit_auth_event(service_name, "denied_access", {"reason": "owner_override_not_allowed", "tenant_id": requested})
            auth_error(403, "forbidden", "Owner override is not allowed on this endpoint")
        if claim_tenant:
            return claim_tenant
        return ""

    if not claim_tenant:
        audit_auth_event(service_name, "denied_access", {"reason": "missing_tenant_claim"})
        auth_error(403, "forbidden", "Missing tenant claim")

    if requested and requested != claim_tenant:
        audit_auth_event(
            service_name,
            "tenant_mismatch",
            {"request_tenant_id": requested, "claim_tenant_id": claim_tenant},
        )
        auth_error(
            403,
            "tenant_mismatch",
            "Request tenant does not match authenticated tenant",
            {"request_tenant_id": requested, "claim_tenant_id": claim_tenant},
        )

    return claim_tenant


def enforce_resource_tenant(
    *,
    service_name: str,
    claims: dict,
    resource_tenant_id: str,
) -> None:
    role = claims.get("role")
    claim_tenant = str(claims.get("tenant_id") or "").strip()
    resource_tenant = str(resource_tenant_id or "").strip()

    if role == OWNER_ROLE:
        if not claim_tenant or claim_tenant != resource_tenant:
            audit_auth_event(service_name, "owner_override", {"resource_tenant_id": resource_tenant})
        return

    if not claim_tenant:
        audit_auth_event(service_name, "denied_access", {"reason": "missing_tenant_claim"})
        auth_error(403, "forbidden", "Missing tenant claim")

    if claim_tenant != resource_tenant:
        audit_auth_event(
            service_name,
            "tenant_mismatch",
            {"resource_tenant_id": resource_tenant, "claim_tenant_id": claim_tenant},
        )
        auth_error(403, "forbidden", "Cross-tenant access is not allowed")
