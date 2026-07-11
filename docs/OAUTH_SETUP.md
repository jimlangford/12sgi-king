# OAuth Sign-In Setup Guide

This document covers the one-time setup needed to enable GitHub and Google sign-in for the Naga console owner surfaces.

## Architecture overview

```
Browser (Naga console / GitHub Pages)
  │ clicks "Continue with GitHub"
  ▼
https://auth.12sgi.com   ← Cloudflare Tunnel → king-server localhost:8101
  │ GET /api/v2/auth/github  →  GitHub OAuth authorize
  │ GET /api/v2/auth/github/callback  ←  GitHub callback
  │ issues govOS JWT, redirects to console
  ▼
https://12sgi.com/king/#token=...   ← console picks up token, stores to localStorage
```

The auth service runs in Docker on king-server (Tailscale host `12sgianonymous`).  
A Cloudflare Tunnel exposes it publicly at `auth.12sgi.com` — no inbound ports required.

---

## 1. Register the OAuth apps

### GitHub

1. Go to **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**
2. Fill in:
   - **Application name:** 12sgi King Console
   - **Homepage URL:** `https://12sgi.com`
   - **Authorization callback URL:** `https://auth.12sgi.com/api/v2/auth/github/callback`
3. Click **Register application**
4. Copy the **Client ID** and generate + copy the **Client Secret**

### Google

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials → OAuth 2.0 Client ID**
3. Application type: **Web application**
4. **Authorized redirect URI:** `https://auth.12sgi.com/api/v2/auth/google/callback`
5. Click **Create**
6. Copy the **Client ID** and **Client Secret**

---

## 2. Create .env.v2 on king-server

Create `/path/to/12sgi-king/.env.v2` (gitignored).  
The `docker-compose.v2.yml` reads `${VAR:-default}` from this file.

```env
# OAuth credentials
GITHUB_CLIENT_ID=<paste from GitHub>
GITHUB_CLIENT_SECRET=<paste from GitHub>

GOOGLE_CLIENT_ID=<paste from Google>
GOOGLE_CLIENT_SECRET=<paste from Google>

# Auth service public URL (set after Cloudflare Tunnel is running)
AUTH_PUBLIC_URL=https://auth.12sgi.com

# Console URL to redirect back to after sign-in
OAUTH_REDIRECT_BASE=https://12sgi.com/king/

# Your GitHub login and/or Google email (comma-separated for multiple owners)
OWNER_GITHUB_LOGINS=jimlangford
OWNER_GOOGLE_EMAILS=you@gmail.com

# CORS origins for the console front-end
CORS_ORIGINS=https://jimlangford.github.io,https://12sgi.com

# Strong random secret — generate with: python -c "import secrets; print(secrets.token_hex(32))"
AUTH_SIGNING_SECRET=<generate>
```

---

## 3. Set up the Cloudflare Tunnel

Run these on **king-server** (PowerShell):

```powershell
# Install cloudflared (if not already)
winget install Cloudflare.cloudflared

# Authenticate
cloudflared tunnel login

# Create a named tunnel
cloudflared tunnel create king-auth

# Route the tunnel to the auth container
# (auth is bound to 127.0.0.1:8101 by docker-compose.v2.yml)
cloudflared tunnel route dns king-auth auth.12sgi.com

# Create config at %USERPROFILE%\.cloudflared\king-auth.yml
# Contents:
#   tunnel: <TUNNEL-ID>
#   credentials-file: C:\Users\<you>\.cloudflared\<TUNNEL-ID>.json
#   ingress:
#     - hostname: auth.12sgi.com
#       service: http://localhost:8101
#     - service: http_status:404

# Run the tunnel (or install as a Windows service)
cloudflared tunnel run king-auth
```

---

## 4. Start / restart the auth service

```powershell
cd C:\path\to\12sgi-king
docker compose -f docker-compose.v2.yml --env-file .env.v2 up -d --build auth
```

Verify:
```powershell
curl https://auth.12sgi.com/api/v2/live
# → {"status":"alive","service":"auth",...}
```

---

## 5. Sign in to the console

1. Open the Naga console (e.g., `https://12sgi.com/king/`)
2. Click the 🔒 lock button in the sidebar
3. Choose **Continue with GitHub** or **Continue with Google**
4. Authorize — you'll be redirected back with the owner surfaces unlocked
5. The session lasts **8 hours** and is stored in `localStorage`
6. While the token is still valid, the console silently calls `POST /api/v2/auth/renew` before expiry so long editing sessions do not force a fresh OAuth round-trip

---

## Token details

- The govOS JWT is issued by the auth service and stored in `localStorage` as `king.ownerToken`
- It carries `sub` (e.g. `github:jimlangford`), `provider`, and `exp` (expiry)
- On page load the console checks `exp`; expired tokens are ignored automatically
- Clicking 🔓 → **sign out** clears the token immediately

---

## Allowlist management

Add or remove owners by updating the docker-compose env vars in `.env.v2` and restarting the auth container:

```powershell
docker compose -f docker-compose.v2.yml --env-file .env.v2 up -d auth
```

The `OWNER_GITHUB_LOGINS` and `OWNER_GOOGLE_EMAILS` variables are comma-separated.  
Whitespace is ignored, and matching is case-insensitive for both GitHub logins and Google e-mail addresses.  
If `OWNER_GOOGLE_EMAILS` is left empty, any Google account is blocked.

---

## Testing with Tailscale (no Cloudflare Tunnel)

If Tailscale is still active and you want to test locally before setting up the tunnel:

1. Set `KING_AUTH_URL` on the page (in browser console):
   ```js
   window.KING_AUTH_URL = 'http://12sgianonymous.tail760750.ts.net:8101';
   ```
2. Or add `<script>window.KING_AUTH_URL='http://...'</script>` to `king_public_src/index.html` for local builds.
3. The OAuth providers require HTTPS for callbacks, so for pure Tailscale testing you'll need to set up a local HTTPS proxy (e.g., `caddy reverse-proxy --from https://auth.local.ts --to :8101`).
