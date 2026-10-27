#!/usr/bin/env python3
"""
Start 12sgi.com local server in background (non-blocking).
Can be called from CI/CD without stopping the workflow.
"""

import subprocess
import time
import sys
import os
from pathlib import Path

def start_server_bg(port=8080):
    """Start server in background subprocess."""
    script = Path(__file__).parent / "local_server.py"
    
    if not script.exists():
        print(f"✗ ERROR: {script} not found")
        return False
    
    try:
        # Start process in background (detached on Windows)
        if sys.platform == 'win32':
            # Windows: use CREATE_NEW_PROCESS_GROUP
            proc = subprocess.Popen(
                [sys.executable, str(script), '--port', str(port), '--bg'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )
        else:
            # Unix: use preexec_fn
            proc = subprocess.Popen(
                [sys.executable, str(script), '--port', str(port), '--bg'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
        
        print(f"✓ Server starting on port {port} (PID: {proc.pid})")
        time.sleep(2)  # Give server time to start
        
        # Check if it's still running
        if proc.poll() is None:
            print(f"✓ Server running in background (port {port})")
            return True
        else:
            stdout, stderr = proc.communicate()
            print(f"✗ Server failed to start:")
            if stdout:
                print(f"  stdout: {stdout.decode()[:200]}")
            if stderr:
                print(f"  stderr: {stderr.decode()[:200]}")
            return False
    
    except Exception as e:
        print(f"✗ Failed to start server: {e}")
        return False

def setup_hosts(hostname='12sgi.com', ip='127.0.0.1'):
    """Add hostname to Windows hosts file (requires admin)."""
    hosts_path = Path("C:\\Windows\\System32\\drivers\\etc\\hosts")
    
    if not hosts_path.exists():
        print(f"⚠ Hosts file not found: {hosts_path}")
        return False
    
    try:
        content = hosts_path.read_text()
        
        # Check if already exists
        for line in content.split('\n'):
            if hostname in line and not line.strip().startswith('#'):
                print(f"✓ Hostname already in hosts: {line.strip()}")
                return True
        
        # Try to add (may fail without admin)
        new_line = f"{ip} {hostname} www.{hostname}"
        try:
            with open(hosts_path, 'a') as f:
                f.write(f"\n{new_line}\n")
            print(f"✓ Added to hosts: {new_line}")
            return True
        except PermissionError:
            print(f"⚠ Admin required to modify hosts file")
            print(f"  Manual: Add to C:\\Windows\\System32\\drivers\\etc\\hosts:")
            print(f"  {new_line}")
            return False
    
    except Exception as e:
        print(f"✗ Error updating hosts: {e}")
        return False

def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='Start 12sgi.com local server (non-blocking)')
    parser.add_argument('--port', type=int, default=8080, help='Port (default: 8080)')
    parser.add_argument('--hosts', action='store_true', help='Try to add 12sgi.com to hosts file')
    args = parser.parse_args()
    
    print(f"\n{'='*70}")
    print(f"Starting 12sgi.com Local Server (Non-Blocking)")
    print(f"{'='*70}\n")
    
    # Start server
    if not start_server_bg(args.port):
        print("✗ Failed to start server")
        return 1
    
    # Update hosts if requested
    if args.hosts:
        setup_hosts()
    
    print(f"\n{'='*70}")
    print(f"✓ Server ready!")
    print(f"  http://localhost:{args.port}/")
    print(f"  http://127.0.0.1:{args.port}/")
    print(f"  (optional) http://12sgi.com:{args.port}/")
    print(f"\nServer runs in background - CI/CD won't block")
    print(f"{'='*70}\n")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
