# OAuth Setup Checklist — govOS v2

Quick reference for enabling all OAuth providers. Follow sequentially; skip optional items if not ready now.

---

## Pre-Flight

- [ ] Docker v2 stack running: `docker compose -f docker-compose.v2.yml ps`
- [ ] Auth container healthy: `curl http://127.0.0.1:8101/api/v2/health`
- [ ] Cloudflare Tunnel ready (for public `auth.12sgi.com`): `cloudflared tunnel list`
- [ ] `.env.v2` file created (from `.env.v2.example`)

---

## Required: GitHub OAuth

**Time:** 10 min

1. Go to https://github.com/settings/developers → **OAuth Apps** → **New OAuth App**
2. Fill in:
   - **Application name:** `12sgi King Console`
   - **Homepage URL:** `https://12sgi.com`
   - **Authorization callback URL:** `https://auth.12sgi.com/api/v2/auth/github/callback`
3. Click **Register Application**
4. Copy **Client ID** and **Client Secret** to `.env.v2`:
   ```
   GITHUB_CLIENT_ID=<paste>
   GITHUB_CLIENT_SECRET=<paste>
   ```
5. Restart auth: `docker compose -f docker-compose.v2.yml up -d --build auth`
6. Verify: `curl http://127.0.0.1:8101/api/v2/auth/debug | jq '.github.configured'` → should be `true`

---

## Required: Google OAuth

**Time:** 10 min

1. Go to https://console.cloud.google.com/apis/credentials
2. Click **+ Create Credentials** → **OAuth 2.0 Client ID**
3. Choose **Web application** if prompted
4. Add **Authorized redirect URI:** `https://auth.12sgi.com/api/v2/auth/google/callback`
5. Click **Create**
6. Copy **Client ID** and **Client Secret** to `.env.v2`:
   ```
   GOOGLE_CLIENT_ID=<paste>
   GOOGLE_CLIENT_SECRET=<paste>
   ```
7. Restart: `docker compose -f docker-compose.v2.yml up -d --build auth`
8. Verify: `curl http://127.0.0.1:8101/api/v2/auth/debug | jq '.google.configured'` → should be `true`

---

## Optional: Apple Sign-In (Sprint 1.1)

**Time:** 15 min  
**Status:** Not yet implemented (endpoints stubbed; skip for now)

When ready (after Sprint 1.1 implementation):

1. Go to https://developer.apple.com/account/resources/identifiers/list
2. **Identifiers** → **+** → **App IDs**
3. Configure "Sign in with Apple"
4. Set **Return URL:** `https://auth.12sgi.com/api/v2/auth/apple/callback`
5. Generate private key (`.p8` file)
6. Add to `.env.v2`:
   ```
   APPLE_CLIENT_ID=<App ID>
   APPLE_TEAM_ID=<Team ID from Apple Developer>
   APPLE_KEY_ID=<Key ID from .p8>
   APPLE_PRIVATE_KEY=<contents of .p8 file>
   ```

---

## Optional: Microsoft Entra (Sprint 1.2)

**Time:** 15 min  
**Status:** Not yet implemented (endpoints stubbed; skip for now)

When ready (after Sprint 1.2 implementation):

1. Go to https://portal.azure.com → **Azure Active Directory** → **App registrations** → **+ New registration**
2. Fill in:
   - **Name:** `govOS v2 Console`
   - **Redirect URI:** `https://auth.12sgi.com/api/v2/auth/microsoft/callback`
3. Go to **Certificates & secrets** → **+ New client secret**
4. Copy **Client ID** and **Client secret** value to `.env.v2`:
   ```
   MICROSOFT_CLIENT_ID=<paste>
   MICROSOFT_CLIENT_SECRET=<paste>
   MICROSOFT_TENANT_ID=common
   ```

---

## Optional: Passkeys/WebAuthn (Sprint 1.3)

**Time:** 5 min (config only; implementation follows)  
**Status:** Not yet implemented

Add to `.env.v2`:

```
WEBAUTHN_RP_ID=12sgi.com
WEBAUTHN_ORIGIN=https://12sgi.com
```

---

## Optional: Magic Links (Sprint 1.4)

