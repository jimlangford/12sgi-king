# SESSION 2 KICKOFF — TIER 1 (Passkeys + Magic Links + UIs)

**Status:** READY TO START  
**System:** Verified and healthy  
**Branch:** main / commit 598ecb2  
**Token budget:** ~120,000 fresh tokens  
**Estimated completion:** 46 hrs (Passkeys 12h + Magic Links 8h + Tenant UI 12h + Admin UI 12h + Swagger 2h)

---

## Quick Start

```bash
cd 12sgi-king
git pull origin main  # Already at 598ecb2
cat TIER_1_CONTINUATION.md  # Complete implementation guide + code examples
```

---

## System Health

| Metric | Status | Value |
|--------|--------|-------|
| **Auth service** | ✅ Running | Healthy (12 sessions) |
| **Docker containers** | ✅ Running | 14 active |
| **RAM available** | ✅ Good | 12 GB free (32 GB total) |
| **Disk free** | ⚠️ Tight | 54 GB (94% full) |
| **Other Claude instances** | ✅ Permitted | Can run in parallel |

---

## Session 2 Scope (REVISED from original Tier 1)

**Skip:** Apple OAuth (1.1) + Microsoft OAuth (1.2)  
**Focus:**

### 1.3: Passkeys/WebAuthn (12 hrs)
- Integrate `services/auth/app/passkeys.py` module
- Add 4 endpoints (register/signin begin + complete)
- Database schema: `passkey_users` + `passkey_credentials` + `passkey_challenges`
- Clone detection via sign-count validation
- Test with authenticator device (or fido2-ctap2 simulator)

### 1.4: Magic Links (8 hrs)
- Add endpoints: `/magiclink/request` → email + `/magiclink/claim` → JWT
- Database: `magic_link_tokens` table
- SMTP integration (Gmail or custom mail server)
- 15-minute token TTL + cleanup
- Test with real email address

### 1.5: Tenant App UI (12 hrs)
- React: `<CaseList />`, `<CaseDetail />`, `<NewCaseForm />`
- API integration to `/api/v2/cases`
- Tailwind styling
- localStorage token handling

### 1.6: Admin App UI (12 hrs)
- React: `<AllowlistManager />`, `<ServiceHealth />`, `<AuditLog />`
- Admin endpoints: `PATCH /api/v2/auth/owner/allowlist`
- API integration + styling

### 1.7: Swagger Docs (2 hrs)
- FastAPI docstrings on all endpoints
- Auto-generated `/api/v2/docs` + `/api/v2/openapi.json`

---

## Key Files (Already Prepared)

| File | Purpose | Status |
|------|---------|--------|
| `TIER_1_CONTINUATION.md` | Complete implementation guide with code examples | ✅ Ready |
| `services/auth/app/passkeys.py` | WebAuthn module (ready to integrate) | ✅ Ready |
| `.env.v2` | Environment config + SMTP placeholders | ✅ Ready |
| `docs/SERVICE_REGISTRY.md` | All 10 services reference | ✅ Complete |
| `services/auth/app/main.py` | GitHub + Google OAuth patterns to follow | ✅ Reference |

---

## Before Starting

1. **Verify git is clean:**
   ```bash
   git status  # Should show only docker-compose.v2.yml line endings (OK to ignore)
   ```

2. **Test auth service:**
   ```bash
   curl http://127.0.0.1:8101/api/v2/health
   ```

3. **Have SMTP credentials ready** (for Magic Links):
   - Gmail: app password (not regular password)
   - Or: your mail server (host, port, user, pass)

4. **Optional: Get authenticator device ready** (for Passkeys testing):
   - Real device (YubiKey, Apple Face ID, Windows Hello)
   - Or: fido2-ctap2 simulator

---

## Commit Strategy

- After each major feature (Passkeys, Magic Links, each UI):
  - Commit with clear message: `feat: Implement Passkeys endpoints`
  - Run tests: `pytest tests/v2/test_v2_contract.py`
  - Push to main

- If session gets interrupted:
  - Git will preserve work
  - TIER_1_CONTINUATION.md documents exact stopping point
  - Fresh session can resume from last commit

---

## Expected Outcomes (End of Session 2)

- ✅ All 4 passwordless/email auth methods working (Passkeys + Magic Links)
- ✅ Tenant app displaying cases
- ✅ Admin app managing allowlists
- ✅ Swagger docs live at `/api/v2/docs`
- ✅ All tests passing
- ✅ Ready for Tier 1.5+ (frontend polish, deployment prep)

---

## Token Tracking

- **Session 1 used:** 120,000 / 200,000 (60%)
- **Session 2 budget:** ~120,000 (fresh session)
- **Estimated usage:** 60,000–80,000 for full Tier 1
- **Remaining for future:** ~40,000+ if needed

---

## If Stuck

- Check `TIER_1_CONTINUATION.md` — has code examples for all 4 features
- Auth tests: `pytest tests/v2/test_v2_contract.py -v`
- API playground: `curl http://127.0.0.1:8101/api/v2/...`
- Docker logs: `docker compose logs auth`
- Memory state stored in `.claude` directory

---

**System ready. Standing by for Session 2 start. 🚀**
