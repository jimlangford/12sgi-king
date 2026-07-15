#!/usr/bin/env python3
"""
Cleanup script — remove duplication and optimize disk/memory.
Production system audit cleanup.

Run: python cleanup_system.py --verify first, then --execute
"""

import os
import shutil
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent

# Files to delete (absolute disk duplication)
DELETE_FILES = [
    "docker-compose.v2.yml.clean",
    "docker-compose.postiz.yml",
    "HEALING_README.py",
    "HEALING_LINKS.py",
    "GORDON_README.py",
    "fix_compose.py",
    "fix_static.py",
    "fix_yaml_validator.py",
    "add_monitor_service.py",
    "add_static.py",
    "rebuild_site.py",
    "SETUP.md",
    "TEST_AUTONOMOUS_REPAIRS.md",
    "services/github_auto_repair.py",
    "services/github_error_scanner.py",
    "services/github_repair_archetypes.py",
]

# Patterns to clean (.dispatch_cursor_*.txt)
PATTERNS_TO_DELETE = [
    ".dispatch_cursor_*.txt",
]

def verify():
    """Preview what will be deleted."""
    print("=" * 80)
    print("CLEANUP VERIFICATION — What will be deleted:")
    print("=" * 80)
    
    total_size = 0
    file_count = 0
    
    for f in DELETE_FILES:
        path = HERE / f
        if path.exists():
            size = path.stat().st_size
            total_size += size
            file_count += 1
            print(f"  ✗ {f} ({size:,} bytes)")
    
    # Handle patterns
    import glob
    for pattern in PATTERNS_TO_DELETE:
        matches = list(HERE.glob(pattern))
        for match in matches:
            if match.is_file():
                size = match.stat().st_size
                total_size += size
                file_count += 1
                print(f"  ✗ {match.name} ({size:,} bytes)")
    
    print(f"\nTotal: {file_count} files, {total_size:,} bytes ({total_size / 1024 / 1024:.1f} MB)")
    print("\nRun with --execute to proceed")

def execute():
    """Actually delete files."""
    print("=" * 80)
    print("EXECUTING CLEANUP...")
    print("=" * 80)
    
    deleted = []
    
    # Delete specific files
    for f in DELETE_FILES:
        path = HERE / f
        if path.exists():
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                deleted.append(f)
                print(f"  ✓ Deleted: {f}")
            except Exception as e:
                print(f"  ✗ Failed to delete {f}: {e}")
    
    # Handle patterns
    import glob
    for pattern in PATTERNS_TO_DELETE:
        matches = list(HERE.glob(pattern))
        for match in matches:
            if match.is_file():
                try:
                    match.unlink()
                    deleted.append(match.name)
                    print(f"  ✓ Deleted: {match.name}")
                except Exception as e:
                    print(f"  ✗ Failed to delete {match.name}: {e}")
    
    print(f"\n✓ Cleanup complete: {len(deleted)} files deleted")
    print("\nVerify system still works:")
    print("  python king-watchdog.py")
    print("  curl http://localhost:8799/health")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python cleanup_system.py [--verify|--execute]")
        print("  --verify   Show what will be deleted (no changes)")
        print("  --execute  Actually delete files")
        sys.exit(1)
    
    if sys.argv[1] == "--verify":
        verify()
    elif sys.argv[1] == "--execute":
        execute()
    else:
        print(f"Unknown option: {sys.argv[1]}")
        sys.exit(1)
