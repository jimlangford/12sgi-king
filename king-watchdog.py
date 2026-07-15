"""
king-watchdog.py — keep all govOS services alive + Gordon AI coordinator.

Monitors:
  - Docker containers (studio-assets, neo4j, auth)
  - king-bridge (port 8109)
  - Ollama (port 11434)
  - Board API (port 8799)
  - Gordon AI coordinator (background)

Restarts anything that goes down. Logs to watchdog.log.
Run: python king-watchdog.py
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE    = Path(__file__).resolve().parent
LOG     = HERE / 'watchdog.log'
POLL_S  = 30  # check every 30 seconds
HST     = -10 * 3600  # Hawaii Standard Time offset

def now():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

def log(msg):
    line = f'[{now()}] {msg}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def http_ready(url, timeout=4):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False

def docker_running(name):
    try:
        out = subprocess.check_output(
            ['docker', 'inspect', '--format', '{{.State.Status}}', name],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        return out == 'running'
    except Exception:
        return False

def docker_restart(name):
    log(f'RESTART docker:{name}')
    subprocess.run(['docker', 'restart', name], capture_output=True)

# ── Service definitions ───────────────────────────────────────────────────────
DOCKER_SERVICES = [
    {'name': 'studio-assets-studio-assets-1', 'health': 'http://localhost:8108/api/v2/ready'},
    {'name': 'studio-assets-studio-neo4j-1',  'health': None},
    {'name': '12sgi-king-auth-1',             'health': 'http://localhost:8101/api/v2/ready'},
]

# Processes we manage (cmd, ready_url, label)
_procs = {}

def ensure_process(label, cmd, ready_url, cwd=HERE):
    p = _procs.get(label)
    alive = p and p.poll() is None
    if alive and (not ready_url or http_ready(ready_url)):
        return  # all good
    if alive and ready_url and not http_ready(ready_url):
        log(f'UNRESPONSIVE {label} — killing and restarting')
        p.terminate()
        time.sleep(2)
        alive = False
    if not alive:
        log(f'START {label}: {" ".join(cmd)}')
        _procs[label] = subprocess.Popen(
            cmd, cwd=str(cwd),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(3)

# king-bridge and board-api run as Docker containers (docker-compose.v2.yml).
# Watchdog health-checks them but does NOT try to start them as subprocesses.
PROCESS_SERVICES = []

HTTP_HEALTH_CHECKS = [
    {'label': 'king-bridge',  'url': 'http://localhost:8109/api/v2/ready'},
    {'label': 'board-api',    'url': 'http://localhost:8799/health'},
]

def check_docker():
    for svc in DOCKER_SERVICES:
        name = svc['name']
        if not docker_running(name):
            log(f'DOWN docker:{name}')
            docker_restart(name)
            time.sleep(5)
        elif svc.get('health') and not http_ready(svc['health']):
            log(f'UNHEALTHY docker:{name} — restarting')
            docker_restart(name)
            time.sleep(5)

def check_processes():
    for svc in PROCESS_SERVICES:
        ensure_process(svc['label'], svc['cmd'], svc.get('ready_url'))
    # Health-check Docker-managed services (not started here; just monitored)
    for chk in HTTP_HEALTH_CHECKS:
        if not http_ready(chk['url']):
            log(f"WARNING: {chk['label']} not responding at {chk['url']} -- check docker compose logs")

def check_ollama():
    if not http_ready('http://localhost:11434/api/tags', timeout=3):
        log('WARNING: Ollama not responding on :11434 — king-bridge will run degraded')

def tailscale_serve_setup():
    """Set up Tailscale serve rules for the king stack."""
    try:
        out = subprocess.check_output(['tailscale', 'serve', 'status'], text=True, stderr=subprocess.DEVNULL)
        serves = {
            '8109': 'king-bridge (API + AI)',
            '8799': 'board-api (owner console)',
            '8888': 'static pages (govOS)',
        }
        for port, desc in serves.items():
            if port not in out:
                log(f'SETUP REQUIRED: run `tailscale serve --bg http://{port}` for {desc}')
            else:
                log(f'OK: Tailscale serve {port} ({desc})')
    except Exception as e:
        log(f'WARNING: Tailscale not available or error checking serve status: {e}')

def start_gordon_coordinator():
    """Start Gordon AI coordinator in a background thread."""
    try:
        from services.gordon_coordinator import GordonCoordinator
        coordinator = GordonCoordinator()
        log('STARTING: Gordon AI coordinator (background daemon)')
        thread = threading.Thread(
            target=coordinator.run_continuous_loop,
            kwargs={'interval': 30, 'duration_hours': None},
            daemon=True
        )
        thread.start()
        return coordinator
    except ImportError as e:
        log(f'WARNING: Gordon coordinator not available: {e}')
        return None
    except Exception as e:
        log(f'ERROR starting Gordon coordinator: {e}')
        return None

def main():
    log('=== king-watchdog started ===')
    log(f'Monitoring: {len(DOCKER_SERVICES)} Docker + {len(PROCESS_SERVICES)} processes')
    tailscale_serve_setup()
    
    # Start Gordon AI coordinator
    gordon = start_gordon_coordinator()

    # Initial start
    check_docker()
    check_processes()
    check_ollama()

    while True:
        try:
            check_docker()
            check_processes()
            # Every 5 minutes also check Ollama
            if int(time.time()) % 300 < POLL_S:
                check_ollama()
            time.sleep(POLL_S)
        except KeyboardInterrupt:
            log('watchdog stopped by user')
            for p in _procs.values():
                try: p.terminate()
                except: pass
            break
        except Exception as e:
            log(f'ERROR in watchdog loop: {e}')
            time.sleep(POLL_S)

if __name__ == '__main__':
    main()
