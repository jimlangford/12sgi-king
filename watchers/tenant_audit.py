#!/usr/bin/env python3
# tenant_audit.py - run ONE govOS tenant's audit chain, CPU-balanced.
#   Acquires the cpu_lock (one tenant at a time; yields if the box is busy), runs that
#   tenant's step list from tenants.json, regenerates its pages, releases the lock.
#   This is the per-tenant "constant prosecutorial push" balanced across CPU like the
#   GPU work is balanced one-at-a-time.
#
#   python tenant_audit.py --tenant hi-maui
#   python tenant_audit.py --all          # every tenant, sequential (still one-at-a-time)
import argparse, importlib, json, os, sys, time
from datetime import datetime, timedelta, timezone

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
HOME     = os.path.expanduser("~")
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
DISPATCH = os.path.join(PROJECT, ".dispatch_log.jsonl")
HST      = timezone(timedelta(hours=-10))
if TOOL_DIR not in sys.path: sys.path.insert(0, TOOL_DIR)

def now_hst(): return datetime.now(HST)
def dispatch(tag, msg):
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "kilo-aupuni", "event": f"{tag}: {msg}"}, ensure_ascii=False) + "\n")
    except Exception: pass

def tenants():
    return json.load(open(os.path.join(TOOL_DIR, "tenants.json"), encoding="utf-8"))["tenants"]

def run_step(step):
    try:
        if step == "watchers":
            import kilo_aupuni; importlib.reload(kilo_aupuni)
            reg = kilo_aupuni.load_registry()
            kilo_aupuni.run_live_watchers(reg); kilo_aupuni.build_dashboard(reg)
            return True
        m = importlib.import_module(step); importlib.reload(m)
        if hasattr(m, "main"): m.main()
        return True
    except Exception as e:
        dispatch("FINDING", f"tenant_audit step '{step}' failed: {e}")
        print(f"   x {step}: {e}"); return False

def audit_tenant(t):
    from cpu_lock import CPULock, cpu_percent
    lock = CPULock(f"audit:{t['id']}")
    if not lock.acquire(block=True, timeout=2400):
        print(f"[{t['id']}] CPU busy / another tenant auditing - skipping this run"); return 1
    print(f"=== audit {t['id']} ({t['name']}) | CPU {cpu_percent():.0f}% | {now_hst():%H:%M HST} ===")
    dispatch("FINDING", f"tenant_audit START {t['id']} ({t['name']})")
    try:
        for step in t.get("steps", []):
            ok = run_step(step); print(f"   {'+' if ok else 'x'} {step}")
        try:
            import tenant_pages; importlib.reload(tenant_pages)
            tenant_pages.gen(t); tenant_pages.build_hub(tenants())
            print("   + pages")
        except Exception as e:
            dispatch("FINDING", f"tenant_audit pages {t['id']} failed: {e}"); print(f"   x pages: {e}")
    finally:
        lock.release()
    dispatch("SHIPPED", f"tenant_audit DONE {t['id']} ({t['name']}) - publish={t.get('publish')}")
    return 0

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--tenant"); g.add_argument("--all", action="store_true")
    a = ap.parse_args()
    ts = tenants()
    targets = ts if a.all else [t for t in ts if t["id"] == a.tenant]
    if not targets: print(f"unknown tenant '{a.tenant}'"); return 1
    for t in targets:
        audit_tenant(t)
    return 0

if __name__ == "__main__":
    sys.exit(main())
