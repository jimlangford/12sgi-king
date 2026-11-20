# 12sgi-king System Setup & Claude Integration Guide

## Quick Start

### 1. Check System Status
```bash
python status_dashboard.py
```
Shows real-time status of all services and Claude integration readiness.

### 2. Start/Recover System
```bash
python startup_system.py
```
- Restarts Docker Desktop if needed
- Brings up the entire compose stack (V2 services + Neo4j)
- Waits for all services to pass health checks
- Takes 2-3 minutes on cold start

### 3. Health Check
```bash
python health_check.py
```
Validates:
- Docker daemon running
- Compose stack online
- Individual service health endpoints

## System Architecture

### Docker Compose Stack (docker-compose.v2.yml)
**Core V2 Services (auth, tenant, documents, storage, ai, gpu-router, health, king-bridge, board-api):**
- Multi-service FastAPI stack
- Shared Docker image built from services/Dockerfile
- Each service runs on unique port (8101-8109, 8799)
- All services depend on auth service
- Health checks on all services

**External Services:**
- neo4j: 7474 (HTTP), 7687 (Bolt)
- postgres (if needed): 5433

### Port Mapping
| Service | Port | Health Endpoint |
|---------|------|-----------------|
| auth | 8101 | /api/v2/ready |
| tenant | 8102 | /api/v2/ready |
| documents | 8103 | /api/v2/ready |
| storage | 8104 | /api/v2/ready |
| ai | 8105 | /api/v2/ready |
| health | 8106 | /api/v1/ready |
| gpu-router | 8107 | /api/v2/ready |
| king-bridge | 8109 | /api/v2/ready |
| board-api | 8799 | /health |

## Claude Integration

### What Claude Can Do
- **Build & Deploy**: Automated CI/CD runs V2 smoke tests, builds services, deploys to king-server
- **Monitor**: Health checks validate all endpoints
- **Debug**: Service logs via `docker compose logs <service>`
- **Manage**: Start/stop/restart services, update configs

### Health Check Indicators
- ✓ READY: Docker online, 4+ services responding
- ⚠ PARTIAL: Docker online, 2-3 services responding
- ✗ NOT READY: <2 services or Docker offline

## Common Tasks

### View All Service Logs
```bash
docker compose logs -f
```

### View Specific Service Log
```bash
docker compose logs -f king-bridge
```

### Restart a Service
```bash
docker compose restart auth
```

### Rebuild Images
```bash
docker compose build --no-cache
```

### Full System Restart
```bash
docker compose down -v
python startup_system.py
```

## Troubleshooting

### Docker Desktop Frozen/Unresponsive
1. Run: `python startup_system.py` (includes Docker restart logic)
2. If that fails, manually restart Docker Desktop and run script again

### Services Failing to Start
1. Check logs: `docker compose logs <service>`
2. Common causes:
   - Port conflicts: `netstat -ano | findstr :<port>`
   - Missing env vars: check `.env.v2` exists
   - Memory/disk: `docker system df`

### Services Not Responding on Ports
1. Verify running: `docker compose ps`
2. Check port binding: `docker inspect <container>`
3. Check service logs for startup errors

## Files

- `health_check.py` - System health validator
- `startup_system.py` - Automated startup with recovery
- `status_dashboard.py` - Real-time status monitor
- `.env.v2` - Private environment (secrets, config)
- `docker-compose.v2.yml` - Service definitions
- `services/Dockerfile` - Build image for all services

## CI/CD Pipeline

The workflow (deploy-v2-king-server.yml) automatically:
1. Runs V2 contract smoke tests
2. Validates private environment
3. Validates service files exist
4. Builds Docker images
5. Starts services via compose
6. Waits for readiness
7. Validates all health endpoints
8. Writes deployment log with SHA + timestamp

**Trigger:** Any push to `main` that touches services/, docker-compose.v2.yml, or workflow file.

---

**Claude is ready to help with deployment, debugging, and maintenance. Use `status_dashboard.py` to check readiness at any time.**
