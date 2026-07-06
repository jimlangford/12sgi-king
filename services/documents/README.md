# Documents service

Purpose

Template-based document generation metadata API for govOS v2.

Owner

- Document engineering

API

- `/api/v2/live`
- `/api/v2/ready`
- `/api/v2/health`
- `/api/v2/documents/generate`
- `/api/v2/documents/{document_id}`

Run locally

```bash
uvicorn app.main:app --app-dir services/documents --host 0.0.0.0 --port 8103
```

Notes

- Local implementation stores generated document metadata in memory.
