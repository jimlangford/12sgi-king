#!/usr/bin/env python3
"""
Automated system startup and recovery for 12sgi-king.
Ensures Docker Desktop is responsive and starts the deployment stack.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent


def run_cmd(cmd, timeout=30, cwd=None):
    """Run command with timeout."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                cwd=str(cwd or REPO), shell=False)
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

def restart_docker():
    """Launch Docker Desktop without shutting down unrelated WSL distributions."""
    executable = Path(os.environ.get(
        "DOCKER_DESKTOP_EXE",
        r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
    ))
    if not executable.is_file():
        print(f"✗ Docker Desktop executable not found: {executable}")
        return False
    print(f"↻ Launching Docker Desktop: {executable.name}")
    try:
        subprocess.Popen([str(executable)], cwd=str(executable.parent),
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        print("✓ Docker Desktop launch requested")
        time.sleep(10)
        return True
    except OSError as exc:
        print(f"✗ Docker Desktop launch failed: {exc}")
        return False

def wait_for_docker(max_wait=60):
    """Wait for Docker daemon to be responsive."""
    print("⏳ Waiting for Docker daemon...")
    start = time.time()
    while time.time() - start < max_wait:
        ok, _ = run_cmd(["docker", "version", "--format", "json"], timeout=5)
        if ok:
            print("✓ Docker daemon responding")
            return True
        time.sleep(3)
    print(f"✗ Docker not responsive after {max_wait}s")
    return False

def start_services():
    """Start docker-compose stack."""
    print("↑ Starting services...")
    compose_file = REPO / "docker-compose.v2.yml"
    if not compose_file.is_file():
        print(f"✗ Compose file not found: {compose_file.name}")
        return False
    command = ["docker", "compose"]
    env_file = REPO / ".env.v2"
    if env_file.is_file():
        command.extend(["--env-file", str(env_file)])
    command.extend(["-f", str(compose_file), "up", "-d"])
    ok, msg = run_cmd(command, timeout=300, cwd=REPO)
    if ok:
        print("✓ Services started")
        return True
    else:
        print(f"✗ Service startup failed: {msg[:200]}")
        return False

def wait_for_health(max_wait=180):
    """Wait for services to become healthy."""
    print("⏲ Waiting for service health checks...")
    import urllib.request

    services = [
        (8101, "auth"),
        (8102, "tenant"),
        (8106, "health"),
        (8107, "gpu-router"),
        (8109, "king-bridge"),
        (8110, "ai-gateway"),
    ]

    start = time.time()
    healthy = set()

    while time.time() - start < max_wait:
        for port, name in services:
            if name in healthy:
                continue
            try:
                url = f"http://127.0.0.1:{port}/api/v2/ready"
                if port == 8106:
                    url = f"http://127.0.0.1:{port}/api/v1/ready"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        healthy.add(name)
                        print(f"  ✓ {name} ready")
            except Exception:
                pass

        if len(healthy) == len(services):
            print(f"✓ All services healthy ({len(services)}/{len(services)})")
            return True

        print(f"  ⏳ {len(healthy)}/{len(services)} services ready...")
        time.sleep(5)

    print(f"✗ Timeout waiting for health checks ({len(healthy)}/{len(services)} ready)")
    return len(healthy) > 0

def main():
    print("\n" + "="*60)
    print("12sgi-king System Startup & Recovery")
    print("="*60 + "\n")

    # Step 1: Ensure Docker is running
    ok, _ = run_cmd(["docker", "version", "--format", "json"], timeout=5)
    if not ok:
        if not restart_docker():
            sys.exit(1)

    # Step 2: Wait for Docker daemon
    if not wait_for_docker():
        sys.exit(1)

    # Step 3: Start services
    if not start_services():
        sys.exit(1)

    # Step 4: Wait for health
    wait_for_health()

    print("\n" + "="*60)
    print("✓ System READY for Claude integration")
    print("="*60 + "\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
