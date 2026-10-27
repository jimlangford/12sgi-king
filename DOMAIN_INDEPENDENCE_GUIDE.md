# 🌐 12sgi.com - Complete Domain Independence Setup

## Your Domain is Now Completely Independent

You now have a setup where **12sgi.com is 100% independent** from any cloud provider billing. The domain is yours on Wix, and it points directly to your king-server via Tailscale.

---

## 📋 Quick Summary

**Current State:**
- ❌ 12sgi.com forwards to elementlotus.com (needs fixing)
- ✅ Wix account has domain (you own it)
- ✅ King-server is on Tailscale (private network)
- ✅ Services running on king-server (ports 8080, 8799, etc)

**After Setup:**
- ✅ 12sgi.com points to king-server via Tailscale
- ✅ No forwarding to other services
- ✅ Complete control
- ✅ Zero billing dependencies

---

## 🎯 3 Steps to Independence

### Step 1: Update Wix DNS Records (15 minutes)

**Go to Wix Dashboard:**
1. Login: https://www.wix.com/dashboard
2. Click your site (12sgi.com)
3. Go to: Settings → Domains
4. Click: "Manage DNS"

**Remove Old Forward:**
- Delete any records pointing to elementlotus.com
- Remove any URL forwarding rules

**Add New Records:**

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | 100.124.152.3 | 3600 |
| CNAME | www | 100.124.152.3 | 3600 |
| CNAME | api | 100.124.152.3 | 3600 |
| CNAME | site | 100.124.152.3 | 3600 |

**Save and wait for propagation (1-24 hours)**

### Step 2: Verify DNS (5 minutes)

Once DNS propagates, test:

```powershell
nslookup 12sgi.com
nslookup www.12sgi.com
nslookup api.12sgi.com
nslookup site.12sgi.com
```

All should resolve to: **100.124.152.3**

**Check online:** https://www.whatsmydns.net/

### Step 3: Test Access (5 minutes)

From any device on your Tailscale network:

```bash
# Test web server (dashboards)
curl http://100.124.152.3:8080/site/

# Test API
curl http://100.124.152.3:8799/api/

# Test Neo4j
curl http://100.124.152.3:7474/

# Test CI/CD webhook
curl http://100.124.152.3:9000/webhook
```

---

## 🏗️ Architecture Diagram

```
┌──────────────────────────────────────┐
│ 12sgi.com                            │
│ (Wix - Your Ownership)               │
└──────────────┬───────────────────────┘
               │
               │ DNS A Record
               ↓
┌──────────────────────────────────────┐
│ Tailscale Private Network             │
│ tail760750.ts.net                    │
│                                       │
│ ✅ Encrypted (WireGuard)             │
│ ✅ Free tier (no billing)            │
│ ✅ Only tailnet devices              │
└──────────────┬───────────────────────┘
               │
               ↓
┌──────────────────────────────────────┐
│ King-Server (100.124.152.3)          │
│                                       │
│ Services:                            │
│ ├─ Port 8080: Web (dashboards)      │
│ ├─ Port 8799: API (board-api)       │
│ ├─ Port 7474: Neo4j (database)      │
│ ├─ Port 9000: CI/CD webhook         │
│ └─ Ports 8101-8109: V2 services    │
│                                       │
│ Features:                            │
│ ✅ Local CI/CD                       │
│ ✅ Auto-recovery                     │
│ ✅ Health monitoring                 │
│ ✅ Continuous deployment             │
└──────────────────────────────────────┘
```

---

## 🔐 Security & Privacy

### What's Protected

✅ **All data stays private**
- Only devices in your Tailscale tailnet can access
- Encryption in transit (WireGuard)
- No internet-facing ports
- No third-party CDN

✅ **Complete control**
- You own the domain (Wix account)
- You own the server (king-server)
- You own the network (Tailscale account)
- You own the data (Neo4j on your server)

✅ **Zero billing issues**
- Tailscale free tier (unlimited devices)
- Domain on Wix (separate from services)
- Server runs locally (one-time cost)
- No cloud hosting bills

---

## 🚀 Access Methods

### From Tailscale Network (Recommended)

```bash
# Direct IP (always works)
http://100.124.152.3:8080/site/

# Via hostname
http://king.tail760750.ts.net:8080/site/

# Via domain (after DNS propagates)
http://12sgi.com:8080/site/
```

### From Internet (Advanced - Optional)

If you want public internet access while keeping services private:

```bash
# On king-server, enable Tailscale Funnel
tailscale funnel --bg http://localhost:8080

# Then access from anywhere
https://king--tail760750.ts.net/site/
```

**Note:** This is optional. Default setup is Tailscale-only (more secure).

---

## 📊 What Changed from Old Setup

