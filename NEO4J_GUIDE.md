# 12sgi-King Neo4j Setup & Verification Guide

## Overview

Neo4j is the **QUAD OS brain** — a graph database holding ~14,300 nodes representing the entire system's knowledge graph. It's used by 14+ native tools and services for AI/GPU orchestration, workboard dispatch, and state management.

### Key Facts
- **Status**: ✅ Data SAFE and PRESERVED
- **Location**: Separate Docker compose (`docker-compose.neo4j.yml`)
- **Isolation**: Deliberately isolated from V2 app stack to prevent accidental wipes
- **Data**: External volumes `12sgi-king_v2-neo4j-data` + `12sgi-king_v2-neo4j-logs`
- **Ports**: 7474 (HTTP), 7687 (Bolt protocol)
- **Memory**: 640MB limit, 256MB reservation

---

## Architecture: Why Separate?

### Before (Problem)
```
docker-compose.v2.yml
├── auth, tenant, documents, storage, ai, gpu-router, health, king-bridge
└── neo4j ← could be wiped by `compose down -v`
```
**Issue**: `docker compose -f docker-compose.v2.yml down -v` would destroy the graph database.

### After (Solution)
```
docker-compose.v2.yml
├── auth, tenant, documents, storage, ai, gpu-router, health, king-bridge
│   └── reference NEO4J_HTTP env var → http://host.docker.internal:7474

docker-compose.neo4j.yml
└── neo4j (isolated, restart:unless-stopped, external volumes)
```
**Benefit**: V2 deploys never touch Neo4j. The brain persists independently.

---

## Verification & Startup

### Quick Check
```bash
python verify_neo4j.py
```
Output:
- ✓ Volumes found
- ✓ Container status
- ✓ HTTP endpoint (7474) responsive
- ✓ Bolt endpoint (7687) responsive

### Start Neo4j
```bash
# Start the standalone Neo4j stack
docker compose -f docker-compose.neo4j.yml up -d

# Or just the container
docker start quados-neo4j

# Check status
docker compose -f docker-compose.neo4j.yml ps
```

### View Logs
```bash
docker compose -f docker-compose.neo4j.yml logs -f neo4j
```

### Stop (Safely)
```bash
# Stop but preserve data
docker compose -f docker-compose.neo4j.yml down

# NEVER use -v flag (that destroys volumes!)
# ❌ docker compose -f docker-compose.neo4j.yml down -v
```

---

## Data Safety

### Volumes (External, Persistent)
- `12sgi-king_v2-neo4j-data`: Graph database files (~14,300 nodes)
- `12sgi-king_v2-neo4j-logs`: Neo4j operation logs

These are **NOT** managed by the compose file. They survive:
- Container restart ✓
- Container removal ✓
- Compose down ✓
- Docker restart ✓
- Windows restart ✓

### Backup Strategy
To backup the Neo4j graph:
```bash
# Create snapshot of the data volume
docker run --rm -v 12sgi-king_v2-neo4j-data:/data -v C:/backup:/backup alpine tar czf /backup/neo4j-backup.tar.gz -C /data .

# Restore from backup
docker run --rm -v 12sgi-king_v2-neo4j-data:/data -v C:/backup:/backup alpine tar xzf /backup/neo4j-backup.tar.gz -C /data
```

---

## V2 Services Integration

All V2 services access Neo4j via environment variables:

```yaml
NEO4J_HTTP: http://host.docker.internal:7474/db/neo4j/tx/commit
NEO4J_AURA_URI: ${NEO4J_AURA_URI:-}  # Optional: cloud fallback
NEO4J_AURA_USER: ${NEO4J_AURA_USER:-neo4j}
NEO4J_AURA_PASSWORD: ${NEO4J_AURA_PASSWORD:-}
NEO4J_AURA_ENABLED: ${NEO4J_AURA_ENABLED:-false}
```

### Services That Use Neo4j
- `auth` - Identity graph
- `tenant` - Multi-tenant relationships
- `documents` - Document indexing
- `storage` - File graph
- `ai` - AI model registry
- `gpu-router` - GPU workload state
- `health` - Fleet status graph
- `king-bridge` - Workboard→Ollama dispatch state
- `board-api` - Owner console queries
- `connector-runner` - Connector state
- `github-workflow-monitor` - Workflow state

### Fallback: Neo4j Aura (Cloud)
If local Neo4j is unavailable, services can fallback to Neo4j Aura (cloud):
```bash
# In .env.v2:
NEO4J_AURA_ENABLED=true
NEO4J_AURA_URI=neo4j+s://xxxx.databases.neo4j.io
NEO4J_AURA_USER=neo4j
NEO4J_AURA_PASSWORD=<password>
```

