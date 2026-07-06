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
- `/api/v2/auth/jwks`

Run locally

```bash
uvicorn app.main:app --app-dir services/auth --host 0.0.0.0 --port 8101
```

Notes

- Uses an in-memory session placeholder for local integration.
- Do not commit secrets or real signing keys.
