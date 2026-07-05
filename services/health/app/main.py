from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import os
import json
import ipaddress
import secrets
from datetime import datetime
from .checks import run_all_checks, run_surfaces_checks, load_surfaces_from_env

app = FastAPI(title="12SGI Health Service")
security = HTTPBasic()

API_PREFIX = "/api/v1"
VERSION = os.environ.get("VERSION", "0.1.0")
RELEASE_FILE = os.environ.get("RELEASE_FILE", "./release.json")
ADMIN_ALLOWED_IPS = os.environ.get("ADMIN_ALLOWED_IPS", "")  # comma-separated CIDR or IPs
ADMIN_BASIC_USER = os.environ.get("ADMIN_BASIC_USER")
ADMIN_BASIC_PASS = os.environ.get("ADMIN_BASIC_PASS")

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

@app.get("/", include_in_schema=False)
async def root():
    # Keep compatibility: redirect to API health
    return RedirectResponse(url=f"{API_PREFIX}/health")

@app.get(f"{API_PREFIX}/live")
async def live():
    return JSONResponse({"status": "alive", "timestamp": datetime.utcnow().isoformat() + 'Z'})

@app.get(f"{API_PREFIX}/ready")
async def ready():
    # For readiness, run minimal critical checks: surfaces
    surfaces = load_surfaces_from_env()
    results = await run_surfaces_checks(surfaces)
    all_ok = all(v.get('ok', False) for v in results.values())
    status = "ready" if all_ok else "not-ready"
    return JSONResponse({"status": status, "timestamp": datetime.utcnow().isoformat() + 'Z', "services": results})

@app.get(f"{API_PREFIX}/health")
async def health():
    # Run full checks
    checks = await run_all_checks()
    release = read_release_metadata()
    out = {
        "status": "healthy" if all(v.get('ok', False) for v in checks.values()) else "degraded",
        "version": VERSION,
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "services": checks,
    }
    if release:
        out["release"] = release
    return JSONResponse(out)

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
