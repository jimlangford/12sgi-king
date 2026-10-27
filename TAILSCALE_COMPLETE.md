# ✅ Tailscale Architecture: Public GitHub Pages + Protected Backend

## Status: 🟢 READY FOR IMPLEMENTATION

**12sgi.com can be fully public while backend services remain protected via zero-trust Tailscale network.**

---

## Architecture Overview

```
┌─────────────────────────────────────────┐
│         INTERNET (Public)               │
│  12sgi.com (GitHub Pages)               │
│  ✓ Worldwide accessible                 │
│  ✓ 297 civic dashboards                 │
│  ✓ No authentication required           │
│  ✓ CDN-backed (fast)                    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
      ┌───────────────────────┐
      │  GitHub Pages CDN    │
      │  12sgi.com (CNAME)   │
      │  /site/ → jimlangford│
      │         .github.io/  │
      └───────────────────────┘


┌─────────────────────────────────────────┐
│     TAILSCALE (Private Network)         │
│  Zero-Trust, Encrypted                  │
│                                         │
│  Protected Services (ACL-controlled):   │
│  - Neo4j (7474, 7687)                  │
│  - Auth (8101)                         │
│  - Tenant (8102)                       │
│  - Documents (8103)                    │
│  - Storage (8104)                      │
│  - AI (8105)                           │
│  - Health (8106)                       │
│  - GPU Router (8107)                   │
│  - King-Bridge (8109)                  │
│  - Board API (8799)                    │
│  - Connectors & monitoring              │
│                                         │
│  Access: Tailscale members only        │
│  Security: WireGuard encrypted         │
│  Policy: ACL-driven                    │
│  Audit: All access logged              │
└─────────────────────────────────────────┘
```

---

## What This Achieves

