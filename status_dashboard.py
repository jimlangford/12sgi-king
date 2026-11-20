#!/usr/bin/env python3
"""
Real-time system status dashboard for 12sgi-king.
Shows deployment status, service health, and Claude integration readiness.
"""

import json
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

def run_cmd(cmd, timeout=10):
    """Run command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        return result.returncode, result.stdout
    except Exception as e:
        return -1, str(e)

def get_compose_status():
    """Get docker-compose status."""
    cmd = 'cd "C:\\Users\\12sgi\\actions-runner\\_work\\12sgi-king\\12sgi-king" && docker compose ps --format json 2>nul'
    code, out = run_cmd(cmd, timeout=15)
    
    if code != 0 or not out:
        return {"status": "offline", "services": []}
    
    try:
        containers = json.loads(out)
        running = [c for c in containers if c.get("State") == "running"]
        return {
            "status": "online" if running else "partial",
            "running": len(running),
            "total": len(containers),
            "services": [{"name": c.get("Service", "?"), "state": c.get("State", "?")} for c in containers]
        }
    except:
        return {"status": "error", "services": []}

def check_endpoints():
    """Check all service endpoints."""
    endpoints = [
        ("Auth", 8101, "/api/v2/ready"),
        ("Tenant", 8102, "/api/v2/ready"),
        ("Documents", 8103, "/api/v2/ready"),
        ("Storage", 8104, "/api/v2/ready"),
        ("AI", 8105, "/api/v2/ready"),
        ("Health", 8106, "/api/v1/ready"),
        ("GPU Router", 8107, "/api/v2/ready"),
        ("King-Bridge", 8109, "/api/v2/ready"),
    ]
    
    results = {}
    for name, port, path in endpoints:
        url = f"http://127.0.0.1:{port}{path}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                results[name] = "✓ UP" if resp.status == 200 else "✗ BAD"
        except:
            results[name] = "✗ DOWN"
    
    return results

def get_deployment_info():
    """Get deployment metadata."""
    log_dir = Path("C:\\Users\\12sgi\\Documents\\Claude\\logs\\v2-deploy")
    if not log_dir.exists():
        return {}
    
    latest = max((log_dir.glob("deploy-*.json")), default=None)
    if not latest:
        return {}
    
    try:
        data = json.loads(latest.read_text())
        return {
            "timestamp": data.get("timestamp", "?"),
            "sha": data.get("sha", "?")[:7],
            "outcome": data.get("outcome", "?"),
        }
    except:
        return {}

def main():
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + "  12sgi-king System Status Dashboard".ljust(69) + "█")
    print("█" + f"  Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}".ljust(69) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    # Compose status
    print("\n[DOCKER COMPOSE STACK]")
    compose = get_compose_status()
    if compose["status"] == "online":
        print(f"  Status: ✓ ONLINE ({compose['running']}/{compose['total']} services running)")
    elif compose["status"] == "partial":
        print(f"  Status: ⚠ PARTIAL ({compose['running']}/{compose['total']} services running)")
    else:
        print(f"  Status: ✗ OFFLINE")
    
    # Service endpoints
    print("\n[SERVICE ENDPOINTS]")
    endpoints = check_endpoints()
    up_count = sum(1 for v in endpoints.values() if "✓" in v)
    for name, status in endpoints.items():
        print(f"  {name:20} {status}")
    print(f"\n  Summary: {up_count}/{len(endpoints)} services responding")
    
    # Deployment info
    print("\n[LAST DEPLOYMENT]")
    deploy_info = get_deployment_info()
    if deploy_info:
        print(f"  Timestamp: {deploy_info.get('timestamp', '?')}")
        print(f"  Commit:    {deploy_info.get('sha', '?')}")
        print(f"  Outcome:   {deploy_info.get('outcome', '?')}")
    else:
        print("  No deployment logs found")
    
    # Claude integration status
    print("\n[CLAUDE INTEGRATION]")
    if compose["status"] == "online" and up_count >= 4:
        print("  Status: ✓ READY")
        print("  All critical services online and responding")
    elif compose["status"] == "partial" and up_count >= 2:
        print("  Status: ⚠ PARTIALLY READY")
        print(f"  {up_count}/{len(endpoints)} endpoints available")
    else:
        print("  Status: ✗ NOT READY")
        print("  Services offline or unreachable")
    
    print("\n" + "█"*70 + "\n")

if __name__ == "__main__":
    main()
