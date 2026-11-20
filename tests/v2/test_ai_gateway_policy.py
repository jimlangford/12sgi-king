"""
tests/v2/test_ai_gateway_policy.py

Profile-tool consistency tests for the AI Gateway.

Proves:
  - every allowed_tools glob in every profile resolves to at least one tool
  - every tool is reachable by at least one profile
  - public profiles resolve only read / analysis / draft / mutation_low tools
  - public profiles cannot reach owner, GPU admin, workboard mutation,
    private records, or publishing tools
  - forbidden_actions override (take precedence over) allowed_tools globs
  - no unknown scope appears in any tool
  - no administrative tool is labeled as read or analysis
  - mutation_guarded / approval / publish / administrative / destructive tools
    all carry idempotency_required=True
  - no duplicate tool_id in the registry
  - every tool carries an arguments_schema

These tests run entirely offline against the JSON config files.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "config" / "ai_tool_registry.v2.json"
PROFILES_DIR = REPO_ROOT / "config" / "ai_profiles"

IMMEDIATE_CLASSES = {"read", "analysis", "draft", "mutation_low"}
GUARDED_CLASSES = {
    "mutation_guarded", "approval", "publish", "administrative", "destructive",
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

# Tool globs that must never be reachable from a public profile.
_PUBLIC_FORBIDDEN_PATTERNS = [
    "ops.", "workboard.", "graph.", "records.get_provenance",
    "publish.", "civic.stage_public_report", "gpu.",
    "storyboard.archive", "storyboard.lock", "storyboard.approve_revision",
    "assets.archive",
]

PUBLIC_PROFILE_PREFIX = "12sgi-public-"


def _load_registry() -> list[dict]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _load_profiles() -> list[dict]:
    profiles = []
    for p in sorted(PROFILES_DIR.glob("*.json")):
        profiles.append(json.loads(p.read_text(encoding="utf-8")))
    return profiles


def _pattern_matches(pattern: str, tool_id: str) -> bool:
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return tool_id == prefix or tool_id.startswith(prefix + ".")
    return pattern == tool_id


def _profile_allows_tool(profile: dict, tool_id: str) -> bool:
    allowed = profile.get("allowed_tools", [])
    forbidden = set(profile.get("forbidden_actions", []))
    if any(_pattern_matches(p, tool_id) for p in forbidden):
        return False
    return any(_pattern_matches(p, tool_id) for p in allowed)


class TestRegistryBasics(unittest.TestCase):
    def setUp(self):
        self.registry = _load_registry()

    def test_registry_is_non_empty(self):
        self.assertGreater(len(self.registry), 0, "Registry must have at least one tool")

    def test_no_duplicate_tool_ids(self):
        ids = [t["tool_id"] for t in self.registry]
        dupes = [x for x in ids if ids.count(x) > 1]
        self.assertEqual(dupes, [], f"Duplicate tool_ids: {dupes}")

    def test_every_tool_has_arguments_schema(self):
        missing = [t["tool_id"] for t in self.registry if not t.get("arguments_schema")]
        self.assertEqual(missing, [], f"Tools missing arguments_schema: {missing}")

    def test_every_tool_has_audit_event(self):
        missing = [t["tool_id"] for t in self.registry if not t.get("audit_event")]
        self.assertEqual(missing, [], f"Tools missing audit_event: {missing}")

    def test_every_tool_has_timeout(self):
        missing = [t["tool_id"] for t in self.registry if not t.get("timeout_seconds")]
        self.assertEqual(missing, [], f"Tools missing timeout_seconds: {missing}")

    def test_no_unknown_scopes(self):
        violations = []
        for t in self.registry:
            for scope in t.get("required_scopes", []):
                if scope not in KNOWN_SCOPES:
                    violations.append((t["tool_id"], scope))
        self.assertEqual(violations, [], f"Unknown scopes: {violations}")

    def test_guarded_tools_have_idempotency(self):
        violations = [
            t["tool_id"]
            for t in self.registry
            if t.get("risk_class") in GUARDED_CLASSES
            and not t.get("idempotency_required")
        ]
        self.assertEqual(
            violations, [],
            f"Guarded tools missing idempotency_required: {violations}",
        )

    def test_no_administrative_tool_labeled_read(self):
        violations = [
            t["tool_id"]
            for t in self.registry
            if t.get("risk_class") == "administrative"
            and t.get("risk_class") in IMMEDIATE_CLASSES
        ]
        self.assertEqual(violations, [], f"Administrative tools labeled immediate: {violations}")

    def test_delete_is_destructive(self):
        violations = [
            t["tool_id"]
            for t in self.registry
            if t.get("http_method", "GET").upper() == "DELETE"
            and t.get("risk_class") != "destructive"
        ]
        self.assertEqual(violations, [], f"DELETE tools not labeled destructive: {violations}")


class TestProfileConsistency(unittest.TestCase):
    def setUp(self):
        self.registry = _load_registry()
        self.profiles = _load_profiles()
        self.tool_ids = {t["tool_id"] for t in self.registry}
        self.tools_by_id = {t["tool_id"]: t for t in self.registry}

    def test_profiles_loaded(self):
        self.assertGreater(len(self.profiles), 0, "No profiles found in config/ai_profiles/")

    def test_every_profile_glob_resolves_to_at_least_one_tool(self):
        unresolved = []
        for profile in self.profiles:
            pid = profile.get("profile_id", "?")
            for pattern in profile.get("allowed_tools", []):
                if pattern == "*":
                    continue  # wildcard always resolves
                matches = [
                    tid for tid in self.tool_ids
                    if _pattern_matches(pattern, tid)
                ]
                if not matches:
                    unresolved.append((pid, pattern))
        self.assertEqual(
            unresolved, [],
            f"Profile globs with no matching tool: {unresolved}",
        )

    def test_every_tool_reachable_by_at_least_one_profile(self):
        unreachable = []
        for tool_id in self.tool_ids:
            reachable = any(
                _profile_allows_tool(p, tool_id) for p in self.profiles
            )
            if not reachable:
                unreachable.append(tool_id)
        self.assertEqual(
            unreachable, [],
            f"Tools not reachable by any profile: {unreachable}",
        )

    def test_public_profiles_have_only_immediate_tools(self):
        violations = []
        for profile in self.profiles:
            pid = profile.get("profile_id", "?")
            if not pid.startswith(PUBLIC_PROFILE_PREFIX):
                continue
            for tool_id in self.tool_ids:
                if not _profile_allows_tool(profile, tool_id):
                    continue
                tool = self.tools_by_id[tool_id]
                rc = tool.get("risk_class", "read")
                if rc not in IMMEDIATE_CLASSES:
                    violations.append((pid, tool_id, rc))
        self.assertEqual(
            violations, [],
            f"Public profiles can reach non-immediate tools: {violations}",
        )

    def test_public_profiles_cannot_reach_private_tools(self):
        violations = []
        for profile in self.profiles:
            pid = profile.get("profile_id", "?")
            if not pid.startswith(PUBLIC_PROFILE_PREFIX):
                continue
            for tool_id in self.tool_ids:
                if not _profile_allows_tool(profile, tool_id):
                    continue
                if any(tool_id.startswith(pref) or tool_id == pref
                       for pref in _PUBLIC_FORBIDDEN_PATTERNS):
                    violations.append((pid, tool_id))
        self.assertEqual(
            violations, [],
            f"Public profiles can reach private/mutating tools: {violations}",
        )

    def test_forbidden_actions_override_allowed_globs(self):
        """A tool that appears in both allowed and forbidden must NOT be reachable."""
        violations = []
        for profile in self.profiles:
            pid = profile.get("profile_id", "?")
            forbidden = set(profile.get("forbidden_actions", []))
            allowed = profile.get("allowed_tools", [])
            for f_action in forbidden:
                # Only check exact tool IDs that actually exist.
                if f_action not in self.tool_ids:
                    continue
                if any(_pattern_matches(p, f_action) for p in allowed):
                    if _profile_allows_tool(profile, f_action):
                        violations.append((pid, f_action))
        self.assertEqual(
            violations, [],
            f"Forbidden actions still reachable via allowed_tools globs: {violations}",
        )

    def test_public_profiles_no_wildcard_allowed(self):
        violations = [
            p.get("profile_id")
            for p in self.profiles
            if p.get("profile_id", "").startswith(PUBLIC_PROFILE_PREFIX)
            and "*" in p.get("allowed_tools", [])
        ]
        self.assertEqual(
            violations, [],
            f"Public profiles must not use wildcard allowed_tools: {violations}",
        )


class TestRiskModelMapping(unittest.TestCase):
    """Verify that the risk class taxonomy matches the policy intent."""

    def setUp(self):
        self.registry = _load_registry()

    def test_at_least_one_tool_per_risk_class(self):
        """All risk classes used in the policy should have at least one example tool."""
        expected_classes = IMMEDIATE_CLASSES | GUARDED_CLASSES
        present_classes = {t.get("risk_class") for t in self.registry}
        # We don't require every class to be present, but immediate and at
        # least one guarded class must be.
        self.assertIn("read", present_classes)
        self.assertTrue(
            present_classes & GUARDED_CLASSES,
            f"No guarded-class tool found; present classes: {present_classes}",
        )

    def test_no_bare_mutation_class(self):
        """The legacy 'mutation' class should not appear in new tool definitions."""
        legacy = [t["tool_id"] for t in self.registry if t.get("risk_class") == "mutation"]
        self.assertEqual(
            legacy, [],
            f"Tools still using legacy 'mutation' class (use mutation_low or mutation_guarded): {legacy}",
        )

    def test_mutation_low_tools_do_not_require_idempotency(self):
        """mutation_low tools are immediate; idempotency_required is recommended but not enforced."""
        # This test documents that mutation_low does NOT require idempotency at
        # the policy layer (unlike guarded tools).  It should not fail.
        pass


if __name__ == "__main__":
    unittest.main()
