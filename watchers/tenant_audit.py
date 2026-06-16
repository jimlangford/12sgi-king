#!/usr/bin/env python3
# tenant_audit.py - run ONE govOS tenant's audit chain, CPU-balanced.
#   Acquires the cpu_lock (one tenant at a time; yields if the box is busy), runs that
#   tenant's step list from tenants.json, regenerates its pages, releases the lock.
#   This is the per-tenant "constant prosecutorial push" balanced across CPU like the
#   GPU work is balanced one-at-a-time.
#
#   python tenant_audit.py --tenant hi-maui
#   python tenant_audit.py --all          # every tenant, sequential (still one-at-a-time)
import argparse, importlib, io, json, os, sys, time
from datetime import datetime, timedelta, timezone

# tenant names carry ʻokina (ʻ); the Windows console is cp1252 and will crash on print.
if sys.platform == "win32":
    try: sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception: pass

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
    t0 = time.perf_counter(); step_times = {}
    try:
        print(f"=== audit {t['id']} ({t['name']}) | CPU {cpu_percent():.0f}% | {now_hst():%H:%M HST} ===")
        dispatch("FINDING", f"tenant_audit START {t['id']} ({t['name']})")
        for step in t.get("steps", []):
            s = time.perf_counter(); ok = run_step(step); dt = round(time.perf_counter() - s, 1)
            step_times[step] = dt; print(f"   {'+' if ok else 'x'} {step}  ({dt}s)")
        try:
            s = time.perf_counter()
            import tenant_pages; importlib.reload(tenant_pages)
            tenant_pages.gen(t); tenant_pages.build_hub(tenants())
            step_times["pages"] = round(time.perf_counter() - s, 1); print(f"   + pages  ({step_times['pages']}s)")
        except Exception as e:
            dispatch("FINDING", f"tenant_audit pages {t['id']} failed: {e}"); print(f"   x pages: {e}")
    finally:
        lock.release()
    total = round(time.perf_counter() - t0, 1)
    _record_timing(t, total, step_times)
    print(f"=== {t['id']} full update: {total}s ({total/60:.1f} min) ===")
    dispatch("SHIPPED", f"tenant_audit DONE {t['id']} ({t['name']}) in {total}s ({total/60:.1f}min) - publish={t.get('publish')}")
    return 0

def _record_timing(t, total, step_times):
    """Persist per-tenant durations so the staggered schedule can be tuned to reality."""
    p = os.path.join(PROJECT, "reports", "mauios", "tenant_timings.json")
    try:
        data = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    except Exception:
        data = {}
    data[t["id"]] = {"name": t["name"], "last_run": now_hst().strftime("%Y-%m-%d %H:%M HST"),
                     "total_s": total, "total_min": round(total / 60, 1),
                     "sched_hour": t.get("sched_hour"), "steps_s": step_times}
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(p + ".tmp", p)
    except Exception: pass

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
