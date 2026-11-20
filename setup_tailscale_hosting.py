#!/usr/bin/env python3
"""
12sgi.com Hosting Setup - Tailscale Private Hosting
Configure your domain to use Tailscale for completely independent hosting.

This script helps you:
1. Keep 12sgi.com domain on Wix (billing/control)
2. Point all traffic to your king-server (via Tailscale)
3. Set up internal DNS records
4. Verify everything is working
"""

import subprocess
import socket
import sys
import json
from pathlib import Path
from datetime import datetime

class TailscaleHostingSetup:
    def __init__(self):
        self.king_server_ip = "100.124.152.3"  # Your Tailscale IP
        self.tailnet = "tail760750.ts.net"
        self.domain = "12sgi.com"
        
    def get_local_ip(self):
        """Get your local network IP."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "192.168.1.X"
    
    def show_setup_instructions(self):
        """Display Wix DNS setup instructions."""
        print("\n" + "="*70)
        print("STEP 1: Configure Wix DNS Records")
        print("="*70)
        print()
        print("Go to: https://www.wix.com/dashboard")
        print("  1. Click your site (12sgi.com)")
        print("  2. Go to: Settings → Domains")
        print("  3. Click: Manage DNS")
        print()
        print("ADD THESE DNS RECORDS:")
        print()
        print("Type: A")
        print(f"Name: @ (or 12sgi.com)")
        print(f"Value: {self.king_server_ip}")
        print("TTL: 3600 (1 hour)")
        print()
        print("Type: CNAME")
        print("Name: www")
        print(f"Value: {self.king_server_ip}")
        print("TTL: 3600")
        print()
        print("Type: CNAME")
        print("Name: api")
        print(f"Value: {self.king_server_ip}")
        print("TTL: 3600")
        print()
        print("Type: CNAME")
        print("Name: site")
        print(f"Value: {self.king_server_ip}")
        print("TTL: 3600")
        print()
        print("="*70)
        print("IMPORTANT: Remove any existing forward to elementlotus.com")
        print("="*70)
        print()
        
    def show_hosts_file_setup(self):
        """Show local hosts file setup."""
        local_ip = self.get_local_ip()
        print("\n" + "="*70)
        print("STEP 2: Configure Local Hosts File (For Testing)")
        print("="*70)
        print()
        print("On your local machine, add this to your hosts file:")
        print()
        print(f"Windows: C:\\Windows\\System32\\drivers\\etc\\hosts")
        print(f"macOS/Linux: /etc/hosts")
        print()
        print("Add these lines:")
        print(f"{local_ip}      12sgi.local")
        print(f"{local_ip}      www.12sgi.local")
        print(f"{local_ip}      api.12sgi.local")
        print(f"{local_ip}      site.12sgi.local")
        print()
        print("Then access locally: http://12sgi.local/site/")
        print()
        
    def show_tailscale_access(self):
        """Show Tailscale access information."""
        print("\n" + "="*70)
        print("STEP 3: Access Via Tailscale")
        print("="*70)
        print()
        print(f"Your king-server Tailscale IP: {self.king_server_ip}")
        print()
        print("From any Tailscale device, access:")
        print(f"  http://{self.king_server_ip}:8080/site/")
        print(f"  http://{self.king_server_ip}:8799/api/")
        print(f"  http://{self.king_server_ip}:7474  (Neo4j)")
        print()
        print("Or via hostname:")
        print(f"  http://king.{self.tailnet}:8080/site/")
        print()
        
    def show_remote_access_setup(self):
        """Show how to access from outside Tailscale."""
        print("\n" + "="*70)
        print("STEP 4: Remote Access (Tailscale Funnel - Optional)")
        print("="*70)
        print()
        print("If you want to expose services to internet via Tailscale:")
        print()
        print("On king-server:")
        print("  tailscale funnel --bg http://localhost:8080")
        print("  tailscale funnel --bg http://localhost:8799")
        print()
        print("Then access from anywhere with Tailscale installed:")
        print(f"  https://king--{self.tailnet}/site/")
        print()
        print("Or via direct Tailscale URL:")
        print(f"  https://[{self.king_server_ip}]:443/")
        print()
        
    def show_verification_steps(self):
        """Show how to verify everything works."""
        print("\n" + "="*70)
        print("STEP 5: Verification")
        print("="*70)
        print()
        print("On king-server, run:")
        print("  tailscale status")
        print("  docker compose -f docker-compose.v2.yml ps")
        print("  python verify_neo4j.py")
        print()
        print("From any Tailscale device:")
        print(f"  curl http://{self.king_server_ip}:8080/site/")
        print(f"  curl http://{self.king_server_ip}:8799/api/")
        print()
        print("Check your local machine (after hosts file update):")
        print("  curl http://12sgi.local/site/")
        print()
        
    def show_dns_propagation(self):
        """Show DNS propagation check."""
        print("\n" + "="*70)
        print("STEP 6: DNS Propagation Check")
        print("="*70)
        print()
        print("After updating Wix DNS, check propagation:")
        print()
        print("PowerShell:")
        print("  nslookup 12sgi.com")
        print("  nslookup www.12sgi.com")
        print("  nslookup api.12sgi.com")
        print()
        print("Or online:")
        print("  https://www.whatsmydns.net/")
        print()
        print("DNS typically takes 1-24 hours to propagate worldwide.")
        print()
        
    def show_architecture(self):
        """Show the complete architecture."""
        print("\n" + "="*70)
        print("YOUR HOSTING ARCHITECTURE")
        print("="*70)
        print()
        print("┌─────────────────────────────────────────────┐")
        print("│ 12sgi.com Domain (Wix)                      │")
        print("└──────────────┬──────────────────────────────┘")
        print("               │ DNS A Record Points To:")
        print("               ↓")
        print("┌──────────────────────────────────────────────┐")
        print("│ Tailscale Private Network                    │")
        print("│ tail760750.ts.net                            │")
        print("└──────────────┬───────────────────────────────┘")
        print("               │")
        print("               ↓")
        print("┌──────────────────────────────────────────────┐")
        print("│ King-Server (100.124.152.3)                 │")
        print("│                                              │")
        print("│ ├─ Port 8080: Web Server (dashboards)       │")
        print("│ ├─ Port 8799: Board API                     │")
        print("│ ├─ Port 8101-8109: V2 Services              │")
        print("│ ├─ Port 7474: Neo4j                         │")
        print("│ └─ Port 9000: CI/CD Webhook                 │")
        print("└──────────────────────────────────────────────┘")
        print()
        print("KEY BENEFITS:")
        print("  ✅ No internet-exposed ports")
        print("  ✅ Tailscale encryption (WireGuard)")
        print("  ✅ Zero billing issues (Tailscale free tier)")
        print("  ✅ Only devices in tailnet can access")
        print("  ✅ Complete control of infrastructure")
        print()
        
    def create_checklist(self):
        """Create a checklist document."""
        checklist = """# 12sgi.com Tailscale Hosting - Checklist

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
- [ ] Edit your hosts file (C:\\Windows\\System32\\drivers\\etc\\hosts)
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
"""
        
        Path("TAILSCALE_HOSTING_CHECKLIST.md").write_text(checklist)
        return checklist
    
    def run(self):
        """Run complete setup."""
        print("\n" + "="*70)
        print("🚀 12sgi.com Tailscale Hosting Setup")
        print("="*70)
        
        self.show_architecture()
        self.show_setup_instructions()
        self.show_hosts_file_setup()
        self.show_tailscale_access()
        self.show_remote_access_setup()
        self.show_verification_steps()
        self.show_dns_propagation()
        
        print("\n" + "="*70)
        print("CREATING CHECKLIST")
        print("="*70)
        self.create_checklist()
        print("✓ Saved: TAILSCALE_HOSTING_CHECKLIST.md")
        
        print("\n" + "="*70)
        print("NEXT STEPS:")
        print("="*70)
        print()
        print("1. Read: TAILSCALE_HOSTING_CHECKLIST.md")
        print("2. Go to Wix and update DNS records")
        print("3. Wait for DNS propagation (1-24 hours)")
        print("4. Test from a Tailscale device")
        print("5. Verify 12sgi.com works!")
        print()
        print("Questions? Check:")
        print("  - TAILSCALE_DEPLOYMENT_COMPLETE.md")
        print("  - TAILSCALE_SETUP_GUIDE.md")
        print()

if __name__ == "__main__":
    setup = TailscaleHostingSetup()
    setup.run()
