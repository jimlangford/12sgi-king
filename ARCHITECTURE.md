# ARCHITECTURE.md — govOS v2 additions

## govOS v2 Module Registry

Implemented v2 backend service scaffolds:

- Auth (`/services/auth`) — `/api/v2/auth/*`
- Tenant (`/services/tenant`) — `/api/v2/cases*`
- Documents (`/services/documents`) — `/api/v2/documents*`
- Storage (`/services/storage`) — `/api/v2/storage/objects*`
- AI (`/services/ai`) — `/api/v2/ai/assist`
- Health gateway (`/services/health`) — `/api/v1/*` probes + surface aggregation

Frontend integration scaffolds:

- govOS (`/apps/govos/public`)
- Tenant (`/apps/tenant/public`)
- Admin (`/apps/admin/public`)
- Civic Signal (`/apps/civic-signal/public`)

## Contract and integration

- Canonical contract: `/home/runner/work/12sgi-king/12sgi-king/docs/api/v2-api-contract.yaml`
- Integration guide: `/home/runner/work/12sgi-king/12sgi-king/docs/GOVOS_V2_LOCAL_DEV.md`

## Module guidance

- Every service exposes `/api/v2/live`, `/api/v2/ready`, and `/api/v2/health`.
- Health gateway checks v2 readiness via `SURFACES_LIST` + `SURFACES_HEALTH_PATH`.
- No internal hostnames or credentials should be hard-coded.
