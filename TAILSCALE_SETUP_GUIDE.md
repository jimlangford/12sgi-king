# Tailscale Implementation Guide: 12sgi.com Public + Protected Backend

## Quick Setup (15 minutes)

### Phase 1: GitHub Pages Public (Already Done ✅)

Your workflow already includes:
```yaml
- name: Add custom domain
  run: printf '%s\n' '12sgi.com' > site/CNAME

- name: Deploy to GitHub Pages
  uses: actions/deploy-pages@v5
```

Result: ✅ https://12sgi.com/site/ is public and live

---

### Phase 2: Tailscale Network Setup (NEW)

#### Step 1: Create Tailnet
1. Go to https://login.tailscale.com/
2. Sign in with your account
3. Create organization "12 Stones Global" (if needed)
4. You'll see: "Your Tailnet is ready"

#### Step 2: Add King-Server to Network

**Option A: Windows Runner (Using GUI)**
```
1. Download: https://tailscale.com/download/windows
2. Install and run
3. Click "Connect" → Authenticate
4. Appears in: https://login.tailscale.com/admin/machines/
```

**Option B: Windows Runner (Using CLI)**
```powershell
# In PowerShell as Administrator:
choco install tailscale

# Start service:
Start-Service tailscaled

# Authenticate:
tailscale login

# Set hostname:
tailscale set --hostname=king-server

# Verify:
tailscale status
```

#### Step 3: Create Tailscale Pre-Auth Key

1. Go to: https://login.tailscale.com/admin/settings/keys
2. Click "Generate auth key"
3. Set:
   - Reusable: ✓ (checkbox)
   - Expiry: 90 days
   - Tags: `tag:ci` (optional, for ACL)
4. Copy the key

#### Step 4: Add Key to GitHub

1. Go to: https://github.com/jimlangford/12sgi-king
2. Settings → Secrets and variables → Actions
3. New secret:
   - Name: `TAILSCALE_AUTH_KEY`
   - Value: (paste from Step 3)
4. Save

---

### Phase 3: Update GitHub Actions (NEW)

Your `publish.yml` already has the Tailscale code, but verify these sections exist:

```yaml
# Near the end of the deploy job:

- name: Check for Tailscale key
  id: tskey
  run: |
    if [ -n "${{ secrets.TAILSCALE_AUTH_KEY }}" ]; then
      echo "present=true" >> "$GITHUB_OUTPUT"
    else
      echo "present=false" >> "$GITHUB_OUTPUT"
    fi

- name: Connect to Tailscale (best-effort, private notify only)
  if: ${{ success() && steps.tskey.outputs.present == 'true' }}
  continue-on-error: true
  uses: tailscale/github-action@v3
  with:
    authkey: ${{ secrets.TAILSCALE_AUTH_KEY }}
    hostname: ci-runner

- name: Notify private King on success
  if: ${{ success() && steps.tskey.outputs.present == 'true' }}
  continue-on-error: true
  run: |
    curl -s -m 15 -X POST http://100.124.152.3:8799/api/dispatch/log \
      -H 'Content-Type: application/json' \
      -d '{"message":"✅ PUBLIC: GitHub Pages live at https://12sgi.com/site/","source":"ci-runner"}' \
      || echo "private notify failed (non-fatal) -- public deploy already succeeded"
```

**If not present**, add them to the end of the `deploy` job (before the last `endgroup`).

---

### Phase 4: Set Tailscale ACL Policy (NEW)

1. Go to: https://login.tailscale.com/admin/acls/

2. Replace the entire policy with:

```json
{
  "groups": {
    "group:admins": [
      "jimlangford@gmail.com"
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

    // CI: Backend services only
    {
      "action": "accept",
      "src": ["group:ci"],
      "dst": [
        "100.124.152.3:7474",
        "100.124.152.3:7687",
        "100.124.152.3:8101",
        "100.124.152.3:8102",
        "100.124.152.3:8103",
        "100.124.152.3:8104",
        "100.124.152.3:8105",
        "100.124.152.3:8106",
        "100.124.152.3:8107",
        "100.124.152.3:8109",
        "100.124.152.3:8799"
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
```

3. Click "Save"

---

## Testing

### Test 1: Public Deploy

```bash
# Manually trigger workflow:
# GitHub: Actions → kilo-aupuni publish → Run workflow → Run on main

# Check result at:
https://12sgi.com/site/reports.html

# Should see: "Kilo Aupuni - Maui County / Hawaii Civic Transparency"
```

