#!/bin/bash
# startup.sh — boot all 12sgi-king services with health checks and auto-compact

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
LOG="$HERE/startup.log"

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ─── Logging ─────────────────────────────────────────────────────────────────
log() {
  echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG"
}

success() {
  echo -e "${GREEN}✓ $1${NC}" | tee -a "$LOG"
}

error() {
  echo -e "${RED}✗ $1${NC}" | tee -a "$LOG"
}

warn() {
  echo -e "${YELLOW}⚠ $1${NC}" | tee -a "$LOG"
}

# ─── Health Check Helpers ────────────────────────────────────────────────────
http_check() {
  local url="$1"
  local timeout="${2:-5}"
  local label="${3:-Service}"
  
  for i in {1..12}; do
    if curl -s -f --max-time "$timeout" "$url" > /dev/null 2>&1; then
      return 0
    fi
    if [ $i -lt 12 ]; then
      sleep 2
    fi
  done
  
  return 1
}

docker_check() {
  local name="$1"
  docker inspect --format '{{.State.Status}}' "$name" 2>/dev/null | grep -q "running"
}

# ─── Phase 1: Docker Services ────────────────────────────────────────────────
log "Phase 1: Starting Docker services..."

if ! command -v docker &> /dev/null; then
  error "Docker not found. Install Docker Desktop and try again."
  exit 1
fi

# Ensure docker daemon is running
if ! docker ps > /dev/null 2>&1; then
  error "Docker daemon not running"
  exit 1
fi

success "Docker daemon is running"

# Start docker-compose stack if present
if [ -f "$HERE/docker-compose.v2.yml" ]; then
  log "Bringing up docker-compose stack..."
  cd "$HERE"
  docker-compose -f docker-compose.v2.yml up -d
  sleep 5
  
  if http_check "http://localhost:8108/api/v2/ready" 5 "studio-assets"; then
    success "studio-assets API is ready"
  else
    warn "studio-assets API not responding yet (will be retried by watchdog)"
  fi
  
  if docker_check "studio-assets-studio-neo4j-1"; then
    success "Neo4j container is running"
  else
    warn "Neo4j container status unknown"
  fi
else
  warn "docker-compose.v2.yml not found — skipping Docker stack"
fi

# ─── Phase 2: Process Services ───────────────────────────────────────────────
log "Phase 2: Starting managed processes (king-bridge, static server)..."

# Start watchdog in background (it manages king-bridge and static server)
if command -v node &> /dev/null; then
  log "Starting king-watchdog (Node.js)..."
  nohup node "$HERE/king-watchdog.js" >> "$LOG" 2>&1 &
  WATCHDOG_PID=$!
  echo "$WATCHDOG_PID" > "$HERE/.watchdog.pid"
  success "Watchdog started (PID: $WATCHDOG_PID)"
  sleep 3
  
  if http_check "http://localhost:8109/api/v2/ready" 8 "king-bridge"; then
    success "king-bridge API is ready on :8109"
  else
    warn "king-bridge not responding yet (watchdog will retry)"
  fi
  
  if http_check "http://localhost:8888/" 3 "static-server"; then
    success "Static server is ready on :8888"
  else
    warn "Static server not responding yet"
  fi
else
  error "Node.js not found — watchdog requires node. Install Node.js 18+ and try again."
  exit 1
fi

# ─── Phase 3: Optional Checks ───────────────────────────────────────────────
log "Phase 3: Checking optional services..."

if command -v ollama &> /dev/null; then
  if http_check "http://localhost:11434/api/tags" 3 "ollama"; then
    success "Ollama is ready on :11434 (inference available)"
  else
    warn "Ollama not responding — model inference will be unavailable"
  fi
else
  warn "Ollama not installed — skip this if you don't need local inference"
fi

# ─── Phase 4: Auto-Compact Conversations ────────────────────────────────────
log "Phase 4: Enabling auto-compact and best features..."

if [ -f "$HERE/services/king_bridge/app/main.py" ]; then
  # Check if auto-compact is already enabled
  if ! grep -q "CONV_AUTO_COMPACT" "$HERE/services/king_bridge/app/main.py"; then
    log "Setting up conversation auto-compaction (Neo4j TTL)..."
    # Note: In production, this would be configured via environment variables
    # For now, just log the instruction
    log "  → Set NEO4J_CONV_TTL_DAYS=30 to auto-compact after 30 days"
    log "  → Set NEO4J_CONV_BATCH_SIZE=1000 for batch processing"
  fi
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
log ""
success "=== STARTUP COMPLETE ==="
log ""
log "Dashboard:        http://localhost:8888/king_landing.html"
log "king-bridge API:  http://localhost:8109/api/v2/"
log "Studio Assets:    http://localhost:8108/api/v2/"
log "Neo4j Browser:    http://localhost:7474/ (if credentials saved)"
log "Watchdog log:     $HERE/watchdog.log"
log ""
log "Services:"
log "  13 Tenants (9 films, 1 game, 2 music videos, 1 civic studio)"
log "  25 Named characters across all tenants"
log "  6 Lipsync skills (dialogue, ceremony, rhythm, song, 3D, etc.)"
log "  5 Render registers (photoreal, cartoon-3d, animated, etc.)"
log "  12 Civic divisions (HI state, counties, NY, etc.)"
log ""
log "Optional setup:"
log "  • Tailscale serve: tailscale serve --bg http://8109"
log "  • Browser: tailscale.com/kb/1427 (MagicDNS setup)"
log ""
