#!/usr/bin/env python3
"""
System health check and status monitor for 12sgi-king deployment.
Verifies Claude integration, service health, and deployment status.
"""

import json
import sys
import subprocess
import urllib.request
import time
from pathlib import Path
from datetime import datetime

def run_cmd(cmd, timeout=10):
    """Run shell command and return output."""
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            shell=True
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def check_docker():
    """Check Docker daemon status."""
    code, out, err = run_cmd("docker version --format json")
    if code != 0:
        return False, "Docker daemon not responding"
    return True, "Docker running"

def check_compose_stack():
    """Check docker-compose stack status."""
    cmd = 'cd "C:\\Users\\12sgi\\actions-runner\\_work\\12sgi-king\\12sgi-king" && docker compose ps --format json'
    code, out, err = run_cmd(cmd, timeout=20)
    
    if code != 0:
        return False, f"Compose check failed: {err[:100]}"
    
    try:
        containers = json.loads(out) if out else []
        running = [c for c in containers if c.get("State") == "running"]
        return len(running) > 0, f"{len(running)} services running"
    except:
        return False, "Could not parse compose output"

def check_service_health(port, path="/api/v2/ready", timeout=5):
    """Check service health endpoint."""
    url = f"http://127.0.0.1:{port}{path}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return True, f"Port {port} responding"
    except Exception as e:
        return False, f"Port {port} unreachable: {str(e)[:50]}"

def main():
    """Run full health check."""
    print(f"\n{'='*60}")
    print(f"12sgi-king System Health Check")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    checks = [
        ("Docker Daemon", lambda: check_docker()),
        ("Compose Stack", lambda: check_compose_stack()),
        ("Auth Service (8101)", lambda: check_service_health(8101)),
        ("Tenant Service (8102)", lambda: check_service_health(8102)),
        ("Health Service (8106)", lambda: check_service_health(8106, "/api/v1/ready")),
        ("King-Bridge (8109)", lambda: check_service_health(8109)),
    ]
    
    results = {}
    for name, check_fn in checks:
        try:
            ok, msg = check_fn()
            status = "✓ PASS" if ok else "✗ FAIL"
            print(f"{status} | {name}: {msg}")
            results[name] = {"status": ok, "message": msg}
        except Exception as e:
            print(f"✗ ERROR | {name}: {str(e)[:80]}")
            results[name] = {"status": False, "message": str(e)[:80]}
    
    # Summary
    passed = sum(1 for r in results.values() if r["status"])
    total = len(results)
    
    print(f"\n{'='*60}")
    print(f"Summary: {passed}/{total} checks passed")
    
    if passed == total:
        print("✓ System HEALTHY - All checks passed")
        print("✓ Claude integration READY")
        return 0
    else:
        print(f"✗ System DEGRADED - {total - passed} checks failed")
        print("Recommendation: Review failed services and restart Docker Desktop if needed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
