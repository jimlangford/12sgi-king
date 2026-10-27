# 12sgi.com Tailscale Hosting - Checklist

## Pre-Setup
- [ ] Have Wix dashboard access ready
- [ ] Know your king-server Tailscale IP (100.124.152.3)
- [ ] Tailscale is running on king-server
- [ ] All Docker services are running

## DNS Configuration (Wix)
- [ ] Go to Wix Dashboard
- [ ] Find Settings → Domains → Manage DNS
- [ ] Remove any existing elementlotus.com forward
- [ ] Add A record: @ → 100.124.152.3
- [ ] Add CNAME: www → 100.124.152.3
- [ ] Add CNAME: api → 100.124.152.3
- [ ] Add CNAME: site → 100.124.152.3
- [ ] Save all records
- [ ] Wait 1-24 hours for propagation

## Local Testing (Optional)
- [ ] Edit your hosts file (C:\Windows\System32\drivers\etc\hosts)
- [ ] Add: 192.168.X.X  12sgi.local www.12sgi.local api.12sgi.local
- [ ] Test: http://12sgi.local/site/
- [ ] Remove from hosts file after testing

## Tailscale Verification
- [ ] Run: tailscale status
- [ ] Verify king-server is ONLINE
- [ ] Run: docker compose ps
- [ ] All services should be UP

## Remote Access Test
- [ ] From another Tailscale device
- [ ] Connect to tailnet
- [ ] Access: http://100.124.152.3:8080/site/
- [ ] Access: http://100.124.152.3:8799/api/
- [ ] Verify both work

## DNS Propagation Check
- [ ] Run: nslookup 12sgi.com
- [ ] Should resolve to 100.124.152.3
- [ ] Check: https://www.whatsmydns.net/
- [ ] Should show your king-server IP

## Final Verification
- [ ] 12sgi.com resolves to king-server
- [ ] All services accessible via Tailscale
- [ ] No internet-facing services exposed
- [ ] Local CI/CD system still deploying
- [ ] Neo4j 14,300 nodes intact

## Troubleshooting
- [ ] DNS not resolving? Clear cache: ipconfig /flushdns
- [ ] Can't connect? Check Tailscale: tailscale status
- [ ] Services down? Run: docker compose logs
- [ ] Webhook not working? Check port 9000: netstat -ano | findstr :9000

---

**Status**: Ready for Wix DNS configuration
**Next Step**: Update DNS records in Wix dashboard
