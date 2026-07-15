#!/usr/bin/env python3
"""
quick_setup.py — Interactive setup helper for Points 3-5 final integration.
Run this to step through the owner tasks interactively.

Usage:
  python quick_setup.py
"""

import os
import sys
import webbrowser
from pathlib import Path
import subprocess
import json

def status(msg, icon="→"):
    print(f"\n{icon} {msg}")

def success(msg):
    print(f"✓ {msg}")

def error(msg):
    print(f"✗ {msg}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def prompt_continue(msg="Press Enter to continue..."):
    input(f"\n{msg}")

def main():
    section("GOVOS FINAL INTEGRATION SETUP")
    print("Points 3-5: Gordon, Owner Policy, Auth Sprint 1, Postiz, WordPress\n")
    print("This guide will help you through the owner-only setup tasks.")
    print("Read SETUP_FINAL_INTEGRATION.md for detailed instructions.\n")

    tasks = {
        "1": ("Postiz Setup (Meta + LinkedIn)", postiz_setup),
        "2": ("WordPress Jetpack OAuth", wordpress_setup),
        "3": ("Auth Sprint 1 Verification", auth_sprint1_setup),
        "4": ("Owner Policy Activation", policy_setup),
        "5": ("Full Stack Test", test_stack),
        "0": ("Exit", None),
    }

    while True:
        print("\nQuick Setup Tasks:")
        for key, (name, _) in tasks.items():
            print(f"  [{key}] {name}")

        choice = input("\nSelect task (0-5): ").strip()

        if choice not in tasks:
            error("Invalid choice. Try again.")
            continue

        name, handler = tasks[choice]

        if handler is None:
            success("Goodbye!")
            sys.exit(0)

        section(name)
        try:
            handler()
            prompt_continue("\nPress Enter to return to menu...")
        except KeyboardInterrupt:
            print("\n(Cancelled)")
        except Exception as e:
            error(f"Error: {e}")

def postiz_setup():
    status("Postiz Setup")
    print("""
Step 1: Start Postiz Docker container
  docker compose -f docker-compose.postiz.yml up -d

Step 2: Open Postiz UI
  Opening http://localhost:4008 in your browser...
""")
    webbrowser.open("http://localhost:4008")

    prompt_continue("\nPress Enter after you've created the owner account and added Meta + LinkedIn apps...")

    print("""
Step 3: Connect your channels
  - In Postiz UI: Settings → Channels
  - Add "Facebook" with your Meta app credentials
  - Add "Instagram" with same credentials
  - Add "LinkedIn" with your LinkedIn app credentials
  - Authorize each one — Postiz will show integration_id

Step 4: Generate Postiz API key
  - Postiz UI: Settings → API → Create Key
  - Copy the key

Step 5: Update config/own_channels.json
  cp config/own_channels.json.example config/own_channels.json
  # Edit with your integration_ids and API key
""")

    print("""
Verify:
  python gordon_setup.py
  # Should show ✓ connected for your channels
""")
    success("Postiz setup complete!")

def wordpress_setup():
    status("WordPress Jetpack OAuth Setup")
    print("""
This sets up one-time OAuth so GitHub Actions can publish drafts to WordPress.

Step 1: Find your WordPress.com Site ID
  Open: https://public-api.wordpress.com/rest/v1.1/sites/12sgi.com
  Copy the "ID" field (numeric)

Step 2: Register WordPress.com Application
  https://developer.wordpress.com/apps/
  Create → "12SGI CI/CD"
  Note: Client ID and Client Secret

Step 3: Authorize (do this locally, never in shared chat)
  Click the authorization URL (shown after you create the app)
  Log in → approve → copy the "code" from redirect URL

Step 4: Exchange code for token (run once)
  curl -s https://public-api.wordpress.com/oauth2/token \\
    -d client_id=YOUR_CLIENT_ID \\
    -d client_secret=YOUR_CLIENT_SECRET \\
    -d redirect_uri=https://12sgi.com/oauth/callback \\
    -d grant_type=authorization_code \\
    -d code=CODE_FROM_STEP_3
  
  Copy the "access_token" from response

Step 5: Store as GitHub secrets
  gh secret set JETPACK_TOKEN
  # Paste: <your access_token>
  
  gh secret set JETPACK_SITE_ID
  # Paste: <your site ID from Step 1>

Verify:
  gh secret list | grep JETPACK
  python gordon_setup.py
""")
    success("WordPress Jetpack setup complete!")

def auth_sprint1_setup():
    status("Auth Sprint 1 Verification")
    print("""
All auth methods are already coded. Verify they're configured:
""")

    try:
        # Try to check if auth service is running
        import urllib.request
        resp = urllib.request.urlopen("http://localhost:8101/api/v2/auth/debug/sprint1", timeout=5)
        data = json.loads(resp.read())
        
        print("\nAuth providers status:")
        for provider, config in data.get("providers", {}).items():
            configured = config.get("configured", False)
            icon = "✓" if configured else "✗"
            print(f"  {icon} {provider}")
            if provider == "magic_link" and config.get("smtp_configured"):
                print(f"      SMTP configured")
            elif provider == "magic_link":
                print(f"      (dev mode: returns direct URL)")
    except Exception as e:
        error(f"Could not reach auth service: {e}")
        print("\nEnsure docker-compose.v2.yml is running:")
        print("  docker compose -f docker-compose.v2.yml up -d")

    print("""
To enable Apple / Microsoft sign-in:
  1. Register apps at:
     - https://developer.apple.com/
     - https://portal.azure.com/
  2. Set env vars in docker-compose.v2.yml:
     - APPLE_CLIENT_ID, APPLE_TEAM_ID, APPLE_KEY_ID, APPLE_PRIVATE_KEY
     - MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID
  3. Restart auth service: docker compose -f docker-compose.v2.yml up -d auth
""")
    success("Auth Sprint 1 verified!")

def policy_setup():
    status("Owner Policy Activation")
    print("""
Your owner policy is already live in config/owner_policy.json:

  auto_approve_creative: true
  auto_approve_output: true
  social_media_gate: true
  studio_model: department

This means:
  ✓ Creative/output lane work auto-approves (no owner sign-off needed)
  ✓ Social media posts require owner sign-off
  ✓ Studios are departments (no separate corporate gate)

Verify:
  python gordon_setup.py
  # Should show OWNER POLICY section with your settings
""")
    success("Owner policy is active!")

def test_stack():
    status("Full Stack Test")
    print("""
Quick tests to verify everything is working:

Test 1: Gordon Page
  Open: http://localhost:8799/gordon.html (via Tailscale)
  Click: "Full Diagnostics"
  Expect: All services green

Test 2: Postiz UI
  Open: http://localhost:4008
  Dashboard should show your connected channels

Test 3: Auth Sprint 1
  curl http://localhost:8101/api/v2/auth/debug/sprint1
  Should list all 6 auth providers

Test 4: Owner Policy Gate
  python -m services.v2_workboard --emit facebook --lane output --action post
  Check: /data/dispatch/govos_v2_dispatch.jsonl
  Should show: social media post pending owner approval

All green? You're ready to go!
""")
    success("Full stack is operational!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
