#!/usr/bin/env python3
"""tools/seed_studio_tenants.py — seed studio tenant identities into the v2 system.

Reads tenant_registry.json creative tenants, verifies the auth service can issue a
scoped token for each tenant_id, then emits a workboard job per studio confirming
it is registered and ready for case/document/storage operations.

Usage:
    python tools/seed_studio_tenants.py              # dry-run (no tokens issued)
    python tools/seed_studio_tenants.py --apply      # issue verification tokens + emit workboard jobs
    python tools/seed_studio_tenants.py --apply --verbose

The script is idempotent: re-running it will re-verify and re-emit (tombstoned by
prior runs in the dispatch log as usual).

Canon (JRCSL): studios are departments, not corporations. No corporate gate. Seed
only confirms the tenant_id is reachable — it does not create any public records
or modify private content.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.v2_workboard import emit_workboard_job

# ── Config ────────────────────────────────────────────────────────────────────
AUTH_URL        = "http://localhost:8101/api/v2/auth/session"
AUTH_READY_URL  = "http://localhost:8101/api/v2/ready"
REGISTRY_PATH   = _REPO / "tenant_registry.json"
TIMEOUT         = 5

# Studio collaborator role policy (owner_policy.json studio_roles block):
#   Partner  — active crew/collaborators: read tenant+docs, read/write storage, ai+gpu
#   Resident — external reviewers / light touch: read-only tenant+docs+storage, ai+gpu
#
# Default for all studio tenants is Partner unless overridden per-tenant below.
_ROLE_OVERRIDES: dict[str, str] = {
    # Proposed / early-stage tenants default to Resident until production begins.
    "film_seventh_stone":       "Resident",
    "film_wutang":              "Resident",   # rd_private
    "film_willie_k":            "Resident",   # forming
    "mv_john_saunders_band":    "Resident",   # proposed_internal
    "film_the_movie":           "Resident",   # blessing_gated_preproduction
}

# Scopes issued for Partner role verification token (matches authz.py DEFAULT_SCOPES_BY_ROLE)
_PARTNER_SCOPES = [
    "tenant:read",
    "documents:read",
    "documents:write",
    "storage:read",
    "storage:write",
    "ai:assist",
    "gpu:infer",
]
_RESIDENT_SCOPES = [
    "tenant:read",
    "documents:read",
    "storage:read",
    "ai:assist",
    "gpu:infer",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_auth_ready() -> bool:
    try:
        with urllib.request.urlopen(AUTH_READY_URL, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode())
            return data.get("status") in ("ready", "healthy")
    except Exception as exc:
        print(f"  [!] auth not reachable at {AUTH_READY_URL}: {exc}", file=sys.stderr)
        return False


def _issue_verification_token(tenant_id: str, role: str) -> tuple[bool, str]:
    """Issue a short-lived verification token for the tenant_id via the auth service.

    Uses magic_link provider (Service-style) with explicit scopes — no OAuth round-trip.
    Returns (ok, reason).
    """
    scopes = _PARTNER_SCOPES if role == "Partner" else _RESIDENT_SCOPES
    payload = json.dumps({
        "provider": "magic_link",
        "subject": f"seed:{tenant_id}",
        "email":   "seed@king-server.internal",
        "tenant_id": tenant_id,
        "role":    role,
        "scopes":  scopes,
        "expires_in": 300,   # 5-minute verification token only
    }).encode()
    req = urllib.request.Request(
        AUTH_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode())
            if data.get("access_token"):
                return True, "token issued"
            return False, f"no access_token in response: {data}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:200]
        return False, f"HTTP {exc.code}: {body}"
    except Exception as exc:
        return False, str(exc)[:120]


def _emit_seed_job(tenant: dict, role: str, verified: bool, dry_run: bool) -> None:
    tid = tenant["id"]
    name = tenant["name"]
    kind = tenant["kind"]
    status_val = tenant.get("status", "unknown")
    event = (
        f"STUDIO TENANT SEEDED: {tid} ({name}) "
        f"role={role} kind={kind} status={status_val} verified={verified}"
    )
    if dry_run:
        print(f"  [DRY RUN] would emit: {event}")
        return
    emit_workboard_job(
        source="seed-studio-tenants",
        action="studio.tenant.seeded",
        event=event,
        lane="engineering",
        status="done",
        payload={
            "tenant_id":      tid,
            "name":           name,
            "kind":           kind,
            "production_status": status_val,
            "role":           role,
            "auth_verified":  verified,
            "seeded_at":      _now(),
        },
    )


def run(apply: bool, verbose: bool) -> int:
    dry_run = not apply
    print("=" * 66)
    print("STUDIO TENANT SEED")
    print(f"  mode      : {'APPLY' if apply else 'DRY RUN (pass --apply to commit)'}")
    print(f"  registry  : {REGISTRY_PATH}")
    print("=" * 66)

    if not REGISTRY_PATH.exists():
        print(f"ERROR: tenant_registry.json not found at {REGISTRY_PATH}", file=sys.stderr)
        return 1

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    creative = registry.get("creative_tenants", [])
    if not creative:
        print("No creative_tenants found in registry.", file=sys.stderr)
        return 1

    print(f"\nFound {len(creative)} creative tenants.\n")

    # Check auth availability (only matters for --apply)
    auth_ok = False
    if apply:
        print("Checking auth service readiness...")
        auth_ok = _check_auth_ready()
        if auth_ok:
            print("  ✓ auth ready\n")
        else:
            print("  ✗ auth not ready — tokens will not be issued (seed jobs still emitted)\n")

    ok_count = verified_count = 0
    rows = []

    for tenant in creative:
        tid   = tenant.get("id", "")
        name  = tenant.get("name", "")
        kind  = tenant.get("kind", "")
        pstatus = tenant.get("status", "unknown")
        role  = _ROLE_OVERRIDES.get(tid, "Partner")

        verified = False
        verify_msg = "skipped (dry run)" if dry_run else "skipped (auth offline)"

        if apply and auth_ok:
            verified, verify_msg = _issue_verification_token(tid, role)
            if verified:
                verified_count += 1

        _emit_seed_job(tenant, role, verified, dry_run)
        ok_count += 1

        status_icon = "✓" if (verified or dry_run) else "~"
        rows.append((status_icon, tid, role, kind, pstatus, verify_msg))

        if verbose or not verified:
            verify_label = "✓ verified" if verified else f"~ {verify_msg}"
            print(f"  {status_icon} {tid}")
            print(f"      name   : {name}")
            print(f"      kind   : {kind}")
            print(f"      status : {pstatus}")
            print(f"      role   : {role}")
            print(f"      auth   : {verify_label}")
            print()

    if not verbose:
        # Compact summary table
        print(f"  {'ID':<35} {'ROLE':<12} {'KIND':<14} {'AUTH'}")
        print(f"  {'-'*35} {'-'*12} {'-'*14} {'-'*12}")
        for icon, tid, role, kind, pstatus, msg in rows:
            auth_col = "verified" if "token issued" in msg else msg[:20]
            print(f"  {icon} {tid:<34} {role:<12} {kind:<14} {auth_col}")

    print()
    print("=" * 66)
    print(f"  Tenants processed : {ok_count}/{len(creative)}")
    if apply:
        print(f"  Auth verified     : {verified_count}/{ok_count}")
    print(f"  Workboard jobs    : {'emitted' if apply else 'dry-run only'}")
    print("=" * 66)

    if apply and ok_count > 0:
        print(f"\n✓ Studio tenants seeded. Check dispatch log:")
        print(f"  python -m services.v2_workboard --pending")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed studio tenant identities into the v2 system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Issue verification tokens and emit workboard jobs. Default is dry-run.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full detail per tenant.",
    )
    args = parser.parse_args()
    sys.exit(run(apply=args.apply, verbose=args.verbose))
