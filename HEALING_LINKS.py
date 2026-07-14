"""
AI HEALING DASHBOARD — WORKING LINKS
═════════════════════════════════════════════════════════════════════════════════

The healing dashboard automatically detects your environment and builds the correct API URLs.
Both LOCAL and TAILSCALE work with IDENTICAL rules.

═════════════════════════════════════════════════════════════════════════════════
LOCAL ACCESS
═════════════════════════════════════════════════════════════════════════════════

DASHBOARD:
  http://localhost:8799/go/healing.html

API ENDPOINTS (local):
  http://localhost:8799/gordon/healing/dashboard
  http://localhost:8799/gordon/healing/tenant/my-tenant
  http://localhost:8799/gordon/healing/cycle/my-tenant
  http://localhost:8799/gordon/healing/guidance/my-tenant
  http://localhost:8799/gordon/healing/summary

QUICK START (Local):
  1. Start watchdog:
     python king-watchdog.py

  2. Open dashboard:
     http://localhost:8799/go/healing.html

  3. Create a tenant:
     curl -X POST http://localhost:8799/gordon/healing/cycle/my-tenant

  4. Refresh dashboard and watch healing happen

═════════════════════════════════════════════════════════════════════════════════
TAILSCALE ACCESS
═════════════════════════════════════════════════════════════════════════════════

Replace YOURHOST with your actual Tailscale hostname.

DASHBOARD:
  https://YOURHOST.tail760750.ts.net/king/go/healing.html

API ENDPOINTS (Tailscale):
  https://YOURHOST.tail760750.ts.net/king/gordon/healing/dashboard
  https://YOURHOST.tail760750.ts.net/king/gordon/healing/tenant/my-tenant
  https://YOURHOST.tail760750.ts.net/king/gordon/healing/cycle/my-tenant
  https://YOURHOST.tail760750.ts.net/king/gordon/healing/guidance/my-tenant
  https://YOURHOST.tail760750.ts.net/king/gordon/healing/summary

EXAMPLE (if your Tailscale hostname is "king-machine"):
  Dashboard:
    https://king-machine.tail760750.ts.net/king/go/healing.html

  API:
    https://king-machine.tail760750.ts.net/king/gordon/healing/dashboard

QUICK START (Tailscale):
  1. Ensure Tailscale is running on your machine
  
  2. Start watchdog on your machine:
     python king-watchdog.py

  3. From any device on your Tailscale network, open:
     https://YOURHOST.tail760750.ts.net/king/go/healing.html

  4. Create a tenant:
     curl -X POST https://YOURHOST.tail760750.ts.net/king/gordon/healing/cycle/my-tenant

  5. Watch healing happen across your network

═════════════════════════════════════════════════════════════════════════════════
HOW IT AUTO-DETECTS (Same Rules)
═════════════════════════════════════════════════════════════════════════════════

The dashboard JavaScript automatically detects your environment:

1. Gets current protocol (http:// or https://)
2. Gets current hostname (localhost or your-tailscale-domain)
3. Gets current port (8799 locally, empty on Tailscale/80/443)
4. Builds API URL automatically

LOCAL:
  Window location: http://localhost:8799/go/healing.html
  → API Base: http://localhost:8799
  → API: http://localhost:8799/gordon/healing/dashboard

TAILSCALE:
  Window location: https://yourhost.tail760750.ts.net/king/go/healing.html
  → API Base: https://yourhost.tail760750.ts.net
  → API: https://yourhost.tail760750.ts.net/gordon/healing/dashboard

RESULT: Same HTML, same behavior, works everywhere!

═════════════════════════════════════════════════════════════════════════════════
DASHBOARD FEATURES
═════════════════════════════════════════════════════════════════════════════════

TAB-BASED INTERFACE:
  • One tab per tenant
  • Click to switch tenants
  • Shows tenant ID and status

HEALTH SCORE (0-100):
  🟢 HEALTHY (80-100)
  🟡 DEGRADED (50-79)
  🔴 CRITICAL (0-49)

METRICS DISPLAYED:
  • Scans: Number of diagnostic runs
  • Repairs: Number of auto-fixes applied
  • Guides: Number of recommendations issued
  • Last: Time since last check (m/h/d format)

GUIDANCE BOX:
  • Real-time recommendations
  • What's being fixed
  • What needs attention
  • Next steps

ACTION BUTTONS:
  🔧 Heal - Run immediate healing cycle for this tenant
  📊 Details - View full history and recommendations

STATUS BAR (Top):
  • Overall system status
  • Count of healthy/degraded/critical tenants
  • Auto-updates every 15 seconds

═════════════════════════════════════════════════════════════════════════════════
CURL COMMANDS (Works Locally & Tailscale)
═════════════════════════════════════════════════════════════════════════════════

Replace APIBASE with:
  LOCAL: http://localhost:8799
  TAILSCALE: https://your-tailscale-domain/king

CREATE/RUN TENANT HEALING:
  curl -X POST APIBASE/gordon/healing/cycle/my-tenant

GET ALL TENANTS STATUS:
  curl APIBASE/gordon/healing/dashboard

GET ONE TENANT STATUS:
  curl APIBASE/gordon/healing/tenant/my-tenant

GET GUIDANCE FOR TENANT:
  curl APIBASE/gordon/healing/guidance/my-tenant

GET QUICK SUMMARY:
  curl APIBASE/gordon/healing/summary

RUN DIAGNOSTICS ONLY:
  curl APIBASE/gordon/healing/diagnose/my-tenant

APPLY REPAIRS ONLY:
  curl -X POST APIBASE/gordon/healing/repair/my-tenant

PRETTY PRINT (with jq):
  curl APIBASE/gordon/healing/dashboard | jq

LOCAL EXAMPLE:
  curl -X POST http://localhost:8799/gordon/healing/cycle/my-tenant | jq

TAILSCALE EXAMPLE:
  curl -X POST https://king-machine.tail760750.ts.net/king/gordon/healing/cycle/my-tenant | jq

═════════════════════════════════════════════════════════════════════════════════
TROUBLESHOOTING LINKS
═════════════════════════════════════════════════════════════════════════════════

404 on dashboard?
  → Ensure watchdog is running: python king-watchdog.py
  → Check board-api is up: curl http://localhost:8799/health

Can't access via Tailscale?
  → Verify Tailscale is running on both devices
  → Check your Tailscale hostname: tailscale status
  → Verify /king path exists: use https://host/king/go/healing.html

No tenants showing?
  → Create one: curl -X POST http://localhost:8799/gordon/healing/cycle/test-tenant
  → Refresh dashboard
  → Wait 15 seconds for auto-refresh

Healing cycle failed?
  → Check coordinator is running (in watchdog output)
  → Check logs: tail -f logs/tenant-healing/*.jsonl
  → Verify services are running: curl http://localhost:8799/health

═════════════════════════════════════════════════════════════════════════════════
COMBINED REFERENCE TABLE
═════════════════════════════════════════════════════════════════════════════════

╔═══════════════════╦═══════════════════════════════════╦═══════════════════════════════════════════════╗
║ COMPONENT         ║ LOCAL                             ║ TAILSCALE                                     ║
╠═══════════════════╬═══════════════════════════════════╬═══════════════════════════════════════════════╣
║ DASHBOARD         ║ http://localhost:8799/go/         ║ https://HOST/king/go/healing.html            ║
║                   ║       healing.html                ║                                               ║
║───────────────────┼───────────────────────────────────┼───────────────────────────────────────────────┤
║ API BASE          ║ http://localhost:8799             ║ https://HOST/king                             ║
║───────────────────┼───────────────────────────────────┼───────────────────────────────────────────────┤
║ Dashboard API     ║ localhost:8799/gordon/healing/    ║ HOST/king/gordon/healing/dashboard           ║
║                   ║        dashboard                  ║                                               ║
║───────────────────┼───────────────────────────────────┼───────────────────────────────────────────────┤
║ Create Tenant     ║ curl -X POST localhost:8799/      ║ curl -X POST HOST/king/gordon/healing/       ║
║                   ║ gordon/healing/cycle/test         ║ cycle/test                                    ║
║───────────────────┼───────────────────────────────────┼───────────────────────────────────────────────┤
║ Run Immediately   ║ Click "🔧 Heal" in dashboard      ║ Click "🔧 Heal" in dashboard                 ║
║───────────────────┼───────────────────────────────────┼───────────────────────────────────────────────┤
║ View Details      ║ Click "📊 Details" in dashboard   ║ Click "📊 Details" in dashboard              ║
║───────────────────┼───────────────────────────────────┼───────────────────────────────────────────────┤
║ Auto-Refresh      ║ Every 15 seconds                  ║ Every 15 seconds                              ║
║───────────────────┼───────────────────────────────────┼───────────────────────────────────────────────┤
║ Healing Cycle     ║ Every 30 seconds per tenant       ║ Every 30 seconds per tenant                   ║
║                   ║ (in background)                   ║ (in background)                               ║
╚═══════════════════╩═══════════════════════════════════╩═══════════════════════════════════════════════╝

Replace HOST with your Tailscale hostname (e.g., king-machine.tail760750.ts.net)

═════════════════════════════════════════════════════════════════════════════════
SETUP CONFIRMATION
═════════════════════════════════════════════════════════════════════════════════

✓ HTML uses same detection logic for local & Tailscale
✓ API endpoints respond with identical data either way
✓ Tenant healing runs identically in both environments
✓ Guidance and repairs apply the same regardless of access method
✓ Dashboard auto-refreshes every 15 seconds on both
✓ Healing cycle runs every 30 seconds on both

RESULT: Complete transparency. Same experience everywhere.

═════════════════════════════════════════════════════════════════════════════════
"""

if __name__ == "__main__":
    print(__doc__)
