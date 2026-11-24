"""Owner-approved PUBLIC releases; no private runtime, DNS, or content approval changes."""

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import local_validation as validation
import public_build_hygiene as hygiene

ROOT = Path(__file__).resolve().parents[1]
STATIC_SUFFIXES = {
    ".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".gif",
    ".webp", ".ico", ".avif", ".woff", ".woff2", ".ttf", ".otf", ".txt",
    ".xml", ".webmanifest", ".pdf", ".mp3", ".mp4", ".webm", ".ogg", ".wav",
    ".mjs", ".geojson", ".md",
}
PRIVATE_PARTS = {
    "go", "king_private_src", "private", ".git", "node_modules", "__pycache__",
    "receipts", "logs", "models", "databases", "empty-home", "scratch",
}
PRIVATE_NAMES = {
    *(name.lower() for name in validation.FORBIDDEN),
    "buildinfo.json", "receipt.json", "coverage.xml",
    "test-results.xml", "cname", "local_validation.py",
}
PRIVATE_TEXT = re.compile(
    r"PRIVATE:[^\n]*(?:Tailscale|owner|king-local|not part of the public)"
    r"|owner ops board|Tailscale-only"
    r"|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net\b"
    r"|(?:[A-Z]:\\Users\\|/Users/|/home/)[^\s\"<>]+"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.I,
)


class ReleaseError(Exception):
    pass