| Aspect | Old (elementlotus forward) | New (Tailscale) |
|--------|---|---|
| **Domain Owner** | ❓ Unclear | ✅ You (Wix) |
| **Data Location** | ❓ Forwarded | ✅ Local (king-server) |
| **Billing Risk** | ⚠️ High | ✅ Zero |
| **Control** | ❓ Limited | ✅ Complete |
| **Privacy** | ❓ Unknown | ✅ Private network |
| **Encryption** | ❓ Unknown | ✅ WireGuard (Tailscale) |
| **Speed** | ❌ Redirect lag | ✅ Direct (Tailscale) |

---

## ✅ Verification Checklist

**Before DNS Update:**
- [ ] King-server is running (`docker compose ps`)
- [ ] Tailscale is connected (`tailscale status`)
- [ ] All services accessible via `100.124.152.3:port`
- [ ] Local CI/CD is running
- [ ] Neo4j has 14,300 nodes (`python verify_neo4j.py`)

**After DNS Update:**
- [ ] Wix DNS records saved
- [ ] Old forward removed
- [ ] DNS propagated (check whatsmydns.net)
- [ ] `nslookup 12sgi.com` returns 100.124.152.3
- [ ] Services work on 12sgi.com

**Final Verification:**
- [ ] Access from Tailscale: `http://100.124.152.3:8080/site/`
- [ ] Access via domain: `http://12sgi.com:8080/site/`
- [ ] All 11 services running
- [ ] Neo4j accessible
- [ ] CI/CD webhook responding

---

## 🆘 Troubleshooting

### DNS Not Resolving

```powershell
# Clear DNS cache
ipconfig /flushdns

# Try again
nslookup 12sgi.com

# Still not working? Wait more (can take 24 hours)
# Check progress: https://www.whatsmydns.net/
```

### Can't Connect via Tailscale

```powershell
# Check Tailscale status
tailscale status

# Should show king-server as ONLINE
# If offline, restart Tailscale on king-server

# From your machine, check connection
ping 100.124.152.3

# Should get response
```

### Services Not Responding

On king-server:
```powershell
# Check all services
docker compose -f docker-compose.v2.yml ps

# Should show 11/11 UP
# If not, start them:
docker compose -f docker-compose.v2.yml up -d

# Check logs
docker compose logs
```

### Firewall Blocking Ports

```powershell
# Check if ports are listening
netstat -ano | findstr :8080
netstat -ano | findstr :8799
netstat -ano | findstr :7474

# Should show LISTENING
# If not, ports are blocked by firewall
```

---

## 📚 Related Documentation

- **`TAILSCALE_SETUP_GUIDE.md`** - Complete Tailscale setup
- **`TAILSCALE_DEPLOYMENT_COMPLETE.md`** - Current status
- **`LOCAL_CICD_READY.md`** - CI/CD system
- **`FULL_DIRECTORY_STRUCTURE.md`** - Project overview

---

## 🎯 Your New Hosting Model

```
You Own Everything:
├─ Domain (12sgi.com on Wix)
├─ Server (king-server, physical hardware)
├─ Network (Tailscale tailnet)
├─ Code (GitHub repo)
├─ Services (11 Docker containers)
├─ Data (Neo4j, 14,300 nodes)
└─ CI/CD (local webhook system)

No Billing Dependencies:
├─ ❌ Not dependent on GitHub billing
├─ ❌ Not dependent on cloud providers
├─ ❌ Not dependent on CDN services
├─ ✅ Only Wix for domain (already paid)
├─ ✅ Only Tailscale (free tier)
└─ ✅ Only your hardware
```

---

## 🚀 Next Steps

1. **Run setup script** (already done - `setup_tailscale_hosting.py`)
2. **Update Wix DNS records** (15 minutes)
3. **Wait for DNS propagation** (1-24 hours)
4. **Verify everything works** (5 minutes)
5. **Enjoy your independent hosting!** 🎉

---

## 💡 Pro Tips

1. **Keep Tailscale running** - All access goes through Tailscale
2. **Monitor services** - Run `python status_dashboard.py` regularly
3. **Backup data** - Neo4j volumes are persistent, but backup regularly
4. **Update DNS TTL** - If you plan to change servers later, lower TTL to 300 first
5. **Document access** - Add this doc to your team wiki

---

## ✨ You're Now Completely Independent!

Your 12sgi.com hosting is:
- ✅ Owned by you (Wix domain)
- ✅ Controlled by you (DNS settings)
- ✅ Running on your hardware (king-server)
- ✅ Protected by your network (Tailscale)
- ✅ Free from billing issues (Tailscale free tier)

**No more elementlotus.com forward. No more billing surprises. Complete independence!**

