# govOS v2 Local Integration

This guide wires backend services, health checks, and frontend scaffolds for local v2 integration.

## 1) Start backend services

```bash
uvicorn app.main:app --app-dir services/auth --port 8101
uvicorn app.main:app --app-dir services/tenant --port 8102
uvicorn app.main:app --app-dir services/documents --port 8103
uvicorn app.main:app --app-dir services/storage --port 8104
uvicorn app.main:app --app-dir services/ai --port 8105
uvicorn app.main:app --app-dir services/health --port 8000
```

## 2) Configure health aggregation

Set environment variables for health service:

```bash
SURFACES_LIST="auth=localhost:8101,tenant=localhost:8102,documents=localhost:8103,storage=localhost:8104,ai=localhost:8105"
SURFACES_HEALTH_PATH="/api/v2/ready"
```

## 3) Load frontend scaffolds

Serve each app folder statically (example):

```bash
python -m http.server 4173 --directory apps/govos/public
python -m http.server 4174 --directory apps/tenant/public
python -m http.server 4175 --directory apps/admin/public
python -m http.server 4176 --directory apps/civic-signal/public
```

Defaults point to localhost service ports above. You can override with globals:

- `AUTH_SERVICE_URL`
- `TENANT_SERVICE_URL`
- `DOCUMENTS_SERVICE_URL`
- `STORAGE_SERVICE_URL`
- `AI_SERVICE_URL`
- `HEALTH_SERVICE_URL`

## 4) End-to-end checks

- Create auth session (govOS app)
- Create tenant case (govOS app)
- Generate document (govOS app)
- Ask AI guidance (govOS or tenant app)
- Check `/api/v1/health` from health service and verify all v2 services show ready
