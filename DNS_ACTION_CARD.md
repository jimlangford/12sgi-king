# ⚡ ACTION CARD - Move 12sgi.com from elementlotus to King-Server

## Your Domain Right Now

```
12sgi.com forwards to elementlotus.com ❌ (NOT YOUR CONTROL)
```

## Your Domain After (5 Min Update)

```
12sgi.com points to 100.124.152.3 (king-server) ✅ (YOUR CONTROL)
```

---

## 🎯 DO THIS NOW

### 1. Go to Wix (2 minutes)
```
https://www.wix.com/dashboard
  → Click: 12sgi.com
  → Settings → Domains
  → Manage DNS
```

### 2. Delete Old Records (1 minute)
Find "A (Host)" section:
- ❌ Delete: 12sgi.com → 192.0.78.128
- ❌ Delete: 12sgi.com → 192.0.78.254

### 3. Add New Records (2 minutes)
Click "+ Add Record" for each:

```
1st Record:
  Type: A
  Name: @ (root)
  Value: 100.124.152.3
  TTL: 1 Hour
  Save

2nd Record:
  Type: A
  Name: www
  Value: 100.124.152.3
  TTL: 1 Hour
  Save

3rd Record:
  Type: A
  Name: api
  Value: 100.124.152.3
  TTL: 1 Hour
  Save

4th Record:
  Type: A
  Name: site
  Value: 100.124.152.3
  TTL: 1 Hour
  Save
```

### 4. Save (1 minute)
- Click: Save/Done
- Confirm changes saved

---

## ⏱️ WAIT

DNS propagates in **1-24 hours**

Check progress:
```powershell
nslookup 12sgi.com
```

Should eventually return: **100.124.152.3**

---

## ✅ VERIFY

```powershell
# Check DNS resolved
nslookup 12sgi.com

# Test from Tailscale device
curl http://100.124.152.3:8080/site/
curl http://100.124.152.3:8799/api/
```

---

## 📋 DOCUMENTATION

- **`WIX_DNS_UPDATE_GUIDE.md`** - Step-by-step guide
- **`DNS_BEFORE_AFTER.md`** - Before/after comparison
- **`COMPLETE_INDEPENDENCE.md`** - Full overview

---

## 🎉 RESULT

✅ 12sgi.com is 100% yours
✅ Points to king-server
✅ Zero external dependencies
✅ Zero billing risk
✅ Complete control

---

**Total time: 5 minutes to update, 1-24 hours to propagate**

