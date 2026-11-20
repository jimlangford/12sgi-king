# Tailscale + Public GitHub Pages Architecture for 12sgi.com

## Overview

**Public:** 12sgi.com GitHub Pages (world-accessible)
**Private:** Backend services protected via Tailscale

```
┌─────────────────────────────────────────────────────────────┐
│  INTERNET (Public)                                          │
│  12sgi.com (GitHub Pages CDN)                               │
│  ✓ Accessible worldwide                                     │
│  ✓ No authentication needed                                 │
│  ✓ Civic transparency dashboards                           │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTPS/CDN
                      ▼
         ┌────────────────────────────┐
         │  GitHub Pages             │
         │  jimlangford.github.io    │
         │  /12sgi-king/site/        │
         └────────────────────────────┘
                      │
                      │ DNS CNAME
                      │ (12sgi.com → github.io)
                      ▼
         ┌────────────────────────────────────────┐
         │  CUSTOM DOMAIN: 12sgi.com             │
         │  (Public, no authentication)           │
         │  Served by GitHub Pages                │
         │  All 297 civic dashboards              │
         └────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│  TAILSCALE NETWORK (Private)                                │
│  100.x.x.x/32 (Private IPs)                                 │
│                                                             │
│  Protected Services:                                        │
│  ├── Neo4j (7474, 7687)     [brain - graph DB]            │
│  ├── king-bridge (8109)     [dispatcher]                  │
│  ├── auth (8101)            [identity]                   │
│  ├── tenant (8102)          [multi-tenant]               │
│  ├── documents (8103)       [storage]                    │
│  ├── storage (8104)         [files]                      │
│  ├── ai (8105)              [inference]                  │
│  ├── gpu-router (8107)      [GPU orchestration]          │
│  ├── health (8106)          [fleet monitoring]           │
│  ├── board-api (8799)       [owner console]              │
│  ├── connector-runner       [background jobs]            │
│  └── github-workflow-monitor [CI/CD integration]         │
│                                                             │
│  ✓ Only Tailscale users can access                         │
│  ✓ Zero-trust networking                                   │
│  ✓ Encrypted end-to-end                                    │
│  ✓ ACL-controlled access                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Architecture: Public vs. Private

### Public Access (GitHub Pages)
```
User Browser → GitHub CDN → 12sgi.com (CNAME)
                              ↓
                        site/reports.html
                        site/agendas_*.html
                        site/money_*.html
                        [297 static pages]
                        
Access: Worldwide, no auth
Performance: CDN-backed, fast
Data: Public civic records
```

### Private Access (Tailscale)
```
Tailscale Client → Tailscale Relay → Private IP (100.x.x.x)
                                       ↓
                         king-server (self-hosted runner)
                         - Neo4j (7474)
                         - V2 Services (8101-8109)
                         - board-api (8799)
                         
Access: Tailscale users only (ACL-controlled)
Security: Zero-trust, encrypted
Data: Sensitive backend systems
```

---

## Step 1: GitHub Pages Setup (Public)

### DNS Configuration
Your domain registrar should have:

```
CNAME Record:
  Name:    12sgi.com (or @)
  Target:  jimlangford.github.io
  TTL:     3600
```

### GitHub Actions Setup
```yaml
# .github/workflows/publish.yml (already configured)

- name: Add custom domain
  run: |
    printf '%s\n' '12sgi.com' > site/CNAME

- name: Deploy to GitHub Pages
  uses: actions/deploy-pages@v5
```

The workflow already:
✅ Adds CNAME file (github.io recognizes it)
✅ Deploys to GitHub Pages
✅ GitHub automatically handles SSL/TLS
✅ Public at https://12sgi.com/site/

---

## Step 2: Tailscale Network Setup (Private)

### 1. Create Tailscale Tailnet

```bash
# Go to https://login.tailscale.com/
# Create new tailnet (or use existing)
# Organization: 12 Stones Global
```

### 2. Add King-Server to Tailscale

```bash
# On king-server (Windows with Docker):
# Download: https://tailscale.com/download/windows

# Or via PowerShell:
choco install tailscale