**Time:** 10 min

Add to `.env.v2` with your email server details:

```
SMTP_HOST=smtp.gmail.com              # or your mail server
SMTP_PORT=587
SMTP_USER=your-email@gmail.com        # Gmail: enable "App Passwords"
SMTP_PASS=<app-password>
SMTP_FROM=noreply@12sgi.com           # Sender address
OWNER_MAGIC_EMAILS=jimlangford@me.com,your@email.com
```

---

## Testing OAuth Flows

### Test GitHub

```bash
# Start browser at this URL:
# https://auth.12sgi.com/api/v2/auth/github

# You'll be redirected to console with #token=...
# Token is valid for 8 hours
```

### Test Google

```bash
# Start browser at this URL:
# https://auth.12sgi.com/api/v2/auth/google

# You'll be redirected to console with #token=...
```

### Test Token

```bash
# Extract token from browser console: localStorage.king_ownerToken
# Then introspect it:

curl -X POST http://127.0.0.1:8101/api/v2/auth/introspect \
  -H "Content-Type: application/json" \
  -H "X-Service-Token: <INTERNAL_SERVICE_TOKEN from .env.v2>" \
  -d '{"token": "<your-token-here>"}'

# Response should show active: true
```

### Debug Config

```bash
# Check what's configured (no auth required):
curl http://127.0.0.1:8101/api/v2/auth/debug | jq

# Example output:
# {
#   "github": {"configured": true, "callback_uri": "..."},
#   "google": {"configured": true, "callback_uri": "..."},
#   "owner_github_login_count": 1,
#   "owner_google_email_count": 4
# }
```

---

## Troubleshooting

### "GitHub OAuth is not configured"

→ `GITHUB_CLIENT_ID` or `GITHUB_CLIENT_SECRET` is empty in `.env.v2`  
→ Restart auth after updating `.env.v2`

### "This GitHub account is not authorised"

→ GitHub login not in `OWNER_GITHUB_LOGINS` env var  
→ Add your GitHub login to `.env.v2` and restart

### "This Google account is not authorised"

→ Email not in `OWNER_GOOGLE_EMAILS` env var  
→ Add your Google email to `.env.v2` and restart

### "Authorization callback URL mismatch"

→ Provider config says `auth.12sgi.com` but your actual URL is different  
→ Update provider's callback URL to match `AUTH_PUBLIC_URL` in `.env.v2`

### Token renewal fails

→ Token is expired or invalid  
→ Sign in again via OAuth flow  
→ Or extend token TTL with `AUTH_TOKEN_TTL_SECONDS` (default: 3600 = 1 hour)

---

## Allowlist Management

**Add/remove owners** by editing `.env.v2`:

```env
OWNER_GITHUB_LOGINS=jimlangford,new-owner
OWNER_GOOGLE_EMAILS=jimlangford@me.com,newemail@gmail.com
```

Then restart:

```bash
docker compose -f docker-compose.v2.yml up -d auth
```

No database migration needed — auth service reads from env at startup.

---

## Architecture Diagram

```
Browser
  ↓ clicks "Continue with GitHub"
  ↓
GitHub OAuth endpoint
  ↓ redirects with code
  ↓
https://auth.12sgi.com/api/v2/auth/github/callback  (Cloudflare Tunnel)
  ↓ exchanges code for token
  ↓
King-server (docker)
  port 8101 (auth service)
  ↓ verifies, issues govOS JWT
  ↓
Browser (token in localStorage)
  ↓ authorized
  ↓
govOS console (govos, tenant, admin apps)
```

---

## Next: OAuth Implementation Roadmap

- **Sprint 1.1:** Apple Sign-In endpoint + handler
- **Sprint 1.2:** Microsoft Entra endpoint + handler
- **Sprint 1.3:** Passkeys (WebAuthn) registration + signin flows
- **Sprint 1.4:** Magic links (email) + SMTP integration
- **Sprint 1.5:** Frontend login UI (multi-provider picker)

---

## See Also

- Full setup guide: `docs/OAUTH_SETUP.md`
- Auth service internals: `services/auth/app/main.py`
- Service registry: `docs/SERVICE_REGISTRY.md`
