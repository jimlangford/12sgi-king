# 12sgi-king Error Recovery & Port Conflict Workaround
# ========================================================

## Issue: Port 8799 Binding Failure

**Symptom:**
```
Error response from daemon: ports are not available: exposing port TCP 127.0.0.1:8799 -> 127.0.0.1:0: 
listen tcp4 127.0.0.1:8799: bind: Only one usage of each socket address (protocol/network address/port) is normally permitted
```

**Root Causes:**
1. Docker daemon cache still holds port after container removal
2. External process (Python, Windows service) holding the port
3. Windows networking stack hasn't released the port (TIME_WAIT state)

## Solutions (in order of effectiveness):

### Solution 1: Restart Docker Daemon (Preferred)
**Windows (Docker Desktop):**
```powershell
# In PowerShell as Administrator:
Restart-Service Docker -Force
# Wait 30 seconds
docker compose -f docker-compose.v2.yml up -d
```

**Linux:**
```bash
sudo systemctl restart docker
# or with systemctl alternative
sudo service docker restart
```

**macOS:**
```bash
# Restart Docker Desktop app from menu, or:
osascript -e 'quit app "Docker"'
sleep 5
open -a Docker
```

### Solution 2: Remove Port from Docker (Temporary Fix)
Edit `docker-compose.v2.yml`, find board-api service, and temporarily comment out the ports:

```yaml
  board-api:
    # ... (service definition)
    # ports:
    # - 127.0.0.1:8799:8799
    # Access via internal network instead: http://board-api:8799
```

Then start: `docker compose up -d`

### Solution 3: Use Different Port Temporarily
Edit `docker-compose.v2.yml`:
```yaml
    ports:
    - 127.0.0.1:8800:8799    # Use 8800 externally, 8799 internally
```

Update `king-watchdog.py`:
```python
HTTP_HEALTH_CHECKS = [
    {'label': 'board-api',    'url': 'http://127.0.0.1:8800/health'},
    # ...
]
```

### Solution 4: Force Port Release (Windows)
```powershell
# Find process holding port 8799
Get-NetTCPConnection -LocalPort 8799 -State Listen | ForEach-Object {Get-Process -Id $_.OwningProcess}

# Kill it (if identified)
taskkill /PID <pid> /F

# Then retry compose
docker compose down
docker compose up -d
```

### Solution 5: Full Docker Reset (Nuclear Option)
```bash
# WARNING: Removes all containers, images, volumes
docker system prune -a --volumes -f
docker compose -f docker-compose.v2.yml up -d
```

---

## After Port is Free

Verify board-api is running:
```bash
curl http://127.0.0.1:8799/health
# Should return: {"status": "alive", "service": "board-api", ...}
```

Verify with watchdog:
```bash
cd 12sgi-king
python king-watchdog.py
# Should show: OK: king-bridge, board-api, studio-assets all healthy
```

---

## Permanent Fix: Don't Use Loopback

For production, consider using internal Docker network instead of host port binding:

```yaml
  board-api:
    # Remove this:
    # ports:
    # - 127.0.0.1:8799:8799
    
    # Access via: http://board-api:8799 from other containers
    # Access via nginx proxy from host
```

Then nginx (running on host or in separate container) proxies to internal network.

---

## If Problem Persists After Reboot

1. Check if another service owns 127.0.0.1:8799:
   ```powershell
   netstat -anbo | Select-String "8799"
   ```

2. If Windows service (not Docker), either:
   - Disable the service: `Get-Service | Where-Object Name -like "*8799*" | Stop-Service`
   - Change board-api to different port (see Solution 3)

3. Reset Windows TCP stack:
   ```powershell
   # Admin PowerShell
   netsh int ipv4 reset resetall
   # Requires reboot
   ```

---
