#!/usr/bin/env python3
"""
Tailscale Deployment Status & Next Steps for 12sgi.com

This script documents the current Tailscale setup and provides next steps.
"""

import json
from datetime import datetime

DEPLOYMENT_STATUS = {
    "timestamp": datetime.now().isoformat(),
    "status": "🟢 PARTIAL - Backend Infrastructure Ready",
    
    "completed": [
        "✅ Tailnet created: tail760750.ts.net",
        "✅ King-server connected: 100.124.152.3",
        "✅ Hostname set: king.tail760750.ts.net",
        "✅ Admin user: jimlangford@me.com",
        "✅ Other devices: ipad, jimmys-phone (connected)",
        "✅ Funnel enabled: HTTPS on port 8443",
    ],
    
    "pending": [
        "⏳ Create pre-auth key for CI/CD (GitHub Actions)",
        "⏳ Add TAILSCALE_AUTH_KEY to GitHub repo secrets",
        "⏳ Configure ACL policy (backend protection)",
        "⏳ Test public deploy (GitHub Pages)",
        "⏳ Test private notify (Tailscale connection)",
    ],
}

NEXT_STEPS = """
╔════════════════════════════════════════════════════════════════╗
║  Tailscale Deployment - Manual Steps Required                  ║
╚════════════════════════════════════════════════════════════════╝

CURRENT STATUS:
✅ Tailscale infrastructure operational
✅ King-server connected (100.124.152.3)
✅ Admin panel ready

MANUAL STEPS (5 minutes):

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Create Pre-Auth Key for CI/CD
────────────────────────────────────

1. Go to: https://login.tailscale.com/admin/settings/keys
2. Click "Generate auth key"
3. Configure:
   - [✓] Reusable
   - Expiry: 90 days
   - Tags: tag:ci
4. Copy the entire key value
5. Save it securely

Expected format: tskey-c......................[long key]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 2: Add Key to GitHub Repository
────────────────────────────────────

1. Go to: https://github.com/jimlangford/12sgi-king/settings/secrets/actions
2. Click "New repository secret"
3. Name: TAILSCALE_AUTH_KEY
4. Value: [paste from STEP 1]
5. Click "Add secret"

Verify: Should show as "encrypted" after save

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 3: Configure Tailscale ACL Policy
─────────────────────────────────────

1. Go to: https://login.tailscale.com/admin/acls/
2. Replace entire policy with:

{
  "groups": {
    "group:admins": [
      "jimlangford@me.com"
    ],
    "group:ci": [
      "tag:ci"
    ]
  },

  "acls": [
    // Admins: Full access
    {
      "action": "accept",
      "src": ["group:admins"],
      "dst": ["*:*"]
    },

    // CI/CD: Backend services only
    {
      "action": "accept",
      "src": ["group:ci"],
      "dst": [
        "100.124.152.3:7474",   // Neo4j HTTP
        "100.124.152.3:7687",   // Neo4j Bolt
        "100.124.152.3:8101",   // auth
        "100.124.152.3:8102",   // tenant
        "100.124.152.3:8103",   // documents
        "100.124.152.3:8104",   // storage
        "100.124.152.3:8105",   // ai
        "100.124.152.3:8106",   // health
        "100.124.152.3:8107",   // gpu-router
        "100.124.152.3:8109",   // king-bridge
        "100.124.152.3:8799"    // board-api
      ]
    },

    // Deny everything else
    {
      "action": "deny",
      "src": ["*"],
      "dst": ["*:*"]
    }
  ]
}

3. Click "Save"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 4: Test Deployment
──────────────────────

After completing steps 1-3:

1. Trigger workflow:
   GitHub → Actions → kilo-aupuni publish → Run workflow

2. Verify public deploy:
   https://12sgi.com/site/reports.html
   (Should load civic dashboards)

3. Check Tailscale connection:
   tailscale status
   (Should show ci-runner connected during workflow)

4. Verify private notify:
   http://100.124.152.3:8799/api/dispatch/log
   (Should show notification from ci-runner)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESULT:

✅ Public: 12sgi.com/site/ live worldwide
✅ Private: Backend protected by Tailscale ACL
✅ Integrated: CI/CD automated non-blocking
✅ Secure: Zero-trust, end-to-end encrypted

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ESTIMATED TIME: 5 minutes
COMPLEXITY: Simple (copy/paste)
REVERSIBLE: Yes (can disable anytime)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Questions? See documentation:
- TAILSCALE_SETUP_GUIDE.md (detailed guide)
- TAILSCALE_PUBLIC_PRIVATE_ARCH.md (architecture)
- TAILSCALE_COMPLETE.md (full reference)
"""

print(NEXT_STEPS)

print("\n" + "="*70)
print("CURRENT INFRASTRUCTURE STATUS")
print("="*70 + "\n")

for item in DEPLOYMENT_STATUS["completed"]:
    print(item)

print("\n" + "PENDING (Manual Steps Required):\n")
for item in DEPLOYMENT_STATUS["pending"]:
    print(item)

print("\n" + "="*70)
print(f"Deployment time: {DEPLOYMENT_STATUS['timestamp']}")
print("="*70)
