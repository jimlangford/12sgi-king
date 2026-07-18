import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import ipaddress
import json
import os
import re
import secrets

import requests
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .checks import load_surfaces_from_env, run_all_checks
from services.service_metadata import with_service_metadata

app = FastAPI(title="12SGI Health Service")
security = HTTPBasic()

API_PREFIX = "/api/v1"
SERVICE_NAME = "health"
VERSION = os.environ.get("VERSION", "0.1.0")
RELEASE_FILE = os.environ.get("RELEASE_FILE", "./release.json")
ADMIN_ALLOWED_IPS = os.environ.get("ADMIN_ALLOWED_IPS", "")  # comma-separated CIDR or IPs
ADMIN_BASIC_USER = os.environ.get("ADMIN_BASIC_USER")
ADMIN_BASIC_PASS = os.environ.get("ADMIN_BASIC_PASS")
DEPENDENCY_TIMEOUT_SECONDS = max(float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "5") or "5"), 0.1)
PROVENANCE_FIELDS = ("service", "version", "commit_sha", "build_timestamp", "environment")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# Helper: determine client IP respecting X-Forwarded-For if present
def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # take the first in list
        return xff.split(",")[0].strip()
    client = request.client
    if client:
        return client.host
    return "127.0.0.1"

# Admin protection dependency
async def admin_guard(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    # If allowed IPs configured, allow by IP
    client_ip = get_client_ip(request)
    if ADMIN_ALLOWED_IPS:
        for item in [s.strip() for s in ADMIN_ALLOWED_IPS.split(",") if s.strip()]:
            try:
                if '/' in item:
                    net = ipaddress.ip_network(item, strict=False)
                    if ipaddress.ip_address(client_ip) in net:
                        return True
                else:
                    if ipaddress.ip_address(client_ip) == ipaddress.ip_address(item):
                        return True
            except Exception:
                continue
    # If basic auth configured, check credentials
    if ADMIN_BASIC_USER and ADMIN_BASIC_PASS:
        # credentials may be provided; if not, HTTPBasic will prompt
        is_valid_user = secrets.compare_digest(credentials.username, ADMIN_BASIC_USER)
        is_valid_pass = secrets.compare_digest(credentials.password, ADMIN_BASIC_PASS)
        if is_valid_user and is_valid_pass:
            return True
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # No admin protection configured; disable admin access
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access not configured")

# Helper to read release metadata
def read_release_metadata():
    try:
        if os.path.exists(RELEASE_FILE):
            with open(RELEASE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        return None
    return None


def _sanitize_failure_detail(detail) -> str:
    text = str(detail or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"//([^/\s:@]+):([^/@\s]+)@", "//***:***@", text)
    text = re.sub(r"(?i)\b(token|secret|password)=([^&\s]+)", r"\1=***", text)
    if len(text) > 240:
        text = text[:240] + "..."
    return text or "dependency check failed"


def _extract_provenance(payload: dict) -> dict:
    return {
        field: str(payload[field]).strip()
        for field in PROVENANCE_FIELDS
        if isinstance(payload.get(field), str) and payload.get(field).strip()
    }


def _check_dependency_ready_sync(name: str, hostport: str, path: str, timeout: float) -> dict:
    url = f"http://{hostport}{path}"
    result = {
        "ok": False,
        "target": hostport,
        "path": path,
    }
    try:
        response = requests.get(url, timeout=timeout)
    except requests.Timeout:
        result.update(
            {
                "failure": "timeout",
                "detail": f"dependency readiness check timed out after {timeout:g}s",
            }
        )
        return result
    except requests.RequestException as exc:
        result.update(
            {
                "failure": "unreachable",
                "detail": _sanitize_failure_detail(exc),
            }
        )
        return result

    result["http_status"] = response.status_code

    try:
        payload = response.json()
    except ValueError:
        result.update(
            {
                "failure": "malformed-json",
                "detail": "dependency readiness response was not valid JSON",
            }
        )
        return result

    if not isinstance(payload, dict):
        result.update(
            {
                "failure": "malformed-json",
                "detail": "dependency readiness response JSON was not an object",
            }
        )
        return result

    provenance = _extract_provenance(payload)
    if provenance:
        result["provenance"] = provenance

    dependency_status = payload.get("status")
    if isinstance(payload.get("dependencies"), dict):
        result["dependencies"] = payload["dependencies"]
    if isinstance(payload.get("services"), dict):
        result["services"] = payload["services"]

    result["reported_status"] = dependency_status if isinstance(dependency_status, str) else "unknown"

    if not isinstance(dependency_status, str) or not dependency_status.strip():
        result.update(
            {
                "failure": "missing-status",
                "detail": "dependency readiness response missing status field",
            }
        )
        return result

    if dependency_status != "ready":
        result.update(
            {
                "failure": "not-ready",
                "detail": f"dependency reported status '{dependency_status}'",
            }
        )
        return result

    if response.status_code != 200:
        result.update(
            {
                "failure": "unexpected-http-status",
                "detail": f"dependency reported ready with HTTP {response.status_code}",
            }
        )
        return result

    result.update({"ok": True, "detail": "dependency ready"})
    return result


async def _run_dependency_checks(surfaces: dict) -> dict:
    path = os.environ.get("SURFACES_HEALTH_PATH", "/api/v2/ready")
    path = path if path.startswith("/") else f"/{path}"
    loop = asyncio.get_running_loop()
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(surfaces) or 1))) as executor:
        tasks = {
            name: loop.run_in_executor(
                executor,
                _check_dependency_ready_sync,
                name,
                hostport,
                path,
                DEPENDENCY_TIMEOUT_SECONDS,
            )
            for name, hostport in surfaces.items()
        }
        for name, task in tasks.items():
            results[name] = await task
    return results

