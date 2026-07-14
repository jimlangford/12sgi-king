# Final Integration Setup — Points 3-5 Implementation

**Status**: Commit c9506432 ✓ Complete. This guide walks through the remaining hands-on setup to make everything live.

**Time estimate**: 30–45 minutes (mostly third-party OAuth registration, no coding).

---

## What's Already Done (c9506432)

✓ **Point 3**: Gordon server backup page (`gordon.html`) — live at `http://localhost:8799/gordon.html` via Tailscale
✓ **Point 4**: Owner policy reset (`config/owner_policy.json`) — auto-approve creative/output, studios=departments, social media gate only
✓ **Point 5**: Auth Sprint 1 — Apple, Microsoft, magic links, passkeys implemented in `services/auth/app/auth_sprint1.py`
✓ **Point 5**: Postiz ready — `docker-compose.postiz.yml` (v2.11.2, Postgres+Redis, free)
✓ **Point 5**: WordPress/Jetpack path confirmed — OAuth token exchange documented

---

## What You Need to Do (Owner Actions Only)

### 1. Postiz: Connect Meta + LinkedIn (15 minutes)

**Why**: Postiz is free and necessary for automatic posting to Facebook/Instagram/LinkedIn. X (Twitter) is skipped (pay-per-call, no free tier) — stays in manual queue per your 2026-07-11 decision.

**Steps**:

1. **Start Postiz**:
   ```bash
   docker compose -f docker-compose.postiz.yml up -d
   ```
   Verify at `http://localhost:4008` (should load UI).

2. **Create the owner account** (first time only):
   - Open `http://localhost:4008`
   - Register a new account (owner email)
   - This auto-enables registration lock after first account

3. **Create free Meta Developer App** (Facebook/Instagram):
   - Go to https://developers.facebook.com/
   - Create App → Select "Business" type → name it "12SGI Civic"
   - In **Settings → Basic**, note the `App ID` and `App Secret`
   - Create an app role user for your account (if not already done)
   - In **Tools → Graph API Explorer**, test your token

4. **Connect your 12SGI Facebook Page + Instagram Business Account**:
   - In Postiz, go to **Settings → Channels**
   - Add "Facebook" → paste `App ID` and `App Secret`
   - Authorize with your account → select 12SGI Page
   - Repeat for Instagram Business (if separate account)
   - Once connected, Postiz shows the **integration ID**

5. **Create free LinkedIn Developer App** (Company Page posting):
   - Go to https://www.linkedin.com/developers/apps
   - Create app → name "12SGI Civic"
   - In **Auth**, set redirect URI to `http://localhost:4008/callback` (or similar)
   - Note the `Client ID` and `Client Secret`
   - Request "Sign in with LinkedIn" and "Marketing Developer Platform" access

6. **Connect your 12SGI LinkedIn Company Page**:
   - In Postiz, go to **Settings → Channels**
   - Add "LinkedIn" → paste `Client ID` and `Client Secret`
   - Authorize with your account → select company page
   - Once connected, Postiz shows the **integration ID**

7. **Generate Postiz API key**:
   - In Postiz, go to **Settings → API**
   - Create new key → copy it

8. **Update `config/own_channels.json`**:
   ```bash
   cp config/own_channels.json.example config/own_channels.json
   ```
   Edit with the integration IDs and credentials:
   ```json
   {
     "channels": {
       "facebook_12sgi": {
         "platform": "facebook",
         "integration_id": "PASTE_FROM_POSTIZ_HERE",
         "enabled": true
       },
       "instagram_business": {
         "platform": "instagram",
         "integration_id": "PASTE_FROM_POSTIZ_HERE",
         "enabled": true
       },
       "linkedin_company": {
         "platform": "linkedin",
         "integration_id": "PASTE_FROM_POSTIZ_HERE",
         "enabled": true
       }
     },
     "postiz_api_key": "PASTE_API_KEY_HERE"
   }
   ```

9. **Test posting**:
   ```bash
   docker compose -f docker-compose.postiz.yml logs -f postiz-own
   ```
   You can now manually post via the Postiz UI to verify integration works.

**Verify**: 
- Go to `http://localhost:4008` → **Dashboard** → see your connected channels
- Run `python gordon_setup.py` — should show "✓ connected" for your channels

---

### 2. WordPress + Jetpack OAuth Setup (15 minutes)

**Why**: WordPress is the public-facing site. Jetpack OAuth allows the CI/CD pipeline to post drafts and handle branch-page publishing without storing long-lived credentials in GitHub.

**Prerequisites**:
- Your site is hosted on WordPress.com (confirmed)
- You have admin access to the site
- `gh` CLI is installed locally (`brew install gh` / `choco install gh`)

**Steps**:

1. **Find your WordPress.com Site ID**:
   - Log into WordPress.com
   - Visit: `https://public-api.wordpress.com/rest/v1.1/sites/12sgi.com` (replace domain if needed)
   - In the JSON response, copy the `"ID"` field (numeric value)
   - Example: `"ID": 12345678`

