#!/usr/bin/env python3
"""Small authenticated host bridge for Local AI to request Claude Code reviews.

The bridge accepts no shell commands or paths. It runs Claude Code in print mode
against this checkout with read-only tools and stores bounded results privately.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("CLAUDE_BRIDGE_DATA", Path.home() / ".quad-os" / "claude-bridge"))
DB_PATH = DATA / "jobs.sqlite3"
HOST = os.environ.get("CLAUDE_CODE_BRIDGE_BIND", "127.0.0.1")
PORT = int(os.environ.get("CLAUDE_CODE_BRIDGE_PORT", "8127"))
TOKEN = os.environ.get("CLAUDE_CODE_BRIDGE_TOKEN", "").strip()
MAX_TASK_CHARS = 4000
MAX_OUTPUT_CHARS = 24000
MAX_RUNTIME_SECONDS = 900
_slot = threading.BoundedSemaphore(1)

# The reviewer sees a throwaway copy of TRACKED files only: untracked files (.env.v2, tokens, databases) never exist there,
# and anything tracked whose name looks secret is left out too. Generated trees are skipped to keep the copy small.
SKIP_PREFIXES = ("site/", "reports/", "seed_reports/")
SECRET_FILE_RX = re.compile(
    r"(^|/)(\.env[^/]*|[^/]*\.(pem|key|pfx|p12|sqlite3?|db)|[^/]*(secret|credential|token|password)[^/]*\.(json|ya?ml|txt|ini|cfg))$",
    re.I,
)
REDACTIONS = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S), "[redacted private key]"),
    (re.compile(r"""(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY)[A-Z0-9_]*["']?\s*[=:]\s*)["']?[^\s"',}]{8,}"""),
     r"\1[redacted]"),
    (re.compile(r"\b(?:ghp|gho|ghs|ghr)_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9_\-]{20,}|\bAKIA[0-9A-Z]{16}"), "[redacted]"),
    (re.compile(r"\b[0-9a-fA-F]{48,}\b"), "[redacted]"),
)


def _redact(text: str) -> str:
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def _snapshot(destination: Path) -> int:
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True, timeout=120,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    copied = 0
    for raw in listed.stdout.split(b"\0"):
        name = raw.decode("utf-8", "replace")
        if not name or name.startswith(SKIP_PREFIXES) or SECRET_FILE_RX.search(name):
            continue
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied += 1
    return copied


@contextmanager
def _db():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,status TEXT NOT NULL,task TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,result TEXT NOT NULL DEFAULT '',error TEXT NOT NULL DEFAULT '')")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _run(job_id: str, task: str):
    try:
        cli = shutil.which("claude")
        if not cli:
            raise RuntimeError("Claude Code CLI is not on the bridge process PATH")
        with _db() as conn:
            conn.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?", (_now(), job_id))
        system_prompt = (
            "You are responding to a task delegated by the owner's Local AI. "
            "Review the request and repository carefully. You have read-only tools only. "
            "Do not claim to edit, test, commit, push, deploy, or publish anything. "
            "Report findings, evidence, blockers, and next steps concisely."
        )
        # SECURITY (review 2026-11-26): the task is DATA and goes in on stdin. As an argv element, text beginning with "--" was
        # parsed as a CLI option (verified), and --settings can carry hooks that run commands. --safe-mode drops hooks,
        # plugins, MCP servers and CLAUDE.md; --tools limits the available tools (--allowedTools alone only pre-approves).
        # --restricted confines the file tools to the working directory and ignores user/project settings.
        with tempfile.TemporaryDirectory(prefix="claude-review-", ignore_cleanup_errors=True) as workdir:
            _snapshot(Path(workdir))
            proc = subprocess.run(
                [cli, "-p", "--output-format", "text", "--permission-mode", "plan",
                 "--restricted", "--safe-mode", "--strict-mcp-config", "--tools", "Read,Grep,Glob",
                 "--append-system-prompt", system_prompt],
                input=task, encoding="utf-8", errors="replace",
                cwd=workdir, capture_output=True, text=True, timeout=MAX_RUNTIME_SECONDS,
                check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        output = _redact((proc.stdout or "").strip())[-MAX_OUTPUT_CHARS:]
        error = _redact((proc.stderr or "").strip())[-3000:]
        status = "complete" if proc.returncode == 0 else "failed"
        with _db() as conn:
            conn.execute("UPDATE jobs SET status=?,updated_at=?,result=?,error=? WHERE id=?",
                         (status, _now(), output, error, job_id))
    except subprocess.TimeoutExpired:
        with _db() as conn:
            conn.execute("UPDATE jobs SET status='timed_out',updated_at=?,error=? WHERE id=?",
                         (_now(), "Claude Code exceeded the 15 minute limit", job_id))
    except Exception as exc:
        with _db() as conn:
            conn.execute("UPDATE jobs SET status='failed',updated_at=?,error=? WHERE id=?",
                         (_now(), str(exc)[:3000], job_id))
    finally:
        _slot.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalClaudeBridge/1"

    def log_message(self, fmt, *args):
        # Do not log request bodies, tasks, or credentials.
        return

    def _authorized(self):
        supplied = self.headers.get("X-Service-Token", "")
        return bool(TOKEN) and hmac.compare_digest(supplied, TOKEN)

    def _json(self, status: int, body: dict):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._authorized():
            return self._json(401, {"error": "unauthorized"})
        if self.path == "/health":
            return self._json(200, {"status": "ready", "mode": "claude-code-read-only", "checkout": "12sgi-king"})
        prefix = "/jobs/"
        if self.path.startswith(prefix):
            job_id = unquote(self.path[len(prefix):])
            with _db() as conn:
                row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                return self._json(404, {"error": "job not found"})
            return self._json(200, dict(row))
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._authorized():
            return self._json(401, {"error": "unauthorized"})
        if self.path != "/jobs":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 12000:
                return self._json(413, {"error": "request size out of bounds"})
            body = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "invalid JSON"})
        task = str(body.get("task", "")).strip()
        if body.get("owner_instruction") is not True:
            return self._json(403, {"error": "an explicit Owner instruction is required"})
        if len(task) < 12 or len(task) > MAX_TASK_CHARS or "\x00" in task:
            return self._json(400, {"error": f"task must contain 12 to {MAX_TASK_CHARS} characters"})
        if not _slot.acquire(blocking=False):
            return self._json(429, {"error": "Claude bridge is already running a job"})
        job_id = str(uuid4())
        with _db() as conn:
            conn.execute("INSERT INTO jobs(id,status,task,created_at,updated_at) VALUES(?,?,?,?,?)",
                         (job_id, "queued", task, _now(), _now()))
        threading.Thread(target=_run, args=(job_id, task), name=f"claude-{job_id[:8]}", daemon=True).start()
        return self._json(202, {"job_id": job_id, "status": "queued", "status_url": f"/jobs/{job_id}"})


def main():
    if len(TOKEN) < 64 or TOKEN.lower() in {"changeme", "change-me"}:
        raise SystemExit("Configure a dedicated CLAUDE_CODE_BRIDGE_TOKEN of at least 64 characters")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local Claude Code bridge listening on {HOST}:{PORT}; read-only review mode")
    server.serve_forever()


if __name__ == "__main__":
    main()
