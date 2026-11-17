# Independent Local Deployment — PRIVATE / BRIDGE

## Current procedure (2026-11-17)

This section supersedes the historical session summary below. Those earlier checkmarks
are **not live verification**. Disk/RAM readings, container health, DNS, certificates,
and graph counts must be checked on king-server. No host cleanup has been performed by
this repository change.

“Independent” here means local inference and local deployment execution, not zero
external dependencies: Tailscale, Wix DNS, optional OAuth/email, package/image downloads,
and optional GitHub monitoring still have their own external services. Existing public
publishing, Cloudflare, local mirrors, and creative/output approval gates are preserved.

### 1. Recover resources safely

Run from the checkout on king-server. Stop the recovery monitor during maintenance.
Never use blanket `taskkill /IM pythonw.exe`, `docker system prune -a`,
`docker volume prune`, or `docker compose down -v` as this procedure.

```powershell
python cleanup_system.py --verify --python-cache --docker-cache
python cleanup_system.py --execute --python-cache --docker-cache
powershell -NoProfile -File tools/cleanup_pythonw.ps1
# Only after reviewing executable, command line, and memory, select a stale repo-owned PID:
powershell -NoProfile -File tools/cleanup_pythonw.ps1 -ProcessId <PID> -Execute
```

Cleanup removes only untracked, non-symlink cursor files/optional Python bytecode older
than 24 hours. Docker cleanup is separately opt-in: build cache older than seven days
only, never images/containers/volumes. It may not reclaim enough space: inspect
`docker system df` and owner-managed backups if disk stays at or above 85%. Do not
delete local models or graph data to meet a percentage target. Restart only the intended
service through its existing supervisor; do not start a second watchdog blindly.

### 2. Configure and start

1. Copy `.env.v2.example` to `.env.v2` **only if it does not already exist**. Preserve
   existing credentials. Generate separate random auth/internal/webhook secrets using
   `python -c "import secrets; print(secrets.token_hex(32))"`.
   Set `GOVOS_ALLOW_DEV_SECRETS=0`; never use published development secrets.
2. Keep inference local: `GPU_RUNTIME_URL` and `OLLAMA_BASE` should target host Ollama
   (`http://host.docker.internal:11434` for Docker Desktop). Install the selected
   `GPU_DEFAULT_MODEL` locally. Leave Aura/cloud graph routing disabled.
3. Keep `AUTH_PUBLIC_URL`, `OAUTH_REDIRECT_BASE`, `CORS_ORIGINS`,
   `WEBAUTHN_ORIGIN`, and `WEBAUTHN_RP_ID` consistent with the final HTTPS browser
   hostname. For a MagicDNS hostname, auth can share that origin via `/api/v2/auth/`;
   register OAuth callbacks on that origin. Re-register passkeys after changing RP ID.
4. Confirm Tailscale is connected (`tailscale status --json`). Verify existing graph
   volumes with `docker volume inspect 12sgi-king_v2-neo4j-data 12sgi-king_v2-neo4j-logs`.
   Start **only the existing standalone graph**:

   ```powershell
   docker compose -f docker-compose.neo4j.yml up -d
   ```

   If a required external volume is missing, **stop and restore the correct backup**;
   never create an empty replacement to make startup green.
5. Start the existing native board listener on `127.0.0.1:8799` through its normal
   supervisor, and the separate Studio asset stack on loopback `8108`.
   `king_serve.py` is a host-side dependency, not supplied by this checkout.
   The v2 container intentionally does not publish host port 8799.
6. Run `python setup_tailscale_hosting.py --start`. It verifies tailnet connectivity,
   disk <85%, graph count >=14,300, resolved Compose loopback bindings, production
   secrets, and local inference targets before starting **v2 only**. It then runs the
   read-only host health checks. No DNS, firewall, Tailscale, or database settings change.
   All Compose operations use `--env-file .env.v2`.

Docker Desktop is the current host topology. On Linux, `host-gateway` resolves the host
but does **not** make host-loopback services reachable from containers. If Studio,
Ollama, or Neo4j readiness fails there, coordinate a private host/container bridge with
the owner; do not solve it by exposing unauthenticated ports on `0.0.0.0`.

### 3. Expose only through Tailscale

The v2 nginx container owns loopback `8080`. Alternatively, `python serve.py 8080`
serves **built `site/` only**, never repository credentials/source; do not run both
servers on the same port.

Create `logs/` locally if absent. Start a **host** nginx instance with the checked-in
private configuration (substitute the absolute checkout path, with trailing slash):