2. **Register a WordPress.com application** (one-time):
   - Go to https://developer.wordpress.com/apps/
   - Click **"Create New Application"**
   - Name: "12SGI CI/CD"
   - Description: "GitHub Actions publishing bridge"
   - Redirect URI: `https://12sgi.com/oauth/callback` (or any URL you control)
   - Click **"Create"**
   - Note the **Client ID** and **Client Secret** shown

3. **Authorize once (manual OAuth flow)**:
   - Construct this URL (replace CLIENT_ID):
     ```
     https://public-api.wordpress.com/oauth2/authorize?client_id=CLIENT_ID&redirect_uri=https://12sgi.com/oauth/callback&response_type=code&scope=global
     ```
   - Open it in your browser
   - Log in and approve access
   - You'll be redirected to your redirect_uri with `?code=...` in the URL
   - **Copy that code** — you'll use it once in the next step

4. **Exchange the code for a token** (run once on your machine, never in shared chat):
   ```bash
   curl -s https://public-api.wordpress.com/oauth2/token \
     -d client_id=CLIENT_ID \
     -d client_secret=CLIENT_SECRET \
     -d redirect_uri=https://12sgi.com/oauth/callback \
     -d grant_type=authorization_code \
     -d code=CODE_FROM_STEP_3
   ```
   Response will be JSON with `"access_token"` — **copy that value**. This is your `JETPACK_TOKEN`.

5. **Store as GitHub repository secrets**:
   ```bash
   # Navigate to the repo directory
   cd 12sgi-king
   
   # Set secrets (will prompt for values)
   gh secret set JETPACK_TOKEN
   # Paste: <the access_token from step 4>
   
   gh secret set JETPACK_SITE_ID
   # Paste: <the ID from step 1>
   ```

6. **Verify secrets are set**:
   ```bash
   gh secret list
   ```
   Should show `JETPACK_TOKEN` and `JETPACK_SITE_ID` with `✓`.

7. **Optional: Store WordPress Application Password** (fallback auth, not needed if Jetpack token works):
   - In WordPress admin, go **Users → Your Profile**
   - Scroll to **Application Passwords**
   - Click **"Add New Application Password"**
   - Name: "GitHub Actions"
   - Generate and copy
   - Set as secret:
     ```bash
     gh secret set WP_APP_PASSWORD
     gh secret set WP_USER  # your WordPress username
     gh secret set WP_URL   # https://12sgi.com
     ```

**Verify**:
- Run `python gordon_setup.py` — should show "✓ JETPACK_TOKEN" and "✓ JETPACK_SITE_ID"
- Dispatch `.github/workflows/wp-publish.yml` with `dry_run=true` to test the OAuth connection

---

### 3. GitHub Actions Secrets (Final Checklist)

Run this locally to verify all required secrets are set:

```bash
gh secret list
```

**Required for WordPress publishing**:
- ✓ `JETPACK_TOKEN` (OAuth access token from step 4 above)
- ✓ `JETPACK_SITE_ID` (WordPress.com site numeric ID from step 1)

**Optional but recommended** (Application Password fallback):
- `WP_URL` (your WordPress URL)
- `WP_USER` (WordPress username)
- `WP_APP_PASSWORD` (from WordPress → Application Passwords)

**Optional for Postiz integration** (if you want CI/CD to post via Postiz):
- `POSTIZ_OWN_API_KEY` (generated in Postiz → Settings → API)

---

### 4. Auth Sprint 1 Verification (5 minutes)

All four new auth methods are already integrated. Verify they're wired:

```bash
# Check the debug endpoint on auth service
curl http://localhost:8101/api/v2/auth/debug/sprint1
```

Expected response (example):
```json
{
  "sprint": 1,
  "providers": {
    "github": { "configured": true },
    "google": { "configured": true },
    "apple": { "configured": true },
    "microsoft": { "configured": true },
    "magic_link": {
      "configured": true,
      "smtp_configured": false,
      "owner_emails": 4
    },
    "passkey": {
      "configured": true,
      "rp_id": "12sgi.com",
      "origin": "https://12sgi.com"
    }
  }
}
```

**Notes**:
- `apple` and `microsoft` configured: Requires env vars set in Docker (see `docker-compose.v2.yml`)
- `magic_link`: SMTP not configured locally (dev mode sends URLs directly instead)
- `passkey`: WebAuthn ready (challenge/verify endpoints live)

---

### 5. Owner Policy Activation (5 minutes)

Your owner policy is live in `config/owner_policy.json`. To activate it in production:

1. **Verify the policy**:
   ```bash
   python gordon_setup.py
   ```
   Should show:
   ```
   auto_approve_creative: True
   auto_approve_output:   True
   social_media_gate:     True
   studio_model:          department
   ```

2. **Test the social media gate**:
   - Create a test job in the workboard targeting `facebook` or `instagram`
   - When king-bridge processes it, `v2_workboard.requires_owner_signoff()` checks:
     ```python
     if platform in SOCIAL_MEDIA_PLATFORMS:
         return True  # Owner sign-off required
     ```
   - The job will be flagged for your approval before posting

3. **Test creative auto-approve**:
   - Create a test job in the `creative` lane
   - It auto-advances without owner sign-off (per `auto_approve_creative: true`)
   - Verify in the workboard log