### Test 2: Tailscale Connection

```bash
# On king-server:
tailscale status
# Should show: king-server is RUNNING

# On your laptop (if on Tailnet):
ping king-server
# Or: ping 100.124.152.3

# Should respond within 1-2ms (local network)
```

### Test 3: Private Notify

```bash
# After public deploy completes, check:
# http://100.124.152.3:8799/api/dispatch/log (via Tailscale)

# Should see log entry from ci-runner with:
# "✅ PUBLIC: GitHub Pages live at https://12sgi.com/site/"
```

---

## Result

After setup, you have:

### ✅ Public (GitHub Pages)
```
https://12sgi.com/site/
├── reports.html          (Main hub)
├── agendas_*.html        (18 jurisdictions)
├── money_*.html          (Financial data)
└── [297 total pages]

Accessible: Worldwide ✓
Auth: None (public data)
Speed: CDN-backed
Update: Automatic (daily)
```

### 🔒 Private (Tailscale)
```
100.124.152.3 (king-server)
├── Neo4j (7474, 7687)
├── V2 services (8101-8109)
├── board-api (8799)
└── All backend systems

Accessible: Tailscale users only ✓
Auth: ACL policy
Security: Zero-trust, encrypted
Protection: Intact ✓
```

### ⚡ CI/CD Integration
```
GitHub Actions publish.yml
├── Build static site
├── Deploy to GitHub Pages (PUBLIC)
│   └── https://12sgi.com/site/
├── Connect to Tailscale (PRIVATE)
└── Notify king-server
    └── http://100.124.152.3:8799/api/dispatch/log
    
Blocks: None (non-blocking)
Fails: Never (public deploy succeeds independently)
Time: ~5-10 minutes total
```

---

## Troubleshooting

### "Tailscale not connecting"
```bash
# Check service:
tailscale status

# If not running:
Start-Service tailscaled

# Login again:
tailscale login

# Check firewall:
# Allow UDP 41641 for Tailscale
```

### "Can't reach backend from GitHub Actions"
```
Verify:
1. king-server shows in Tailscale admin
2. ACL policy allows tag:ci to backend ports
3. Pre-auth key has tag:ci
4. Workflow uses correct TAILSCALE_AUTH_KEY secret
```

### "GitHub Pages not updating"
```bash
# Check workflow:
GitHub → Actions → kilo-aupuni publish

# Verify CNAME file:
cat site/CNAME
# Should show: 12sgi.com

# Verify DNS:
nslookup 12sgi.com
# Should point to: github.io
```

---

## Advanced: Optional Nginx Reverse Proxy

If you want single entry point for both public + private:

```nginx
# On a machine with Tailscale access:

upstream github_pages {
    server jimlangford.github.io:443;
}

upstream king_backend {
    server 100.124.152.3:8799;
}

server {
    listen 80;
    listen 443 ssl http2;
    server_name 12sgi.com www.12sgi.com;

    # SSL certificate (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/12sgi.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/12sgi.com/privkey.pem;

    # PUBLIC: GitHub Pages
    location /site/ {
        proxy_pass https://jimlangford.github.io/12sgi-king/site/;
        proxy_set_header Host jimlangford.github.io;
        proxy_ssl_verify off;
        expires 1h;
    }

    # PRIVATE: Backend API
    location /api/ {
        proxy_pass http://100.124.152.3:8799;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Root
    location / {
        return 301 https://12sgi.com/site/reports.html;
    }
}
```

---

## Security Checklist

- [ ] Tailscale auth key: Reusable + 90-day expiry
- [ ] GitHub Actions secret: `TAILSCALE_AUTH_KEY` created
- [ ] ACL policy: Restricts CI to backend only
- [ ] Public GitHub Pages: No Tailscale required
- [ ] Private backend: Tailscale-only access
- [ ] Workflow: `continue-on-error` on private notify
- [ ] DNS CNAME: 12sgi.com → jimlangford.github.io
- [ ] Firewall: UDP 41641 allowed (Tailscale WireGuard)

---

## Next Steps

1. ✅ Create Tailnet (https://login.tailscale.com/)
2. ✅ Add king-server to network
3. ✅ Create pre-auth key
4. ✅ Add key to GitHub secrets
5. ✅ Update ACL policy
6. ✅ Test public deploy
7. ✅ Test Tailscale connection
8. ✅ Monitor logs

---

**Setup time: 15 minutes**
**Result: Public GitHub Pages + Protected Backend**

