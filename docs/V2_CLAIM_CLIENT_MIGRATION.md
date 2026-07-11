# V2 Strict-Claim Live Verification Readiness

Decision: **NO-GO for citizen accounts** until live caller verification is complete.

Status: code-side migration is hardened; proceed with monitored production-adoption verification only.

## INSPECTED

- `/home/runner/work/12sgi-king/12sgi-king/docs/V2_CLAIM_CLIENT_MIGRATION.md`
- `/home/runner/work/12sgi-king/12sgi-king/services/auth/app/main.py`
- `/home/runner/work/12sgi-king/12sgi-king/services/authz.py`
- `/home/runner/work/12sgi-king/12sgi-king/.github/workflows/deploy-v2-king-server.yml`
- `/home/runner/work/12sgi-king/12sgi-king/docs/DEPLOYMENT.md`
- `/home/runner/work/12sgi-king/12sgi-king/apps/govos/public/app.js`
- `/home/runner/work/12sgi-king/12sgi-king/apps/tenant/public/app.js`
- `/home/runner/work/12sgi-king/12sgi-king/apps/civic-signal/public/app.js`
- `/home/runner/work/12sgi-king/12sgi-king/king_public_src/index.html`
- `/home/runner/work/12sgi-king/12sgi-king/king_public_src/Gpu.dc.html`
- `/home/runner/work/12sgi-king/12sgi-king/services/{ai,documents,tenant,storage,gpu_router}/app/main.py`
- `/home/runner/work/12sgi-king/12sgi-king/tests/v2/test_v2_client_migration.py`
- `/home/runner/work/12sgi-king/12sgi-king/tests/v2/test_v2_hardening.py`
- `/home/runner/work/12sgi-king/12sgi-king/tests/v2/test_v2_integration_stack.py`
- `/home/runner/work/12sgi-king/12sgi-king/docs/api/v2-api-contract.yaml`

## VERIFICATION TRACKER

