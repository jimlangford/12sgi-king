# Storage service

Purpose

Object metadata service for uploads and generated artifacts in govOS v2.

Owner

- Platform / storage engineering

API

- `/api/v2/live`
- `/api/v2/ready`
- `/api/v2/health`
- `/api/v2/storage/objects`
- `/api/v2/storage/objects/{object_id}`

Run locally

```bash
uvicorn app.main:app --app-dir services/storage --host 0.0.0.0 --port 8104
```

Notes

- Local implementation registers objects in memory and returns placeholder download URLs.
