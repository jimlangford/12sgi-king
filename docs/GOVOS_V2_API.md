# govOS v2 API Contract

This document defines the shared v2 contract for backend and frontend integration.

- Version: `2.0.0`
- Base path: `/api/v2`
- Canonical spec: `/home/runner/work/12sgi-king/12sgi-king/docs/api/v2-api-contract.yaml`
- Error format:

```json
{
  "error": {
    "code": "resource_not_found",
    "message": "Case was not found",
    "details": {}
  }
}
```

## Service boundaries

- Auth service: session issuing and JWKS (`/api/v2/auth/*`)
- Tenant service: case model CRUD (`/api/v2/cases*`)
- Documents service: generation metadata (`/api/v2/documents*`)
- Storage service: object metadata (`/api/v2/storage/objects*`)
- AI service: tenant assistant guidance (`/api/v2/ai/assist`)

## Frontend integration targets

- govOS app: auth + cases + documents + ai
- tenant app: cases + ai + documents
- admin app: health + auth + storage + tenant summaries
- civic-signal app: read-only health and sample case metrics

## Environment wiring

Frontends use per-service environment variables:

- `AUTH_SERVICE_URL`
- `TENANT_SERVICE_URL`
- `DOCUMENTS_SERVICE_URL`
- `STORAGE_SERVICE_URL`
- `AI_SERVICE_URL`

Health service can monitor v2 readiness with:

- `SURFACES_LIST="auth=localhost:8101,tenant=localhost:8102,documents=localhost:8103,storage=localhost:8104,ai=localhost:8105"`
- `SURFACES_HEALTH_PATH="/api/v2/ready"`