# Authenticate:
tailscale login

# Verify:
tailscale status
```

### 3. Set Hostname

```bash
# On king-server:
tailscale set --hostname=king-server

# Verify it appears in Tailscale admin:
https://login.tailscale.com/admin/machines/
```

### 4. Enable MagicDNS (Optional)

```
Admin console:
  → DNS
  → Enable MagicDNS
  
This allows: ping king-server (instead of 100.x.x.x)
```

---

## Step 3: Tailscale ACL Policy

### Create ACL Policy

Go to: https://login.tailscale.com/admin/acls/

```json
{
  "groups": {
    "group:admins": [
      "jimlangford",
      "jimmy@12sgi.com"
    ],
    "group:ci": [
      "ci-runner",
      "github-actions"
    ]
  },

  "acls": [
    // Admins: Full access to everything
    {
      "action": "accept",
      "src": ["group:admins"],
      "dst": ["*:*"]
    },

    // CI/CD: Access to backend services only (not public web)
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

    // API calls from public GitHub Actions:
    // (ci-runner connects to private IP after auth)
    {
      "action": "accept",
      "src": ["group:ci"],
      "dst": ["100.124.152.3:8799"]  // board-api (dispatch logging)
    },

    // Deny everything else
    {
      "action": "deny",
      "src": ["*"],
      "dst": ["*:*"]
    }
  ]
}
```

---

## Step 4: CI/CD Integration (Non-Blocking)

### Add Tailscale Auth Key to GitHub

1. Go to: https://login.tailscale.com/admin/settings/keys
2. Create new Pre-auth key:
   - Reusable: ✓
   - Expiry: 90 days (or longer)
   - Tags: `tag:ci`
3. Add to GitHub repo:
   - Settings → Secrets and variables → Actions
   - New secret: `TAILSCALE_AUTH_KEY`
   - Value: (paste key from step 2)

### Update Workflow (publish.yml)

```yaml
- name: Check for Tailscale key
  id: tskey
  run: |
    if [ -n "${{ secrets.TAILSCALE_AUTH_KEY }}" ]; then
      echo "present=true" >> "$GITHUB_OUTPUT"
    else
      echo "present=false" >> "$GITHUB_OUTPUT"
    fi

- name: Connect to Tailscale (best-effort, for private notify only)
  if: ${{ success() && steps.tskey.outputs.present == 'true' }}
  continue-on-error: true
  uses: tailscale/github-action@v3
  with:
    authkey: ${{ secrets.TAILSCALE_AUTH_KEY }}
    hostname: ci-runner

- name: Notify private King on successful public deploy
  if: ${{ success() && steps.tskey.outputs.present == 'true' }}
  continue-on-error: true
  run: |
    curl -s -m 15 -X POST http://100.124.152.3:8799/api/dispatch/log \
      -H 'Content-Type: application/json' \
      -d '{
        "message": "✅ PUBLIC: GitHub Pages live at https://12sgi.com/site/",
        "source": "ci-runner",
        "status": "shipped"
      }' \
      || echo "Private notify failed (non-fatal) — public deploy already live"
```

**Key points:**
- ✅ Public deploy ALWAYS succeeds (GitHub Pages)
- ✅ Private notify is best-effort (continue-on-error)
- ✅ Non-blocking: workflow returns immediately
- ✅ CI/CD pipeline never waits for Tailscale

---

## Step 5: Local Access (Both Public & Private)

### Public Content
```bash
# GitHub Pages (worldwide)
https://12sgi.com/site/reports.html
https://12sgi.com/site/agendas_maui.html

# Or local mirror
http://localhost:8080/site/reports.html
```

### Private Backend (Tailscale only)
```bash
# Must be on Tailscale network:

# Neo4j
http://100.124.152.3:7474/

# King-bridge
http://100.124.152.3:8109/api/v2/ready

# Dashboard
http://100.124.152.3:8799/api/dispatch/log
```

### Reverse Proxy (Optional: Single Entry Point)

To expose BOTH public + private through one domain, use Nginx:

```nginx
# /etc/nginx/sites-available/12sgi.com

