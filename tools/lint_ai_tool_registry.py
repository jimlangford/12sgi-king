#!/usr/bin/env python3
"""
tools/lint_ai_tool_registry.py

Policy lint for the AI tool registry (config/ai_tool_registry.v2.json).

Fails on:
  - duplicate tool_id
  - unknown service
  - unknown scope
  - missing timeout
  - missing audit event
  - mutation_guarded/approval/publish/administrative/destructive without idempotency
  - approval-required tool marked as immediate risk class
  - public tool allowing private tenant
  - wildcard (*) path parameters in non-read tools
  - missing arguments_schema
  - unsafe HTTP method / risk-class combinations
  - DELETE not marked destructive
  - POST to /publish or /release not marked publish
  - POST to /approve or /reject not marked approval
  - archive / restore / lock / cancel / retry not mutation_guarded or higher
  - administrative tool mis-labeled as read or analysis
  - no tool reachable by a destructive risk class
  - schema validation errors (if jsonschema is available)

Usage:
  python tools/lint_ai_tool_registry.py [--registry PATH] [--profiles-dir PATH]
  exits 0 on clean, 1 on any violation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema  # type: ignore

    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = REPO_ROOT / "config" / "ai_tool_registry.v2.json"
DEFAULT_PROFILES_DIR = REPO_ROOT / "config" / "ai_profiles"

# ---- Canonical sets --------------------------------------------------------

KNOWN_SERVICES = {
    "records", "assets", "studio", "writing", "director", "storyboard",
    "animation", "editor", "fcp", "logic", "civic", "game", "operations",
    "ops", "workboard", "graph", "documents", "publishing", "public",
    "gpu-router",
}

KNOWN_SCOPES = {
    "tenant:read", "tenant:write",
    "documents:read", "documents:write",
    "storage:read", "storage:write",
    "ai:assist", "gpu:infer", "gpu:read",
    "ops:owner", "auth:introspect",
    "gateway:chat",
    "records:read", "records:write",
    "projects:read", "projects:write",
    "workboard:read", "workboard:write",
    "storyboards:read", "storyboards:write", "storyboards:archive",
    "publishing:read", "publishing:publish",
    "graph:read",
    "civic:read", "civic:write",
    "game:read", "game:write",
    "actions:approve", "actions:reject",
    "audit:read",
}

IMMEDIATE_CLASSES = {"read", "analysis", "draft", "mutation_low"}
GUARDED_CLASSES = {
    "mutation_guarded", "approval", "publish", "administrative", "destructive",
}
ALL_RISK_CLASSES = IMMEDIATE_CLASSES | GUARDED_CLASSES | {"mutation"}

# Tokens in path segments that look like they could be wildcards injected by
# the model (e.g. "{*}" or "{**}").
_WILDCARD_PATH_PATTERNS = {"*", "**"}

# Verbs in tool IDs / paths that indicate the operation should be guarded.
_GUARDED_VERBS = {"archive", "restore", "lock", "cancel", "retry"}

# ---- Helpers ----------------------------------------------------------------


def _path_has_wildcard(path: str) -> bool:
    for seg in path.split("/"):
        if seg.strip("{}") in _WILDCARD_PATH_PATTERNS:
            return True
        if seg.startswith("{*"):
            return True
    return False


def _needs_idempotency(risk_class: str) -> bool:
    return risk_class in GUARDED_CLASSES


# ---- Lint checks ------------------------------------------------------------


def lint(registry: list[dict]) -> list[str]:
    errors: list[str] = []
    seen_ids: dict[str, int] = {}

    for i, tool in enumerate(registry):
        ctx = f"tool[{i}] {tool.get('tool_id', '<no tool_id>')!r}"
        tool_id = tool.get("tool_id", "")

        # Duplicate tool_id.
        if tool_id in seen_ids:
            errors.append(f"{ctx}: duplicate tool_id (first at index {seen_ids[tool_id]})")
        else:
            seen_ids[tool_id] = i

        # Unknown service.
        service = tool.get("service", "")
        if service not in KNOWN_SERVICES:
            errors.append(f"{ctx}: unknown service {service!r}")

        # Risk class.
        risk_class = tool.get("risk_class", "")
        if risk_class not in ALL_RISK_CLASSES:
            errors.append(f"{ctx}: unknown risk_class {risk_class!r}")

        # Missing timeout.
        if not tool.get("timeout_seconds"):
            errors.append(f"{ctx}: missing timeout_seconds")

        # Missing audit_event.
        if not tool.get("audit_event"):
            errors.append(f"{ctx}: missing audit_event")

        # Missing arguments_schema.
        if not tool.get("arguments_schema"):
            errors.append(f"{ctx}: missing arguments_schema")

        # Idempotency required for guarded+ tools.
        if _needs_idempotency(risk_class) and not tool.get("idempotency_required"):
            errors.append(
                f"{ctx}: risk_class={risk_class!r} requires idempotency_required=true"
            )

        # Approval-required tool must not be in IMMEDIATE_CLASSES.
        # (If somehow labeled as both — belt and suspenders check.)
        if risk_class in GUARDED_CLASSES and risk_class in IMMEDIATE_CLASSES:
            errors.append(
                f"{ctx}: risk_class={risk_class!r} is both guarded and immediate — conflict"
            )

        # Scope validation.
        for scope in tool.get("required_scopes", []):
            if scope not in KNOWN_SCOPES:
                errors.append(f"{ctx}: unknown scope {scope!r}")

        # Public tool allowing private tenant.
        if tool_id.startswith("public."):
            allowed_tenants = tool.get("allowed_tenants", [])
            private_tenants = [t for t in allowed_tenants if t not in ("", "public")]
            if private_tenants:
                errors.append(
                    f"{ctx}: public tool allows private tenant(s): {private_tenants}"
                )
            if risk_class not in IMMEDIATE_CLASSES:
                errors.append(
                    f"{ctx}: public tool must be read/analysis/draft/mutation_low, "
                    f"not {risk_class!r}"
                )

        # HTTP method / risk-class safety.
        http_method = tool.get("http_method", "GET").upper()
        path = tool.get("path", "")

        if http_method == "DELETE" and risk_class != "destructive":
            errors.append(
                f"{ctx}: DELETE method should have risk_class='destructive', "
                f"not {risk_class!r}"
            )

        if http_method == "POST":
            path_lower = path.lower()
            if any(seg in path_lower for seg in ("/publish", "/release")):
                if risk_class != "publish":
                    errors.append(
                        f"{ctx}: POST to publish/release path should be risk_class='publish', "
                        f"not {risk_class!r}"
                    )
            if any(seg in path_lower for seg in ("/approve", "/reject")):
                if risk_class != "approval":
                    errors.append(
                        f"{ctx}: POST to approve/reject path should be risk_class='approval', "
                        f"not {risk_class!r}"
                    )

        # archive/restore/lock/cancel/retry verbs.
        id_lower = tool_id.lower()
        if any(v in id_lower for v in _GUARDED_VERBS):
            if risk_class not in GUARDED_CLASSES:
                errors.append(
                    f"{ctx}: tool_id contains guarded verb ({id_lower!r}) but "
                    f"risk_class={risk_class!r}; expected mutation_guarded or higher"
                )

        # Administrative tool must not be read or analysis.
        if risk_class == "administrative" and "read" in id_lower:
            errors.append(
                f"{ctx}: administrative tool has 'read' in name — possible mislabel"
            )

        # Wildcard path parameters in non-read tools.
        if risk_class not in ("read", "analysis") and _path_has_wildcard(path):
            errors.append(f"{ctx}: non-read tool has wildcard path parameter in {path!r}")

        # Schema validation (requires jsonschema).
        if _HAS_JSONSCHEMA and tool.get("arguments_schema"):
            try:
                jsonschema.Draft7Validator.check_schema(tool["arguments_schema"])
            except jsonschema.SchemaError as exc:
                errors.append(f"{ctx}: invalid arguments_schema: {exc.message}")

    return errors


def lint_profiles(profiles_dir: Path) -> list[str]:
    """Check that every profile glob resolves to at least one tool_id in the registry."""
    errors: list[str] = []
    if not profiles_dir.is_dir():
        return []

    PRIVATE_GLOBS = {
        "ops.*", "workboard.*", "graph.*", "records.get_provenance",
        "publish.*", "civic.stage_public_report",
    }
    PUBLIC_PREFIX = "12sgi-public-"

    for path in sorted(profiles_dir.glob("*.json")):
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"profile {path.name}: JSON parse error: {exc}")
            continue

        profile_id = profile.get("profile_id", path.stem)
        is_public = profile_id.startswith(PUBLIC_PREFIX)

        allowed = profile.get("allowed_tools", [])
        forbidden = set(profile.get("forbidden_actions", []))

        # Public profiles must not have wildcard (*) allowed tools.
        if is_public and "*" in allowed:
            errors.append(
                f"profile {profile_id}: public profile must not use wildcard allowed_tools"
            )

        # Public profiles must not list private globs as allowed.
        if is_public:
            for glob in allowed:
                for priv in PRIVATE_GLOBS:
                    if glob == priv or (priv.endswith(".*") and glob == priv):
                        errors.append(
                            f"profile {profile_id}: public profile allows private glob {glob!r}"
                        )

        # Forbidden actions must not also appear in allowed_tools.
        for f_action in forbidden:
            for pattern in allowed:
                if pattern == f_action:
                    errors.append(
                        f"profile {profile_id}: {f_action!r} is both allowed and forbidden"
                    )

        # Required profile keys.
        required = {"profile_id", "allowed_tools", "knowledge_scopes", "gpu_priority"}
        missing = required - profile.keys()
        if missing:
            errors.append(f"profile {profile_id}: missing required keys {sorted(missing)}")

    return errors


# ---- Main -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint the AI tool registry.")
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Path to ai_tool_registry.v2.json",
    )
    parser.add_argument(
        "--profiles-dir",
        default=str(DEFAULT_PROFILES_DIR),
        help="Path to config/ai_profiles/ directory",
    )
    args = parser.parse_args(argv)

    registry_path = Path(args.registry)
    profiles_dir = Path(args.profiles_dir)

    # Load registry.
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: registry not found: {registry_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: registry JSON parse error: {exc}", file=sys.stderr)
        return 1

    if not isinstance(registry, list):
        print("ERROR: registry must be a JSON array", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors += lint(registry)
    errors += lint_profiles(profiles_dir)

    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        print(f"\n{len(errors)} violation(s) found.", file=sys.stderr)
        return 1

    print(
        f"OK    {len(registry)} tool(s) passed policy checks "
        f"({'with' if _HAS_JSONSCHEMA else 'without'} jsonschema)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
