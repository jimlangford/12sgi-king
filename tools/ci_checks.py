"""Shared, offline CI lint and secret gates; never installs tools or fetches refs."""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITLEAKS_VERSION = "8.24.3"
EXCLUDES = [":(exclude).github/agents/**", ":(exclude).git/**"]
PYTHON_PATTERNS = ["*.py", "*.pyi", ":(exclude)site/**", *EXCLUDES]
STRICT_TARGETS = {
    "tools/lint_ai_tool_registry.py",
    "tools/civic_onboarding_readiness.py",
}
YAML_CONFIG = """extends: relaxed
rules:
  line-length: disable
  commas:
    ignore: |
      deploy/studio-assets/docker-compose.studio-assets.yml
"""
# Nine existing diagnostics, not blanket file or rule exclusions.
# Touched files also run the strict gate without these allowances.
CORRECTNESS_BASELINE = {
    ("_fix_failing.py", "invalid-syntax", "missing closing quote in string literal"): 1,
    ("services/king_bridge/app/_tree.py", "F821", "Undefined name `_neo_cypher`"): 1,
    ("services/studio_assets/app/main.py", "F821", "Undefined name `_sys`"): 5,
    ("watchers/moon_letter.py", "F821", "Undefined name `sourced_count`"): 1,
    ("watchers/studio_project.py", "F821", "Undefined name `store_path`"): 1,
}
SCRATCH_PREFIXES = (
    ".ci-checks-", ".secret-scan-", ".local-validation-", ".local-ci-",
)
SCRATCH_DIRS = {
    "site", ".git", ".venv", "venv", "env", ".tox", ".nox",
    "__pycache__", "node_modules", ".pytest_cache", ".ruff_cache",
    ".secret-scan-work", ".local-validation", "tmp", "temp",
}


class CheckError(RuntimeError):
    """A gate cannot run safely or has failed."""


def execute(command, *, capture=False, env=None, cwd=None):
    try:
        return subprocess.run(
            command, cwd=ROOT if cwd is None else cwd, shell=False, check=False,
            capture_output=capture, text=True, env=env,
        )
    except OSError as error:
        raise CheckError(f"Cannot run {command[0]}: {error.strerror}") from error


def require_success(result, name):
    if result.returncode:
        raise CheckError(f"{name} failed (exit {result.returncode})")


def git(*args):
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, shell=False, check=False,
            capture_output=True,
        )
    except OSError as error:
        raise CheckError(f"Cannot run git: {error.strerror}") from error
    require_success(result, f"git {args[0]}")
    return os.fsdecode(result.stdout)


def tracked(*patterns):
    return [path for path in git("ls-files", "-z", "--", *patterns, *EXCLUDES).split("\0")
            if path]


def permitted_path(name, *, python=False):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    parts = path.parts
    if not parts or ".git" in parts or parts[:2] == (".github", "agents"):
        return False
    if python and any(
        part in SCRATCH_DIRS or part.startswith(SCRATCH_PREFIXES) for part in parts[:-1]
    ):
        return False
    candidate = ROOT
    for part in parts:
        candidate /= part
        if candidate.is_symlink():
            return False
    return candidate.is_file()


def tool_command(name, *, module=False):
    if module and importlib.util.find_spec(name) is not None:
        return [sys.executable, "-m", name]
    binary = shutil.which(name)
    if not binary:
        raise CheckError(f"Missing required tool: {name}; install the pinned CI version manually")
    return [binary]


def verify_ref(ref):
    git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")


