# govOS v2 Closure Plan — Session 2 Continuation Guide

**Session 1 Status:** TIER 0 complete (5.75 hrs billed)  
**Session 2 Target:** TIER 1 revised (Passkeys + Magic Links + Frontend UIs + Swagger)  
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

## GitHub + Google OAuth (Already Done ✅)

Both fully implemented in `services/auth/app/main.py`:
- ✅ GitHub OAuth flow working
- ✅ Google OAuth flow working
- ✅ Both in docker-compose.v2.yml
- ✅ Both in .env.v2 with placeholders

**To activate:** Fill in GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET in `.env.v2` and restart auth container.

---

## What's Next (Session 2) — TIER 1 (REVISED)

**SKIP:** Apple OAuth + Microsoft OAuth  
**FOCUS:** Passkeys → Magic Links → Frontend UIs → Swagger Docs

### 1.3: Passkeys/WebAuthn (Est. 12 hrs)

**Framework:** `py_webauthn` (already in services/auth/app/passkeys.py)

**Endpoints to add:**
- `POST /api/v2/auth/passkey/register/begin` → challenge
- `POST /api/v2/auth/passkey/register/complete` → store credential
- `POST /api/v2/auth/passkey/signin/begin` → challenge
- `POST /api/v2/auth/passkey/signin/complete` → issue JWT

**Database Schema:**
```sql
CREATE TABLE passkey_users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE passkey_credentials (
    credential_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    public_key TEXT NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    transports TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    FOREIGN KEY(user_id) REFERENCES passkey_users(user_id)
);

CREATE TABLE passkey_challenges (
    user_id TEXT NOT NULL,
    challenge TEXT NOT NULL,
    type TEXT,  -- registration or signin
    created_at TEXT NOT NULL
);
```

**Integration in main.py:**
```python
from services.auth.app.passkeys import (
    passkey_register_begin, passkey_register_complete,
    passkey_signin_begin, passkey_signin_complete
)

@app.post(f"{API_PREFIX}/auth/passkey/register/begin")
def register_passkey_begin(req: PasskeyRegisterBeginRequest):
    return passkey_register_begin(req)

@app.post(f"{API_PREFIX}/auth/passkey/register/complete")
def register_passkey_complete(req: PasskeyRegisterCompleteRequest):
    return passkey_register_complete(req)

@app.post(f"{API_PREFIX}/auth/passkey/signin/begin")
def signin_passkey_begin(req: PasskeySigninBeginRequest):
    return passkey_signin_begin(req)

@app.post(f"{API_PREFIX}/auth/passkey/signin/complete")
def signin_passkey_complete(req: PasskeySigninCompleteRequest):
    token, _ = _issue_and_store_session(
        subject=f"passkey:{req.user_id}",
        provider="passkey",
        email=response.email,
        tenant_id="",
        role="Owner",
        scopes=_default_scopes("Owner"),
        ttl_seconds=8 * 3600
    )
    return AuthSessionResponse(...)
```

---

### 1.4: Magic Links (Est. 8 hrs)

**Endpoints:**
- `POST /api/v2/auth/magiclink/request` → send email with link
- `GET /api/v2/auth/magiclink/claim?token=...&email=...` → verify link, issue JWT

**Database Schema:**
```sql
CREATE TABLE magic_link_tokens (
    token TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
```

**Implementation:**
```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@12sgi.com")
OWNER_MAGIC_EMAILS = _csv_env_set("OWNER_MAGIC_EMAILS")

@app.post(f"{API_PREFIX}/auth/magiclink/request")
def magiclink_request(email: str):
    if not SMTP_HOST or not SMTP_USER:
        raise HTTPException(status_code=501, detail="Magic links not configured")
    
    if email.casefold() not in OWNER_MAGIC_EMAILS:
        return {"status": "check_email"}  # Don't reveal which emails are valid
    
    token = secrets.token_urlsafe(32)
    expires_at = _now_utc() + timedelta(minutes=15)
    
    with _db() as conn:
        conn.execute(
            "INSERT INTO magic_link_tokens (token, email, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, email, _now_utc().isoformat(), expires_at.isoformat())
        )
        conn.commit()
    
    # Send email
    claim_url = f"{AUTH_PUBLIC_URL.rstrip('/')}{API_PREFIX}/auth/magiclink/claim?token={token}&email={urllib.parse.quote(email)}"
    subject = "Your govOS Sign-In Link"
    body = f"Click here to sign in: {claim_url}\n\nThis link expires in 15 minutes."
    
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
    except Exception as exc:
        _log.error(f"Failed to send magic link email: {exc}")
        raise HTTPException(status_code=503, detail="Could not send email")
    
    return {"status": "check_email"}

@app.get(f"{API_PREFIX}/auth/magiclink/claim")
def magiclink_claim(token: str, email: str):
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM magic_link_tokens WHERE token = ? AND email = ?",
            (token, email)
        ).fetchone()
        
        if not row:
            return _error_page("Magic link not found or already used")
        
        if datetime.fromisoformat(row["expires_at"]) < _now_utc():
            return _error_page("Magic link expired")
        
        # Delete token (one-time use)
        conn.execute("DELETE FROM magic_link_tokens WHERE token = ?", (token,))
        conn.commit()
    
    # Issue JWT
    token, _ = _issue_and_store_session(
        subject=f"magiclink:{email}",
        provider="magic_link",
        email=email,
        tenant_id="",
        role="Owner",
        scopes=_default_scopes("Owner"),
        ttl_seconds=8 * 3600
    )
    
    redirect_url = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/#token={urllib.parse.quote(token, safe='')}"
    return RedirectResponse(url=redirect_url)
```

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

