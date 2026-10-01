#!/usr/bin/env python3
"""
12sgi-king Local CI/CD Quick Start
Run this to start your complete self-hosted deployment system.
"""

import subprocess
import os
import sys
from pathlib import Path

REPO_PATH = Path("C:/Users/12sgi/actions-runner/_work/12sgi-king/12sgi-king")
os.chdir(REPO_PATH)

print("=" * 70)
print("🚀 12sgi-king Local CI/CD System - Quick Start")
print("=" * 70)
print()

# Check prerequisites
print("✓ Checking prerequisites...")
try:
    subprocess.run(["docker", "--version"], capture_output=True, check=True)
    print("  ✓ Docker installed")
except:
    print("  ❌ Docker not found")
    sys.exit(1)

try:
    subprocess.run(["git", "--version"], capture_output=True, check=True)
    print("  ✓ Git installed")
except:
    print("  ❌ Git not found")
    sys.exit(1)

try:
    subprocess.run(["python", "--version"], capture_output=True, check=True)
    print("  ✓ Python installed")
except:
    print("  ❌ Python not found")
    sys.exit(1)

print()
print("✓ All prerequisites met!")
print()

# Show what's about to start
print("=" * 70)
print("STARTING SYSTEMS:")
print("=" * 70)
print()
print("System 1: Local CI/CD Server")
print("  Command: python local_ci_cd_server.py")
print("  Purpose: Webhook receiver, deployment orchestrator")
print("  Listens: 0.0.0.0:9000/webhook")
print("  Logs: logs/ci-cd/*.log")
print()

print("System 2: Service Auto-Recovery Monitor")
print("  Command: python service_auto_recovery.py")
print("  Purpose: Health monitoring, auto-restart failed services")
print("  Interval: Every 30 seconds")
print("  Max restarts: 3 per service")
print()

print("=" * 70)
print("Instructions:")
print("=" * 70)
print()
print("1. This script will open TWO new terminal windows")
print("2. Keep BOTH windows open - they run continuously")
print("3. When you git push to main, deployment starts automatically")
print("4. Check logs: cat logs/ci-cd/deployments.jsonl")
print()

input("Press ENTER to continue...")

# Start services in new terminals
import threading
import time

def start_cicd_server():
    """Start CI/CD server in new terminal."""
    if sys.platform == "win32":
        subprocess.Popen([
            "powershell", "-NoExit", "-Command",
            f"cd '{REPO_PATH}'; python local_ci_cd_server.py"
        ])
    else:
        subprocess.Popen([
            "gnome-terminal", "--", "bash", "-c",
            f"cd {REPO_PATH} && python local_ci_cd_server.py; bash"
        ])

def start_auto_recovery():
    """Start auto-recovery in new terminal."""
    time.sleep(2)  # Stagger start
    if sys.platform == "win32":
        subprocess.Popen([
            "powershell", "-NoExit", "-Command",
            f"cd '{REPO_PATH}'; python service_auto_recovery.py"
        ])
    else:
        subprocess.Popen([
            "gnome-terminal", "--", "bash", "-c",
            f"cd {REPO_PATH} && python service_auto_recovery.py; bash"
        ])

print()
print("✅ Starting systems...")
print()

t1 = threading.Thread(target=start_cicd_server, daemon=True)
t2 = threading.Thread(target=start_auto_recovery, daemon=True)

t1.start()
t2.start()

print("✅ CI/CD Server starting...")
print("✅ Auto-Recovery Monitor starting...")
print()
print("=" * 70)
print("✅ Local CI/CD System is running!")
print("=" * 70)
print()
print("Next steps:")
print()
print("1. Check status:")
print("   python status_dashboard.py")
print()
print("2. Make a change and push:")
print("   git add .")
print("   git commit -m 'Test local CI/CD'")
print("   git push origin main")
print()
print("3. Monitor deployment:")
print("   Get-Content logs/ci-cd/deployments.jsonl -Tail 1")
print()
print("4. View all logs:")
print("   Get-Content logs/ci-cd/ci-cd-*.log")
print()
print("=" * 70)
print()

# Keep main process alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Stopping...")
