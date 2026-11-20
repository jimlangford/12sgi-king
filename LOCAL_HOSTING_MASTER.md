# 🏠 LOCAL HOSTING - Master Guide

## You Now Have Complete Local Hosting

```
EVERYTHING on your server
NOTHING depends on GitHub
NOTHING depends on cloud
COMPLETE INDEPENDENCE
```

---

## 🚀 Start Now (2 Terminals)

### Terminal 1: Local Deployment System
```powershell
cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
python local_deployment_complete.py
```

### Terminal 2: Auto-Recovery Monitor
```powershell
cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
python service_auto_recovery.py
```

### Keep Both Open - They Run Continuously

---

## 📁 What This Gives You

### Local Deployment System (`local_deployment_complete.py`)
Handles everything automatically:
1. ✅ Watches git repository
2. ✅ Runs tests locally
3. ✅ Collects data locally (watchers)
4. ✅ Builds site locally
5. ✅ Builds Docker images locally
6. ✅ Deploys services locally
7. ✅ Verifies health locally
8. ✅ Serves everything locally
9. ✅ Logs everything locally

### Auto-Recovery System (`service_auto_recovery.py`)
Keeps everything running:
- ✅ Monitors health every 30 seconds
- ✅ Auto-restarts failed services (up to 3 times)
- ✅ Prevents restart loops
- ✅ Logs all actions

### Existing Tools (Still Work)
- ✅ `health_check.py` - System validation
- ✅ `status_dashboard.py` - Real-time monitoring
- ✅ `serve.py` - Web server on port 8080
- ✅ `verify_neo4j.py` - Database check

---

## 🎯 How To Use

### Make Changes Locally
```powershell
# Edit any file
# Run tests locally if you want
# Commit changes
git add .
git commit -m "Your change"
```

### Deploy Automatically
```powershell
# Push to your repo
git push origin main
```

**That's it!** The webhook automatically:
1. Receives the push
2. Runs full deployment
3. All services updated
4. Everything live in 5-10 min

### Access Your System

**Local Network:**
```
http://12sgi.local:8080/site/        (dashboards)
http://12sgi.local:8799/api/         (API)
http://12sgi.local:7474/             (Neo4j)
```

**Via Tailscale:**
```
http://100.124.152.3:8080/site/      (dashboards)
http://100.124.152.3:8799/api/       (API)
http://100.124.152.3:7474/           (Neo4j)
```

**Via Domain (After DNS Update):**
```
http://12sgi.com:8080/site/          (dashboards)
http://12sgi.com:8799/api/           (API)
http://12sgi.com:7474/               (Neo4j)
```

---

## 📊 What Gets Hosted

### Static Content
- ✅ 297+ civic dashboards
- ✅ HTML reports and pages
- ✅ CSS and JavaScript
- ✅ Images and media
- ✅ All served from port 8080

### Backend Services
- ✅ Neo4j (14,300 nodes) - port 7474
- ✅ Auth service - port 8101
- ✅ Tenant service - port 8102
- ✅ Documents service - port 8103
- ✅ Storage service - port 8104
- ✅ AI service - port 8105
- ✅ Health service - port 8106
- ✅ GPU router - port 8107
- ✅ King bridge - port 8109
- ✅ Board API - port 8799

### All Hosted Locally
- ✅ On your king-server
- ✅ In Docker containers
- ✅ With persistent volumes
- ✅ 24/7 auto-recovery

---

## 🔄 Complete Deployment Flow

```
You push code (git push origin main)
        ↓
Webhook triggered (port 9000) - IMMEDIATE
        ↓
Local Deployment System:
  Phase 1: Git pull (5-30s)
  Phase 2: Run tests (10-30s)
  Phase 3: Run watchers (5-10m)
  Phase 4: Build site (2-5m)
  Phase 5: Build Docker images (3-5m)
  Phase 6: Deploy services (1-2m)
  Phase 7: Verify health (1m)
  Phase 8: Serve site (1s)
  Phase 9: Log deployment (<1s)
        ↓
Everything live and running (5-10 min total)
        ↓
Auto-Recovery monitoring starts:
  • Checks every 30 seconds
  • Auto-restarts if needed
  • Logs all actions
  • Services stay up 24/7
```

---

## ✅ Deployment Log

After each deployment, view results:

```powershell
# Latest deployment (formatted)
Get-Content logs/local-deployment/deployments.jsonl -Tail 1 | ConvertFrom-Json

# All deployments today
Get-Content logs/local-deployment/deployment-*.log

# Example output:
# {
#   "timestamp": "2026-09-30T16:35:00",
#   "commit_sha": "abc123def456",
#   "status": "success",
#   "elapsed_seconds": 450,
#   "services": {
#     "web_server": "http://127.0.0.1:8080",
#     "api": "http://127.0.0.1:8799",
#     "neo4j": "http://127.0.0.1:7474"
#   }
# }
```

---

