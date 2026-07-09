#!/usr/bin/env python3
# surface_health.py - the GENERALIZED boot-persistence sweep (Jimmy 2026-06-16: "consider that type of
#   problem for the other surfaces and crosstrain"). The :8799 King server stayed dark after a reboot
#   because its Startup shortcut didn't fire and NOTHING was watching. That is a CLASS of fault: anything
#   meant to auto-start/persist (servers, scheduled tasks, startup-only daemons) can silently not come
#   back, unnoticed until needed. This sweeps the whole expected-persistent set across surfaces, flags
#   anything down, and (with --heal) relaunches the SAFE lightweight ones the canonical windowless way.
#
#   The supervisor (studio_supervisor.py) already keeps :8770 / roster_loop / jobrunner / tunnel alive,
#   so those are NOT our job here. We cover the Startup-ONLY items that have no keep-alive net.
#   GPU rule: NEVER relaunch/kill ComfyUI (:8000) or Ollama (:11434) - report only.
#
#   Usage:  python surface_health.py            # report
#           python surface_health.py --heal      # relaunch safe DOWN daemons/servers, then report
# Stdlib only (socket + subprocess to schtasks/powershell). Writes reports/_status/surface_health.{json,html}.
import json, os, sys, socket, subprocess
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT = os.path.join(PROJECT, "reports", "_status")
HST = timezone(timedelta(hours=-10))
PYW = os.path.join(HOME, "AppData", "Local", "Programs", "Python", "Python311", "pythonw.exe")
CREATE_NO_WINDOW = 0x08000000

# Servers that should be LISTENING. heal=True => safe to relaunch windowless; comfy/ollama report-only.
SERVERS = [
    {"name": "ComfyUI render",   "port": 8000,  "heal": False, "note": "ComfyUI Desktop - never auto-touch (GPU)"},
    {"name": "studio library",   "port": 8770,  "heal": False, "note": "supervisor-managed - leave to studio_supervisor"},
    {"name": "status dashboard", "port": 8781,  "heal": True,
     "cmd": ["wscript.exe", os.path.join(PROJECT, "tools", "kilo-aupuni", "run_hidden.vbs"),
             os.path.join(PROJECT, "tools", "kilo-aupuni", "kilo_monitor_task.bat")]},
    {"name": "private King",     "port": 8799,  "heal": True,
     "cmd": [PYW, os.path.join(HOME, "AppData", "Local", "king-extract", "king_serve.py")]},
    {"name": "Ollama",           "port": 11434, "heal": False, "note": "Ollama service - external"},
]
# Startup-ONLY *persistent* daemons (always-running, no port). Detect by cmdline; relaunch windowless.
# NOTE (Jimmy 2026-06-16): only PERSISTENT daemons belong here. kilo_aupuni_task is a PERIODIC task
# (runs the audit, then EXITS) — checking it as 'process alive' is a false positive (it's correctly idle
# between runs) and relaunching spawns a duplicate run. Periodic tasks are judged by OUTPUT FRESHNESS
# (prog_freshness / the audit reports), not liveness. So it is intentionally NOT in this always-on set.
DAEMONS = [
    {"name": "publish watcher", "match": "publish_watch", "heal": True,
     "cmd": [PYW, os.path.join(HOME, "AppData", "Local", "12sgi-publish", "publish_watch.py")]},
]
# Supervisor itself must be alive (it heals :8770/roster/jobrunner/tunnel).
SUPERVISOR = {"name": "studio_supervisor", "match": "studio_supervisor"}
# LAUNCHER INTEGRITY (new facet of boot-persistence, learned from the reboot 2026-06-16): a Startup
# launcher that points at a MISSING script throws "couldn't find a script" on boot and the daemon never
# starts. So we also verify the scripts our launchers depend on actually exist.
LAUNCHER_SCRIPTS = [
    ("Kilo Aupuni run_hidden", os.path.join(PROJECT, "tools", "kilo-aupuni", "run_hidden.vbs")),
    ("Kilo Aupuni task",       os.path.join(PROJECT, "tools", "kilo-aupuni", "kilo_aupuni_task.bat")),
    ("dashboard monitor task", os.path.join(PROJECT, "tools", "kilo-aupuni", "kilo_monitor_task.bat")),
    ("King serve",             os.path.join(HOME, "AppData", "Local", "king-extract", "king_serve.py")),
    ("publish_watch",          os.path.join(HOME, "AppData", "Local", "12sgi-publish", "publish_watch.py")),
]
# Scheduled tasks: expected State.
# NOTE (inloop_schedule consolidation, 2026-06-24): the 9 govOS+daily tasks below were DELIBERATELY
# disabled when their jobs were migrated to the internal ONE-clock (tools/ops/inloop_schedule.py,
# ticked by studio_supervisor). They must stay Disabled — re-enabling them would DUPLICATE fires.
# Flag any that re-enable (that would be a regression).
TASKS_READY    = []   # no OS-scheduled tasks are expected Ready any more
TASKS_DISABLED = [
    "12sgi skill refresh",            # retired - flag if it ever re-enables
    # migrated to inloop_schedule (must stay Disabled):
    "elementLOTUS Daily Film Crosscheck",
    "elementLOTUS Daily Models",
    "elementLOTUS Daily YouTube",
    "govOS Audit - Maui County",
    "govOS Audit - State of Hawaii",
    "govOS Audit - Hawaii County",
    "govOS Audit - Honolulu",
    "govOS Audit - Kauai County",
    "govOS Audit - New York",
]

