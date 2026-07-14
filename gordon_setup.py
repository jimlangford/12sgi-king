#!/usr/bin/env python3
"""
gordon_setup.py — One-time setup helper for Gordon, Postiz, and WordPress.
Checks what's configured and prints exact next steps.

Run: python gordon_setup.py
"""
import os
import json
import subprocess
import socket
from pathlib import Path

ROOT = Path(__file__).parent

def check_port(port):
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except Exception:
        return False

def check_env_file(path):
    try:
        content = Path(path).read_text(encoding='utf-8')
        env = {}
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
        return env
    except Exception:
        return {}

def check_github_secrets():
    try:
        result = subprocess.run(
            ['gh', 'api', 'repos/jimlangford/12sgi-king/actions/secrets'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return [s['name'] for s in data.get('secrets', [])]
    except Exception:
        pass
    return None

def main():
    print("=" * 70)
    print("GORDON / POSTIZ / WORDPRESS SETUP STATUS")
    print("=" * 70)

    # Gordon API
    print("\n🐳 GORDON API (port 8504)")
    if check_port(8504):
        print("  ✓ Online")
    else:
        print("  ✗ Offline — start with:")
        print("    cd Projects/genai-stack && docker compose up -d")

    # Postiz
    print("\n📣 POSTIZ (port 4008)")
    if check_port(4008):
        print("  ✓ Online — open http://localhost:4008 to connect channels")
    else:
        print("  ✗ Offline — start with:")
        print("    docker compose -f docker-compose.postiz.yml up -d")

    # own_channels.json
    chan_path = ROOT / 'config' / 'own_channels.json'
    print("\n📋 OWN_CHANNELS.JSON")
    if chan_path.exists():
        try:
            cfg = json.loads(chan_path.read_text())
            channels = cfg.get('channels', {})
            for name, c in channels.items():
                iid = c.get('integration_id', '')
                real = bool(iid) and not iid.startswith('PASTE_')
                enabled = c.get('enabled', False)
                status = '✓ connected' if (real and enabled) else '⚠ needs integration_id'
                print(f"  {status} — {name}")
            if not channels:
                print("  ✗ No channels configured — copy config/own_channels.json.example")
        except Exception as e:
            print(f"  ✗ Error reading: {e}")
    else:
        print("  ✗ Missing — copy config/own_channels.json.example to config/own_channels.json")

    # POSTIZ_OWN_API_KEY
    api_key = os.environ.get('POSTIZ_OWN_API_KEY', '')
    print("\n🔑 POSTIZ_OWN_API_KEY")
    print("  " + ("✓ Set" if api_key else "✗ Not set — generate in Postiz UI → Settings → API"))

    # GitHub Actions secrets
    print("\n🔐 GITHUB ACTIONS SECRETS (jimlangford/12sgi-king)")
    secrets = check_github_secrets()
    if secrets is None:
        print("  ⚠ Could not check — run: gh api repos/jimlangford/12sgi-king/actions/secrets")
    else:
        required = ['WP_URL', 'WP_USER', 'WP_APP_PASSWORD', 'JETPACK_TOKEN', 'JETPACK_SITE_ID',
                    'DOCKER_USERNAME', 'DOCKER_PASSWORD']
        for s in required:
            found = s in secrets
            print(f"  {'✓' if found else '✗'} {s}")
        missing = [s for s in required if s not in secrets]
        if missing:
            print(f"\n  Set missing secrets:")
            for m in missing:
                print(f"    gh secret set {m}")

    # WordPress
    print("\n🌐 WORDPRESS / JETPACK")
    print("  Setup guide: docs/WORDPRESS_PUBLIC_LAYER.md")
    print("  Register app: https://developer.wordpress.com/apps/")
    print("  Steps:")
    print("    1. Register app at developer.wordpress.com/apps")
    print("    2. Authorize: GET https://public-api.wordpress.com/oauth2/authorize")
    print("       ?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=code&scope=posts")
    print("    3. Exchange code:")
    print("       curl https://public-api.wordpress.com/oauth2/token \\")
    print("         -d 'client_id=ID&client_secret=SECRET&code=CODE'\\")
    print("         -d 'redirect_uri=http://localhost&grant_type=authorization_code'")
    print("    4. Set secrets:")
    print("       gh secret set JETPACK_TOKEN")
    print("       gh secret set JETPACK_SITE_ID")

    # owner_policy.json
    print("\n📋 OWNER POLICY")
    policy_path = ROOT / 'config' / 'owner_policy.json'
    if policy_path.exists():
        try:
            policy = json.loads(policy_path.read_text())
            print(f"  auto_approve_creative: {policy.get('auto_approve_creative', False)}")
            print(f"  auto_approve_output:   {policy.get('auto_approve_output', False)}")
            print(f"  social_media_gate:     {policy.get('social_media_gate', {}).get('enabled', False)}")
            print(f"  studio_model:          {policy.get('studio_policy', {}).get('model', '?')}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        print("  ✗ Missing config/owner_policy.json")

    print("\n" + "=" * 70)
    print("GORDON COMMAND PAGE: http://localhost:8799/gordon.html (via Tailscale)")
    print("GORDON API:          http://localhost:8504/admin/gordon")
    print("POSTIZ:              http://localhost:4008")
    print("=" * 70 + "\n")

if __name__ == '__main__':
    main()
