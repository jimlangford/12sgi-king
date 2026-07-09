#!/usr/bin/env python3
"""civic_ingest_assist.py — ANY thread releases pressure on the system by ingesting the next civic-tenant
gap (Jimmy 2026-06-18: "this thread can also ingest civic data to release pressure ... learn this as a
self-heal across threads to keep working").

The 6 scheduled per-tenant tasks + the daily cycle do the baseline ingest. But onboarding shouldn't wait
only on them — when ANY live thread (claude-home / studio / audit / a cowork session) has spare capacity,
it runs this to pick the highest-priority onboarding gap and ingest it. Safe by construction:

  • tenant_audit acquires the CPULock (one tenant at a time, yields if the box is busy) — so two threads
    can NEVER double-run a tenant or oversubscribe the CPU. If busy, this YIELDS (releases pressure by NOT
    piling on) rather than fighting.
  • picks the lowest-% (thinnest) tenant first — pushes the real remaining onboarding (NY, then State).
  • refreshes tenant_depth + the onboarding ratchet after, so the gain shows + the board stays current.

CPU only; never GPU; never interrupts a render (the lock + the box-busy yield cover it). Run from any thread:
  python civic_ingest_assist.py --source claude-home-thread        # pick + ingest the priority gap
  python civic_ingest_assist.py --tenant ny --source <thread>      # target a specific gap
"""
import os, sys, json, subprocess
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
ST = os.path.join(PROJ, "reports", "_status")
HST = timezone(timedelta(hours=-10))
PY = sys.executable
NW = 0x08000000 if os.name == "nt" else 0


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def pick_gap():
    """The highest-priority onboarding gap: lowest % first (push the real remaining work)."""
    d = load(os.path.join(ST, "tenant_depth.json"), {})
    short = [t for t in d.get("tenants", []) if t.get("pct", 0) < 100]
    short.sort(key=lambda t: (t.get("pct", 0), t.get("id", "")))
    return (short[0]["id"], short[0].get("pct", 0)) if short else (None, None)


def _run(args, timeout):
    try:
        r = subprocess.run([PY, "-X", "utf8"] + args, cwd=PROJ, capture_output=True, text=True,
                           timeout=timeout, creationflags=NW)
        return r.returncode, (r.stdout or "")[-400:]
    except Exception as e:
        return 1, str(e)[:200]


def _dispatch(msg, source):
    try:
        subprocess.run([PY, os.path.join(PROJ, "app", "server", "dispatch.py"), PROJ,
                        "--log-event", msg, "--source", source],
                       capture_output=True, timeout=30, creationflags=NW)
    except Exception:
        pass


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="")
    ap.add_argument("--source", default="claude-home-thread")
    a, _ = ap.parse_known_args()

    tid, pct = (a.tenant, None) if a.tenant else pick_gap()
    if not tid:
        print("civic_ingest_assist: all civic tenants at full depth — nothing to assist. ✓")
        return 0
    print("civic_ingest_assist[%s]: assisting ingest of %s (%s) — lock-coordinated, yields if busy"
          % (a.source, tid, ("%d%%" % pct) if pct is not None else "targeted"))

    # the CPULock inside tenant_audit makes this safe from any thread (no double-run / no oversubscribe)
    rc, tail = _run([os.path.join("tools", "kilo-aupuni", "tenant_audit.py"), "--tenant", tid], 2400)
    if "CPU busy" in tail or rc != 0 and "busy" in tail.lower():
        print("  yielded — box busy / another tenant auditing (pressure released, no pile-on).")
        return 0
    # refresh the depth + ratchet so the gain shows + the board updates
    _run([os.path.join("tools", "kilo-aupuni", "tenant_depth.py")], 180)
    _run([os.path.join("tools", "kilo-aupuni", "tenant_onboard_ratchet.py")], 120)

    dep = load(os.path.join(ST, "tenant_depth.json"), {})
    now = next((t for t in dep.get("tenants", []) if t.get("id") == tid), {})
    _dispatch("FINDING (cross-thread ingest assist): %s ingested civic tenant %s (now %d%% depth, rc=%s) to "
              "release pressure + keep onboarding advancing. Any thread runs civic_ingest_assist.py when idle."
              % (a.source, tid, now.get("pct", 0), rc), a.source)
    print("  done: %s now %d%% depth (rc=%s)" % (tid, now.get("pct", 0), rc))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