```text
nginx -p <absolute-checkout>/ -c nginx-tailscale.conf -t
nginx -p <absolute-checkout>/ -c nginx-tailscale.conf
tailscale serve --bg http://127.0.0.1:8081
tailscale serve status
```

`nginx-tailscale.conf` binds only `127.0.0.1:8081`, includes the `/board/api/` proxy
to native host `8799`, routes the v2 API namespaces to their local services, and
serves the built website via `8080`. It must not be copied into a public vhost.
Tailnet ACLs must restrict clients to intended users/devices. **Do not enable Funnel**.
Keep the CI webhook and database off this browser proxy.

Use the HTTPS MagicDNS URL shown by Serve. To use **12sgi.com**, configure private
DNS/hosts or owner-approved Wix **A** records for `@`/`www`/`api`/`auth` pointing to the
**current** `tailscale ip -4` (historically `100.124.152.3`). CNAMEs take hostnames,
not IPs. Public DNS pointing to a tailnet address does not make it publicly routable.
Serve's automatic `*.ts.net` certificate does **not** cover `12sgi.com`: provision a
valid custom-domain certificate (for example via DNS validation) and an owner-reviewed
nginx HTTPS listener bound **only to the Tailscale IP**, reusing the private routes.
Do not change existing public DNS/Cloudflare bridges until the owner approves cutover.
Remove unintended AAAA records for this private hostname. Custom-domain TLS/DNS is a
host administration step, not something this checkout can provision automatically.

### 4. Local CI and recovery

For a deployment of the **current trusted checkout** with no GitHub pull/webhook:
`python local_ci_cd_server.py --deploy-local`. This runs tests, cached Docker builds,
deployment, and health gates; failures return nonzero. Existing packages/images/models
must already be available for offline execution.

Optional webhook mode: export a unique `WEBHOOK_SECRET` of at least 32 characters in
the process environment, then run `python local_ci_cd_server.py`. It binds
`127.0.0.1:9000` and requires HMAC-SHA256 signed pushes to the exact repository's
`refs/heads/main`. GitHub cannot reach a tailnet-only receiver directly: use an
owner-controlled signed tailnet relay, or use `--deploy-local`. Do not expose port 9000
publicly. `.env.v2` is read by Compose, **not automatically by the Python receiver**.

Run `python service_auto_recovery.py` after maintenance. It checks all Compose
containers, including stopped/unhealthy ones, every 30 seconds; restart attempts,
including failed attempts, are capped at three until five consecutive minutes of
healthy observations. It never manages the standalone Neo4j service or creative jobs.
On exhausted retries, inspect logs and fix the root cause before restarting the monitor.

### 5. VERIFY / troubleshooting

Run `python health_check.py` (or `python setup_tailscale_hosting.py --verify`).
Nonzero means the deployment is not verified. Checks cover:

| Surface | Host endpoint/check |
|---|---|
| Auth, tenant, documents, storage, AI | `127.0.0.1:8101`–`8105/api/v2/ready` |
| Health aggregator | `127.0.0.1:8106/api/v1/ready` |
| GPU router, Studio assets, king-bridge | `127.0.0.1:8107`–`8109/api/v2/ready` |
| Native board | `127.0.0.1:8799/health` |
| Built website | `127.0.0.1:8080/reports.html` |
| Connector runner, workflow monitor, container board | Compose process/health state |
| Neo4j | Read-only `MATCH (n) RETURN count(n) AS nodes`, minimum 14,300 |
| Host | Tailscale state, `12sgi.com` resolution, disk usage below 85% |

Studio is intentionally required by aggregator readiness; start its separate stack
rather than hiding a failure. No `/health` entry is added to `SURFACES_LIST`: its format
is `name=host:port` and its shared readiness path is `/api/v2/ready`.

From a second authorized tailnet device, verify HTTPS, sign-in, and `/board/api/system`.
Verify those private routes **fail from outside the tailnet**, and inspect host listeners
for unintended LAN/public binds. Observe RAM and per-process working sets over time
before declaring a leak fixed; killing a stale PID alone does not establish stability.
If the graph count is low, stop writes and inspect the correct volume/backup rather
than resetting Neo4j. Use `docker compose --env-file .env.v2 -f docker-compose.v2.yml logs
--tail 100 <service>` locally; do not publish logs or resolved config containing secrets.

---

## Historical session summary (unverified; superseded by procedure above)

## What You Now Have

**Complete, self-hosted solution with ZERO dependencies:**

