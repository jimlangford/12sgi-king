"""Run existing validation gates offline; keep PRIVATE evidence outside the checkout."""

import argparse
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = (
    "test", "lint-python", "lint-yaml", "lint-shell", "secrets", "build", "accessibility",
)
PROFILE_VARS = ("HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA")
FORBIDDEN = (
    "go", "go.html", "king/app.html", "king/go.html", "king/live.js",
    "case_files.html", "owner_jobs.html", "king_private_src", "recusal_evidence.html",
)


def private_directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        path.chmod(0o700)
    return path


def output_directory(base):
    base = base.expanduser().resolve()
    if base == ROOT or ROOT in base.parents or base in ROOT.parents:
        raise ValueError("Output must be outside the checkout and not an ancestor of it")
    if not base.exists():
        base.mkdir(mode=0o700, parents=True)
    if not base.is_dir():
        raise ValueError("Output parent must be a directory")
    return private_directory(base / f"run-{uuid.uuid4().hex}")


def private_file(path, content):
    with path.open("w", encoding="utf-8") as handle:
        if os.name == "posix":
            os.fchmod(handle.fileno(), 0o600)
        handle.write(content)


def seal_artifacts(run):
    if os.name == "posix":
        for path in run.rglob("*"):
            if not path.is_symlink():
                path.chmod(0o700 if path.is_dir() else 0o600)


def build_environment(run):
    # Whitelist OS/tool discovery only: never import owner build overrides or credentials.
    allowed = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    home = private_directory(run / "empty-home")
    scratch = private_directory(run / "scratch")
    env.update(dict.fromkeys(PROFILE_VARS, str(home)))
    env.update({
        "KA_SITE": str(run / "a11y" / "site"), "PYTHONUTF8": "1",
        "PYTHONNOUSERSITE": "1", "TMPDIR": str(scratch), "TEMP": str(scratch),
        "TMP": str(scratch),
    })
    return env


def accessibility_environment(run, shard, browser_scratch=None):
    env = build_environment(run)
    env["A11Y_WORK_DIR"] = str(run / "a11y")
    env.update({
        "npm_config_offline": "true", "npm_config_update_notifier": "false",
        "npm_config_audit": "false", "npm_config_fund": "false",
        "npm_config_cache": str(run / "scratch" / "npm-cache"),
    })
    # The scanner's diagnostic filters/proposals must not weaken this gate.
    if shard:
        env["A11Y_SHARD"] = shard
    if os.environ.get("CHROME_BIN"):
        env["CHROME_BIN"] = os.environ["CHROME_BIN"]
    if browser_scratch is not None:
        env.update(dict.fromkeys(("TMPDIR", "TMP", "TEMP"), str(browser_scratch)))
    return env


def browser_scratch_directory():
    base = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()).resolve()
    if ROOT == base or ROOT in base.parents:
        raise ValueError("Browser scratch must be outside the checkout")
    # Chromium creates a Unix-domain SingletonSocket below TMPDIR (108-byte Linux limit).
    if os.name == "posix" and len(os.fsencode(base / ".a12345678")) > 60:
        raise ValueError("Set RUNNER_TEMP to a short external path for Chromium socket scratch")
    return Path(tempfile.mkdtemp(prefix=".a", dir=base))


def terminate_tree(process):
    cleanup = {"descendant_cleanup": "not confirmed"}
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
            cleanup["descendant_cleanup"] = "process group terminated"
        else:
            system = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
            command = [str(system / "System32" / "taskkill.exe"), "/PID", str(process.pid), "/T", "/F"]
            cleanup["cleanup_command"] = command
            result = subprocess.run(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15, check=False,
            )
            cleanup["cleanup_exit_code"] = result.returncode
            if result.returncode == 0:
                cleanup["descendant_cleanup"] = "process tree terminated"
            else:
                process.kill()
        process.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
            process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return cleanup