---

## Troubleshooting

### Neo4j Not Starting
```bash
# 1. Check logs
docker compose -f docker-compose.neo4j.yml logs neo4j

# 2. Verify volumes
docker volume ls | grep neo4j

# 3. Check memory
docker stats quados-neo4j

# 4. Inspect configuration
docker inspect quados-neo4j | grep -A 10 "Env"
```

### Ports Already in Use
```bash
# Find what's using 7474/7687
netstat -ano | findstr :7474
netstat -ano | findstr :7687

# Kill the process if needed
taskkill /PID <process_id> /F
```

### Docker Desktop Hanging
When Docker Desktop becomes unresponsive:
1. Close Docker: Docker icon → Exit
2. Wait 30 seconds
3. Reopen Docker Desktop
4. Run: `python verify_neo4j.py`

### Volume Corruption
If volumes become corrupted:
```bash
# Check volume mount point
docker volume inspect 12sgi-king_v2-neo4j-data

# Recreate volume (WARNING: data loss!)
docker volume rm 12sgi-king_v2-neo4j-data
docker volume create 12sgi-king_v2-neo4j-data

# Neo4j will reinitialize on next start
docker compose -f docker-compose.neo4j.yml up -d
```

---

## Configuration

### docker-compose.neo4j.yml
```yaml
neo4j:
  image: neo4j:5-community
  container_name: quados-neo4j
  environment:
    NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
    NEO4J_AUTH: none                           # No auth (local dev)
    NEO4J_server_default__listen__address: 0.0.0.0
    NEO4J_server_memory_pagecache_size: 256M
    NEO4J_server_memory_heap_initial__size: 256M
    NEO4J_server_memory_heap_max__size: 256M
  volumes:
    - v2-neo4j-data:/data      # Graph data
    - v2-neo4j-logs:/logs      # Operation logs
  ports:
    - 127.0.0.1:7474:7474      # HTTP API
    - 127.0.0.1:7687:7687      # Bolt protocol
  restart: unless-stopped
  mem_limit: 640m
  healthcheck:
    test: ["CMD-SHELL", "wget -q -O /dev/null http://localhost:7474 || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 30s
```

### Environment Variables (.env.v2)
```bash
# Local Neo4j (default)
NEO4J_HTTP=http://neo4j:7474/db/neo4j/tx/commit

# Fallback to cloud
NEO4J_AURA_ENABLED=false
NEO4J_AURA_URI=
NEO4J_AURA_USER=neo4j
NEO4J_AURA_PASSWORD=

# Memory sizing
NEO4J_HEAP_SIZE=256m              # Heap
NEO4J_PAGECACHE_SIZE=256m         # Cache
```

---

## Tools & Scripts

### verify_neo4j.py
Comprehensive Neo4j health check:
```bash
python verify_neo4j.py
```
Verifies:
- Volumes exist and are external
- Container is running/reachable
- HTTP endpoint (7474) responding
- Bolt endpoint (7687) open
- Reports: "✓ Neo4j ACCESSIBLE" or "✗ NOT ACCESSIBLE"

### Command Cheatsheet
```bash
# Start
docker compose -f docker-compose.neo4j.yml up -d

# Stop (safe)
docker compose -f docker-compose.neo4j.yml down

# Status
docker compose -f docker-compose.neo4j.yml ps

# Logs
docker compose -f docker-compose.neo4j.yml logs -f

# Remove container (volume persists)
docker rm quados-neo4j

# Access Neo4j browser
# http://127.0.0.1:7474   (in browser)
```

---

## Production Deployment

For production (beyond this king-server instance):

### Option 1: Neo4j Aura (Managed Cloud)
- Easiest: No ops burden
- Set `NEO4J_AURA_ENABLED=true` + credentials in `.env.v2`
- All V2 services automatically fallback to cloud

### Option 2: Docker on Separate Host
- Run `docker-compose.neo4j.yml` on a dedicated Neo4j server
- Point V2 services to: `NEO4J_HTTP=http://neo4j-host:7474/db/neo4j/tx/commit`

### Option 3: Neo4j Enterprise (Self-Managed)
- Use `neo4j:enterprise` image
- Add clustering, backup, high availability
- Setup 3-node cluster on separate machines

---

## Summary

✅ **Neo4j is production-ready**
- 14,300-node QUAD OS brain protected by isolated compose and external volumes
- Automatically started on `docker compose -f docker-compose.neo4j.yml up -d`
- V2 services access via NEO4J_HTTP environment variable
- Verified healthy via `verify_neo4j.py`

🔐 **Data is safe**: External volumes survive any container/Docker/OS restart

📋 **Integration**: Transparent to V2 app stack (no changes needed to deploy)

---

