"""
Integrated AI Autonomy + GitHub Error Repair Training

This module teaches king-* models to autonomously repair GitHub CI/CD errors.

Detection → Classification → Repair → Validation → Commit

Error archetypes with autonomy scores:
  ✓ 95: lint_error (black/ruff auto-fix)
  ✓ 90: type_error (generate type hints)
  ✓ 85: import_error (fix circular imports)
  ✓ 80: missing_dependency (add to requirements.txt)
  ✓ 65: config_missing (create template config)
  ✗ 0: permission_error (always owner gate)
"""

from services.ai_autonomy import ARCHETYPES, AutonomyArchetype


# GitHub error repair archetypes
_GITHUB_ARCHETYPES = {
    "github_lint_repair": AutonomyArchetype(
        name="github_lint_repair",
        autonomy_score=95,
        success_criteria="Run auto-formatter (black/ruff), commit, workflow re-runs and passes",
        safety_gates=[
            "Stop if more than 100 files changed",
            "Stop if formatter modifies non-code files",
        ],
        timeout_seconds=120,
        requires_owner_fields=["error_type", "file_path"],
        description="Repair GitHub linting errors autonomously"
    ),
    "github_type_repair": AutonomyArchetype(
        name="github_type_repair",
        autonomy_score=90,
        success_criteria="Generate type hints, validate with mypy/pyright, commit, workflow passes",
        safety_gates=[
            "Stop if error in third-party code",
            "Stop if affects more than 5 functions",
        ],
        timeout_seconds=180,
        requires_owner_fields=["error_type", "file_path"],
        description="Repair GitHub type checking errors autonomously"
    ),
    "github_import_repair": AutonomyArchetype(
        name="github_import_repair",
        autonomy_score=85,
        success_criteria="Fix circular imports, reorganize, validate, commit, workflow passes",
        safety_gates=[
            "Stop if circular import spans more than 3 modules",
            "Stop if affects more than 10 files",
        ],
        timeout_seconds=180,
        requires_owner_fields=["error_type", "file_path"],
        description="Repair GitHub import errors autonomously"
    ),
    "github_deps_repair": AutonomyArchetype(
        name="github_deps_repair",
        autonomy_score=80,
        success_criteria="Add package to requirements.txt, re-lock, commit, workflow passes",
        safety_gates=[
            "Stop if package name is ambiguous",
            "Stop if requires version negotiation with other packages",
        ],
        timeout_seconds=180,
        requires_owner_fields=["error_type", "package_name"],
        description="Repair missing dependency errors autonomously"
    ),
    "github_config_repair": AutonomyArchetype(
        name="github_config_repair",
        autonomy_score=65,
        success_criteria="Create config template with sensible defaults, commit, workflow passes",
        safety_gates=[
            "Stop if config structure is unclear from error",
            "Stop if defaults would require secrets or sensitive data",
        ],
        timeout_seconds=120,
        requires_owner_fields=["error_type", "config_file"],
        description="Create missing config files autonomously"
    ),
}

# Merge into global registry
ARCHETYPES.update(_GITHUB_ARCHETYPES)

__all__ = ["ARCHETYPES"]
