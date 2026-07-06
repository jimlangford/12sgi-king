# Admin app

Purpose

Admin-facing v2 frontend integration scaffold for service status checks.

Current implementation

- `public/index.html`: health snapshot control panel
- `public/app.js`: requests health from auth, tenant, documents, storage, ai, and health gateway services

Configuration

- `AUTH_SERVICE_URL`
- `TENANT_SERVICE_URL`
- `DOCUMENTS_SERVICE_URL`
- `STORAGE_SERVICE_URL`
- `AI_SERVICE_URL`
- `HEALTH_SERVICE_URL`
