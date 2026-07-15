# govOS v2 Closure Plan — Continuation Guide

**Session 1 Status:** TIER 0 complete (5.75 hrs billed)  
**Session 2 Target:** TIER 1 complete (Apple OAuth, Microsoft OAuth, Passkeys, Magic Links)  
**Total Project:** 88 hrs estimated

---

## What Was Completed (Session 1)

### ✅ Tier 0 — Friction Removal

1. **docs/SERVICE_REGISTRY.md** (28.7 KB)
   - Complete API documentation for all 10 v2 services
   - No TBD fields
   - Endpoints, dependencies, health checks, env vars for each service
   - Deployment instructions

2. **CI Workflows** (production-ready)
   - `.github/workflows/ci-lint.yml` — Python (ruff), YAML, Shell linting
   - `.github/workflows/ci-test.yml` — pytest on v2 contract + integration tests
   - `.github/workflows/ci-accessibility.yml` — WCAG 2.2 AA scanning (pa11y + axe)
   - `.github/workflows/ci-secret-scan.yml` — truffleHog + detect-secrets
   - All now trigger on `pull_request` (not `workflow_dispatch`)

3. **.github/OAUTH_CHECKLIST.md** (6.9 KB)
   - Quick-reference OAuth setup for GitHub, Google
   - Future: Apple, Microsoft, Passkeys, Magic Links
   - <30 min per provider to configure

4. **.env.v2 + .env.v2.example**
   - Real secrets generated (AUTH_SIGNING_SECRET, INTERNAL_SERVICE_TOKEN)
   - OAuth provider placeholders ready
   - Deployment-safe template

5. **Passkeys Module** (services/auth/app/passkeys.py)
   - WebAuthn (FIDO2) credential registration
   - Credential signin flow
   - Sign-count verification (clone detection)
   - Ready to integrate into main auth service

**Commit:** `c43ab49` — "TIER 0 CLOSURE: Service registry, CI workflows, OAuth checklist"

---

## What's Next (Session 2) — TIER 1

### 1.1: Apple Sign-In OAuth (Est. 6 hrs)

**Files to modify:**
- `services/auth/app/main.py`
  - Add Apple env vars (APPLE_CLIENT_ID, APPLE_TEAM_ID, APPLE_KEY_ID, APPLE_PRIVATE_KEY)
  - Add `/api/v2/auth/apple` endpoint (redirect)
  - Add `/api/v2/auth/apple/callback` endpoint (token exchange)
  - Add to OWNER_APPLE_EMAILS allowlist
  - Pattern: copy GitHub flow, decode JWT instead of exchanging for token

**Key differences from GitHub:**
- Apple returns JWT (id_token) directly; no token exchange
- Must validate JWT signature against Apple's JWKS
- Apple returns unique `sub` identifier (not human-readable)

**Test:**
```bash
curl http://127.0.0.1:8101/api/v2/auth/debug | jq '.apple.configured'  # should be true
```

---

### 1.2: Microsoft OAuth (Est. 6 hrs)

**Files to modify:**
- `services/auth/app/main.py`
  - Add Microsoft env vars (MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID)
  - Add `/api/v2/auth/microsoft` endpoint
  - Add `/api/v2/auth/microsoft/callback` endpoint
  - Add to OWNER_MICROSOFT_EMAILS allowlist

**Key differences from GitHub:**
- Uses Azure AD token endpoint
- Returns access_token + id_token
- Must fetch user info from `/me` endpoint
- Tenant support (multi-tenant or single-tenant)

---

### 1.3: Passkeys/WebAuthn (Est. 12 hrs)

**Framework:** `py_webauthn` (already in services/auth/app/passkeys.py)

**Endpoints to add:**
- `POST /api/v2/auth/passkey/register/begin` → challenge
- `POST /api/v2/auth/passkey/register/complete` → store credential
- `POST /api/v2/auth/passkey/signin/begin` → challenge
- `POST /api/v2/auth/passkey/signin/complete` → issue JWT

**Database:**
- Extend `sessions` table or create `passkey_users` + `passkey_credentials` tables
- Store credential ID, public key, sign count
- Implement clone detection (sign count validation)

**Import in main.py:**
```python
from services.auth.app.passkeys import (
    passkey_register_begin, passkey_register_complete,
    passkey_signin_begin, passkey_signin_complete
)
```

---

### 1.4: Magic Links (Est. 8 hrs)