@app.get("/", include_in_schema=False)
async def root():
    # Keep compatibility: redirect to API health
    return RedirectResponse(url=f"{API_PREFIX}/health")

@app.get(f"{API_PREFIX}/live")
async def live():
    return JSONResponse(
        with_service_metadata(
            {"status": "alive", "timestamp": _utc_timestamp()},
            SERVICE_NAME,
            VERSION,
        )
    )

@app.get(f"{API_PREFIX}/ready")
async def ready():
    surfaces = load_surfaces_from_env()
    results = await _run_dependency_checks(surfaces)
    all_ok = all(v.get('ok', False) for v in results.values())
    status_text = "ready" if all_ok else "not-ready"
    return JSONResponse(
        with_service_metadata(
            {
                "status": status_text,
                "timestamp": _utc_timestamp(),
                "services": results,
            },
            SERVICE_NAME,
            VERSION,
        ),
        status_code=200 if all_ok else 503,
    )

@app.get(f"{API_PREFIX}/health")
async def health():
    # Run full checks
    checks = await run_all_checks()
    release = read_release_metadata()
    out = {
        # Only a real failure (ok is False) degrades the stack; ok=None means not-configured /
        # not-applicable (e.g. tailscale-in-container, unwired storage) and is NEUTRAL, not a fault.
        # (2026-07-15 fix: was `all(ok, False)` which counted None as failure -> permanent 'degraded'.)
        "status": "degraded" if any(v.get('ok') is False for v in checks.values()) else "healthy",
        "timestamp": _utc_timestamp(),
        "services": checks,
    }
    if release:
        out["release"] = release
    return JSONResponse(with_service_metadata(out, SERVICE_NAME, VERSION))

@app.get("/health", include_in_schema=False)
async def compat_health():
    # compatibility redirect
    return RedirectResponse(url=f"{API_PREFIX}/health")

@app.get("/admin/status")
async def admin_status(request: Request, _=Depends(admin_guard)):
    release = read_release_metadata()
    checks = await run_all_checks()
    # Simple HTML rendering
    html = ["<html><head><title>Admin Status</title></head><body>"]
    html.append(f"<h1>Admin Status - {VERSION}</h1>")
    if release:
        html.append("<h2>Release</h2>")
        html.append(f"<pre>{json.dumps(release, indent=2)}</pre>")
    html.append("<h2>Services</h2>")
    html.append("<ul>")
    for name, res in checks.items():
        state = 'ok' if res.get('ok') else ('unknown' if res.get('ok') is None else 'error')
        msg = res.get('msg','')
        html.append(f"<li><strong>{name}</strong>: {state} {msg}</li>")
    html.append("</ul>")
    html.append("</body></html>")
    return HTMLResponse(''.join(html))