def execute(command, cwd, env, log, timeout):
    result = {"command": [str(part) for part in command], "exit_code": 1, "log": str(log)}
    started = time.monotonic()
    process = None
    try:
        with log.open("w", encoding="utf-8") as handle:
            if os.name == "posix":
                os.fchmod(handle.fileno(), 0o600)
            process = subprocess.Popen(
                command, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT,
                start_new_session=os.name == "posix",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            result["exit_code"] = process.wait(timeout=timeout)
        if result["exit_code"]:
            result["error"] = "Command failed; inspect PRIVATE log"
    except FileNotFoundError:
        result["error"] = f"Missing required tool: {Path(command[0]).name}"
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        interrupted = isinstance(error, KeyboardInterrupt)
        result["error"] = "Command interrupted" if interrupted else f"Command exceeded {timeout}s timeout"
        if interrupted:
            result.update(exit_code=130, interrupted=True)
        if process is not None:
            result.update(terminate_tree(process))
    except OSError:
        result["error"] = "Command could not execute; check tool and output permissions"
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


def git_metadata():
    metadata = {"commit": None, "dirty": None, "errors": []}
    for key, args in (
        ("commit", ["rev-parse", "HEAD"]),
        ("dirty", ["status", "--porcelain", "--untracked-files=normal"]),
    ):
        try:
            result = subprocess.run(
                ["git", *args], cwd=ROOT, capture_output=True, text=True,
                timeout=30, check=False,
            )
            if result.returncode:
                raise OSError
            value = result.stdout.strip()
            if key == "commit":
                if not re.fullmatch(r"[a-fA-F0-9]{40,64}", value):
                    raise OSError
                metadata[key] = value
            else:
                metadata[key] = bool(value)
        except (OSError, subprocess.TimeoutExpired):
            metadata["errors"].append(f"Unable to determine git {key}")
    return metadata


def check_build(site):
    info = json.loads((site / "buildinfo.json").read_text(encoding="utf-8"))
    lanes = info.get("lanes")
    if (
        not isinstance(lanes, list) or not lanes or info.get("lanes_failed") != []
        or not all(
            isinstance(lane, dict) and isinstance(lane.get("lane"), str)
            and lane["lane"] and lane.get("ok") is True for lane in lanes
        )
    ):
        raise ValueError("PUBLIC build must report successful named lanes and no failed lanes")
    if any((site / name).exists() for name in FORBIDDEN):
        raise ValueError("Forbidden PRIVATE path present in PUBLIC build")
    pages = len(list(site.rglob("*.html")))
    if not pages:
        raise ValueError("PUBLIC build generated no HTML pages")
    return {"lanes": len(lanes), "html_pages": pages}


def npm_command():
    npm = shutil.which("npm")
    if not npm:
        return None
    if os.name != "nt":
        return [npm]
    # Execute npm's installed JS entry directly, not a Windows batch file via a shell.
    node = shutil.which("node")
    cli = Path(npm).parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    return [node, str(cli)] if node and cli.is_file() else None


def stage(name, run, shard, built, base=None, head=None):
    result = {"stage": name, "exit_code": 1, "commands": [], "errors": [], "artifacts": []}
    env = dict(os.environ)
    scratch = private_directory(run / "scratch")
    env.update(TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))

    def command(argv, cwd=ROOT, timeout=600, command_env=None):
        log = run / f"{name}-{len(result['commands']) + 1}.log"
        outcome = execute(argv, cwd, command_env or env, log, timeout)
        result["commands"].append(outcome)
        result["artifacts"].append(str(log))
        if outcome["exit_code"]:
            result["errors"].append(outcome["error"])
        return outcome["exit_code"] == 0

    if name == "test":
        junit, coverage = run / "test-results.xml", run / "coverage.xml"
        missing = [name for name in ("pytest", "pytest_cov") if importlib.util.find_spec(name) is None]
        if missing:
            result["errors"].append(f"Missing required Python test tools: {', '.join(missing)}")
            return result
        ok = command([
            sys.executable, "tools/local_ci.py", f"--junitxml={junit}",
            f"--coverage-xml={coverage}",
        ])
        result["artifacts"].extend(str(path) for path in (junit, coverage) if path.is_file())
        if coverage.is_file():
            try:
                data = ET.parse(coverage).getroot()
                result["coverage"] = {
                    "scope": "services", "line_rate": float(data.attrib["line-rate"]),
                    "threshold": None,
                }
            except (OSError, ET.ParseError, KeyError, ValueError):
                result["errors"].append("Test coverage XML is invalid")
        elif ok:
            result["errors"].append("Test coverage XML is missing")
    elif name in STAGES[1:5]:
        argv = [sys.executable, "tools/ci_checks.py", "--stage", name]
        if name == "lint-python":
            if base is not None:
                argv.extend(["--base", base])
            if head is not None:
                argv.extend(["--head", head])
        command(argv)
    elif name == "build":
        private_directory(run / "a11y")
        if command([sys.executable, "build_site.py"], command_env=build_environment(run)):
            try:
                result["coverage"] = check_build(run / "a11y" / "site")
                result["artifacts"].append(str(run / "a11y" / "site" / "buildinfo.json"))
            except (OSError, ValueError, TypeError, AttributeError):
                result["errors"].append("PUBLIC build metadata or PRIVATE path isolation check failed")
    elif name == "accessibility":
        if not built:
            result["errors"].append("Dependency failed: a successful build stage is required")
        elif not (ROOT / "tools/a11y/node_modules/axe-core").is_dir() or not (
            ROOT / "tools/a11y/node_modules/puppeteer-core"
        ).is_dir():
            result["errors"].append("Missing locked accessibility dependencies: tools/a11y/node_modules")
        else:
            npm = npm_command()
            if not shutil.which("node"):
                result["errors"].append("Missing required tool: node")
            elif not npm:
                result["errors"].append("Missing required tool: npm")
            else:
                try:
                    browser_scratch = browser_scratch_directory()
                except (OSError, ValueError):
                    result["errors"].append(
                        "Cannot create short PRIVATE browser scratch; "
                        "set RUNNER_TEMP to a short writable external path"
                    )
                    return result
                try:
                    aenv = accessibility_environment(run, shard, browser_scratch)
                    cwd = ROOT / "tools" / "a11y"
                    if command([*npm, "test"], cwd, 180, aenv):
                        command([*npm, "run", "scan"], cwd, 600 if shard else 2100, aenv)
                finally:
                    shutil.rmtree(browser_scratch)
                report = run / "a11y" / "report.json"
                if report.is_file():
                    try:
                        data = json.loads(report.read_text(encoding="utf-8"))
                        result["coverage"] = {
                            "pages_scanned": len(data["pages"]), "shard": shard or "all",
                            "scan_errors": len(data["errors"]),
                            "regressions": len(data.get("regressions", [])),
                            "resolved_baseline_entries": int(data.get("resolved", 0)),
                        }
                        if data["errors"] or not data["pages"]:
                            result["errors"].append("Accessibility scan reported errors or no pages")
                    except (OSError, ValueError, KeyError, TypeError):
                        result["errors"].append("Accessibility report is missing, empty, or invalid")
                elif not result["errors"]:
                    result["errors"].append("Accessibility report is missing")
                result["artifacts"].extend(
                    str(path) for path in (report, run / "a11y" / "summary.md") if path.is_file()
                )
    result["exit_code"] = int(bool(result["errors"]))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="append", choices=STAGES)
    parser.add_argument("--output-dir", type=Path, help="PRIVATE output parent outside the checkout")
    parser.add_argument("--shard", help="Explicit accessibility CI shard N/M (default: all pages)")
    parser.add_argument("--base", help="Existing local Python lint base ref; never fetched")
    parser.add_argument("--head", help="Existing local Python lint head ref; never fetched")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error("Python 3.11 or newer is required")
    selected = args.stage or list(STAGES)
    if (args.base is not None or args.head is not None) and "lint-python" not in selected:
        parser.error("--base/--head require the lint-python stage")
    if args.shard:
        match = re.fullmatch(r"([1-9]\d*)/([1-9]\d*)", args.shard)
        if not match or int(match[1]) > int(match[2]) or "accessibility" not in selected:
            parser.error("--shard requires accessibility and a valid N/M with 1 <= N <= M")
    # A standalone accessibility selection still builds its own isolated input.
    if "accessibility" in selected and "build" not in selected:
        selected = [*selected, "build"]
    previous_umask = os.umask(0o077)
    try:
        try:
            default_parent = Path(
                os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
            ) / "12sgi-local-validation"
            run = output_directory(args.output_dir or default_parent)
        except (OSError, ValueError) as error:
            parser.error(f"Cannot create PRIVATE output: {error}")
        git = git_metadata()
        receipt = {
            "visibility": "PRIVATE", "git": git, "output_directory": str(run),
            "requested_stages": args.stage or list(STAGES),
            "selected_stages": [name for name in STAGES if name in selected], "stages": [],
            "github": {"status": "not checked", "approval": "unknown"},
            "deployment": "not attempted",
        }
        built = False
        for name in STAGES:
            if name not in selected:
                continue
            try:
                outcome = stage(name, run, args.shard, built, base=args.base, head=args.head)
            except Exception:
                # Never serialize exception text: a tool may have included a credential.
                outcome = {
                    "stage": name, "exit_code": 1, "commands": [], "artifacts": [],
                    "errors": ["Unexpected stage error; no sensitive exception text recorded"],
                }
            receipt["stages"].append(outcome)
            if name == "build":
                built = outcome["exit_code"] == 0
            print(f"{name}: {'FAIL' if outcome['exit_code'] else 'PASS'}")
            if any(command.get("interrupted") for command in outcome.get("commands", [])):
                break
        receipt["errors"] = []
        try:
            seal_artifacts(run)
        except OSError:
            receipt["errors"].append("Unable to enforce PRIVATE artifact permissions")
        failed = (
            bool(git["errors"]) or bool(receipt["errors"])
            or any(item["exit_code"] for item in receipt["stages"])
        )
        receipt["local_validation"] = "failed" if failed else "passed"
        private_file(run / "receipt.json", json.dumps(receipt, indent=2) + "\n")
        print(f"PRIVATE receipt: {run / 'receipt.json'}")
        return int(failed)
    finally:
        os.umask(previous_umask)


if __name__ == "__main__":
    sys.exit(main())
