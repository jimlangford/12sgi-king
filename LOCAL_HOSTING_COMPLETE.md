# 🏠 LOCAL HOSTING - Everything Hosted Locally

## Your New Model: 100% Local

```
NO GITHUB DEPENDENCE
NO CLOUD PROVIDERS
NO EXTERNAL BILLING
EVERYTHING ON YOUR SERVER
```

---

## 🎯 What You Get

### Complete Local System
- ✅ **Git repository** - Local (no GitHub sync needed)
- ✅ **Data collection** - Runs locally (watchers)
- ✅ **Website building** - Build site locally
- ✅ **Docker services** - All on king-server
- ✅ **Database** - Neo4j locally (14,300 nodes)
- ✅ **Web hosting** - Served from king-server
- ✅ **CI/CD** - Webhook → auto-deploy locally
- ✅ **Monitoring** - Health checks + auto-recovery

### Zero External Dependencies
- ❌ GitHub Actions not required
- ❌ GitHub Pages not used
- ❌ Cloud storage not needed
- ❌ CDN not needed
- ❌ Paid services not needed

---

## 🚀 How It Works

### Local Deployment Pipeline

```
You commit locally
    ↓
git push origin main (to local or remote repo)
    ↓
Webhook triggers (port 9000)
    ↓
Local deployment system starts
    ├─ Phase 1: Git pull latest
    ├─ Phase 2: Run tests (pytest)
    ├─ Phase 3: Run watchers (data collection)
    ├─ Phase 4: Build static site
    ├─ Phase 5: Build Docker images
    ├─ Phase 6: Deploy services (docker compose)
    ├─ Phase 7: Verify health
    ├─ Phase 8: Serve site locally
    └─ Phase 9: Log deployment
    ↓
Services running on king-server
    ├─ Port 8080: Web dashboards (297+)
    ├─ Port 8799: Board API
    ├─ Port 7474: Neo4j (14,300 nodes)
    ├─ Ports 8101-8109: V2 services (11)
    └─ Port 9000: Webhook receiver
    ↓
Access from anywhere
    ├─ Local: http://12sgi.local:8080
    ├─ Tailscale: http://100.124.152.3:8080
    └─ Via DNS: http://12sgi.com:8080
```

**Total time: 5-10 minutes from push to live**

---

## 📁 Components

### New Local Deployment System
- **`local_deployment_complete.py`** - Complete orchestrator
  - Watches git repository
  - Runs all phases locally
  - Manages all services
  - Logs all deployments

### Existing Components (Unchanged)
- ✅ `serve.py` - Local web server
- ✅ `status_dashboard.py` - Real-time monitoring
- ✅ `health_check.py` - System validation
- ✅ `service_auto_recovery.py` - Auto-restart
- ✅ `docker-compose.v2.yml` - Service definitions
- ✅ `build_site.py` - Site builder

---

## ⚡ Quick Start

### 1. Start Local Deployment System
```powershell
cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
python local_deployment_complete.py
```

**Output:**
```
======================================================================
🚀 12sgi-king LOCAL DEPLOYMENT SYSTEM
======================================================================
Repository: C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king
Webhook port: 9000
Local domain: 12sgi.local
Logs: C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king\logs\local-deployment

Everything hosted LOCALLY - no GitHub dependence

✅ Webhook server running on 0.0.0.0:9000/webhook

READY TO DEPLOY:
  1. Push to main: git push origin main
  2. Webhook triggers automatically
  3. Full deployment cycle starts
  4. Everything hosted locally
```

**Keep this terminal open!**

### 2. Start Auto-Recovery Monitor
```powershell
cd "C:\Users\12sgi\actions-runner\_work\12sgi-king\12sgi-king"
python service_auto_recovery.py
```

**Keep this terminal open too!**

### 3. Test It
```powershell
# Make a change
echo "test" >> test.txt

# Commit and push
git add test.txt
git commit -m "Test local deployment"
git push origin main
```

Watch your deployment system terminal automatically:
1. Receive webhook
2. Pull code
3. Run tests
4. Build images
5. Deploy services
6. Verify health
7. Log result

**Done! Everything hosted locally.** 🎉

---

## 🌐 Access Your System

### Local Network
```
http://12sgi.local:8080/site/          (dashboards)
http://12sgi.local:8799/api/           (API)
http://12sgi.local:7474/               (Neo4j)
http://12sgi.local:8101/api/v2/ready   (auth service)
```

### Via Tailscale (Private Network)
```
http://100.124.152.3:8080/site/        (dashboards)
http://100.124.152.3:8799/api/         (API)
http://100.124.152.3:7474/             (Neo4j)
http://100.124.152.3:8101/api/v2/ready (auth service)
```

### Via Domain (After DNS Update)
```
http://12sgi.com:8080/site/            (dashboards)
http://12sgi.com:8799/api/             (API)
http://12sgi.com:7474/                 (Neo4j)
```

---

## 📊 Deployment Phases

### Phase 1: Update Repository
```
$ git pull origin main
Fetches latest code from your repository
Time: 5-30 seconds
```

### Phase 2: Run Tests
```
$ pytest tests/v2/test_v2_contract.py
$ pytest tests/v2/test_v2_integration_stack.py
Validates code quality
Time: 10-30 seconds
(Continues even if tests fail)
```

