# 🚀 LOCAL CI/CD SYSTEM - Complete Setup Guide

## Your New Self-Hosted CI/CD (Independent of GitHub)

You now have a **completely self-hosted** CI/CD system running on king-server. This is **independent of GitHub's billing** and gives you full control over your deployment pipeline.

---

## ✅ What's Installed

### 1. **Local CI/CD Server** (`local_ci_cd_server.py`)
- Webhook receiver on port 9000
- Listens for Git push events
- Auto-triggers deployments
- Comprehensive logging

### 2. **Auto-Recovery System** (`service_auto_recovery.py`)
- Monitors all services every 30 seconds
- Auto-restarts failed services (up to 3 times)
- Tracks restart counts
- Prevents infinite restart loops

### 3. **Existing Tools**
- `health_check.py` - System validation
- `status_dashboard.py` - Real-time monitoring
- `verify_neo4j.py` - Database verification

---

## 🎯 Quick Start (3 Steps)

### Step 1: Start Local CI/CD Server
```powershell
cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
python local_ci_cd_server.py
```

**Output:**
```
============================================================
12sgi-king Local CI/CD System Starting
============================================================
Repository: C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king
Webhook listening on port 9000
Logs: C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king\logs\ci-cd
✅ Webhook server running on 0.0.0.0:9000/webhook
```

**Keep this terminal open!** The server runs continuously.

### Step 2: Start Auto-Recovery (New Terminal)
```powershell
cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
python service_auto_recovery.py
```

**Output:**
```
2026-09-30 16:30:00,000 [INFO] 🔍 Starting service monitor...
2026-09-30 16:30:30,000 [INFO] ✓ auth running
2026-09-30 16:30:30,000 [INFO] ✓ tenant running
... (monitors all services every 30 seconds)
```

**Keep this terminal open!** The monitor runs continuously.

### Step 3: Test the System
Push a change to your Git repository:

```bash
git add .
git commit -m "Test local CI/CD"
git push origin main
```

**What happens automatically:**
1. ✅ Git webhook sends POST to `localhost:9000/webhook`
2. ✅ CI/CD server receives webhook
3. ✅ Pulls latest code
4. ✅ Runs smoke tests
5. ✅ Builds Docker images
6. ✅ Deploys services
7. ✅ Verifies health
8. ✅ Logs deployment

**Monitor the logs:**
```powershell
Get-Content "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king\logs\ci-cd\deployments.jsonl" -Tail 5
```

---

## 📋 Deployment Pipeline Stages

When you push to main, this happens automatically:

```
Push to main
    ↓
Webhook triggered (port 9000)
    ↓
Git pull latest code
    ↓
Run smoke tests (pytest)
    ↓
Build Docker images (docker compose build)
    ↓
Deploy services (docker compose up -d)
    ↓
Verify service health (health checks)
    ↓
Log deployment (JSON + status)
```

**Total time:** ~5-10 minutes

---

## 🔍 Monitoring

### Real-Time Dashboard
```powershell
python status_dashboard.py
```

Shows all services, endpoints, and health status.

### Deployment Logs
```powershell
# All deployments
Get-Content logs/ci-cd/deployments.jsonl

# Today's CI/CD logs
Get-Content logs/ci-cd/ci-cd-*.log
```

### Service Health
```powershell
docker compose -f docker-compose.v2.yml ps
```

---

## 🛠️ Configuration

### Change Webhook Port
Edit `local_ci_cd_server.py`:
```python
WEBHOOK_PORT = 9000  # Change this to any unused port
```

### Change Webhook Secret
```python
WEBHOOK_SECRET = "12sgi-king-local-ci-cd"  # Change to secure value
```

### Change Health Check Interval
Edit `service_auto_recovery.py`:
```python
self.check_interval = 30  # seconds (change to your preference)
```

### Change Max Restarts Per Service
```python
self.max_restarts = 3  # max restarts before giving up
```

---

## 🚨 Troubleshooting

### "Webhook server not responding"
- Check if `local_ci_cd_server.py` is still running
- Verify port 9000 is not blocked: `netstat -ano | findstr :9000`
- If blocked, change WEBHOOK_PORT and update Git webhook URL

### "Services not auto-restarting"
- Check if `service_auto_recovery.py` is running
- Verify Docker is accessible: `docker ps`
- Check logs in `logs/ci-cd/`

### "Deployments not triggering"
- Confirm webhook is running: `telnet localhost 9000`
- Check Git webhook in repository settings
- Verify webhook URL: `http://your-ip:9000/webhook`

### "Permission denied" errors
- Ensure Python scripts have execute permissions
- Run PowerShell as Administrator if needed
- Check Docker daemon is accessible

---

## 📊 Deployment Log Format

Each deployment is logged as JSON:
```json
{
  "timestamp": "2026-09-30T16:35:00.123456",
  "commit_sha": "abc123def456",
  "status": "success",
  "error": ""
}
```

---

## 🔐 Security Notes

This system runs on your local king-server:
- ✅ No GitHub billing issues
- ✅ Full control over deployments
- ✅ All data stays local
- ⚠️ Change WEBHOOK_SECRET to something secure
- ⚠️ Only accessible from your network (or via Tailscale)

---

## 🚀 Production Ready

Your local CI/CD system includes:
- ✅ Automated testing
- ✅ Docker image building
- ✅ Service deployment
- ✅ Health verification
- ✅ Auto-recovery (restarts failed services)
- ✅ Comprehensive logging
- ✅ Real-time monitoring

**You are NO LONGER dependent on GitHub Actions for deployments.**

---

## 📞 Terminal Windows You Need Running

| Window | Command | Purpose |
|--------|---------|---------|
| 1 | `python local_ci_cd_server.py` | Webhook receiver & orchestrator |
| 2 | `python service_auto_recovery.py` | Health monitor & auto-recovery |
| 3 | `python status_dashboard.py` (optional) | Real-time monitoring |

Keep windows 1 & 2 open. Window 3 is optional for monitoring.

---

**Your 12sgi-king deployment system is now fully self-hosted and independent!**