### 1.5: Tenant App UI (Est. 12 hrs)

**React components:**
- `<CaseList />` — GET `/api/v2/cases`, display table
- `<CaseDetail id={caseId} />` — GET `/api/v2/cases/{id}`, show metadata
- `<NewCaseForm />` — POST `/api/v2/cases`, modal form

**Example (React):**
```jsx
function CaseList() {
  const [cases, setCases] = useState([]);
  const token = localStorage.getItem('king_ownerToken');

  useEffect(() => {
    fetch('http://127.0.0.1:8102/api/v2/cases', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => setCases(data.cases))
      .catch(err => console.error(err));
  }, [token]);

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Cases</h1>
      <table className="w-full border">
        <thead>
          <tr><th>ID</th><th>Title</th><th>Status</th><th>Created</th></tr>
        </thead>
        <tbody>
          {cases.map(c => (
            <tr key={c.id} className="border-t">
              <td>{c.id.slice(0, 8)}...</td>
              <td>{c.title}</td>
              <td>{c.status}</td>
              <td>{new Date(c.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

### 1.6: Admin App UI (Est. 12 hrs)

**React components:**
- `<AllowlistManager />` — edit OWNER_GITHUB_LOGINS, OWNER_GOOGLE_EMAILS
- `<ServiceHealth />` — GET `/api/v1/health`, display service status
- `<AuditLog />` — auth events

**Admin backend endpoints (new):**
```python
@app.patch(f"{API_PREFIX}/auth/owner/allowlist")
def update_allowlist(payload: dict, authorization: str | None = Header(default=None)):
    # Verify owner role
    claims = require_claims(..., required_scopes={"ops:owner"})
    
    # Update env or config file
    # Restart auth service? Or reload at runtime?
    return {"status": "updated"}
```

---

### 1.7: Swagger Docs (Est. 2 hrs)

**Add to all endpoints in main.py:**
```python
@app.get(f"{API_PREFIX}/auth/github")
def oauth_github_start():
    """Redirect to GitHub OAuth authorization page.
    
    Returns a redirect to GitHub's authorization endpoint.
    User authenticates and is redirected back to /api/v2/auth/github/callback.
    """
    ...

@app.post(f"{API_PREFIX}/auth/session", response_model=AuthSessionResponse)
def create_session(payload: AuthSessionRequest):
    """Create an authenticated session.
    
    Issues a JWT token for the given provider + subject.
    
    Args:
        provider: Authentication provider (github, google, passkey, magic_link)
        subject: User identifier (e.g., github:jimlangford, google:sub123)
        email: User email address
        role: User role (Owner, Resident, Service) — default Resident
    
    Returns:
        AuthSessionResponse with access_token, claims, user info
    """
    ...
```

**FastAPI auto-generates:**
- `GET /api/v2/docs` → Swagger UI
- `GET /api/v2/openapi.json` → OpenAPI 3.0 spec

---

## Session 2 Execution Plan

**Billable:** ~46 hrs (Passkeys + Magic Links + 3 frontend tiers)

1. **Integrate Passkeys** (12 hrs)
   - Add tables to init_db()
   - Import passkeys module
   - Add endpoints to main.py
   - Test registration + signin flow

2. **Implement Magic Links** (8 hrs)
   - Add magic_link_tokens table
   - SMTP config + email sending
   - Token claim + JWT issuance
   - Test with real email

3. **Build Tenant App** (12 hrs)
   - React case list + detail + new case form
   - API integration
   - Tailwind styling

4. **Build Admin App** (12 hrs)
   - React allowlist manager + service health + audit log
   - Admin API endpoint (allowlist update)
   - Integration

5. **Add Swagger** (2 hrs)
   - Docstrings on all endpoints
   - FastAPI /docs auto-generation
   - Verify OpenAPI schema

---

## Git Status

**Last commit:** `f2361b6` (pushed to `jimlangford/12sgi-king@main`)

**Files ready for Tier 1:**
- `.env.v2` — SMTP config + Magic Links placeholders
- `services/auth/app/passkeys.py` — WebAuthn module (ready to integrate)
- `services/auth/app/main.py` — GitHub + Google patterns to follow

---

## Continuation Checklist

When starting Session 2:

- [ ] Pull latest: `git pull origin main`
- [ ] Verify auth service running: `curl http://127.0.0.1:8101/api/v2/health`
- [ ] Test existing GitHub + Google OAuth (just set credentials in .env.v2)
- [ ] Start with Tier 1.3 (Passkeys integration)
- [ ] Progress: 1.3 → 1.4 → 1.5 → 1.6 → 1.7

---

## What Works Now

- ✅ GitHub OAuth (full flow)
- ✅ Google OAuth (full flow)
- ✅ CI/CD pipeline enforced on PRs
- ✅ Service registry complete
- ✅ OAuth setup streamlined
- ✅ Passkeys module ready to integrate

## What's Needed for Session 2

- SMTP credentials (Gmail or mail server)
- React dev environment (or defer frontend to later)
- Authenticator device for testing passkeys (optional; can test with fido2-ctap2)

---

## Files to Review Before Session 2

1. `docs/SERVICE_REGISTRY.md` — all 10 services
2. `.github/OAUTH_CHECKLIST.md` — OAuth setup
3. `services/auth/app/main.py` — GitHub + Google patterns
4. `services/auth/app/passkeys.py` — WebAuthn module
5. `docker-compose.v2.yml` — service wiring

---

**Total Project Progress:** 5.75 / 88 hrs = **6.5%**  
**Next milestone:** Tier 1 complete = 51.75 / 88 hrs = **59%**

Ready for fresh session. 🚀
