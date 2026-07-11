import json
import logging
from datetime import datetime, timezone
from urllib import error, request

from fastapi import HTTPException

OWNER_ROLE = "Owner"
VALID_ROLES = {"Owner", "Municipality", "Partner", "Resident", "Service"}

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
    if not claims.get("sub"):
        audit_auth_event(service_name, "denied_access", {"reason": "missing_subject_claim"})
        auth_error(401, "unauthorized", "Session claims are incomplete")
    if claims["role"] not in VALID_ROLES:
        audit_auth_event(service_name, "role_escalation_attempt", {"role": claims["role"]})
        auth_error(403, "forbidden", "Role is not allowed")

    needed = required_scopes or set()
    role = claims["role"]
    scopes = set(claims.get("scopes") or [])
    if role != OWNER_ROLE:
        if needed - scopes:
            audit_auth_event(
                service_name,
                "denied_access",
                {"reason": "missing_scope", "required": sorted(needed), "scopes": sorted(scopes)},
            )
            auth_error(403, "forbidden", "Insufficient scope", {"required_scopes": sorted(needed)})
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