**Endpoints:**
- `POST /api/v2/auth/magiclink/request` → send email with link
- `GET /api/v2/auth/magiclink/claim?token=...&email=...` → verify link, issue JWT

**Implementation:**
- Generate short-lived random token (15 min TTL)
- Send email via SMTP (SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_FROM from .env.v2)
- Store pending token + email in DB
- On claim: verify token, issue JWT, delete token

**SMTP Config in .env.v2:**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=<app-password>
SMTP_FROM=noreply@12sgi.com
OWNER_MAGIC_EMAILS=jimlangford@me.com,your@email.com
```

---

## Tier 1.5–1.7 (Post-Session 2)

Once Tier 1 auth handlers are done:

### 1.5: Tenant App UI (12 hrs)
- React component: case list, detail view, new case form
- API calls to `/api/v2/cases`
- Tailwind styling

### 1.6: Admin App UI (12 hrs)
- React component: owner allowlist management
- Service health dashboard
- Audit log viewer
- API calls to new admin endpoints

### 1.7: Swagger Docs (2 hrs)
- Add docstrings to all endpoints
- Enable `/api/v2/docs` Swagger UI
- Generate OpenAPI schema at `/api/v2/openapi.json`

---

## Session 2 Execution Plan

**Billable:** ~30–32 hrs (all Tier 1 auth work)

1. **Implement Apple OAuth** (6 hrs)
   - Register app on Apple Developer (you)
   - Write endpoint handlers (me)
   - Test with real credentials

2. **Implement Microsoft OAuth** (6 hrs)
   - Register app in Azure AD (you)
   - Write endpoint handlers (me)
   - Test with real credentials

3. **Integrate Passkeys** (12 hrs)
   - Wire services/auth/app/passkeys.py into main auth service
   - Add endpoints
   - Create registration + signin UI stubs (or document for frontend team)
   - Test with authenticator

4. **Implement Magic Links** (8 hrs)
   - SMTP integration
   - Email sending + link claiming
   - Token cleanup (expired link garbage collection)
   - Test with real email

5. **Verify + Test** (2 hrs)
   - End-to-end test: all 6 providers working
   - `/api/v2/auth/debug` shows all configured
   - Tokens verify correctly with `/api/v2/auth/introspect`
   - CI tests still pass

---

## Git Status

**Last commit:** `c43ab49` (pushed to `jimlangford/12sgi-king@main`)

**Files staged for Tier 1:**
- `.env.v2` — OAuth provider placeholders ready
- `services/auth/app/passkeys.py` — WebAuthn module (ready to integrate)
- `docs/SERVICE_REGISTRY.md` — links to OAuth setup guides

---

## Continuation Checklist

When starting Session 2:

- [ ] Pull latest: `git pull origin main`
- [ ] Check `.env.v2` exists with real secrets
- [ ] Verify auth service running: `curl http://127.0.0.1:8101/api/v2/health`
- [ ] Start with Tier 1.1 (Apple OAuth)
- [ ] For each provider:
  1. Register with provider (you → provide credentials)
  2. Update .env.v2
  3. Implement endpoints
  4. Restart auth container
  5. Verify with `/api/v2/auth/debug`
  6. Test signin flow

---

## Contact & Handoff Notes

**What works now:**
- GitHub OAuth ✅
- Google OAuth ✅
- CI/CD pipeline enforced on PRs ✅
- Service registry complete ✅
- OAuth setup streamlined ✅

**What's blocked:**
- Apple OAuth (need Developer account + credentials)
- Microsoft OAuth (need Azure AD tenant + credentials)
- Passkeys (need web browser + authenticator for testing)
- Magic Links (need SMTP credentials)
- Frontend UIs (ready to build once auth is complete)

**Session 2 owner:** Gordon (full token budget)  
**Estimated completion:** 30–32 hrs  
**Completion target:** All 6 OAuth providers + Passkeys + Magic Links working, all tests passing

---

## Files to Review Before Session 2

1. `docs/SERVICE_REGISTRY.md` — refresh on all 10 services
2. `.github/OAUTH_CHECKLIST.md` — quick setup reference
3. `services/auth/app/main.py` — GitHub + Google patterns to copy
4. `services/auth/app/passkeys.py` — WebAuthn module (ready to integrate)
5. `docker-compose.v2.yml` — service wiring + env vars

---

**Total Project Progress:** 5.75 / 88 hrs complete = **6.5%**  
**Next milestone:** Tier 1 auth complete = 35.75 / 88 hrs = **41%**

Let's ship it. 🚀
