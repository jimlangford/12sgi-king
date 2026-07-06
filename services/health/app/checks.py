import os
import asyncio
import requests
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Load surfaces list from env-like string format: name=host:port,name2=host2:port
def load_surfaces_from_env():
    s = os.environ.get('SURFACES_LIST','')
    if not s:
        # try .env in repo root (not committed with secrets)
        env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        try:
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith('SURFACES_LIST'):
                        s = line.split('=',1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            s = ''
    entries = {}
    if s:
        for part in s.split(','):
            if '=' in part:
                name, hostport = part.split('=',1)
                entries[name.strip()] = hostport.strip()
    return entries

SURFACES_HEALTH_PATH = os.environ.get('SURFACES_HEALTH_PATH', '/api/v2/ready')

# Single surface check
def check_surface_sync(name, hostport):
    path = SURFACES_HEALTH_PATH if SURFACES_HEALTH_PATH.startswith('/') else f'/{SURFACES_HEALTH_PATH}'
    url = f'http://{hostport}{path}'
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return {"ok": True}
        return {"ok": False, "msg": f"status:{r.status_code}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}

async def run_surfaces_checks(surfaces: dict):
    loop = asyncio.get_event_loop()
    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        tasks = {name: loop.run_in_executor(ex, check_surface_sync, name, hostport) for name,hostport in surfaces.items()}
        for name,task in tasks.items():
            results[name] = await task
    return results

# Tailscale check: best-effort attempt to run `tailscale status`
def check_tailscale_sync():
    try:
        out = subprocess.check_output(['tailscale','status'], stderr=subprocess.DEVNULL, timeout=5)
        return {"ok": True, "msg": 'connected'}
    except Exception as e:
        return {"ok": False, "msg": 'tailscale-unavailable'}

async def run_all_checks():
    surfaces = load_surfaces_from_env()
    results = {}
    # Tailscale
    results['tailscale'] = check_tailscale_sync()
    # Surfaces
    surf_results = await run_surfaces_checks(surfaces)
    for k,v in surf_results.items():
        results[k] = v
    # Placeholder checks for DB/storage etc. Default unknown
    results['database'] = {"ok": None, "msg": "not-configured"}
    results['storage'] = {"ok": None, "msg": "not-configured"}
    return results