### Phase 3: Run Local Watchers
```
$ python watchers/council_watch.py
$ python watchers/votes_watch.py
...
Collects civic data locally
Time: 5-10 minutes
```

### Phase 4: Build Static Site
```
$ python build_site.py
Generates 297+ dashboards
Time: 2-5 minutes
```

### Phase 5: Build Docker Images
```
$ docker compose build --no-cache
Builds all 11 service images
Time: 3-5 minutes
```

### Phase 6: Deploy Services
```
$ docker compose up -d
Starts all containers
Time: 1-2 minutes
```

### Phase 7: Verify Health
```
$ curl http://localhost:8080/
$ curl http://localhost:8799/api/
Checks all services responding
Time: 1 minute
```

### Phase 8: Serve Site Locally
```
Ensures web server on port 8080
Dashboards accessible
Time: <1 second
```

### Phase 9: Log Deployment
```
Saves deployment record to JSON
Time: <1 second
```

**Total: 5-10 minutes**

---

## 📋 What Gets Deployed

### Local Git Repository
- ✅ Your code
- ✅ Watchers
- ✅ Tests
- ✅ Docker configs
- ✅ Database schemas

### Built Artifacts
- ✅ 297+ civic dashboards
- ✅ 11 Docker images
- ✅ Static HTML files
- ✅ API documentation

### Running Services
- ✅ Neo4j (graph database)
- ✅ Auth service
- ✅ Tenant service
- ✅ Documents service
- ✅ Storage service
- ✅ AI service
- ✅ Health service
- ✅ GPU router
- ✅ King bridge
- ✅ Board API
- ✅ Connector runner

### Monitoring & Management
- ✅ Health checks (every 30s)
- ✅ Auto-recovery (restarts failures)
- ✅ Deployment logs (JSON)
- ✅ Service status dashboard

---

## 🔧 Configuration

### Change Webhook Port
Edit `local_deployment_complete.py`:
```python
WEBHOOK_PORT = 9000  # Change to any unused port
```

### Change Local Domain
```python
LOCAL_DOMAIN = "12sgi.local"  # Your local DNS name
```

### Change Log Directory
```python
LOG_DIR = Path(REPO_PATH) / "logs" / "local-deployment"
```

### Add More Watchers
```python
def _run_local_watchers(self):
    watchers = [
        "council_watch.py",
        "votes_watch.py",
        "my_new_watcher.py",  # Add here
    ]
```

---

## 📊 Monitoring

### Real-Time Dashboard
```powershell
python status_dashboard.py
```

Shows all services, ports, health status.

### Deployment Logs
```powershell
# Latest deployment
Get-Content logs/local-deployment/deployments.jsonl -Tail 1

# All deployments
Get-Content logs/local-deployment/deployments.jsonl

# Today's logs
Get-Content logs/local-deployment/deployment-*.log
```

### Service Health
```powershell
python health_check.py
```

### Neo4j Verification
```powershell
python verify_neo4j.py
```

---

## 🆘 Troubleshooting

### Webhook Not Responding
```powershell
netstat -ano | findstr :9000
```

Should show LISTENING. If not, restart `local_deployment_complete.py`.

### Services Not Starting
```powershell
docker compose -f docker-compose.v2.yml ps
```

Check which services failed. View logs:
```powershell
docker compose logs [service-name]
```

### Deployment Stuck
Check if another deployment is running:
```powershell
Get-Process python | Where-Object {$_.CommandLine -like "*local_deployment*"}
```

### Local Domain Not Resolving
Add to your hosts file:
```
C:\Windows\System32\drivers\etc\hosts

192.168.X.X   12sgi.local www.12sgi.local
```

Where `192.168.X.X` is your king-server's local IP.

---

## 🔐 Security

### Local Network Only
- ✅ No internet exposure by default
- ✅ All traffic on local network
- ✅ Tailscale encryption (if using private IP)

### Data Privacy
- ✅ Data stays on your server
- ✅ No cloud storage
- ✅ No third-party access
- ✅ You own everything

### Access Control
- ✅ Local network access only
- ✅ Or via Tailscale (with ACL)
- ✅ No public ports exposed
- ✅ No API keys needed (locally)

---

## ✨ You Now Have

✅ **Complete local system**
✅ **Zero external dependencies**
✅ **Full control**
✅ **Always available** (not blocked by billing)
✅ **Automatic deployments** (webhook-based)
✅ **Self-healing** (auto-recovery)
✅ **Locally monitored** (dashboards + logs)
✅ **Completely private** (no cloud)

---

## 🎯 Key Commands

```powershell
# Start local deployment
python local_deployment_complete.py

# Start auto-recovery
python service_auto_recovery.py

# Monitor
python status_dashboard.py

# Test deployment
git push origin main

# Check status
Get-Content logs/local-deployment/deployments.jsonl -Tail 1

# View services
docker compose -f docker-compose.v2.yml ps

# Check health
python health_check.py
```

---

## 📝 Next Steps

1. ✅ Start `local_deployment_complete.py`
2. ✅ Start `service_auto_recovery.py`
3. ✅ Push test change
4. ✅ Watch everything deploy locally
5. ✅ Access http://12sgi.local:8080/site/
6. ✅ Update DNS when ready

---

**Everything is now hosted locally. No GitHub. No cloud. Complete independence.** 🏠

