#!/usr/bin/env python3
"""Private deployment instructions, read-only verification, or explicit --start."""

import argparse
import ipaddress
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import health_check

ROOT = Path(__file__).resolve().parent
COMPOSE = ["docker", "compose", "--env-file", str(ROOT / ".env.v2"),
           "-f", str(ROOT / "docker-compose.v2.yml")]
INSTRUCTIONS = """
PRIVATE / BRIDGE: Tailscale Serve only; never enable Funnel.
1. Copy .env.v2.example to private .env.v2; generate strong auth/internal secrets.
   Keep GOVOS_ALLOW_DEV_SECRETS=0 and inference URLs on local/Tailscale hosts.
2. Confirm tailscale status, tailnet ACLs, disk <85%, and existing Neo4j volumes.
   Start the standalone database separately; never remove its volumes.
3. Start the existing native board (127.0.0.1:8799) and Studio asset stack separately.
4. Run python setup_tailscale_hosting.py --start (explicitly starts v2 only).
5. Use nginx-tailscale.conf in HOST nginx (loopback 127.0.0.1:8081).
   It includes nginx-board-config.conf; /board/api/ stays on host :8799.
   Validate nginx -t with this config, then tailscale serve --bg http://127.0.0.1:8081.
6. Use the HTTPS MagicDNS URL reported by tailscale serve status.
   For 12sgi.com, use private DNS/hosts -> king-server's current Tailscale IPv4
   (historically 100.124.152.3) AND provision valid TLS for 12sgi.com on the host proxy.
   Wix A records may point @, www, api, auth at that IP, but only tailnet clients
   can connect. A CNAME targets a hostname, NEVER an IP. Do not remove existing
   public publishing/Cloudflare bridges without owner review. Serve's automatic
   *.ts.net certificate does NOT cover 12sgi.com. Avoid advertising an IPv6 bypass.
7. Run python health_check.py on king-server; test HTTPS and /board/api/ from a
   second authorized tailnet device and verify access fails outside the tailnet.

Read COMPLETE_INDEPENDENCE.md for exact startup, cleanup, and recovery procedures.
This helper does not change DNS, firewall, Tailscale, nginx, or database configuration.
"""


def private_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "host.docker.internal", "gpu-runtime"} or host.endswith(".ts.net"):
        return True
    try:
        address = ipaddress.ip_address(host)
        return (address.is_loopback or address in ipaddress.ip_network("100.64.0.0/10")
                or address in ipaddress.ip_network("fd7a:115c:a1e0::/48"))
    except ValueError:
        return False


def validate_config(config):
    """Fail closed before startup; never print resolved configuration/secrets."""
    services = config.get("services", {})
    if not health_check.EXPECTED_SERVICES.issubset(services):
        raise ValueError("Incomplete v2 Compose service configuration")
    for service in services.values():
        if service.get("network_mode") == "host":
            raise ValueError("Host networking is not allowed in the private v2 stack")
        for port in service.get("ports", []):
            if not isinstance(port, dict) or port.get("host_ip") not in {"127.0.0.1", "::1"}:
                raise ValueError("Every published service port must bind loopback")
        env = service.get("environment", {})
        if str(env.get("GOVOS_ALLOW_DEV_SECRETS", "0")) != "0":
            raise ValueError("GOVOS_ALLOW_DEV_SECRETS must be 0")
        for key in ("AUTH_SIGNING_SECRET", "INTERNAL_SERVICE_TOKEN"):
            if key in env and (len(str(env[key] or "")) < 32
                               or str(env[key]).startswith("dev-")):
                raise ValueError(f"{key} must contain at least 32 characters")
        if str(env.get("NEO4J_AURA_ENABLED", "false")).lower() not in {"false", "0", ""}:
            raise ValueError("Cloud graph routing must be disabled for independent deployment")
        for key in ("GPU_RUNTIME_URL", "OLLAMA_BASE", "COMFYUI_BASE"):
            if key in env and not private_url(env[key]):
                raise ValueError(f"{key} must target a local or Tailscale host")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--start", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        return health_check.main()
    if not args.start:
        print(INSTRUCTIONS)
        return 0
    try:
        for name, check in (("Tailscale", health_check.check_tailscale),
                            ("Disk", health_check.check_disk), ("Neo4j data", health_check.check_neo4j)):
            ok, message = check()
            print(f"{name}: {message}")
            if not ok:
                return 1
        result = subprocess.run([*COMPOSE, "config", "--format", "json"], cwd=ROOT,
                                capture_output=True, text=True, timeout=30, check=True)
        validate_config(json.loads(result.stdout))
        subprocess.run([*COMPOSE, "up", "-d", "--wait", "--wait-timeout", "120"],
                       cwd=ROOT, timeout=180, check=True)
        return health_check.main()
    except Exception as exc:
        # Compose diagnostics/config can contain secrets; leave inspection to the owner locally.
        print(f"Startup stopped ({type(exc).__name__}); inspect private configuration locally.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
