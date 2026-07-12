# Auth service

Purpose

Authentication and authorization service for govOS v2 with passwordless-first provider flows.

Owner

- Security / Auth engineering

API

- `/api/v2/live`
- `/api/v2/ready`
- `/api/v2/health`
- `/api/v2/auth/session`
- `/api/v2/auth/github`
- `/api/v2/auth/github/callback`
- `/api/v2/auth/google`
- `/api/v2/auth/google/callback`
- `/api/v2/auth/renew`
- `/api/v2/auth/jwks`
- `/api/v2/auth/introspect` (internal service-to-service token verification)

Run locally

```bash
uvicorn app.main:app --app-dir services/auth --host 0.0.0.0 --port 8101
```

Notes

- Sessions are persisted in SQLite (`AUTH_DB_PATH`, default `/tmp/govos_v2_auth.db`).
- Service-to-service auth trust uses `INTERNAL_SERVICE_TOKEN`.
- Owner OAuth allow-lists trim whitespace and compare GitHub logins / Google e-mails case-insensitively.
- Session claims include `sub`, `tenant_id`, `role`, `scopes`, `exp`, `iss`, and `aud`.
- Supported roles: `Owner`, `Municipality`, `Partner`, `Resident`, `Service`.
- Do not commit secrets or real signing keys.