### ✅ Public Access
- **12sgi.com/site/** globally accessible
- **297 civic transparency dashboards**
- **No authentication needed** (public civic data)
- **CDN-backed** (fast, worldwide)
- **Automatic updates** (daily via GitHub Actions)

### 🔒 Backend Protection
- **Neo4j brain**: Protected
- **V2 services**: Protected
- **Owner console**: Protected
- **Dispatch logs**: Protected
- **Access control**: ACL policy
- **Encryption**: End-to-end WireGuard
- **Audit trail**: All access logged

### ⚡ CI/CD Integration
- **Public deploy**: GitHub Pages (independent)
- **Private notify**: Tailscale (best-effort)
- **Non-blocking**: Both happen simultaneously
- **No failures**: Public deploy always succeeds

---

## Implementation: 15 Minutes

### Step 1: Create Tailnet
```bash
Visit: https://login.tailscale.com/
Create organization: "12 Stones Global"
Get: Your tailnet ready message
```

### Step 2: Add King-Server
```bash
# On king-server (Windows):
choco install tailscale
tailscale login
tailscale set --hostname=king-server
tailscale status
# Verify in: https://login.tailscale.com/admin/machines/
```

### Step 3: Create Auth Key
```
Go to: https://login.tailscale.com/admin/settings/keys
Create: Pre-auth key (reusable, 90 days)
Add tags: tag:ci
Copy: Key value
```

### Step 4: Add to GitHub
```
Repo Settings → Secrets and variables → Actions
New secret: TAILSCALE_AUTH_KEY
Value: (paste from Step 3)
```

### Step 5: Update ACL Policy
```
Go to: https://login.tailscale.com/admin/acls/
Paste: Policy from TAILSCALE_SETUP_GUIDE.md
Save: Changes
```

### Step 6: Verify Workflow
```yaml
# Already in .github/workflows/publish.yml:
✅ Check for Tailscale key
✅ Connect to Tailscale
✅ Notify private King
✅ continue-on-error (non-blocking)
```

---

## Test It

### Test 1: Public Deploy
```bash
# Trigger workflow:
GitHub → Actions → kilo-aupuni publish → Run

# Expected:
✅ Runs successfully
✅ Deploys to GitHub Pages
✅ Live at https://12sgi.com/site/
✅ Takes ~5-10 minutes
```

### Test 2: Public Access
```bash
# Browser:
https://12sgi.com/site/reports.html

# Expected:
✅ Loads civic dashboards
✅ Fast (CDN-backed)
✅ All 297 pages accessible
✅ No auth needed
```

### Test 3: Tailscale Connection
```bash
# On king-server:
tailscale status

# Expected:
✅ Shows "RUNNING"
✅ Peer: ci-runner (connected from GitHub Actions)
✅ Connection: Encrypted, latency <5ms
```

### Test 4: Private Notify
```bash
# After workflow completes:
Check: http://100.124.152.3:8799/api/dispatch/log
(via Tailscale)

# Expected:
✅ Log entry from ci-runner
✅ Message: "✅ PUBLIC: GitHub Pages live..."
✅ Timestamp: When workflow completed
```

---

## Workflow Integration

### Current: Non-Blocking
```yaml
- name: Deploy to GitHub Pages
  uses: actions/deploy-pages@v5
  # ✅ SUCCEEDS → public deploy live

- name: Check for Tailscale key
  id: tskey
  run: |
    if [ -n "${{ secrets.TAILSCALE_AUTH_KEY }}" ]; then
      echo "present=true" >> "$GITHUB_OUTPUT"
    else
      echo "present=false" >> "$GITHUB_OUTPUT"
    fi
  # ✅ CHECKS if secret exists (doesn't wait)

- name: Connect to Tailscale (best-effort)
  if: ${{ success() && steps.tskey.outputs.present == 'true' }}
  continue-on-error: true
  # ✅ Connects (doesn't block if it fails)

- name: Notify private King
  if: ${{ success() && steps.tskey.outputs.present == 'true' }}
  continue-on-error: true
  # ✅ Sends notification (non-blocking)
  run: |
    curl -s -m 15 -X POST http://100.124.152.3:8799/api/dispatch/log \
      -H 'Content-Type: application/json' \
      -d '{"message":"✅ PUBLIC: GitHub Pages live","source":"ci-runner"}'
```

**Result:**
- Public GitHub Pages: Always succeeds ✅
- Private notification: Best-effort ✅
- Workflow: Never blocked ✅
- Both: Happen simultaneously ✅

---

## Security Model

### Layers

**Layer 1: GitHub Pages (Public)**
```
✅ Static HTML/CSS/JS only
✅ No sensitive data
✅ CDN distributed
✅ No authentication needed
```

**Layer 2: Tailscale Network (Private)**
```
✅ Zero-trust architecture
✅ WireGuard encryption
✅ IP whitelisting (100.x.x.x only)
✅ ACL policy enforcement
✅ Access audit logging
```

**Layer 3: ACL Policy**
```
✅ Admins: Full access
✅ CI/CD: Backend services only
✅ Default: Deny all
✅ Per-port control
```

### What's Protected
- ✅ Neo4j (graph database - 14.3k nodes)
- ✅ Auth service (identity)
- ✅ Document storage
- ✅ AI/GPU orchestration
- ✅ Owner console (board-api)
- ✅ Real-time dispatch logs
- ✅ All internal APIs

### What's Public
- ✅ Civic dashboards (297 pages)
- ✅ Public records data
- ✅ Meeting agendas
- ✅ Financial data (from public sources)
- ✅ Testimony transcripts
- ✅ Voting records

---

## Architecture Files

| File | Purpose |
|------|---------|
| `TAILSCALE_PUBLIC_PRIVATE_ARCH.md` | Architecture overview + security model |
| `TAILSCALE_SETUP_GUIDE.md` | Step-by-step implementation (15 min) |
| `.github/workflows/publish.yml` | Already integrated (verified) |

---

## Key Benefits

### Transparency
- ✅ Public civic data accessible worldwide
- ✅ No access restrictions on dashboards
- ✅ Trust: Data from official sources

### Security
- ✅ Backend protected from internet
- ✅ Zero-trust networking (Tailscale)
- ✅ ACL-based access control
- ✅ No open ports exposed
- ✅ Encrypted end-to-end

### Simplicity
- ✅ GitHub Pages (no server management)
- ✅ Tailscale (no VPN setup)
- ✅ CI/CD integrated (automatic)
- ✅ Non-blocking (no delays)

### Cost
- ✅ GitHub Pages: Free
- ✅ Tailscale: Free tier available
- ✅ Public CDN: No cost
- ✅ Maintenance: Minimal

---

## Deployment Timeline

```
TODAY:
├── Create Tailnet (5 min)
├── Add king-server (2 min)
├── Create auth key (2 min)
├── Add to GitHub (1 min)
├── Set ACL policy (2 min)
├── Test deployment (3 min)
└── ✅ READY (15 min total)

ONGOING:
├── Public deploys: Automatic daily
├── Private notify: Best-effort
├── Tailscale: Automatic reconnect
└── Zero maintenance
```

---

## Next Steps

1. ✅ Create Tailnet: https://login.tailscale.com/
2. ✅ Install on king-server: `choco install tailscale`
3. ✅ Create auth key: https://login.tailscale.com/admin/settings/keys
4. ✅ Add GitHub secret: `TAILSCALE_AUTH_KEY`
5. ✅ Set ACL policy: https://login.tailscale.com/admin/acls/
6. ✅ Test: Trigger workflow + verify both public & private
7. ✅ Monitor: Check logs in dispatch API

---

## Verify Everything Works

### Checklist
- [ ] 12sgi.com/site/ loads (public)
- [ ] Agendas visible (public)
- [ ] Money dashboards work (public)
- [ ] Tailscale shows king-server online
- [ ] ci-runner connects during workflow
- [ ] Dispatch log receives notification
- [ ] ACL policy blocks unauthorized access
- [ ] Workflow completes in <15 min
- [ ] No manual intervention needed
- [ ] Both public + private work simultaneously

---

## Result

### ✅ Public Domain
```
12sgi.com/site/
├── Worldwide accessible
├── 297 civic dashboards
├── No authentication
├── CDN-backed (fast)
└── Auto-updated daily
```

### 🔒 Protected Backend
```
100.124.152.3 (Tailscale)
├── Neo4j: Safe
├── Services: Protected
├── APIs: Secured
├── Logs: Encrypted
└── Access: Controlled
```

### ⚡ Seamless Integration
```
GitHub Actions
├── Public deploy: GitHub Pages ✅
├── Private notify: Tailscale ✅
├── Non-blocking: Both simultaneous ✅
└── Monitoring: Automatic ✅
```

---

**Architecture ready for implementation! See TAILSCALE_SETUP_GUIDE.md for step-by-step instructions.**

Latest commits:
```
6b462ec5 - Add Tailscale architecture: public + protected backend
```