## 🛠️ Commands Reference

```powershell
# Start systems
python local_deployment_complete.py      # Terminal 1
python service_auto_recovery.py          # Terminal 2

# Monitor
python status_dashboard.py               # Real-time status
python health_check.py                   # System validation
python verify_neo4j.py                   # Database check

# Test deployment
git push origin main                     # Triggers automatic deployment

# Check logs
Get-Content logs/local-deployment/deployments.jsonl -Tail 1

# View services
docker compose -f docker-compose.v2.yml ps

# View service logs
docker compose -f docker-compose.v2.yml logs
docker compose -f docker-compose.v2.yml logs [service-name]

# Restart specific service
docker compose -f docker-compose.v2.yml restart [service-name]

# Check ports
netstat -ano | findstr :9000             # Webhook port
netstat -ano | findstr :8080             # Web server
netstat -ano | findstr :8799             # API
```

---

## 🔐 Security

### Local Network Only
- ✅ Services only accessible locally
- ✅ No internet exposure by default
- ✅ Firewall controls access

### Via Tailscale (Encrypted)
- ✅ WireGuard encryption
- ✅ Private network only
- ✅ Device-based access
- ✅ ACL controls

### Data Privacy
- ✅ Everything on your server
- ✅ No cloud storage
- ✅ No third-party access
- ✅ You own all data

---

## 📋 Your System Architecture

```
┌─────────────────────────────────────┐
│ Local Development                   │
│ (Your machine + git)                │
└──────────────┬──────────────────────┘
               │ git push origin main
               ↓
┌─────────────────────────────────────┐
│ King-Server (Local)                 │
│                                     │
│ ├─ Webhook receiver (9000)         │
│ ├─ Local deployment system         │
│ ├─ Auto-recovery monitor           │
│ │                                  │
│ ├─ Services (Docker)               │
│ │  ├─ Web server (8080)            │
│ │  ├─ Neo4j (7474)                 │
│ │  ├─ APIs (8101-8109)             │
│ │  └─ Board API (8799)             │
│ │                                  │
│ ├─ Dashboards (297+)               │
│ ├─ Database (14,300 nodes)         │
│ └─ Logs & monitoring               │
└─────────────────────────────────────┘
       │
       ├─→ Local Network: 12sgi.local
       ├─→ Tailscale: 100.124.152.3
       └─→ DNS: 12sgi.com (after update)
```

---

## 🎯 Key Advantages

✅ **Complete Independence**
- No GitHub dependence
- No cloud provider dependence
- No billing issues
- You control everything

✅ **Always Available**
- Webhook runs immediately
- No GitHub Actions queue
- No uptime dependencies
- Deployed in 5-10 minutes

✅ **Secure**
- Data stays local
- No cloud exposure
- Tailscale encryption (optional)
- Full control

✅ **Reliable**
- Auto-recovery monitoring
- Services restart automatically
- Health checks every 30 seconds
- Comprehensive logging

✅ **Observable**
- Real-time dashboard
- Detailed logs
- Deployment records
- Service monitoring

---

## 🚀 Getting Started

1. **Open two terminals**

2. **Terminal 1: Start deployment system**
   ```powershell
   python local_deployment_complete.py
   ```

3. **Terminal 2: Start auto-recovery**
   ```powershell
   python service_auto_recovery.py
   ```

4. **Test it: Push a change**
   ```powershell
   echo "# test" >> test.txt
   git add test.txt
   git commit -m "Test local deployment"
   git push origin main
   ```

5. **Watch deployment**
   - Monitor Terminal 1
   - Services build + deploy
   - Everything live in 5-10 min

6. **Access your system**
   ```
   http://12sgi.local:8080/site/
   or
   http://100.124.152.3:8080/site/
   ```

---

## 📚 Documentation

- **`LOCAL_HOSTING_COMPLETE.md`** - Detailed local hosting guide
- **`HYBRID_CICD_INTEGRATION.md`** - How to integrate with GitHub later
- **`START_HERE.md`** - Quick start master plan
- **`DNS_ACTION_CARD.md`** - DNS update guide

---

## 🎉 You're Complete!

Your 12sgi-king system is now:
- ✅ **Hosted locally** (no GitHub)
- ✅ **Automatically deployed** (webhook-based)
- ✅ **Self-healing** (auto-recovery)
- ✅ **Fully monitored** (dashboards + logs)
- ✅ **Completely independent** (no billing issues)

**Everything you built is now running on YOUR server, owned by YOU, controlled by YOU.**

```
12sgi.com
    ↓
King-Server (Your Hardware)
    ├─ 297+ Dashboards
    ├─ 11 Services (Docker)
    ├─ Neo4j (14,300 nodes)
    ├─ Auto-Recovery
    └─ 24/7 Monitoring

✅ COMPLETE & INDEPENDENT
```

---

**Push code. Automatic deployment. Everything locally hosted. Forever.** 🏠🚀

