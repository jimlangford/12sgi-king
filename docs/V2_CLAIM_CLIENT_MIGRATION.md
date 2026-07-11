# V2 Claim-Client Migration Layer

Status: in-progress migration hardening (no citizen accounts, no production secret changes).

## 1) V2 caller inventory

| Caller name | Source file | Target endpoint(s) | Current auth method | Required role | Required scopes | Tenant context | Caller type |
|---|---|---|---|---|---|---|---|
| govOS scaffold session creator | `/home/runner/work/12sgi-king/12sgi-king/apps/govos/public/app.js` | `POST /api/v2/auth/session` | passkey -> bearer token | Municipality/Partner/Resident/Owner/Service | caller-specified (validated server-side) | token `tenant_id` claim | interactive |
| govOS scaffold case/doc/ai calls | `/home/runner/work/12sgi-king/12sgi-king/apps/govos/public/app.js` | `POST /api/v2/cases`, `POST /api/v2/documents/generate`, `POST /api/v2/ai/assist` | bearer token | by minted token role | `tenant:write`, `documents:write`, `ai:assist` | claim-derived tenant, payload tenant only business data | interactive |
| Tenant scaffold session creator | `/home/runner/work/12sgi-king/12sgi-king/apps/tenant/public/app.js` | `POST /api/v2/auth/session` | passkey -> bearer token | Resident/Partner/Municipality | scoped by role | token `tenant_id` claim | resident-facing |
| Tenant scaffold tenant/ai calls | `/home/runner/work/12sgi-king/12sgi-king/apps/tenant/public/app.js` | `GET /api/v2/cases`, `POST /api/v2/ai/assist` | bearer token | Resident/Partner/Municipality | `tenant:read`, `ai:assist` | claim-derived tenant | resident-facing |
| Civic Signal scaffold session creator | `/home/runner/work/12sgi-king/12sgi-king/apps/civic-signal/public/app.js` | `POST /api/v2/auth/session` | passkey -> bearer token | Partner | `tenant:read` | token `tenant_id` claim | interactive |
| Civic Signal tenant metrics caller | `/home/runner/work/12sgi-king/12sgi-king/apps/civic-signal/public/app.js` | `GET /api/v2/cases` | bearer token | Partner | `tenant:read` | claim-derived tenant | interactive |
| Naga owner console OAuth | `/home/runner/work/12sgi-king/12sgi-king/king_public_src/index.html` | `GET /api/v2/auth/github`, `GET /api/v2/auth/google` | OAuth redirect + owner bearer in `king.ownerToken` | Owner | owner defaults | owner token (tenant optional) | owner-only |
| Naga GPU Brain panel | `/home/runner/work/12sgi-king/12sgi-king/king_public_src/Gpu.dc.html` | `GET /api/v2/gpu/queue`, `GET /api/v2/gpu/events`, `GET /api/v2/health` | owner bearer token | Owner | `gpu:read` (+owner override paths audited) | optional owner override tenant filter | owner-only |
| AI service -> GPU router | `/home/runner/work/12sgi-king/12sgi-king/services/ai/app/main.py` | `POST /api/v2/gpu/infer` | forwarded bearer token | inherits caller role | `gpu:infer` | tenant from case lookup + claims enforcement | service-to-service |
| AI service -> Tenant service | `/home/runner/work/12sgi-king/12sgi-king/services/ai/app/main.py` | `GET /api/v2/cases/{case_id}` | forwarded bearer token | inherits caller role | `tenant:read` | resource tenant checked vs claims | service-to-service |
| Documents service -> Tenant service | `/home/runner/work/12sgi-king/12sgi-king/services/documents/app/main.py` | `GET /api/v2/cases/{case_id}` | forwarded bearer token | inherits caller role | `tenant:read` | resource tenant checked vs claims | service-to-service |
| V2 services -> Auth introspection | `/home/runner/work/12sgi-king/12sgi-king/services/{tenant,documents,storage,ai,gpu_router}/app/main.py` | `POST /api/v2/auth/introspect` | internal `X-Service-Token` + caller bearer token | Service trust boundary | `auth:introspect` (service trust) | claims normalized before endpoint access | service-to-service |
| Integration/hardening fixtures | `/home/runner/work/12sgi-king/12sgi-king/tests/v2/test_v2_integration_stack.py` | v2 auth/tenant/documents/storage/ai/gpu endpoints | generated bearer tokens via `/auth/session` | Owner/Municipality/Resident/Service coverage | explicit per test | explicit tenant claim and mismatch tests | test fixture |
| Local dev API examples | `/home/runner/work/12sgi-king/12sgi-king/docs/GOVOS_V2_LOCAL_DEV.md` | v2 auth + tenant/documents/storage/ai/gpu examples | documented bearer token flow | role-specific | explicit role scopes in examples | tenant from token claims | local helper |