def port_up(p):
    s = socket.socket(); s.settimeout(2.5)
    try: s.connect(("127.0.0.1", p)); return True
    except Exception: return False
    finally: s.close()

def proc_running(substr):
    try:
        o = subprocess.run(["powershell", "-NoProfile", "-Command",
              "Get-CimInstance Win32_Process -Filter \"name='pythonw.exe' or name='python.exe' or name='wscript.exe'\" | "
              "Where-Object { $_.CommandLine -like '*%s*' } | Measure-Object | Select-Object -ExpandProperty Count" % substr],
              capture_output=True, text=True, timeout=25, creationflags=CREATE_NO_WINDOW)
        return int((o.stdout or "0").strip() or 0) > 0
    except Exception:
        return None  # unknown

def task_state(name):
    try:
        o = subprocess.run(["schtasks", "/query", "/tn", name, "/fo", "list"],
                           capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW)
        for ln in o.stdout.splitlines():
            if ln.strip().lower().startswith("status:"):
                return ln.split(":", 1)[1].strip()
    except Exception:
        pass
    return None

def comfy_ready():
    """Ingest ComfyUI render-readiness (Jimmy 2026-06-16): not just :8000 up, but the nodes our renders
    depend on are registered (DisTorch2 loader, IPAdapter FaceID face-lock, Wan i2v). Catches a ComfyUI
    that booted without a critical custom node."""
    import urllib.request
    need = ["UNETLoaderDisTorch2MultiGPU", "IPAdapterUnifiedLoaderFaceID", "WanImageToVideo"]
    try:
        for n in need:
            urllib.request.urlopen("http://127.0.0.1:8000/object_info/" + n, timeout=6).read(8)
        return True, "render-ready: DisTorch2 + IPAdapter FaceID + Wan i2v nodes registered"
    except Exception as e:
        return False, "render node missing/unreachable (" + str(e)[:46] + ")"

