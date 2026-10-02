# 🏠 12sgi-king Local Hosting System

## ✅ COMPLETE LOCAL HOSTING - READY NOW!

Your 12sgi-king civic transparency platform is now fully hosted locally with **zero GitHub dependence**.

---

## 🚀 START NOW - 2 CLICKS

### Option 1: One-Click Start (Easiest)
```
Double-click: START_LOCAL_HOSTING.bat
```

This opens a menu where you can:
- Start both systems automatically
- Check status
- View logs
- Open the dashboard

### Option 2: Manual Start (2 Terminals)

**Terminal 1:**
```powershell
cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
python local_deployment_complete.py
```

**Terminal 2:**
```powershell
cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
python service_auto_recovery.py
```

---

## 📚 DOCUMENTATION

**Read in this order:**

1. **[LOCAL_HOSTING_INDEX.html](LOCAL_HOSTING_INDEX.html)** - Interactive dashboard (opens in browser)
2. **[LOCAL_HOSTING_MASTER.md](LOCAL_HOSTING_MASTER.md)** - Quick start guide
3. **[LOCAL_HOSTING_COMPLETE.md](LOCAL_HOSTING_COMPLETE.md)** - Detailed guide

---

## 🧪 TEST DEPLOYMENT

After starting both systems, test automatic deployment:

```powershell
# Make a change
echo "test" >> test.txt

# Commit and push
git add test.txt
git commit -m "Test local deployment"
git push origin main
```

**Watch Terminal 1** - your complete deployment system runs automatically:
- Git pull
- Run tests
- Collect data
- Build site
- Build Docker images
- Deploy services
- Verify health
- Everything live in 5-10 minutes

---

## 🌐 ACCESS YOUR SYSTEM

### Local Network (Recommended for local development)
```
http://12sgi.local:8080/site/        (297+ dashboards)
http://12sgi.local:8799/api/         (API)
http://12sgi.local:7474/             (Neo4j graph database)
```

### Via Tailscale Private Network
```
http://100.124.152.3:8080/site/      (dashboards)
http://100.124.152.3:8799/api/       (API)
http://100.124.152.3:7474/           (Neo4j)
```

### Via Domain (After DNS Update)
```
http://12sgi.com:8080/site/          (dashboards)
http://12sgi.com:8799/api/           (API)
http://12sgi.com:7474/               (Neo4j)
```

---

## 📊 WHAT'S INCLUDED

- ✅ **Complete local deployment system** - Webhook-based automation
- ✅ **Auto-recovery monitoring** - Services restart on failure
- ✅ **297+ civic dashboards** - Civic transparency for your community
- ✅ **11 Docker services** - Complete V2 backend
- ✅ **Neo4j database** - 14,300 nodes (civil data graph)
- ✅ **Web server** - Serves everything from port 8080
- ✅ **Comprehensive logging** - All deployments recorded
- ✅ **Health monitoring** - Continuous system validation
- ✅ **Zero external dependencies** - Everything local

---

## 🎯 DEPLOYMENT FLOW

When you push code:

```
Git Push
    ↓
Webhook triggers (port 9000)
    ↓
Automatic Deployment:
  1. Git pull latest code
  2. Run tests locally
  3. Collect data (watchers)
  4. Build dashboards (297+)
  5. Build Docker images
  6. Deploy services (11)
  7. Verify health
  8. Everything live
    ↓
5-10 minutes from push to production
```

---

## 📝 KEY FILES

### To Start
- **`START_LOCAL_HOSTING.bat`** - One-click launcher
- **`local_deployment_complete.py`** - Deployment orchestrator
- **`service_auto_recovery.py`** - Health monitor

### Documentation
- **`LOCAL_HOSTING_INDEX.html`** - Browser dashboard
- **`LOCAL_HOSTING_MASTER.md`** - Quick start
- **`LOCAL_HOSTING_COMPLETE.md`** - Detailed guide
- **`HYBRID_CICD_INTEGRATION.md`** - GitHub integration (later)

### Management
- **`manage_local_hosting.ps1`** - PowerShell control
- **`status_dashboard.py`** - Real-time monitoring
- **`health_check.py`** - System validation

---

## ⚙️ QUICK COMMANDS

```powershell
# Start everything
.\START_LOCAL_HOSTING.bat

# Or manually:
python local_deployment_complete.py      # Terminal 1
python service_auto_recovery.py          # Terminal 2

# Monitor
python status_dashboard.py

# Check health
python health_check.py

# View deployments
Get-Content logs/local-deployment/deployments.jsonl -Tail 1

# Deploy test change
git push origin main
```

---

## ✨ KEY FEATURES

✅ **Everything Hosted Locally**
- No GitHub dependence
- No cloud provider dependence
- Complete control

✅ **Automatic Deployment**
- Webhook-triggered
- Full CI/CD pipeline
- Zero manual steps

✅ **Self-Healing**
- Auto-recovery monitoring
- Automatic restarts
- 24/7 availability

✅ **Secure & Private**
- Local network only
- Tailscale encryption (optional)
- No public exposure by default

✅ **Always Available**
- Not blocked by billing
- Not dependent on any cloud
- Your infrastructure, your rules

---

## 🔄 LATER: GitHub Integration

When your GitHub billing is fixed, you can optionally use GitHub Actions alongside local hosting:
- Local CI/CD always runs immediately
- GitHub Actions provide redundancy
- See `HYBRID_CICD_INTEGRATION.md` for details

---

## 🎓 GETTING HELP

1. **Quick start?** → Read `LOCAL_HOSTING_INDEX.html` (in browser)
2. **Setup help?** → Read `LOCAL_HOSTING_MASTER.md`
3. **Detailed info?** → Read `LOCAL_HOSTING_COMPLETE.md`
4. **Stuck?** → Check terminal output or logs

---

## 📊 SYSTEM STATUS

```
✅ Local deployment system:    READY
✅ Auto-recovery monitor:      READY
✅ Docker services:            READY
✅ Neo4j database:             READY (14,300 nodes)
✅ Web server:                 READY
✅ Health monitoring:          READY
✅ Logging system:             READY

All systems ready for deployment!
```

---

## 🎉 YOU'RE ALL SET!

Your complete 12sgi-king civic transparency platform is now:

- ✅ **Hosted locally** (your server)
- ✅ **Automatically deployed** (webhook-based)
- ✅ **Self-healing** (auto-recovery)
- ✅ **Fully monitored** (dashboards & logs)
- ✅ **Completely independent** (zero external dependencies)

### Next Step: Double-Click `START_LOCAL_HOSTING.bat` and start deploying! 🚀

---

**Everything you need is here. Local hosting. Complete independence. Ready now.**

