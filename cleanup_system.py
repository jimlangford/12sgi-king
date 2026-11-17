#!/usr/bin/env python3
"""Preview stale runtime artifacts; delete only with --execute. Never prune volumes."""

import argparse
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent


def candidates(root, min_age_hours=24, python_cache=False):
    """Return old, untracked, non-symlink artifacts, failing closed without Git."""
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, check=True, timeout=30
    )
    tracked_paths = set(tracked.stdout.decode("utf-8").split("\0"))
    paths = list(root.glob(".dispatch_cursor_*.txt"))
    if python_cache:
        paths.extend(p for p in root.rglob("*.pyc") if p.parent.name == "__pycache__")
    cutoff = time.time() - min_age_hours * 3600
    for path in sorted(set(paths)):
        relative = path.relative_to(root)
        if any(part in {".git", ".venv", "venv", "node_modules"} for part in relative.parts):
            continue
        if any(p.is_symlink() for p in (path, *path.parents)):
            continue
        if (relative.as_posix() not in tracked_paths and path.is_file()
                and path.stat().st_mtime < cutoff):
            yield path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true", help="Preview only (default)")
    mode.add_argument("--execute", action="store_true", help="Delete listed stale artifacts")
    parser.add_argument("--min-age-hours", type=int, default=24)
    parser.add_argument("--python-cache", action="store_true", help="Include stale untracked bytecode")
    parser.add_argument("--docker-cache", action="store_true",
                        help="Also inspect/prune Docker build cache older than seven days")
    args = parser.parse_args(argv)
    if args.min_age_hours < 1:
        parser.error("--min-age-hours must be at least 1")
    try:
        files = list(candidates(HERE, args.min_age_hours, args.python_cache))
        total = sum(path.stat().st_size for path in files)
        print(f"{'DELETE' if args.execute else 'PREVIEW'}: {len(files)} stale files, {total:,} bytes")
        for path in files:
            print(path.relative_to(HERE))
            if args.execute:
                path.unlink()
        if args.docker_cache:
            command = (["docker", "builder", "prune", "--force", "--filter", "until=168h"]
                       if args.execute else ["docker", "system", "df"])
            subprocess.run(command, check=True, timeout=300)
        disk = shutil.disk_usage(HERE)
        used = disk.used / disk.total * 100
        print(f"Disk used: {used:.1f}%; free: {disk.free / 1024**3:.1f} GiB")
        if used >= 85:
            print("Owner action needed: disk remains at or above 85%; inspect Docker usage/backups.")
        return 0
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        print(f"Cleanup stopped: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
