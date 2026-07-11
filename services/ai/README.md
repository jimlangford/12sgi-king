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

- Assist events are persisted in SQLite (`AI_DB_PATH`, default `/tmp/govos_v2_ai.db`).
- Business endpoints require bearer auth sessions validated by auth introspection.
- Case references are validated against the tenant service.
- Business authorization uses claim-derived tenant scope (never client tenant overrides).
