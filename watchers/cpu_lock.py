#!/usr/bin/env python3
# cpu_lock.py - Kilo Aupuni CPU work balancer (the CPU analog of batch/gpu_lock.py).
#   The "constant prosecutorial push" runs ONE tenant audit at a time and yields when
#   the machine CPU is already busy - so the recurring per-tenant audits never thrash
#   the box (just like renders + LoRA training are one-at-a-time on the GPU).
#
# Usage:
#   from cpu_lock import CPULock
#   lock = CPULock("audit:hi-maui")
#   if not lock.acquire(block=True, timeout=1800): sys.exit(0)   # someone else is auditing
#   try: ... run this tenant's chain ...  finally: lock.release()
#
#   python cpu_lock.py check     -> exit 0 if free, 1 if locked
#   python cpu_lock.py release   -> force-release a stale lock
#   python cpu_lock.py busy 70   -> exit 0 if CPU < 70%, 1 if busier (gate before heavy work)
import json, os, sys, time, subprocess
from datetime import datetime

PROJECT = os.environ.get("LOTUS_ROOT",
    r"C:\Users\12sgi\Documents\Claude\Projects\Video System elementLOTUS")
LOCK_PATH = os.path.join(PROJECT, ".cpu_lock")
STALE_AFTER_HOURS = 4          # an audit cycle should never run > 4h; older = crashed
CPU_BUSY_DEFAULT = 75          # yield if system CPU is above this %

def _pid_alive(pid):
    try:
        os.kill(pid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True
    except OSError: return False

def _write(name, pid):
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        json.dump({"name": name, "pid": pid,
                   "acquired": datetime.now().isoformat(timespec="seconds")}, f)

def _remove():
    try: os.remove(LOCK_PATH)
    except FileNotFoundError: pass

def _check():
    if not os.path.exists(LOCK_PATH): return False, {}
    try:
        owner = json.load(open(LOCK_PATH, encoding="utf-8"))
    except Exception:
        _remove(); return False, {}
    pid = owner.get("pid")
    if pid and not _pid_alive(pid):
        _remove(); return False, {}
    try:
        age = (datetime.now() - datetime.fromisoformat(owner["acquired"])).total_seconds() / 3600
        if age > STALE_AFTER_HOURS:
            _remove(); return False, {}
    except Exception: pass
    return True, owner

def cpu_percent():
    """Best-effort system CPU load %, stdlib-only. Returns 0.0 if unknowable."""
    try:
        import psutil
        return float(psutil.cpu_percent(interval=0.5))
    except Exception:
        pass
    try:    # Windows wmic fallback
        out = subprocess.run(["wmic", "cpu", "get", "loadpercentage", "/value"],
                             capture_output=True, text=True, timeout=8).stdout
        for ln in out.splitlines():
            if "LoadPercentage" in ln:
                return float(ln.split("=")[1].strip())
    except Exception:
        pass
    return 0.0

def cpu_busy(threshold=CPU_BUSY_DEFAULT):
    return cpu_percent() >= float(threshold)

class CPULock:
    def __init__(self, name):
        self.name = name; self.pid = os.getpid()
    def acquire(self, block=False, timeout=1800, yield_if_busy=True, busy_threshold=CPU_BUSY_DEFAULT):
        deadline = time.time() + timeout
        while True:
            locked, owner = _check()
            if not locked:
                # don't pile on if the box is already busy (the CPU-balance rule)
                if yield_if_busy and cpu_busy(busy_threshold):
                    if not block or time.time() > deadline: return False
                    time.sleep(20); continue
                _write(self.name, self.pid); return True
            if owner.get("pid") == self.pid: return True
            if not block or time.time() > deadline: return False
            time.sleep(15)
    def release(self):
        locked, owner = _check()
        if locked and owner.get("pid") == self.pid: _remove()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "release":
        _remove(); print("[cpu_lock] released"); sys.exit(0)
    if cmd == "busy":
        thr = float(sys.argv[2]) if len(sys.argv) > 2 else CPU_BUSY_DEFAULT
        p = cpu_percent(); print(f"[cpu_lock] CPU {p:.0f}% (threshold {thr:.0f}%)")
        sys.exit(1 if p >= thr else 0)
    locked, owner = _check()
    if locked:
        print(f"[cpu_lock] LOCKED by {owner.get('name')} pid={owner.get('pid')} since {owner.get('acquired')}")
        sys.exit(1)
    print("[cpu_lock] free"); sys.exit(0)
