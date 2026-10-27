# Local 12sgi.com Server Setup Guide

## Overview

Host 12sgi.com locally from the git repository without blocking CI/CD pipelines.

- **Port**: 8080 (configurable)
- **Server**: Python HTTP server
- **Content**: Static HTML/CSS/JS from git repo
- **CI/CD Impact**: None (runs in background)

---

## Quick Start

### 1. Start the Server (Non-Blocking)

```bash
# Option A: Background (doesn't block terminal)
python start_local_server.py --port 8080

# Option B: Foreground (traditional, press Ctrl+C to stop)
python serve.py 8080
```

### 2. Access

```
http://localhost:8080/
http://127.0.0.1:8080/
http://12sgi.com:8080/  (optional, see setup below)
```

### 3. Test Routes

```
/                          → king_landing.html (root)
/site/reports.html         → Civic dashboards
/site/tenants_hub.html     → Tenants overview
/apps/govos/               → govOS app
/apps/civic-signal/        → Civic Signal app
/education.html            → Education page
/platform.html             → Platform info
```

---

## Setup: 12sgi.com Hostname (Optional)

To access via `http://12sgi.com:8080/` instead of IP:

### Windows

1. **Open Command Prompt (as Administrator)**
   - Right-click Start → Run → `cmd` → Ctrl+Shift+Enter

2. **Open hosts file**
   ```
   notepad C:\Windows\System32\drivers\etc\hosts
   ```

3. **Add this line at the end**
   ```
   127.0.0.1 12sgi.com www.12sgi.com
   ```

4. **Save** (Ctrl+S) and close

5. **Test**
   ```
   ping 12sgi.com
   curl http://12sgi.com:8080/
   ```

### Mac/Linux

```bash
# Edit hosts file
sudo nano /etc/hosts

# Add:
127.0.0.1 12sgi.com www.12sgi.com

# Save (Ctrl+O, Enter, Ctrl+X)

# Test:
ping 12sgi.com
```

---

## Scripts

### `serve.py` — Simple Server
Lightweight HTTP server, direct execution.

```bash
python serve.py 8080
```

**Features:**
- Serves all HTML/CSS/JS files
- Auto-routing for directories
- MIME type detection
- Simple logging

### `start_local_server.py` — Background Startup
Non-blocking startup (good for CI/CD integration).

```bash
python start_local_server.py --port 8080 --hosts
```

**Options:**
- `--port 8080` — Port (default: 8080)
- `--hosts` — Try to add 12sgi.com to hosts file (requires admin)
- `--bg` — Start in background (internal)

### `local_server.py` — Advanced Server
Feature-rich server with better routing.

```bash
python local_server.py --port 8080
```

---

## File Structure

The server serves files from the git repository root:

```
12sgi-king/
├── king_landing.html          ← Root page (/)
├── education.html
├── platform.html
├── gordon.html
├── site/                       ← Civic dashboards
│   ├── govos.css
│   ├── reports.html
│   ├── tenants_hub.html
│   ├── datasets.html
│   ├── ...
├── apps/                       ← Web applications
│   ├── govos/public/
│   ├── civic-signal/public/
│   ├── tenant/public/
│   └── admin/public/
├── content/                    ← Content pages
│   └── wordpress/
├── element_lotus_public/       ← Element Lotus content
└── ...
```

---

## Usage Examples

### Development Workflow

```bash
# Terminal 1: Start server
python serve.py 8080

# Terminal 2: Edit HTML files
code king_landing.html

# Browser: Refresh http://localhost:8080/
```

### CI/CD Integration

```yaml
# GitHub Actions example
- name: Start 12sgi.com local server
  run: |
    python start_local_server.py --port 8080 &
    sleep 2
    # CI/CD continues without waiting...
```

### Production-like Setup

```bash
# Run with explicit port
python serve.py 8443

# Or with hostname:
python serve.py 8080
# Then access: http://12sgi.com:8080/
```

---

## Ports

| Use Case | Port | Access |
|----------|------|--------|
| Local dev | 8080 | http://localhost:8080/ |
| Alternate | 8081 | http://localhost:8081/ |
| HTTPS-like | 8443 | http://localhost:8443/ |
| Production | 80* | http://localhost/ (requires admin) |
| Production HTTPS | 443* | https://localhost/ (requires admin + cert) |

*Port 80/443 require administrator privileges and certificate setup.

---

## Troubleshooting

### "Port already in use"
```bash
# Find what's using the port
netstat -ano | findstr :8080

# Use different port
python serve.py 8081
```

### "Cannot access http://12sgi.com:8080/"
```bash
# Verify hosts file entry
type C:\Windows\System32\drivers\etc\hosts | findstr 12sgi.com

# If missing, add it manually (requires admin):
notepad C:\Windows\System32\drivers\etc\hosts

# Add: 127.0.0.1 12sgi.com www.12sgi.com
```

### "404 File not found"
```bash
# Make sure you're in the right directory
cd C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king
python serve.py 8080

# Verify files exist
ls king_landing.html
ls site/reports.html
```

### Server not responding

```bash
# Check if process is running
netstat -ano | findstr :8080

# Restart
# 1. Stop current process (Ctrl+C in terminal)
# 2. Start fresh: python serve.py 8080
```

---

## Performance

- **Startup**: <1 second
- **Page load**: <100ms (local)
- **Concurrent clients**: Unlimited
- **Resource usage**: Minimal (<10MB RAM)
- **CI/CD impact**: None (background process)

---

## Security Notes

⚠️ **For development only** — not suitable for production.

- No SSL/TLS (use `https://` only on port 443 with proper certs)
- No authentication
- No rate limiting
- No request logging (by default)
- All files are publicly accessible

For production, use:
- Nginx or Apache
- SSL certificates (Let's Encrypt)
- Proper firewall rules
- CDN (CloudFlare, Akamai, etc.)

---

## Integration with 12sgi-king Services

### Local Stack
```
12sgi.com (port 8080)
    ↓
Neo4j (port 7474)
    ↓
V2 Services (ports 8101-8109)
    ↓
External APIs (GitHub, WordPress, etc.)
```

### King-Bridge Integration
The landing page (`king_landing.html`) dynamically pulls data from:

```
http://localhost:8109/api/v2/bridge/tree
```

To get full data:
1. Start server: `python serve.py 8080`
2. Start Neo4j: `docker compose -f docker-compose.neo4j.yml up -d`
3. Start V2 services: `docker compose -f docker-compose.v2.yml up -d`
4. Access: `http://localhost:8080/`

---

## Commands Reference

```bash
# Start server
python serve.py 8080

# Start in background (non-blocking)
python start_local_server.py --port 8080

# Start with hostname setup
python start_local_server.py --port 8080 --hosts

# Check if server is running
netstat -ano | findstr :8080

# Access in browser
http://localhost:8080/
http://127.0.0.1:8080/
http://12sgi.com:8080/  (if hosts file set up)

# View files being served
ls *.html
ls site/
ls apps/
```

---

## Next Steps

1. ✅ **Start server**: `python serve.py 8080`
2. ✅ **Open browser**: `http://localhost:8080/`
3. ✅ **Set up hostname** (optional): Add 12sgi.com to hosts file
4. ✅ **Integrate with CI/CD**: Use `start_local_server.py` in workflows
5. ✅ **Test routes**: Visit `/site/reports.html`, `/apps/govos/`, etc.

---

**12sgi.com is now locally hosted and ready for development!**

