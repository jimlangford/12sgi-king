# AI services

Purpose

Tenant assistant guidance API for govOS v2.

Owner

- AI engineering

API

- `/api/v2/live`
- `/api/v2/ready`
- `/api/v2/health`
- `/api/v2/ai/assist`

Run locally

```bash
uvicorn app.main:app --app-dir services/ai --host 0.0.0.0 --port 8105
```

Notes

- Local response is deterministic placeholder guidance for frontend integration.