def relaunch(cmd):
    try:
        subprocess.Popen(cmd, cwd=os.path.dirname(cmd[-1]) or None, creationflags=CREATE_NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return True
    except Exception as e:
        return str(e)

def main():
    heal = "--heal" in sys.argv
    now = datetime.now(HST)
    items, healed = [], []

    for s in SERVERS:
        up = port_up(s["port"])
        rec = {"surface": s["name"], "kind": "server", "id": ":%d" % s["port"], "ok": up}
        if not up and heal and s.get("heal") and s.get("cmd"):
            r = relaunch(s["cmd"]); rec["healed"] = (r is True); rec["heal_detail"] = r if r is not True else "relaunched"
            healed.append(s["name"])
        elif not up and not s.get("heal"):
            rec["note"] = s.get("note", "report-only")
        items.append(rec)

    # ingest ComfyUI render-readiness (only meaningful if :8000 is up)
    if port_up(8000):
        cok, cnote = comfy_ready()
        items.append({"surface": "ComfyUI render-ready", "kind": "render", "id": "nodes", "ok": cok, "note": cnote})

    for d in DAEMONS:
        run = proc_running(d["match"])
        rec = {"surface": d["name"], "kind": "daemon", "id": d["match"], "ok": run}
        if run is False and heal and d.get("cmd"):
            r = relaunch(d["cmd"]); rec["healed"] = (r is True); rec["heal_detail"] = r if r is not True else "relaunched"
            healed.append(d["name"])
        items.append(rec)

    sup = proc_running(SUPERVISOR["match"])
    items.append({"surface": SUPERVISOR["name"], "kind": "supervisor", "id": SUPERVISOR["match"], "ok": sup,
                  "note": "if down, :8770/roster/jobrunner/tunnel lose their keep-alive"})

    for name, scr in LAUNCHER_SCRIPTS:     # boot-launcher integrity (the reboot lesson)
        ok = os.path.exists(scr)
        items.append({"surface": "launcher: " + name, "kind": "launcher", "id": os.path.basename(scr), "ok": ok,
                      "note": None if ok else "Startup launcher points at a MISSING script -> 'couldn't find a script' on boot"})

    for t in TASKS_READY:
        st = task_state(t)
        items.append({"surface": t, "kind": "task", "id": "scheduled", "ok": (st == "Ready"),
                      "state": st, "note": None if st == "Ready" else "expected Ready"})
    for t in TASKS_DISABLED:
        st = task_state(t)
        items.append({"surface": t, "kind": "task", "id": "scheduled", "ok": (st == "Disabled"),
                      "state": st, "note": "RETIRED - must stay Disabled" if st != "Disabled" else None})

    down = [i for i in items if i["ok"] is False]
    unknown = [i for i in items if i["ok"] is None]
    summary = {"total": len(items), "down": len(down), "unknown": len(unknown), "healed": healed}
    os.makedirs(OUT, exist_ok=True)
    payload = {"generated": now.strftime("%Y-%m-%d %H:%M HST"), "summary": summary, "items": items, "healed": heal}
    json.dump(payload, open(os.path.join(OUT, "surface_health.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    _html(payload)

    print("surface_health: %d items, %d down, %d unknown%s" % (
        len(items), len(down), len(unknown), (" | healed: " + ", ".join(healed)) if healed else ""))
    for i in items:
        flag = "OK " if i["ok"] else ("?? " if i["ok"] is None else "DOWN")
        extra = (" healed" if i.get("healed") else "") + (" [%s]" % i["note"] if i.get("note") else "") + \
                (" state=%s" % i["state"] if i.get("state") and not i["ok"] else "")
        print("  [%s] %-28s %s%s" % (flag, i["surface"], i["id"], extra))
    return 1 if (down and not heal) else 0

def _esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def _html(p):
    color = {True: "#4ade80", False: "#e06a4a", None: "#d9b24c"}
    rows = "".join("<tr><td>%s</td><td class=m>%s</td><td>%s</td><td style='color:%s;font-weight:700'>%s</td><td class=m>%s</td></tr>" % (
        _esc(i["surface"]), _esc(i["kind"]), _esc(i["id"]), color[i["ok"]],
        ("UP/OK" if i["ok"] else ("UNKNOWN" if i["ok"] is None else "DOWN")),
        _esc((i.get("note") or "") + (" healed" if i.get("healed") else "") + (" state=%s"%i["state"] if i.get("state") else ""))) for i in p["items"])
    s = p["summary"]
    html = ("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=300>"
        "<title>Surface health - boot persistence</title><style>"
        "body{font-family:system-ui,Segoe UI,sans-serif;max-width:900px;margin:1.4rem auto;padding:0 1rem;background:#0d1117;color:#e6edf3}"
        "h1{font-size:1.3rem}.sub{color:#8b949e;font-size:.85rem}table{border-collapse:collapse;width:100%%;font-size:.85rem}"
        "td,th{padding:.4rem .55rem;border-bottom:1px solid #21262d;text-align:left}.m{color:#8b949e}</style>"
        "<h1>Surface health <span class=sub>boot-persistence sweep across all surfaces</span></h1>"
        "<div class=sub>%s &middot; %d items, <b style='color:%s'>%d down</b>, %d unknown.%s "
        "The class: anything meant to persist can silently not come back after a reboot/crash - this catches it.</div>"
        "<table><thead><tr><th>surface</th><th>kind</th><th>id</th><th>status</th><th>note</th></tr></thead><tbody>%s</tbody></table>" % (
        _esc(p["generated"]), s["total"], "#e06a4a" if s["down"] else "#4ade80", s["down"], s["unknown"],
        (" Healed: %s." % ", ".join(s["healed"])) if s["healed"] else "", rows))
    open(os.path.join(OUT, "surface_health.html"), "w", encoding="utf-8").write(html)

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