## 2) Canonical claim matrix (fail-closed)

| Role | Allowed scopes | Prohibited scopes | Tenant requirement | Cross-tenant behavior | Token lifetime expectation | Audit expectation |
|---|---|---|---|---|---|---|
| Owner | `tenant:*` mapped as `tenant:read`,`tenant:write`; `documents:read`,`documents:write`; `storage:read`,`storage:write`; `ai:assist`; `gpu:infer`,`gpu:read`; `ops:owner` | undefined scopes, wildcard scopes unless explicitly allowlisted | tenant optional | allowed only via explicit owner override path; must emit `owner_override` audit events | short interactive (default <= 8h) | log owner overrides and all denied attempts |
| Municipality | `tenant:read`,`tenant:write`,`documents:read`,`documents:write`,`storage:read`,`storage:write`,`ai:assist`,`gpu:infer`,`gpu:read` | `ops:owner`, undefined scopes, wildcard scopes | required | denied unless owner override role | short interactive (default <= 8h) | log tenant mismatch, missing scope, denied access |
| Partner | `tenant:read`,`documents:read`,`documents:write`,`storage:read`,`storage:write`,`ai:assist`,`gpu:infer` | `tenant:write`,`gpu:read`,`ops:owner`, undefined scopes, wildcard scopes | required | denied | short interactive (default <= 8h) | log denied access and mismatch |
| Resident | `tenant:read`,`documents:read`,`storage:read`,`ai:assist`,`gpu:infer` | all write scopes except explicit resident policy changes, `gpu:read`,`ops:owner`, undefined scopes, wildcard scopes | required | denied | short interactive (default <= 8h) | log denied access and role escalation attempts |
| Service | explicit allowlisted machine scopes only (`auth:introspect`, tenant/documents/storage/ai/gpu machine scopes as configured) | any non-allowlisted scope, wildcard scopes unless explicitly allowlisted | optional unless machine workflow requires tenant claim | denied by default; never use compatibility mode for cross-tenant | short-lived machine token (default <= 1h, no long-lived static tokens) | log service auth failures, issuer/audience failures, and revoked/expired usage |

Undefined role/scope combinations are rejected at session issuance and at claim-validation time.

## 3) Service-token governance

- Issuer: `AUTH_ISSUER` (auth service only).
- Audience: `AUTH_AUDIENCE` (default `govos-v2`), required and validated.
- Scope ownership: service scopes must be explicitly allowlisted (`AUTH_SERVICE_ALLOWED_SCOPES`).
- Lifetime: short-lived only; `expires_in` bounded and required for active sessions.
- Rotation: rotate `AUTH_SIGNING_SECRET` and `INTERNAL_SERVICE_TOKEN` through deployment environment management; never in repo.
- Revocation: session row invalidation + signing secret rotation for broad invalidation.
- Emergency disable: block service trust by replacing `INTERNAL_SERVICE_TOKEN` and restarting affected services.
- Secret handling: never commit tokens or long-lived credentials; examples use placeholders only.
- Audit: service authentication failures and legacy-claim rejections must emit structured `auth_audit` events.

## 4) Migration safeguards

- Compatibility warnings: structured `legacy_claim_pattern_rejected` audit events for missing claims, invalid roles, wildcard scopes, and undefined scopes.
- Rejections are fail-closed for weak/legacy claim patterns.
- Temporary migration flag: not added (unnecessary); wildcard exceptions require explicit allowlist environment config and are audited.
- Removal condition: any temporary wildcard allowlist entry must be removed once all callers use concrete scopes; no open-ended compatibility mode.
- Cross-tenant guarantee: no compatibility path grants cross-tenant access.