| Caller name | Source path | Owner | Environment | Target service and endpoint | Expected role | Expected scopes | Expected tenant behavior | Token issuer and audience | Verification method | Current status | Rollback action | Evidence location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| govOS scaffold session creator | `/home/runner/work/12sgi-king/12sgi-king/apps/govos/public/app.js` | govOS frontend | local + king-server-private | Auth `POST /api/v2/auth/session` | Municipality/Partner/Resident/Owner/Service | role-allowlisted only | tenant claim required except Owner/Service | `AUTH_ISSUER` / `AUTH_AUDIENCE` | create session + inspect claims + auth audit review | unverified | rollback frontend commit only; keep strict claims | deploy log + auth_audit + test evidence |
| govOS scaffold case/doc/ai callers | `/home/runner/work/12sgi-king/12sgi-king/apps/govos/public/app.js` | govOS frontend | local + king-server-private | Tenant/Documents/AI endpoints | token role | `tenant:write`, `documents:write`, `ai:assist` | claim-derived tenant only | `AUTH_ISSUER` / `AUTH_AUDIENCE` | per-endpoint request replay with request-id audit correlation | unverified | rollback frontend commit only; keep strict claims | endpoint logs + auth_audit + case/doc records |
| Tenant scaffold session creator | `/home/runner/work/12sgi-king/12sgi-king/apps/tenant/public/app.js` | tenant frontend | local + king-server-private | Auth `POST /api/v2/auth/session` | Resident/Partner/Municipality | role-allowlisted only | tenant claim required | `AUTH_ISSUER` / `AUTH_AUDIENCE` | session mint + scope/tenant checks | unverified | rollback frontend commit only; keep strict claims | deploy evidence + auth_audit |
| Tenant scaffold tenant/ai callers | `/home/runner/work/12sgi-king/12sgi-king/apps/tenant/public/app.js` | tenant frontend | local + king-server-private | Tenant `GET /api/v2/cases`, AI `POST /api/v2/ai/assist` | Resident/Partner/Municipality | `tenant:read`, `ai:assist` | no cross-tenant access | `AUTH_ISSUER` / `AUTH_AUDIENCE` | tenant mismatch probes + denied-path audit checks | unverified | rollback frontend commit only; keep strict claims | auth_audit + request-id traces |
| Civic Signal scaffold session creator | `/home/runner/work/12sgi-king/12sgi-king/apps/civic-signal/public/app.js` | civic signal frontend | local + king-server-private | Auth `POST /api/v2/auth/session` | Partner | `tenant:read` | tenant claim required | `AUTH_ISSUER` / `AUTH_AUDIENCE` | session mint + role/scope validation | unverified | rollback frontend commit only; keep strict claims | auth_audit + deploy evidence |
| Civic Signal tenant metrics caller | `/home/runner/work/12sgi-king/12sgi-king/apps/civic-signal/public/app.js` | civic signal frontend | local + king-server-private | Tenant `GET /api/v2/cases` | Partner | `tenant:read` | claim-derived tenant only | `AUTH_ISSUER` / `AUTH_AUDIENCE` | case list probe + tenant mismatch rejection | unverified | rollback frontend commit only; keep strict claims | auth_audit + request-id traces |
| Naga owner console OAuth | `/home/runner/work/12sgi-king/12sgi-king/king_public_src/index.html` | owner console | king-server-private + public owner entrypoint | Auth `GET /api/v2/auth/github`, `GET /api/v2/auth/google` | Owner | Owner defaults including `ops:owner` | owner tenant optional | `AUTH_ISSUER` / `AUTH_AUDIENCE` | owner sign-in run with audit event review | unverified | rollback console commit only; keep strict claims | auth_audit + owner console screenshots |
| Naga GPU Brain panel | `/home/runner/work/12sgi-king/12sgi-king/king_public_src/Gpu.dc.html` | owner console GPU panel | king-server-private | GPU `GET /api/v2/gpu/queue`, `/gpu/events`, `/gpu/usage` | Owner | `gpu:read` (+owner override audit) | owner override only on explicit paths | `AUTH_ISSUER` / `AUTH_AUDIENCE` | owner/non-owner comparison with override audit events | unverified | rollback panel commit only; keep strict claims | gpu events + auth_audit |
| AI service -> GPU router | `/home/runner/work/12sgi-king/12sgi-king/services/ai/app/main.py` | AI service | local + king-server-private | GPU `POST /api/v2/gpu/infer` | inherited caller role | `gpu:infer` | claim + resource tenant enforcement | `AUTH_ISSUER` / `AUTH_AUDIENCE` | integration flow and denied-path replay | unverified | rollback AI service code only; keep strict claims | integration test logs + auth_audit |
| AI service -> Tenant service | `/home/runner/work/12sgi-king/12sgi-king/services/ai/app/main.py` | AI service | local + king-server-private | Tenant `GET /api/v2/cases/{case_id}` | inherited caller role | `tenant:read` | resource tenant match required | `AUTH_ISSUER` / `AUTH_AUDIENCE` | cross-tenant negative test + audit checks | unverified | rollback AI service code only; keep strict claims | integration logs + auth_audit |
| Documents service -> Tenant service | `/home/runner/work/12sgi-king/12sgi-king/services/documents/app/main.py` | Documents service | local + king-server-private | Tenant `GET /api/v2/cases/{case_id}` | inherited caller role | `tenant:read` | resource tenant match required | `AUTH_ISSUER` / `AUTH_AUDIENCE` | document flow with cross-tenant denial checks | unverified | rollback documents service code only; keep strict claims | integration logs + auth_audit |
| V2 services -> Auth introspection | `/home/runner/work/12sgi-king/12sgi-king/services/{tenant,documents,storage,ai,gpu_router}/app/main.py` | service platform | local + king-server-private | Auth `POST /api/v2/auth/introspect` | Service trust boundary | `auth:introspect` service trust | introspection claim normalization before access | `AUTH_ISSUER` / `AUTH_AUDIENCE` | service-token validation + wrong issuer/audience tests | verified (test) | rollback service caller code only; do not loosen auth policy | `tests/v2/test_v2_hardening.py` + `tests/v2/test_v2_integration_stack.py` |
| V2 test fixtures | `/home/runner/work/12sgi-king/12sgi-king/tests/v2/test_v2_integration_stack.py` | engineering | CI/local | auth/tenant/documents/storage/ai/gpu test calls | Owner/Municipality/Resident/Service | explicit per test | explicit mismatch and cross-tenant denial tests | `AUTH_ISSUER` / `AUTH_AUDIENCE` | full V2 suite execution | verified (test) | rollback test change only | CI logs + local unittest logs |

## DIAGNOSTIC DESIGN

Endpoint: `POST /api/v2/auth/diagnostics/claims`

Control and safety:

- disabled by default unless `AUTH_VERIFICATION_DIAGNOSTICS_ENABLED=true`
- owner-authenticated only (requires valid Owner bearer session)
- returns no bearer token, no signature, no secret, no private document content
- uses request-id correlation (`X-Request-ID` accepted, generated if missing)
- emits `auth_audit` event `diagnostic_claim_snapshot` with `audit_event_id`

Response fields:

