#!/usr/bin/env python3
"""Read-only host verification for the private Tailscale deployment."""

import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import urllib.request

from service_auto_recovery import ServiceMonitor

ROOT = Path(__file__).resolve().parent
EXPECTED_SERVICES = {
    "auth", "tenant", "documents", "storage", "ai", "health", "gpu-router",
    "board-api", "king-bridge", "connector-runner", "github-workflow-monitor", "web-server",
}
ENDPOINTS = {
    **{name: (port, "/api/v2/ready") for name, port in (
        ("auth", 8101), ("tenant", 8102), ("documents", 8103), ("storage", 8104),
        ("ai", 8105), ("gpu-router", 8107), ("studio-assets", 8108), ("king-bridge", 8109),
    )},
    "health": (8106, "/api/v1/ready"),
    "native-board": (8799, "/health"),
    "website": (8080, "/reports.html"),
}


def check_tailscale():
    result = subprocess.run(["tailscale", "status", "--json"], capture_output=True,
                            text=True, timeout=10, check=True)
    status = json.loads(result.stdout)
    addresses = status.get("Self", {}).get("TailscaleIPs", [])
    ok = status.get("BackendState") == "Running" and bool(addresses)
    return ok, "Tailnet connected" if ok else "Tailscale is not connected"


def check_dns():
    result = subprocess.run(["tailscale", "ip", "-4"], capture_output=True,
                            text=True, timeout=10, check=True)
    expected = result.stdout.strip()
    addresses = {entry[4][0] for entry in socket.getaddrinfo("12sgi.com", 443)}
    return addresses == {expected}, f"12sgi.com resolves to {', '.join(sorted(addresses))}"


def check_disk():
    usage = shutil.disk_usage(ROOT)
    percent = usage.used / usage.total * 100
    return percent < 85, f"{percent:.1f}% used (must be below 85%)"


def check_compose_stack():
    containers = ServiceMonitor().check_health()
    services = {c.get("Service"): c for c in containers}
    bad = [name for name in sorted(EXPECTED_SERVICES)
           if name not in services or services[name].get("State") != "running"
           or services[name].get("Health", "") not in {"", "healthy"}]
    return not bad, ("Not ready: " + ", ".join(bad)) if bad else f"{len(EXPECTED_SERVICES)} services running"


def check_service_health(port, path="/api/v2/ready", timeout=5):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as response:
        if response.status != 200:
            return False, f"HTTP {response.status}"
        if path.endswith("/ready"):
            payload = json.load(response)
            return payload.get("status") == "ready", f"Port {port}: {payload.get('status')}"
        return True, f"Port {port} responding"


def check_neo4j():
    # Read-only query: never restart/recreate the standalone database or its volumes.
    request = urllib.request.Request(
        "http://127.0.0.1:7474/db/neo4j/tx/commit",
        data=json.dumps({"statements": [{"statement": "MATCH (n) RETURN count(n) AS nodes"}]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if payload.get("errors"):
        return False, "Neo4j query failed; inspect database locally"
    count = payload["results"][0]["data"][0]["row"][0]
    return count >= 14300, f"{count:,} nodes (minimum 14,300)"


def main():
    checks = [
        ("Tailscale", check_tailscale), ("Private DNS", check_dns),
        ("Disk", check_disk), ("Compose stack", check_compose_stack),
        ("Neo4j data", check_neo4j),
    ]
    checks.extend((name, lambda p=port, route=path: check_service_health(p, route))
                  for name, (port, path) in ENDPOINTS.items())
    passed = 0
    for name, check in checks:
        try:
            ok, message = check()
        except Exception as exc:
            ok, message = False, f"Check failed ({type(exc).__name__}); inspect locally"
        print(f"{'PASS' if ok else 'FAIL'} | {name}: {message}")
        passed += bool(ok)
    print(f"{passed}/{len(checks)} checks passed; remote TLS/ACLs and RAM stability require host observation.")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