- ✅ **Domain**: 12sgi.com (owned on Wix)
- ✅ **Hosting**: King-server (your hardware)
- ✅ **Network**: Tailscale (free, encrypted)
- ✅ **CI/CD**: Local webhook system (self-hosted)
- ✅ **Services**: 11 Docker containers + Neo4j
- ✅ **Billing**: ZERO risk (completely independent)

---

## 📋 What Was Fixed

### Problem 1: GitHub Billing Lock
**Before:** GitHub Actions blocked due to billing issue
**After:** Local CI/CD system (no GitHub dependency)

### Problem 2: 12sgi.com Forwarding
**Before:** Domain forwarded to elementlotus.com (not yours)
**After:** Domain points directly to king-server via Tailscale (100% yours)

---

## 🚀 Your Complete Stack

```
12sgi.com (Wix)
    ↓ (DNS Points To)
100.124.152.3 (King-Server on Tailscale)
    ↓
┌─────────────────────────────────┐
│ Services Running                │
├─────────────────────────────────┤
│ 8080: Web dashboards (297+)    │
│ 8799: Board API                 │
│ 7474: Neo4j (14,300 nodes)     │
│ 9000: CI/CD webhook             │
│ 8101-8109: V2 services (11)    │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ CI/CD Pipeline (Local)          │
├─────────────────────────────────┤
│ Webhook receiver (port 9000)    │
│ Auto test, build, deploy        │
│ Health monitoring (30s interval)│
│ Auto-recovery (3 restarts max)  │
└─────────────────────────────────┘
```

---

## 📁 New Files Created

### Domain & Hosting Setup
1. **`setup_tailscale_hosting.py`** - Interactive setup wizard
2. **`TAILSCALE_HOSTING_CHECKLIST.md`** - Step-by-step checklist
3. **`DOMAIN_INDEPENDENCE_GUIDE.md`** - Complete guide

### CI/CD System
4. **`local_ci_cd_server.py`** - Webhook + deployment orchestrator
5. **`service_auto_recovery.py`** - Health monitor + auto-restart
6. **`start_local_cicd.py`** - Quick-start launcher

### CI/CD Documentation
7. **`LOCAL_CICD_READY.md`** - Quick start
8. **`LOCAL_CICD_SETUP.md`** - Configuration
9. **`LOCAL_CICD_REFERENCE.md`** - Complete manual
10. **`QUICK_START_CARD.md`** - 60-second guide

### General Documentation
11. **`BILLING_ISSUE_RESOLVED.md`** - Summary of fixes
12. **`FULL_DIRECTORY_STRUCTURE.md`** - Project map
13. **`DOCUMENTATION_INDEX.md`** - Master index

---

## ✅ Setup Checklist

### For Domain Independence (Do First)
- [ ] Run: `python setup_tailscale_hosting.py`
- [ ] Read: `TAILSCALE_HOSTING_CHECKLIST.md`
- [ ] Go to Wix: Update DNS records
- [ ] Wait: DNS propagation (1-24 hours)
- [ ] Verify: `nslookup 12sgi.com` returns 100.124.152.3

### For Local CI/CD (Do Simultaneously)
- [ ] Terminal 1: `python local_ci_cd_server.py`
- [ ] Terminal 2: `python service_auto_recovery.py`
- [ ] Test: Push code to main branch
- [ ] Verify: Services auto-deploy

### Final Verification
- [ ] 12sgi.com resolves to king-server
- [ ] All services accessible via Tailscale
- [ ] Deployments triggering on git push
- [ ] Auto-recovery monitoring services
- [ ] Neo4j 14,300 nodes intact

---

## 🎯 How to Start

### Step 1: Setup Domain Hosting (15 min setup, 1-24 hrs propagation)

```powershell
cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
python setup_tailscale_hosting.py
```

Follow the instructions to update Wix DNS records.

### Step 2: Start Local CI/CD (Immediate)

**Terminal 1:**
```powershell
python local_ci_cd_server.py
```

**Terminal 2:**
```powershell
python service_auto_recovery.py
```

### Step 3: Test

```powershell
git push origin main
```

Watch services auto-deploy!

---

## 📊 Before vs After