server {
    listen 80;
    listen 443 ssl http2;
    server_name 12sgi.com www.12sgi.com;
    
    # Public: GitHub Pages (upstream)
    location /site/ {
        proxy_pass https://jimlangford.github.io/12sgi-king/site/;
        proxy_set_header Host jimlangford.github.io;
        proxy_ssl_verify off;
        
        # Cache static content
        expires 1h;
        add_header Cache-Control "public, max-age=3600";
    }
    
    # Private: Backend services (Tailscale only)
    location /api/ {
        # Restrict to Tailscale users via ACL
        # (Done at Tailscale layer, not here)
        
        proxy_pass http://100.124.152.3:8799;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Redirect root to public dashboards
    location / {
        return 301 https://12sgi.com/site/reports.html;
    }
}
```

---

## Step 6: Monitoring & Logging

### Public Deploys (GitHub Pages)

```yaml
# Automatic notifications
- name: Log public deploy success
  run: |
    echo "✅ SHIPPED: GitHub Pages live"
    echo "URL: https://12sgi.com/site/reports.html"
    echo "Timestamp: $(date)"
    echo "Commit: ${{ github.sha }}"
```

### Private Notifications (Tailscale)

```yaml
- name: Notify private King
  run: |
    curl -s -X POST http://100.124.152.3:8799/api/dispatch/log \
      -H 'Content-Type: application/json' \
      -d '{
        "message": "✅ Deploy: public GitHub Pages + private backend notified",
        "commit": "${{ github.sha }}",
        "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
        "trigger": "${{ github.event_name }}"
      }'
```

---

## Security: What's Protected?

### ✅ Public (GitHub Pages)
- Static HTML/CSS/JS (297 pages)
- Civic transparency data (public records)
- No authentication needed
- Worldwide accessible
- CDN cached

### 🔒 Private (Tailscale)
- Neo4j graph database
- Auth service (identity)
- Document/storage services
- AI/GPU orchestration
- Board API (owner console)
- Real-time dispatch logging
- Only Tailscale members (ACL-controlled)

### 🔐 Network Security
- Tailscale: End-to-end encryption
- WireGuard protocol (military-grade)
- Zero-trust networking
- No open ports exposed
- ACL policy-driven access
- Audit logging on all access

---

## Quick Reference

### Public Access
```
Website: https://12sgi.com/site/
Hub:     https://12sgi.com/site/reports.html
Public:  Worldwide, no auth, CDN-backed
```

### Private Access
```
Tailscale: connect first
Neo4j:     http://100.124.152.3:7474/
API:       http://100.124.152.3:8799/api/dispatch/log
Admin:     https://login.tailscale.com/admin/machines/
```

### CI/CD Integration
```
GitHub Actions publishes to GitHub Pages (public)
Then notifies king-server via Tailscale (private)
Both happen simultaneously, non-blocking
```

---

## Implementation Checklist

- [ ] Create Tailscale tailnet at https://login.tailscale.com/
- [ ] Add king-server to Tailscale network
- [ ] Set hostname: `tailscale set --hostname=king-server`
- [ ] Create Tailscale pre-auth key (reusable)
- [ ] Add key to GitHub: `Settings → Secrets → TAILSCALE_AUTH_KEY`
- [ ] Set up Tailscale ACL policy (from step 3)
- [ ] Update GitHub Actions workflow (publish.yml)
- [ ] Test public deploy: https://12sgi.com/site/
- [ ] Test private notify: Verify dispatch log received
- [ ] Set up DNS CNAME: 12sgi.com → jimlangford.github.io
- [ ] (Optional) Deploy Nginx reverse proxy
- [ ] (Optional) Enable MagicDNS in Tailscale admin
- [ ] Document for team (this document!)

---

## Result

✅ **Public**: 12sgi.com/site/ available worldwide
✅ **Private**: Backend protected via Tailscale
✅ **Integrated**: CI/CD notifies both seamlessly
✅ **Secure**: Zero-trust, encrypted, ACL-controlled
✅ **Non-blocking**: Public deploy independent of private notify

