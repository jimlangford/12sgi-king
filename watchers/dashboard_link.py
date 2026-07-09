#!/usr/bin/env python3
"""dashboard_link.py — make the emailed dashboard LINK actually work (Jimmy 2026-06-20: "Yes to Tailscale
and have a fall back fix server immediately then a report send if link isn't working after but it needs to
work").

The daily review email links the prosecutor dashboard over Tailscale (private, owner devices only) instead
of attaching it. To guarantee the link WORKS, ensure() runs a self-heal before the email goes out:
  1. make sure the dashboard file is present in king-local (regenerate via cases_crosscheck if missing)
  2. health-check localhost:8799/<file> — this is exactly what the Tailscale /king path proxies to
  3. if it's not 200, FIX THE SERVER immediately: relaunch king_serve windowless (same call the supervisor
     uses), wait, re-check
  4. return whether the link is healthy; the caller links it if healthy, or ATTACHES the dashboard as a
     guaranteed fallback + reports the server problem if it still isn't

Stdlib only; windowless-safe (no popup); private.
"""
import os, sys, time, ssl, urllib.request

HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
KING_EXTRACT = os.path.join(HOME, "AppData", "Local", "king-extract", "deploy", "king-local")
KING_SERVE = os.path.join(HOME, "AppData", "Local", "king-extract", "king_serve.py")
LOGS = os.path.join(PROJ, "logs")
FILE = "prosecutor_dashboard.html"
LOCAL = "http://127.0.0.1:8799/%s" % FILE                     # what /king proxies to (laptop ground truth)
TAILSCALE = "https://12sgianonymous.tail760750.ts.net/king/%s" % FILE  # the link Jimmy taps
NW = 0x08000000 if os.name == "nt" else 0


def _king_dir():
    for d in (KING_EXTRACT, os.path.join(PROJ, "king-local")):
        if os.path.isdir(d):
            return d
    return None


def check(url=LOCAL, timeout=6):
    try:
        r = urllib.request.urlopen(url, timeout=timeout, context=ssl.create_default_context())
        return r.getcode() == 200
    except Exception:
        return False


def ensure_file():
    """Regenerate the dashboard into king-local if it's missing (so the link never 404s on a stale build)."""
    kd = _king_dir()
    if kd and os.path.exists(os.path.join(kd, FILE)):
        return True
    try:
        sys.path.insert(0, os.path.join(PROJ, "tools", "kilo-aupuni"))
        import cases_crosscheck
        cases_crosscheck.main()
        return bool(kd and os.path.exists(os.path.join(kd, FILE)))
    except Exception:
        return False


def fix_server():
    """Relaunch king_serve windowless — the SAME detached call the supervisor uses. Returns True on launch."""
    import subprocess
    ks = KING_SERVE
    cwd = os.path.dirname(ks) if os.path.isdir(os.path.dirname(ks)) else PROJ
    if not os.path.exists(ks):
        return False
    try:
        os.makedirs(LOGS, exist_ok=True)
        subprocess.Popen([sys.executable, "-X", "utf8", ks], cwd=cwd,
                         stdout=open(os.path.join(LOGS, "king_serve.out"), "a"),
                         stderr=subprocess.STDOUT, creationflags=NW, close_fds=True)
        return True
    except Exception:
        return False


def ensure():
    """Return {ok, url, healed, action[]}. Self-heals the server so the Tailscale link works."""
    action = []
    if not ensure_file():
        action.append("dashboard file missing + could not regenerate")
    if check():
        return {"ok": True, "url": TAILSCALE, "healed": False, "action": action or ["served"]}
    # not serving — FIX THE SERVER immediately
    action.append("localhost:8799 not serving -> relaunching king_serve")
    launched = fix_server()
    action.append("king_serve relaunch %s" % ("issued" if launched else "FAILED (king_serve.py missing?)"))
    for _ in range(6):                # give it up to ~12s to come up
        time.sleep(2)
        if check():
            action.append("recovered after relaunch")
            return {"ok": True, "url": TAILSCALE, "healed": True, "action": action}
    action.append("STILL DOWN after relaunch")
    return {"ok": False, "url": TAILSCALE, "healed": False, "action": action}


def main():
    res = ensure()
    print("dashboard_link: ok=%s healed=%s url=%s" % (res["ok"], res["healed"], res["url"]))
    for a in res["action"]:
        print("  - %s" % a)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