| Aspect | Before | After |
|--------|--------|-------|
| **Domain Control** | ❌ Forwarded to elementlotus | ✅ Points to king-server |
| **CI/CD Dependence** | ⚠️ GitHub (billing blocked) | ✅ Local (always available) |
| **Billing Risk** | ❌ HIGH | ✅ ZERO |
| **Data Ownership** | ❓ Forwarded | ✅ On king-server |
| **Auto-Deployment** | ❌ Blocked | ✅ Working |
| **Auto-Recovery** | ❌ No | ✅ Yes (30s checks) |
| **Network Security** | ❓ Unknown | ✅ Tailscale encrypted |
| **Control** | ❌ Limited | ✅ Complete |

---

## 🔐 Security Features

### Network Security
- ✅ Tailscale WireGuard encryption
- ✅ No internet-exposed ports
- ✅ Private network only (tailnet)
- ✅ Device-based access control

### Data Security
- ✅ Data on king-server (your hardware)
- ✅ Neo4j volumes persistent and local
- ✅ No cloud intermediaries
- ✅ Full ownership and control

### Operational Security
- ✅ Local CI/CD (no cloud credentials)
- ✅ Health checks every 30 seconds
- ✅ Auto-recovery prevents extended downtime
- ✅ Comprehensive logging locally

---

## 💡 Key Benefits

1. **Complete Independence**
   - No GitHub dependency
   - No cloud provider dependency
   - No forwarding service dependency

2. **Zero Billing Risk**
   - Tailscale free tier
   - No GitHub billing
   - No cloud hosting bills
   - One-time hardware cost only

3. **Full Control**
   - Own the domain (Wix)
   - Own the hardware (king-server)
   - Own the network (Tailscale account)
   - Own the data (Neo4j local)

4. **Enhanced Reliability**
   - Auto-recovery system
   - Continuous monitoring
   - Local deployment (no network delays)
   - Persistent volumes

5. **Privacy**
   - No data forwarding
   - No third-party CDN
   - Encrypted network
   - Private access only

---

## 📈 System Status

| Component | Status | Details |
|-----------|--------|---------|
| Domain | ✅ Ready | 12sgi.com on Wix |
| King-Server | ✅ Running | 100.124.152.3 (Tailscale) |
| Services | ✅ Running | 11 containers, 8 healthy |
| Neo4j | ✅ Verified | 14,300 nodes, SAFE |
| CI/CD | ✅ Running | Webhook + auto-deploy |
| Auto-Recovery | ✅ Running | 30s health checks |
| Local Hosting | ✅ Ready | Port 8080 (dashboards) |
| Tailscale | ✅ Connected | tail760750.ts.net |

---

## 🚀 What Happens Now

### Immediate (Today)
1. ✅ CI/CD systems running
2. ✅ Local deployments working
3. ✅ Services auto-recovering

### Short Term (This Week)
1. ✅ Update DNS in Wix
2. ✅ Wait for propagation
3. ✅ Test 12sgi.com access

### Medium Term (Ongoing)
1. ✅ Push code normally
2. ✅ Services deploy automatically
3. ✅ No billing interruptions
4. ✅ Complete independence

---

## 📚 Documentation Guide

### For Quick Start
- `QUICK_START_CARD.md` (2 min read)
- `LOCAL_CICD_READY.md` (5 min read)

### For Setup
- `setup_tailscale_hosting.py` (run this)
- `TAILSCALE_HOSTING_CHECKLIST.md` (follow this)
- `DOMAIN_INDEPENDENCE_GUIDE.md` (reference)

### For Complete Understanding
- `LOCAL_CICD_REFERENCE.md` (full manual)
- `FULL_DIRECTORY_STRUCTURE.md` (project map)
- `DOCUMENTATION_INDEX.md` (all docs)

---

## ✨ You Are Now

✅ **Completely Independent**
- No external dependencies
- No billing vulnerabilities
- Complete control
- Secure and encrypted

✅ **Self-Hosted**
- Your hardware
- Your network
- Your data
- Your deployment system

✅ **Production Ready**
- Automated deployments
- Health monitoring
- Auto-recovery
- Comprehensive logging

**12sgi-king is now a completely independent, self-hosted civic transparency platform with zero billing risk!** 🎉

---

## 📞 Quick Reference

```powershell
# Start systems
python local_ci_cd_server.py          # Terminal 1
python service_auto_recovery.py       # Terminal 2

# Monitor
python status_dashboard.py

# Test deployment
git push origin main

# Check domain
nslookup 12sgi.com

# Verify services
docker compose -f docker-compose.v2.yml ps

# Check Neo4j
python verify_neo4j.py

# View CI/CD logs
Get-Content logs/ci-cd/deployments.jsonl -Tail 1
```

---

**Everything is set up. Everything is ready. You're completely independent now!**