def git(root, *args):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    # Prevent a checkout hook from deploying anything when creating our snapshot;
    # source-backup push retains the owner's pre-push policy.
    hooks = ["-c", "core.hooksPath=/dev/null"] if args[0] == "worktree" else []
    process = subprocess.Popen(
        ["git", *hooks, *args], cwd=root, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=os.name == "posix",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    try:
        stdout, _ = process.communicate(timeout=120)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        validation.terminate_tree(process)
        raise ReleaseError("Git operation timed out or was interrupted; process tree stopped") from None
    if process.returncode:
        raise ReleaseError("Git operation failed (details withheld; inspect locally)")
    return stdout.strip()


def clean_source(root, sha):
    if git(root, "rev-parse", "HEAD") != sha:
        raise ReleaseError("HEAD differs from the explicitly approved commit")
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ReleaseError("Reviewed source must be clean, including untracked files")
    if git(root, "rev-parse", "--is-shallow-repository") != "false":
        raise ReleaseError("Complete reachable history is required; provision it manually")
    digest = hashlib.sha256()
    for name in git(
        root, "ls-files", "-z", "--", ".", ":(exclude).github/agents/**",
    ).split("\0"):
        if not name:
            continue
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ReleaseError("Source symlinks, submodules, and missing files are not supported")
        digest.update(name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def check_base(root, base, sha):
    if not base or not re.fullmatch(r"[a-f0-9]{40}", base) or base == sha:
        raise ReleaseError("Lint base must be an explicitly reviewed prior full commit SHA")
    if git(root, "rev-parse", "--verify", base + "^{commit}") != base:
        raise ReleaseError("Reviewed comparison base is not a locally available commit")
    git(root, "merge-base", "--is-ancestor", base, sha)


@contextlib.contextmanager
def release_lock(state):
    lock = state / "release.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ReleaseError("Release already locked; inspect the recorded PID before manual recovery") from error
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def file_hashes(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ReleaseError("PUBLIC export root must be a regular directory")
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ReleaseError("PUBLIC output must not contain symlinks")
        if path.is_file():
            if path.stat().st_nlink != 1:
                raise ReleaseError("PUBLIC output must not contain hardlinks")
            result[path.relative_to(directory).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        elif not path.is_dir():
            raise ReleaseError("PUBLIC output contains a non-regular file")
    return result


def export_public(site, destination, sha):
    try:
        validation.check_build(site)
    except ValueError as error:
        raise ReleaseError("PUBLIC build isolation check failed") from error
    # Fail closed on unexpected file types or private declarations; don't silently
    # strip a leaking build and call the remainder the accessibility-validated build.
    for path in site.rglob("*"):
        relative = path.relative_to(site)
        name = relative.as_posix()
        if path.is_symlink():
            raise ReleaseError("PUBLIC output contains a symlink")
        if any(part.lower() in PRIVATE_PARTS for part in relative.parts):
            raise ReleaseError("PRIVATE directory in PUBLIC output")
        if hygiene.is_build_artifact(relative):
            raise ReleaseError("Implementation or backup artifact in PUBLIC output")
        if name.lower() in {"buildinfo.json", "cname"}:
            continue
        if (
            name.lower() in PRIVATE_NAMES or path.name.lower() in PRIVATE_NAMES
            or path.name.lower().endswith(".dc.html")
        ):
            raise ReleaseError("PRIVATE file in PUBLIC output")
        if any(part.startswith(".") for part in relative.parts) and name != ".nojekyll":
            raise ReleaseError("Hidden file in PUBLIC output")
        if path.is_dir():
            continue
        if not path.is_file() or path.stat().st_nlink != 1:
            raise ReleaseError("PUBLIC output must contain only regular unlinked files")
        if path.suffix.lower() not in STATIC_SUFFIXES and name != ".nojekyll":
            raise ReleaseError("Unreviewed file type in PUBLIC output")
        if path.suffix.lower() in {
            ".html", ".css", ".js", ".json", ".svg", ".txt", ".xml",
            ".mjs", ".geojson", ".md",
        }:
            if PRIVATE_TEXT.search(path.read_text(encoding="utf-8", errors="replace")):
                raise ReleaseError("PRIVATE declaration or local address in PUBLIC output")
    shutil.copytree(site, destination, ignore=lambda _, names: [
        name for name in names if name.lower() in {"buildinfo.json", "cname"}
    ])
    validation.private_file(destination / "buildinfo.json", json.dumps({
        "sha": sha, "sha_short": sha[:12],
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }) + "\n")
    return file_hashes(destination)


def validate(source, run, base, sha):
    # Invoke the existing FULL runner ourselves, never accept a supplied receipt.
    scratch = validation.private_directory(run.parent / "scratch")
    browser = validation.private_directory(run.parents[2] / "browser")
    env = {**os.environ, "RUNNER_TEMP": str(browser),
           "TMPDIR": str(scratch), "TEMP": str(scratch), "TMP": str(scratch)}
    result = validation.execute(
        [sys.executable, "tools/local_validation.py", "--output-dir", str(run),
         "--base", base, "--head", sha],
        source, env, run.parent / "validation.log", 3900,
    )
    receipts = list(run.glob("run-*/receipt.json"))
    if result["exit_code"] or len(receipts) != 1:
        raise ReleaseError("Full validation failed; last good release is unchanged")
    receipt = json.loads(receipts[0].read_text())
    stages = receipt.get("stages", [])
    if (
        receipt.get("local_validation") != "passed"
        or receipt.get("git", {}).get("commit") != sha
        or receipt.get("git", {}).get("dirty") is not False
        or receipt.get("selected_stages") != list(validation.STAGES)
        or [stage.get("stage") for stage in stages] != list(validation.STAGES)
        or any(stage.get("exit_code") != 0 or stage.get("errors") for stage in stages)
        or any(not stage.get("commands") for stage in stages)
        or any(command.get("exit_code") != 0 for stage in stages for command in stage["commands"])
    ):
        raise ReleaseError("Incomplete or mismatched full validation evidence")
    coverage = stages[-1].get("coverage", {})
    if (
        coverage.get("shard") != "all" or coverage.get("scan_errors") != 0
        or not coverage.get("pages_scanned")
        or coverage["pages_scanned"] != stages[-2].get("coverage", {}).get("html_pages")
    ):
        raise ReleaseError("A successful full-site accessibility scan is required")
    return receipts[0].parent / "a11y" / "site"


def scan_export(source, public, work):
    result = validation.execute(
        ["gitleaks", "dir", str(public), "--config", str(source / ".gitleaks.toml"),
         "--ignore-gitleaks-allow", "--gitleaks-ignore-path", str(work / "absent"),
         "--redact", "--no-banner", "--log-level", "error"],
        source, dict(os.environ), work / "export-secret-scan.log", 600,
    )
    if result["exit_code"]:
        raise ReleaseError("PUBLIC export secret scan failed (output withheld)")


def verify_release(release, sha):
    if release.is_symlink() or (release / "manifest.json").is_symlink():
        raise ReleaseError("Release records must not be symlinks")
    manifest = json.loads((release / "manifest.json").read_text())
    marker = json.loads((release / "public" / "buildinfo.json").read_text())
    if (
        manifest.get("commit") != sha or marker.get("sha") != sha
        or manifest.get("files") != file_hashes(release / "public")
    ):
        raise ReleaseError("Immutable release integrity check failed")


def promote(state, release):
    current = state / "current"
    if current.exists() and not current.is_symlink():
        raise ReleaseError("current must be an owned release symlink, not an existing serving directory")
    pointer = state / f".pointer-{uuid.uuid4().hex}"
    try:
        pointer.symlink_to(release / "public", target_is_directory=True)
        os.replace(pointer, current)
    finally:
        pointer.unlink(missing_ok=True)


def origin_url(root, repository):
    urls = git(root, "remote", "get-url", "--all", "origin").splitlines()
    pushes = git(root, "remote", "get-url", "--push", "--all", "origin").splitlines()
    allowed = {
        f"https://github.com/{repository}", f"https://github.com/{repository}.git",
        f"git@github.com:{repository}.git", f"ssh://git@github.com/{repository}.git",
    }
    if len(urls) != 1 or pushes != urls or urls[0] not in allowed:
        raise ReleaseError("origin must be the single expected GitHub repository without URL credentials")
    rewrites = subprocess.run(
        ["git", "config", "--get-regexp", r"^url\..*\.(insteadof|pushinsteadof)$"],
        cwd=root, capture_output=True, check=False,
    )
    if rewrites.returncode != 1:
        raise ReleaseError("Git URL rewriting is not allowed for source backup")
    return urls[0]


def public_backup_url(repository, expected_url):
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository or ""):
        raise ReleaseError("Expected GitHub repository is required")
    owner, name = repository.split("/")
    default_url = f"https://{owner}.github.io/{name}/"
    if expected_url != default_url:
        raise ReleaseError("Explicit default github.io backup URL is required")
    return expected_url


def check_pages(repository, expected_url, token):
    public_backup_url(repository, expected_url)
    if not token:
        raise ReleaseError("Explicit default github.io backup URL and read token are required")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/pages",
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        settings = json.load(response)
    if (
        settings.get("cname") or settings.get("html_url") != expected_url
        or settings.get("build_type") != "workflow"
    ):
        raise ReleaseError("Pages is not the explicitly configured separate github.io backup")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def verify_backup(repository, expected_url, sha):
    url = public_backup_url(repository, expected_url) + "buildinfo.json"
    if not re.fullmatch(r"[a-f0-9]{40}", sha or ""):
        raise ReleaseError("A full expected PUBLIC commit SHA is required")
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    for attempt in range(3):
        try:
            with opener.open(request, timeout=10) as response:
                body = response.read(65537)
                if len(body) > 65536 or json.loads(body).get("sha") != sha:
                    raise ValueError("PUBLIC marker mismatch")
            return datetime.now(timezone.utc).isoformat()
        except (OSError, ValueError, AttributeError):
            if attempt < 2:
                time.sleep(2)
    raise ReleaseError("PUBLIC backup served-commit verification failed")


def backup_summary(url, sha, verified_at=None):
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    with Path(summary).open("a", encoding="utf-8") as handle:
        if verified_at:
            handle.write(
                f"PUBLIC backup verified: {url}\n\n"
                f"Served commit: `{sha}`\n\nVerified at: {verified_at}\n"
            )
        else:
            handle.write(
                "PUBLIC backup served-commit verification **FAILED**. "
                "Pages may already have deployed; no rollback was attempted. "
                "The local release is unaffected.\n"
            )


def sync_source(root, snapshot, repository, branch, sha, fingerprint, work):
    # Scan ALL locally reachable source history immediately before any network sync.
    outcome = validation.execute(
        [sys.executable, "tools/ci_checks.py", "--stage", "secrets",
         "--output-dir", str(work / "source-scan")],
        root, dict(os.environ), work / "source-secret-scan.log", 600,
    )
    if outcome["exit_code"]:
        raise ReleaseError("Source history secret scan failed; backup not attempted")
    url = origin_url(root, repository)
    if clean_source(root, sha) != fingerprint:
        raise ReleaseError("Source changed before backup")
    if git(root, "branch", "--show-current") != branch:
        raise ReleaseError("Source backup requires the explicitly selected checked-out branch")
    remote = git(root, "ls-remote", "--heads", url, f"refs/heads/{branch}").split()
    if remote:
        git(snapshot, "fetch", "--no-tags", url, f"refs/heads/{branch}")
        git(snapshot, "merge-base", "--is-ancestor", "FETCH_HEAD", sha)
    # Push ONLY the already reviewed commit: never add/commit, pull/reset, or force.
    if clean_source(root, sha) != fingerprint:
        raise ReleaseError("Source changed during backup preflight")
    git(root, "-c", "push.followTags=false", "-c", "remote.origin.mirror=false",
        "push", "--no-follow-tags", "--recurse-submodules=no",
        "origin", f"{sha}:refs/heads/{branch}")


def managed_state(path):
    # Never chmod/adopt an arbitrary existing directory, even if it is empty.
    if path.is_symlink() or path.resolve() != path.absolute():
        raise ReleaseError("State and its parent path must not use symlinks")
    marker = path / ".public-release-state"
    if path.exists():
        if (
            not path.is_dir() or marker.is_symlink() or not marker.is_file()
            or marker.read_text() != "12sgi-public-release-v1\n"
        ):
            raise ReleaseError("Existing state must be initialized by this release tool")
    else:
        path.mkdir(mode=0o700, parents=True)
        validation.private_file(marker, "12sgi-public-release-v1\n")
    if os.name == "posix" and (
        path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077
    ):
        raise ReleaseError("State must be owner-only; fix permissions explicitly before retrying")
    for name in ("work", "releases", "browser", "release.lock", "latest.json"):
        if (path / name).is_symlink():
            raise ReleaseError("Managed state paths must not be symlinks")
    return path


def check_current(state):
    pointer = state / "current"
    if not pointer.is_symlink():
        if pointer.exists():
            raise ReleaseError("Existing current serving root is not managed by this tool")
        return
    target = pointer.resolve()
    releases = state / "releases"
    if (
        target.name != "public" or target.parent.parent != releases
        or not re.fullmatch(r"[a-f0-9]{40}", target.parent.name)
        or target.parent.is_symlink()
    ):
        raise ReleaseError("Existing serving pointer is not a managed retained release")
    verify_release(target.parent, target.parent.name)


def save_status(state, status):
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = state / f".status-{uuid.uuid4().hex}"
    validation.private_file(path, json.dumps(status, indent=2) + "\n")
    os.replace(path, state / "latest.json")


def prepare_release(args, state, release, fingerprint, work, snapshot, status):
    initial = clean_source(snapshot, args.expected_sha)
    # Tool dependencies are not source/build inputs. Copy only the existing
    # locked browser installation; never import ignored owner data or models.
    browser = ROOT / "tools/a11y/node_modules"
    if browser.is_dir():
        shutil.copytree(browser, snapshot / "tools/a11y/node_modules", symlinks=False)
    if not release.exists():
        site = validate(snapshot, work / "validation", args.base, args.expected_sha)
        if (
            clean_source(snapshot, args.expected_sha) != initial
            or clean_source(ROOT, args.expected_sha) != fingerprint
        ):
            raise ReleaseError("Source changed during validation")
        candidate = work / "candidate"
        candidate.mkdir()
        files = export_public(site, candidate / "public", args.expected_sha)
        scan_export(snapshot, candidate / "public", work)
        validation.private_file(candidate / "manifest.json", json.dumps({
            "commit": args.expected_sha, "validated_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
        }, indent=2) + "\n")
        release.parent.mkdir(exist_ok=True)
        candidate.rename(release)
        for path in release.rglob("*"):
            path.chmod(0o555 if path.is_dir() else 0o444)
        release.chmod(0o555)
    verify_release(release, args.expected_sha)
    if clean_source(ROOT, args.expected_sha) != fingerprint:
        raise ReleaseError("Source changed before promotion")
    status["validation"] = "passed"
    if not args.package_only:
        promote(state, release)
        status["local_promotion"] = "passed"
        status["promoted_at"] = datetime.now(timezone.utc).isoformat()
    save_status(state, status)
    print(f"PUBLIC release ready: {args.expected_sha}")
    if args.sync_source:
        try:
            sync_source(ROOT, snapshot, args.repository, args.branch,
                        args.expected_sha, fingerprint, work)
            status["source_backup"] = "passed"
            status["source_backup_at"] = datetime.now(timezone.utc).isoformat()
        except (ReleaseError, OSError, subprocess.TimeoutExpired):
            status["source_backup"] = "failed"
            status["error"] = "Source backup failed; validated local release retained"
            save_status(state, status)
            print("SOURCE BACKUP FAILED; validated local release retained", file=sys.stderr)
            return 2
        save_status(state, status)
    return 0


def run(args):
    state = args.state.expanduser().absolute()
    if state == ROOT or state.is_relative_to(ROOT) or ROOT.is_relative_to(state):
        raise ReleaseError("PRIVATE state must be outside the checkout and its ancestors")
    if not re.fullmatch(r"[a-f0-9]{40}", args.expected_sha):
        raise ReleaseError("Use the full explicitly reviewed commit SHA")
    managed_state(state)
    with release_lock(state):
        check_current(state)
        status = {
            "visibility": "PRIVATE", "requested_commit": args.expected_sha,
            "validation": "not_attempted", "local_promotion": "not_attempted",
            "source_backup": "pending" if args.sync_source else "not_requested",
            "repository": args.repository, "branch": args.branch,
            "serving_url": "not configured or checked by this command",
            "pages_deployment": "not checked; consult Actions deployment status",
        }
        save_status(state, status)
        release = state / "releases" / args.expected_sha
        if release.is_symlink():
            raise ReleaseError("Managed releases must not be symlinks")
        if args.rollback:
            verify_release(release, args.expected_sha)
            promote(state, release)
            status.update(validation="retained_release_verified", local_promotion="passed")
            save_status(state, status)
            return 0
        try:
            fingerprint = clean_source(ROOT, args.expected_sha)
            check_base(ROOT, args.base, args.expected_sha)
        except (ReleaseError, OSError):
            status["error"] = "Source or reviewed comparison base preflight failed"
            save_status(state, status)
            raise
        work = validation.private_directory(state / "work" / uuid.uuid4().hex)
        snapshot = work / "source"
        git(ROOT, "worktree", "add", "--detach", "--quiet", str(snapshot), args.expected_sha)
        try:
            return prepare_release(args, state, release, fingerprint, work, snapshot, status)
        except (ReleaseError, OSError, ValueError, subprocess.TimeoutExpired):
            status["error"] = "Release operation refused; inspect PRIVATE evidence"
            save_status(state, status)
            raise
        finally:
            # Only the detached worktree created above, never the owner's checkout.
            try:
                git(ROOT, "worktree", "remove", "--force", str(snapshot))
            except (ReleaseError, OSError, subprocess.TimeoutExpired):
                status["cleanup"] = "Detached worktree cleanup failed; owner inspection required"
                save_status(state, status)
                print("PRIVATE worktree cleanup needs owner inspection", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, help="PRIVATE owner-selected state directory")
    parser.add_argument("--expected-sha", help="Explicit owner release approval, full SHA")
    parser.add_argument("--check-pages", action="store_true", help="Read-only Pages backup preflight")
    parser.add_argument("--verify-backup", action="store_true", help="Verify served PUBLIC backup SHA")
    parser.add_argument("--backup-url", help="Explicit owner-approved github.io backup URL")
    parser.add_argument("--base", help="Reviewed locally available lint comparison commit")
    parser.add_argument("--package-only", action="store_true", help="Validate/export without local promotion")
    parser.add_argument("--rollback", action="store_true", help="Atomically select an intact retained release")
    parser.add_argument("--sync-source", action="store_true", help="Opt-in reviewed committed source push")
    parser.add_argument("--repository", help="Expected owner/repo at github.com")
    parser.add_argument("--branch", help="Explicit owner-selected source backup branch")
    args = parser.parse_args(argv)
    if args.verify_backup:
        try:
            verified_at = verify_backup(args.repository, args.backup_url, args.expected_sha)
            backup_summary(args.backup_url, args.expected_sha, verified_at)
            return 0
        except (ReleaseError, OSError, ValueError):
            backup_summary(None, None)
            print("PUBLIC backup verification failed; local release unaffected.", file=sys.stderr)
            return 1
    if args.check_pages:
        try:
            check_pages(args.repository, args.backup_url, os.environ.get("GH_TOKEN"))
            return 0
        except (ReleaseError, OSError, ValueError, subprocess.TimeoutExpired):
            print("Pages backup preflight refused; settings unchanged.", file=sys.stderr)
            return 1
    if not args.state or not args.expected_sha:
        parser.error("--state and --expected-sha are required for releases")
    if not args.rollback and not args.base:
        parser.error("--base is required for full validation")
    if args.rollback and (args.package_only or args.sync_source):
        parser.error("rollback cannot package or sync source")
    if args.sync_source and (
        not args.repository or not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repository)
        or not args.branch or args.branch.startswith("-")
        or subprocess.run(["git", "check-ref-format", f"refs/heads/{args.branch}"],
                          capture_output=True, check=False).returncode
    ):
        parser.error("source backup requires --repository owner/repo and a valid --branch")
    previous = os.umask(0o077)
    try:
        return run(args)
    except (ReleaseError, OSError, ValueError):
        print("Release refused; last good pointer retained. Inspect PRIVATE state locally.", file=sys.stderr)
        return 1
    finally:
        os.umask(previous)


if __name__ == "__main__":
    sys.exit(main())
