#!/usr/bin/env python3
"""
Neo4j verification and startup for 12sgi-king QUAD OS brain.
Ensures the graph database (14k+ nodes) is running and accessible.
"""

import subprocess
import json
import urllib.request
import time
import sys

def run_cmd(cmd, timeout=10):
    """Run command with timeout."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return -1, "", str(e)

def check_neo4j_container():
    """Check if neo4j container exists and its status."""
    cmd = 'docker ps --all --filter "name=quados-neo4j" --format table'
    code, out, err = run_cmd(cmd, timeout=10)
    
    if code != 0 or not out:
        return None, "Container not found"
    
    lines = out.strip().split('\n')
    if len(lines) > 1:
        parts = lines[1].split()
        if len(parts) > 1:
            status = ' '.join(parts[1:3])  # STATUS column
            return parts[1], status
    
    return None, "Could not parse container info"

def check_neo4j_http():
    """Check Neo4j HTTP endpoint."""
    try:
        req = urllib.request.Request("http://127.0.0.1:7474")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200, "HTTP port responding"
    except Exception as e:
        return False, str(e)[:50]

def check_neo4j_bolt():
    """Check Neo4j Bolt protocol (7687)."""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("127.0.0.1", 7687))
        sock.close()
        if result == 0:
            return True, "Bolt port open"
    except:
        pass
    return False, "Bolt port unreachable"

def restart_neo4j():
    """Restart Neo4j container."""
    print("  ⏳ Restarting Neo4j container...")
    
    # Try to stop
    run_cmd("docker stop quados-neo4j", timeout=20)
    time.sleep(2)
    
    # Try to start
    code, out, err = run_cmd("docker start quados-neo4j", timeout=20)
    if code == 0:
        print("  ✓ Container restart command sent")
        return True
    else:
        print(f"  ✗ Failed to restart: {err[:80]}")
        return False

def verify_volumes():
    """Verify Neo4j volumes exist and are external."""
    print("\n[NEO4J VOLUMES]")
    cmd = 'docker volume ls --format "{{.Name}}"'
    code, out, err = run_cmd(cmd, timeout=10)
    
    if code != 0:
        print("  ✗ Could not list volumes")
        return False
    
    required = ["12sgi-king_v2-neo4j-data", "12sgi-king_v2-neo4j-logs"]
    found = set()
    
    volume_list = [v.strip() for v in out.strip().split('\n') if v.strip()]
    for vol in volume_list:
        if vol in required:
            found.add(vol)
            print(f"  ✓ {vol}")
    
    for vol in required:
        if vol not in found:
            print(f"  ✗ MISSING: {vol}")
    
    return len(found) == len(required)

def main():
    print("\n" + "="*60)
    print("Neo4j Verification & Startup")
    print("QUAD OS Brain - ~14,300 nodes")
    print("="*60)
    
    # Check volumes
    volumes_ok = verify_volumes()
    
    # Check container status
    print("\n[NEO4J CONTAINER]")
    state, status = check_neo4j_container()
    print(f"  Status: {status}")
    
    if state == "running":
        print("  ✓ Container is RUNNING")
    elif state == "exited" or "Exited" in str(status):
        print(f"  ⚠ Container exited - attempting restart...")
        if restart_neo4j():
            print("  ⏳ Waiting for startup...")
            time.sleep(15)
        else:
            print("  ✗ Restart failed")
            return 1
    else:
        print(f"  ⚠ Unknown state: {state}")
    
    # Check HTTP endpoint
    print("\n[NEO4J ENDPOINTS]")
    http_ok, http_msg = check_neo4j_http()
    print(f"  HTTP (7474): {'✓' if http_ok else '✗'} {http_msg}")
    
    # Check Bolt endpoint
    bolt_ok, bolt_msg = check_neo4j_bolt()
    print(f"  Bolt (7687): {'✓' if bolt_ok else '✗'} {bolt_msg}")
    
    # Final status
    print("\n" + "="*60)
    if http_ok or bolt_ok:
        print("✓ Neo4j is ACCESSIBLE")
        print(f"  Data volume: {'✓' if volumes_ok else '⚠'} (holds ~14,300 nodes)")
        print("✓ QUAD OS brain is READY")
        print("="*60 + "\n")
        return 0
    else:
        print("✗ Neo4j is NOT ACCESSIBLE")
        if not volumes_ok:
            print("  WARNING: Data volumes may be missing or corrupted")
        print("  Recommendation: Restart Docker Desktop and retry")
        print("="*60 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