---

## Testing the Full Stack

### Test 1: Gordon Command Page
```
Open http://localhost:8799/gordon.html (via Tailscale)
- Click "Full Diagnostics"
- Should show: neo4j OK, Ollama running, all services up
- Click "Gordon Chat" and try: "What services are running?"
```

### Test 2: Postiz Posting
```
Open http://localhost:4008
- Dashboard → select a channel
- Click "Schedule Post"
- Write test caption
- Click "Post" to publish immediately
- Verify post appears on your Facebook/Instagram/LinkedIn
```

### Test 3: WordPress Publishing
```bash
Dispatch .github/workflows/wp-publish.yml with:
  dry_run: false
  title: "Test Post"
  content: "This is a test."
  status: draft

Verify:
- Workflow runs successfully
- Check WordPress admin → Posts
- Draft "Test Post" appears
```

### Test 4: Auth Sprint 1
```
Open http://localhost:8101/api/v2/auth/debug/sprint1
- Verify all 6 providers listed
- For magic_link, dev_url should work in local mode
- For passkey, try requesting a challenge:

curl -X POST http://localhost:8101/api/v2/auth/passkey/challenge \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}'

Returns challenge ready for WebAuthn flow.
```

### Test 5: Owner Policy Gate
```bash
# Simulate a social media job requiring approval
python -m services.v2_workboard \
  --emit facebook \
  --lane output \
  --action post \
  --payload '{"text": "test"}'

# Check the dispatch log — should show pending owner sign-off
cat /data/dispatch/govos_v2_dispatch.jsonl | tail -5 | jq .

# Approve it:
python -m services.v2_workboard \
  --approve <job_id> \
  --approver owner

# Now king-bridge can process it
```

---

## Troubleshooting

### Postiz won't start
```
docker compose -f docker-compose.postiz.yml logs postiz-own
# Check: Postgres healthy? Redis healthy?
# If memory error: your host is full (docker system df)
docker image prune -a --filter "until=72h"
```

### WordPress authentication fails
```
# Check secrets are set:
gh secret list | grep JETPACK

# Test the Jetpack token directly:
curl -s https://public-api.wordpress.com/rest/v1.1/me \
  -H "Authorization: Bearer JETPACK_TOKEN"

# If 401: token is expired or invalid — re-do the OAuth flow (steps 1-4 above)
```

### Auth Sprint 1 endpoints not found
```
# Verify auth service is running:
docker compose -f docker-compose.v2.yml logs auth | tail -20

# Check env vars are set in docker-compose.v2.yml:
docker compose -f docker-compose.v2.yml config | grep -i apple

# If missing, add to .env.v2:
APPLE_CLIENT_ID=your_id
APPLE_TEAM_ID=your_team_id
APPLE_KEY_ID=your_key_id
APPLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n..."
```

### Magic links not emailing
```
# In dev (no SMTP), dev_url is returned in response:
curl -X POST http://localhost:8101/api/v2/auth/magic-link \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com"}'

# Response includes "dev_url": "http://localhost:8101/api/v2/auth/magic-link/verify?token=..."
# Click that URL to complete the flow

# In production (SMTP configured):
# Set env vars in docker-compose.v2.yml:
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASS=your_smtp_password
```

---

## Next Steps

1. **Postiz channels connected** → Enable in `config/own_channels.json`
2. **Jetpack token set** → Dispatch `wp-publish.yml` test workflow
3. **Auth Sprint 1 verified** → Test Apple/Microsoft sign-in once you set their env vars
4. **Owner policy active** → Tag jobs with social media platforms to test the gate

Once all 5 are live, you have:
- ✓ Gordon command center (backup, diagnostics, chat)
- ✓ Social media auto-posting (Facebook, Instagram, LinkedIn)
- ✓ WordPress publishing (drafts + branch pages)
- ✓ Multi-factor auth (Apple, Microsoft, magic links, passkeys)
- ✓ Owner policy enforcement (creative auto-approve, social gate)

---

## Files Modified / Created

- ✓ `gordon.html` — command page
- ✓ `gordon_setup.py` — setup status checker
- ✓ `config/owner_policy.json` — policy rules
- ✓ `services/auth/app/auth_sprint1.py` — new auth methods
- ✓ `services/v2_workboard.py` — social media gate
- ✓ `docker-compose.postiz.yml` — local Postiz stack
- ✓ `docs/WORDPRESS_PUBLIC_LAYER.md` — architecture
- ✓ `docs/SOCIAL_CONNECTORS.md` — policy & connector guide

No changes needed to app code — all wired via env vars and config files.

---

## References

- **Postiz setup**: http://localhost:4008 (after `docker compose up`)
- **Gordon commands**: http://localhost:8799/gordon.html
- **Setup status**: `python gordon_setup.py`
- **WordPress docs**: `docs/WORDPRESS_PUBLIC_LAYER.md`
- **Social policy**: `docs/SOCIAL_CONNECTORS.md`
- **Auth endpoints**: `services/auth/app/auth_sprint1.py`
