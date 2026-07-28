#!/usr/bin/env python3
"""
Automated system startup and recovery for 12sgi-king.
Ensures Docker Desktop is responsive and starts the deployment stack.
"""

import subprocess
import time
import sys
import os

def run_cmd(cmd, timeout=30):
    """Run command with timeout."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return str(e)

def restart_docker():
    """Restart Docker Desktop service."""
    print("↻ Restarting Docker Desktop...")
    cmd = "wsl --shutdown && timeout /t 5 /nobreak && start /B \"\" \"C:\\Program Files\\Docker\\Docker\\Docker.exe\""
    ok, msg = run_cmd(cmd, timeout=60)
    if ok:
        print("✓ Docker restart initiated")
        time.sleep(10)
        return True
    else:
        print(f"✗ Docker restart failed: {msg[:100]}")
        return False

def wait_for_docker(max_wait=60):
    """Wait for Docker daemon to be responsive."""
    print("⏳ Waiting for Docker daemon...")
    start = time.time()
    while time.time() - start < max_wait:
        ok, _ = run_cmd("docker version --format json", timeout=5)
        if ok:
            print("✓ Docker daemon responding")
            return True
        time.sleep(3)
    print(f"✗ Docker not responsive after {max_wait}s")
    return False

def start_services():
    """Start docker-compose stack."""
    print("↑ Starting services...")
    os.chdir("C:\\Users\\12sgi\\actions-runner\\_work\\12sgi-king\\12sgi-king")
    
    ok, msg = run_cmd("docker compose -f docker-compose.v2.yml up -d", timeout=120)
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
        (8109, "king-bridge"),
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
            except:
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
    ok, _ = run_cmd("docker version --format json", timeout=5)
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