def default_base():
    candidates = ("refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    available = set(git("for-each-ref", "--format=%(refname)", *candidates).splitlines())
    for candidate in candidates:
        if candidate in available:
            return candidate
    raise CheckError(
        "No offline default comparison base (origin/HEAD or origin/main); "
        "specify --base and --head using existing local commits; no refs were fetched"
    )


def changed_python(base=None, head=None):
    ci_range = base is None and head is None and (
        "DIFF_BASE" in os.environ or "DIFF_HEAD" in os.environ
    )
    if ci_range:
        base = os.environ.get("DIFF_BASE", "")
        head = os.environ.get("DIFF_HEAD", "")
        if not head:
            raise CheckError("DIFF_HEAD is required when CI diff environment variables are set")
    else:
        base = default_base() if base is None else base
        head = "HEAD" if head is None else head
    verify_ref(head)
    if ci_range and (not base or set(base) == {"0"}):
        names = git(
            "diff-tree", "--root", "--no-commit-id", "--name-only",
            "--diff-filter=ACMR", "-r", "-z", head, "--", *PYTHON_PATTERNS,
        ).split("\0")
    else:
        verify_ref(base)
        names = git(
            "diff", "--name-only", "--diff-filter=ACMR", "-z",
            f"{base}...{head}", "--", *PYTHON_PATTERNS,
        ).split("\0")
    if not ci_range:
        entries = iter(git(
            "status", "--porcelain=v1", "-z", "--untracked-files=all",
            "--", *PYTHON_PATTERNS,
        ).split("\0"))
        for entry in entries:
            if not entry:
                continue
            status, name = entry[:2], entry[3:]
            names.append(name)
            # Porcelain -z puts the destination first; the source is another field.
            if "R" in status or "C" in status:
                next(entries, None)
    return {
        name for name in names
        if Path(name).suffix in {".py", ".pyi"} and permitted_path(name, python=True)
    }


def lint_python(args):
    ruff = tool_command("ruff", module=True)
    files = [name for name in tracked(*PYTHON_PATTERNS) if permitted_path(name)]
    if not files:
        raise CheckError("No tracked Python files found")
    result = execute([
        *ruff, "check", "--select", "E9,F63,F7,F82",
        "--output-format", "json", "--", *files,
    ], capture=True)
    if result.returncode not in (0, 1):
        raise CheckError(f"Ruff correctness failed (exit {result.returncode})")
    baseline = Counter(CORRECTNESS_BASELINE)
    unexpected = False
    for finding in json.loads(result.stdout or "[]"):
        path = Path(finding["filename"]).relative_to(ROOT).as_posix()
        code, message = finding["code"], finding["message"]
        key = (path, code, message)
        known = baseline[key] > 0
        baseline[key] -= 1
        level = "warning" if known else "error"
        row = finding["location"]["row"]
        label = "legacy baseline" if known else "new correctness error"
        print(f"::{level} file={path},line={row}::{label}: {code}: {message}", flush=True)
        unexpected |= not known
    # Evaluate changed scope even when correctness fails, so bad refs fail closed.
    targets = sorted(STRICT_TARGETS | changed_python(args.base, args.head))
    print("Ruff scope:\n" + "\n".join(targets), flush=True)
    strict = execute([*ruff, "check", "--", *targets])
    require_success(strict, "Ruff strict changed-file gate")
    if unexpected:
        raise CheckError("Ruff found new correctness errors outside the legacy baseline")


def lint_yaml(_args):
    yamllint = tool_command("yamllint", module=True)
    files = [name for name in tracked(
        ".github/workflows/*.yml", ".github/workflows/*.yaml",
        ".github/dependabot.yml", ".github/dependabot.yaml",
        "*compose*.yml", "*compose*.yaml",
    ) if permitted_path(name)]
    if not files:
        raise CheckError("No tracked workflow, Dependabot, or Compose YAML found")
    require_success(
        execute([*yamllint, "--strict", "-d", YAML_CONFIG, *files]), "yamllint",
    )


def lint_shell(_args):
    shellcheck = tool_command("shellcheck")
    exception = "scripts/check_surfaces.sh"
    files = [name for name in tracked(
        ".github/deploy/*.sh", "scripts/*.sh", "tests/*.sh", "v2/scripts/*.sh",
    ) if name != exception and permitted_path(name)]
    if not files:
        raise CheckError("No tracked maintained shell automation found")
    require_success(execute([*shellcheck, "--external-sources", *files]), "ShellCheck")
    require_success(execute([
        *shellcheck, "--external-sources", "--exclude=SC1091", exception,
    ]), "ShellCheck check_surfaces")


def scan_secrets(args):
    scanner = tool_command("gitleaks")
    version = execute([*scanner, "version"], capture=True)
    require_success(version, "Gitleaks version preflight")
    if version.stdout.strip().removeprefix("v") != GITLEAKS_VERSION:
        raise CheckError(f"Gitleaks {GITLEAKS_VERSION} required; install the pinned version manually")
    if git("rev-parse", "--is-shallow-repository").strip() != "false":
        raise CheckError("Git history incomplete; fetch manually before running the secrets gate")
    parent = (Path(tempfile.gettempdir()) if args.output_dir is None
              else Path(args.output_dir)).resolve()
    if parent.is_relative_to(ROOT) or ROOT.is_relative_to(parent):
        raise CheckError("Secret scratch directory must be outside the repository and its ancestors")
    if args.output_dir is not None:
        parent.mkdir(parents=True, exist_ok=True)
    names = git(
        "ls-files", "--cached", "--others", "--exclude-standard", "-z",
        "--", ".", *EXCLUDES,
    ).split("\0")
    with tempfile.TemporaryDirectory(prefix=".ci-checks-", dir=parent) as directory:
        work = Path(directory)
        # The existing tests derive fixture/config paths from their own location.
        # Copy them unchanged so synthetic secrets never enter the checkout.
        (work / "tests").mkdir()
        shutil.copyfile(ROOT / "tests" / "test_secret_scanner.py",
                        work / "tests" / "test_secret_scanner.py")
        shutil.copyfile(ROOT / ".gitleaks.toml", work / ".gitleaks.toml")
        env = {**os.environ, "GITLEAKS": scanner[0]}
        regression = execute([
            sys.executable, "-m", "unittest", "discover",
            "-s", "tests", "-p", "test_secret_scanner.py", "-v",
        ], capture=True, env=env, cwd=work)
        require_success(regression, "Real-scanner enforcement tests (output suppressed)")
        tree = work / "tree"
        tree.mkdir()
        for name in sorted(set(names)):
            if not permitted_path(name):
                continue
            source = ROOT / name
            destination = tree / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination, follow_symlinks=False)
        flags = [
            "--config", str(ROOT / ".gitleaks.toml"), "--ignore-gitleaks-allow",
            "--gitleaks-ignore-path", str(work / "absent"),
            "--redact", "--no-banner", "--log-level", "error",
        ]
        # Never echo scanner output, which may contain sensitive filenames or values.
        current = execute([*scanner, "dir", str(tree), *flags], capture=True)
        history = execute([
            *scanner, "git", ".", "--log-opts=--all --full-history", *flags,
        ], capture=True)
        failed = False
        for label, result in (("current working files", current), ("reachable history", history)):
            print(f"Gitleaks {label}: {'PASS' if result.returncode == 0 else 'FAIL'}", flush=True)
            failed |= result.returncode != 0
        if failed:
            raise CheckError("Gitleaks rejected the scan; inspect locally with redaction, never publish reports")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=[
        "lint-python", "lint-yaml", "lint-shell", "secrets",
    ])
    parser.add_argument(
        "--base", help="Python diff base (local default: existing origin/HEAD or origin/main)",
    )
    parser.add_argument("--head", help="Python committed diff head (local default: HEAD)")
    parser.add_argument("--output-dir", help="External scratch parent; default: system temporary directory")
    args = parser.parse_args(argv)
    stages = {
        "lint-python": lint_python, "lint-yaml": lint_yaml,
        "lint-shell": lint_shell, "secrets": scan_secrets,
    }
    try:
        stages[args.stage](args)
    except (CheckError, ValueError, OSError) as error:
        print(f"{args.stage}: ERROR: {error}", file=sys.stderr, flush=True)
        return 1
    print(f"{args.stage}: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
