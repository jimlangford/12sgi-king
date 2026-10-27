# 🎯 WIX DNS UPDATE - EXACT CHANGES NEEDED

## Your Current DNS (What's There Now)

**A Records (Root Domain):**
- 12sgi.com → 192.0.78.128 (Delete this)
- 12sgi.com → 192.0.78.254 (Delete this)

**CNAME Records (Subdomains):**
- app.12sgi.com → 12sgi.com
- gov.12sgi.com → 12sgi.com
- govos.12sgi.com → 12sgi.com
- tenant.12sgi.com → 12sgi.com
- www.12sgi.com → 12sgi.com

---

## ✅ WHAT TO DO IN WIX

### Step 1: Delete Old A Records

In Wix DNS Management, find the "A (Host)" section:

**DELETE These:**
- ❌ 12sgi.com → 192.0.78.128
- ❌ 12sgi.com → 192.0.78.254

Click the trash icon next to each one.

### Step 2: Add New A Records

Add these NEW A records to point to your king-server:

| Type | Host Name | Value | TTL |
|------|-----------|-------|-----|
| A | 12sgi.com | 100.124.152.3 | 1 Hour |
| A | www | 100.124.152.3 | 1 Hour |
| A | api | 100.124.152.3 | 1 Hour |
| A | site | 100.124.152.3 | 1 Hour |

### Step 3: Keep Existing CNAME Records

Leave these as-is (they're fine):
- ✅ app.12sgi.com → 12sgi.com
- ✅ gov.12sgi.com → 12sgi.com
- ✅ govos.12sgi.com → 12sgi.com
- ✅ tenant.12sgi.com → 12sgi.com
- ✅ www.12sgi.com → 12sgi.com (or update to point to 100.124.152.3 directly)

### Step 4: Keep MX Records

Leave mail records as-is:
- ✅ mx1.titan.email (Priority 10)
- ✅ mx2.titan.email (Priority 20)

---

## 📋 STEP-BY-STEP IN WIX

### 1. Login to Wix
- Go to: https://www.wix.com/dashboard
- Select: 12sgi.com site

### 2. Go to Domain Management
- Settings → Domains
- Click: "Manage DNS"

### 3. Delete Old A Records
Find "A (Host)" section:
- Click trash icon next to: 12sgi.com → 192.0.78.128
- Click trash icon next to: 12sgi.com → 192.0.78.254

### 4. Add New A Record
- Click: "+ Add Record" (or "New Record")
- Type: A
- Name: @ (or leave blank - means root)
- Value: 100.124.152.3
- TTL: 1 Hour
- Click: Save

### 5. Add Subdomain A Records
Repeat for: www, api, site

For each:
- Click: "+ Add Record"
- Type: A
- Name: www (or api, or site)
- Value: 100.124.152.3
- TTL: 1 Hour
- Click: Save

### 6. Save All Changes
- Click: Save/Done at bottom of page
- Wait for confirmation

---

## ✅ AFTER UPDATE - YOUR DNS WILL BE:

**A Records:**
- 12sgi.com → 100.124.152.3
- www → 100.124.152.3
- api → 100.124.152.3
- site → 100.124.152.3

**CNAME Records (unchanged):**
- app.12sgi.com → 12sgi.com
- gov.12sgi.com → 12sgi.com
- govos.12sgi.com → 12sgi.com
- tenant.12sgi.com → 12sgi.com
- www.12sgi.com → 12sgi.com

**MX Records (unchanged):**
- mx1.titan.email (Priority 10)
- mx2.titan.email (Priority 20)

---

## ⏱️ PROPAGATION

After you update DNS in Wix:

1. **Immediate (Wix server):** Update is applied
2. **Within 1 hour:** Most DNS servers update
3. **Within 24 hours:** All DNS servers worldwide update

### Check Propagation

```powershell
# Run this to verify
nslookup 12sgi.com
nslookup www.12sgi.com
nslookup api.12sgi.com
nslookup site.12sgi.com
```

All should return: **100.124.152.3**

Or check online: https://www.whatsmydns.net/

---

## 🧪 VERIFY IT WORKS

Once DNS propagates:

```powershell
# From any Tailscale device
curl http://100.124.152.3:8080/site/
curl http://100.124.152.3:8799/api/
curl http://100.124.152.3:7474/

# Or via domain (after propagation)
curl http://12sgi.com:8080/site/
curl http://api.12sgi.com:8799/
```

---

## 🎯 WHAT THIS DOES

After you make these changes:

✅ 12sgi.com points to your king-server (100.124.152.3)
✅ All traffic goes through Tailscale (encrypted, private)
✅ Services accessible from Tailscale devices
✅ No forwarding to elementlotus.com
✅ No external billing dependencies
✅ 100% under your control

---

## ⚠️ IMPORTANT NOTES

1. **Keep Tailscale running** on king-server
2. **Keep services running** (docker compose up -d)
3. **No internet exposure** - only Tailscale devices can access
4. **Mail still works** - MX records unchanged
5. **Subdomain CNAMEs** - Will resolve through root A record

---

## ❓ WHAT IF DNS DOESN'T UPDATE?

If it takes longer than 24 hours:

1. Check Wix shows your changes (refresh page)
2. Clear local DNS cache: `ipconfig /flushdns`
3. Check propagation: https://www.whatsmydns.net/
4. Lower TTL to 300 seconds (5 min) for faster updates
5. Contact Wix support if stuck

---

## ✅ FINAL CHECKLIST

- [ ] Logged into Wix dashboard
- [ ] Found Manage DNS for 12sgi.com
- [ ] Deleted old A records (192.0.78.x)
- [ ] Added new A records (100.124.152.3)
- [ ] Saved all changes
- [ ] Verified changes saved in Wix
- [ ] Waited for DNS propagation (1-24 hrs)
- [ ] Tested with nslookup
- [ ] Tested access from Tailscale device
- [ ] Confirmed services respond

---

**Once you make these changes in Wix, your 12sgi.com will point to king-server completely independently!**

