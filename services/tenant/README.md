# Tenant service

Purpose

Case management API for tenant workflows in govOS v2.

Owner

- Product engineering / tenant experience

API

- `/api/v2/live`
- `/api/v2/ready`
- `/api/v2/health`
- `/api/v2/cases`
- `/api/v2/cases/{case_id}`

Run locally

```bash
uvicorn app.main:app --app-dir services/tenant --host 0.0.0.0 --port 8102
```

Notes

- Uses in-memory case records for local integration bootstrap.