- authenticated subject identifier as redacted hash (`sha256:*`)
- role
- tenant identifier as redacted hash (`sha256:*`)
- accepted scopes
- issuer
- audience
- expiry time
- authorization decision (`accepted` or `denied`)
- audit event identifier
- request identifier

Operational requirement:

- temporary diagnostic use only for verification windows
- remove/disable after caller verification closes

## AUDIT COVERAGE

Structured `auth_audit` coverage requirement matrix:

| Required verification event | Expected event type / reason | Coverage status | Test reference |
|---|---|---|---|
| successful authorization | diagnostic `authorization_decision=accepted` + normal endpoint success paths | partial (new diagnostic + integration success) | `tests/v2/test_v2_client_migration.py`, `tests/v2/test_v2_integration_stack.py` |
| denied access | `denied_access` (`missing_bearer`, `missing_scope`, etc.) | covered | `tests/v2/test_gpu_router_hardening.py` |
| missing claims | `legacy_claim_pattern_rejected` reason `missing_required_claims` | covered | `tests/v2/test_v2_client_migration.py` |
| legacy claim rejection | `legacy_claim_pattern_rejected` | covered | `tests/v2/test_v2_client_migration.py` |
| tenant mismatch | `tenant_mismatch` | covered | `tests/v2/test_v2_integration_stack.py` |
| undefined scope | `legacy_claim_pattern_rejected` reason `undefined_scopes` | covered | `tests/v2/test_v2_client_migration.py` |
| wildcard scope rejection | `wildcard_scope_blocked` / `legacy_claim_pattern_rejected` | covered | `tests/v2/test_v2_client_migration.py` |
| expired token | `expired_token` | covered | `tests/v2/test_v2_hardening.py` |
| wrong issuer | `denied_access` reason `wrong_issuer` | covered | `tests/v2/test_v2_hardening.py` |
| wrong audience | `denied_access` reason `wrong_audience` | covered | `tests/v2/test_v2_hardening.py` |
| owner override | `owner_override` | covered | `tests/v2/test_v2_client_migration.py`, `tests/v2/test_gpu_router_hardening.py` |
| service authentication failure | `service_auth_failure` | covered (unit path + runtime guard) | `services/authz.py`, `tests/v2/test_v2_hardening.py` |

Correlation rule:

- request IDs must be carried in verification probes and captured in audit evidence
- bearer tokens must never appear in logs or evidence bundles

## CUTOVER PROCEDURE (MONITORED, STRICT CLAIMS)

1. **Pre-cutover backup and evidence capture**
   - capture latest deploy evidence and rollback target commit from private deploy logs
   - capture current auth_audit baselines, denied counts, and owner override baseline
   - capture queue/workboard state and health metadata snapshots
2. **Enable strict claims in live V2 environment**
   - strict claims remain fail-closed; do not enable broad compatibility mode
   - optionally enable diagnostics with explicit owner approval and time-boxed window
3. **Verify callers one-by-one**
   - execute each tracker row in production-like order
   - record result + request-id + evidence path per caller
4. **Watch audit events continuously**
   - monitor denied_access spikes, tenant_mismatch, wrong_issuer/audience, service_auth_failure
   - triage false denials immediately with caller owner
5. **Validate tenant isolation continuously**
   - run cross-tenant read/write negative probes for each active caller class
   - confirm no cross-tenant success path exists
6. **Rollback without weakening policy**
   - rollback only caller/application revisions if needed
   - do not loosen claim checks, do not enable wildcard compatibility, do not disable tenant enforcement
7. **Retire diagnostics after verification**
   - set `AUTH_VERIFICATION_DIAGNOSTICS_ENABLED` back to false
   - retain audit evidence bundle and tracker status archive

No broad compatibility mode is permitted.

## ACCEPTANCE CRITERIA

Citizen-account design becomes **GO** only when all are true:

- every active production caller is verified in the tracker
- no active caller depends on weak or missing claims
- no wildcard scope is enabled without approved documentation
- owner overrides occur only on expected owner paths
- service tokens use approved scopes and short lifetimes
- no cross-tenant read or write succeeds
- audit evidence is complete and request-id correlated
- rollback is rehearsed or validated
- V2 dry-run and controlled deployment gates pass

Until then, status remains **NO-GO**.

## BLOCKED CALLERS

- none retired yet
- all `unverified` callers are operationally blocked from citizen-account GO until evidence is complete

## RISKS STILL OPEN

- production caller-by-caller verification evidence is incomplete
- temporary diagnostic enablement requires strict time-boxing discipline
- owner override paths require live confirmation that events appear only where expected
- service-to-service token lifetime enforcement in production must be re-verified during cutover window

## FINAL LIVE-VERIFICATION READINESS

**NO-GO**
