# 🚀 POINTS 3-5: Quick Reference Card

**Status**: Code complete ✓ | Owner setup tasks defined | ~30-45 minutes to live

---

## What Just Shipped

| Component | Status | Where |
|-----------|--------|-------|
| **Gordon** | ✓ Live | `http://localhost:8799/gordon.html` (Tailscale) |
| **Owner Policy** | ✓ Active | `config/owner_policy.json` |
| **Auth Sprint 1** | ✓ Ready | Apple, Microsoft, Magic Links, Passkeys |
| **Postiz** | ✓ Ready | `docker-compose.postiz.yml` — needs setup |
| **WordPress** | ✓ Ready | Jetpack OAuth — needs secrets |

---

## START HERE (3 Steps)

### 1️⃣ Run Interactive Setup (Recommended)
```bash
python quick_setup.py
# Menu-driven walkthrough, ~30 min
```

### 2️⃣ OR Read Full Guide
```bash
cat SETUP_FINAL_INTEGRATION.md
# Detailed, step-by-step, includes troubleshooting
```

### 3️⃣ Check Status Anytime
```bash
python gordon_setup.py
# Shows: Postiz, Jetpack, Auth, Policy status
```

---

## The 3 Things Owner Must Do

### Task 1: Connect Postiz (Meta + LinkedIn)
**Time**: ~15 minutes  
**Commands**:
```bash
docker compose -f docker-compose.postiz.yml up -d
# Opens http://localhost:4008
# → Create account
# → Add Meta app (Facebook/Instagram)
# → Add LinkedIn app
# → Copy integration IDs to config/own_channels.json
```

### Task 2: Set WordPress Jetpack Token
**Time**: ~15 minutes  
**What you do**:
```
1. Go to https://developer.wordpress.com/apps/
2. Create app → note Client ID + Secret
3. Do OAuth flow (authorize in browser)
4. Exchange code for token (one curl command)
5. gh secret set JETPACK_TOKEN
6. gh secret set JETPACK_SITE_ID
```
**Verify**: `gh secret list | grep JETPACK`

### Task 3: Verify Everything
**Time**: ~5 minutes  
**Commands**:
```bash
python gordon_setup.py
# All items should show ✓

# Test Gordon
curl http://localhost:8799/gordon.html

# Test Auth
curl http://localhost:8101/api/v2/auth/debug/sprint1
```

---

## Files You'll Touch

| File | Action | Why |
|------|--------|-----|
| `config/own_channels.json` | Copy from `.example`, fill in IDs | Postiz config |
| `.env.v2` (or docker-compose.v2.yml) | Set Apple/Microsoft env vars (optional) | Enable those auth methods |
| GitHub secrets (via `gh secret set`) | `JETPACK_TOKEN`, `JETPACK_SITE_ID` | WordPress CI/CD |

---

## Testing After Setup

### Test 1: Gordon Page Works
```
Open http://localhost:8799/gordon.html
Click "Full Diagnostics"
→ Should see all services green
```

### Test 2: Postiz Posts
```
Open http://localhost:4008
Select a channel
→ Try posting a test caption
→ Verify it appears on your Facebook/Instagram/LinkedIn
```

### Test 3: WordPress Publishing
```
In GitHub: Dispatch .github/workflows/wp-publish.yml
Set: dry_run=false, status=draft
→ Check WordPress admin for draft post
```

### Test 4: Social Media Gate
```bash
python -m services.v2_workboard --emit facebook --lane output --action post
# Should show: pending owner sign-off
```

---

## Key URLs

| Resource | URL |
|----------|-----|
| **Gordon Backup Page** | `http://localhost:8799/gordon.html` |
| **Postiz UI** | `http://localhost:4008` |
| **Auth Endpoints** | `http://localhost:8101/api/v2/auth/*` |
| **Setup Guide** | `SETUP_FINAL_INTEGRATION.md` |
| **Status Checker** | `python gordon_setup.py` |
| **Meta Developers** | `https://developers.facebook.com/` |
| **LinkedIn Developers** | `https://linkedin.com/developers/apps` |
| **WordPress.com Apps** | `https://developer.wordpress.com/apps/` |

---

## Troubleshooting (Top 3 Issues)

### ❌ Postiz won't start
```bash
docker compose -f docker-compose.postiz.yml logs postiz-own
# Check if Postgres/Redis are healthy
docker image prune -a --filter "until=72h"  # Free space if needed
```

### ❌ Jetpack token fails
```bash
# Verify token works:
curl -s https://public-api.wordpress.com/rest/v1.1/me \
  -H "Authorization: Bearer JETPACK_TOKEN"
# If 401: redo the OAuth flow (steps in SETUP_FINAL_INTEGRATION.md)
```

### ❌ Auth endpoints return 501
```bash
# Check auth service is running:
docker compose -f docker-compose.v2.yml logs auth | tail -20
# Verify env vars are set for Apple/Microsoft
docker compose -f docker-compose.v2.yml config | grep -i apple
```

---

## System After Setup

```
┌─────────────────────────────────────────┐
│  Gordon                                  │
│  └─ Backup page + diagnostics            │
├─────────────────────────────────────────┤
│  Auth (6 methods)                        │
│  ├─ GitHub, Google                       │
│  ├─ Apple ← NEW (if configured)         │
│  ├─ Microsoft ← NEW (if configured)     │
│  ├─ Magic Links ← NEW                   │
│  └─ Passkeys ← NEW                      │
├─────────────────────────────────────────┤
│  Publishing                              │
│  ├─ Postiz (Facebook/Instagram/LinkedIn) │
│  ├─ WordPress.com (Jetpack OAuth)        │
│  └─ Manual queues (X/TikTok/YouTube)     │
├─────────────────────────────────────────┤
│  Policy                                  │
│  ├─ Creative/Output: auto-approve       │
│  ├─ Social: owner sign-off required      │
│  └─ Studios: departments (no gate)       │
└─────────────────────────────────────────┘
```

---

## Success Checklist

- [ ] `docker compose -f docker-compose.postiz.yml up -d` works
- [ ] Postiz UI loads at http://localhost:4008
- [ ] Meta + LinkedIn apps connected in Postiz
- [ ] `config/own_channels.json` updated with real IDs
- [ ] `gh secret list` shows JETPACK_TOKEN and JETPACK_SITE_ID
- [ ] `python gordon_setup.py` shows all ✓
- [ ] `python quick_setup.py` test passes

---

## One-Liner Status Check

```bash
python gordon_setup.py && echo "✓ READY TO GO"
```

---

## Next: After Setup

1. **Test posting**: Create a job, approve it, post via `publish_approved_social.py`
2. **Test publishing**: Dispatch WordPress workflow, verify draft in admin
3. **Test auth**: Try Apple/Microsoft sign-in if configured
4. **Monitor gates**: Watch creative auto-approve, social media gate enforce

---

**Docs**:
- Full guide: `SETUP_FINAL_INTEGRATION.md`
- Status summary: `POINTS_3_5_STATUS.md`  
- Code locations: commit c9506432
- This card: `POINTS_3_5_QUICK_REFERENCE.md`

**Time to live**: ~30-45 min from now 🚀
