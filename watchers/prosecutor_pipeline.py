#!/usr/bin/env python3
"""prosecutor_pipeline.py - the ONE daily prosecutor-email composition, callable by any owner path.

Runs, in order:
  1. prosecutor_daily.py  - refine the cross-tenant findings + mirror the private case pages
  2. reports_index.py     - rebuild the durable owner index that links every refined report
  3. prosecutor_email.py  - build the NEUTRAL email body (aggregate counts + private Tailscale links)
  4. prosecutor_send.py   - hands-off SMTP send to Jimmy (idempotent per Hawaiian day)

This is the composable ATOM (Jimmy's rule: abilities = ATOMS, apps = COMPOSITION). Both the maintenance
tick and king_serve's own daily backstop call THIS one script, so the sequence lives in exactly one place.
Step 4 is idempotent per Hawaiian day (prosecutor_send writes a .sent_<HST> marker), so calling this from
several trigger paths in the same day NEVER double-sends: the first that day sends, the rest no-op.

Steps 1-3 always run (cheap, refresh the reports + links); only the send is day-guarded. --force passes
through to the send so a manual run re-sends today. Stdlib only, ASCII, windowless children, UTF-8 forced.

Usage: python prosecutor_pipeline.py [--force] [--send-only]
Exit 0 if the send succeeded OR was correctly skipped (already sent); nonzero only on a real send failure.
"""
import os, sys, json, time, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(PROJ, "reports", "_status", "prosecutor")
STATUS = os.path.join(OUT, "pipeline_last.json")
NW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW (Windows) so nothing pops a console

# UTF-8 everywhere (the okina gotcha: civic text carries Hawaiian diacritics)
ENV = dict(os.environ)
ENV["PYTHONUTF8"] = "1"
ENV["PYTHONIOENCODING"] = "utf-8"

STEPS = [
    ("prosecutor_daily.py", [], 300),
    ("reports_index.py",    [], 120),
    ("prosecutor_email.py", [], 120),
    ("prosecutor_send.py",  [], 120),  # send flags appended in main()
]


def _run(script, extra, timeout):
    path = os.path.join(HERE, script)
    if not os.path.isfile(path):
        return {"step": script, "ok": False, "rc": None, "err": "missing"}
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", path] + extra, cwd=PROJ, env=ENV,
                           capture_output=True, text=True, timeout=timeout, creationflags=NW)
        tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
        return {"step": script, "ok": p.returncode == 0, "rc": p.returncode,
                "out": (tail[-1] if tail else "")[:200]}
    except subprocess.TimeoutExpired:
        return {"step": script, "ok": False, "rc": None, "err": "timeout"}
    except Exception as e:
        return {"step": script, "ok": False, "rc": None, "err": str(e)[:160]}


def run(force=False, send_only=False):
    steps = STEPS[3:] if send_only else STEPS
    results = []
    for script, extra, timeout in steps:
        flags = list(extra)
        if script == "prosecutor_send.py" and force:
            flags.append("--force")
        r = _run(script, flags, timeout)
        results.append(r)
        # reports steps (1-3) are best-effort refreshers; keep going even if one hiccups so the send
        # still fires on yesterday-good reports. The send is the only step whose failure fails us.
    send = next((r for r in results if r["step"] == "prosecutor_send.py"), None)
    ok = bool(send and send["ok"])
    summary = {"ok": ok, "epoch": time.time(), "when": time.strftime("%Y-%m-%d %H:%M:%S"),
               "force": force, "send_only": send_only, "steps": results}
    try:
        os.makedirs(OUT, exist_ok=True)
        json.dump(summary, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass
    return summary


def main():
    force = "--force" in sys.argv
    send_only = "--send-only" in sys.argv
    s = run(force=force, send_only=send_only)
    for r in s["steps"]:
        print("  %-22s %s %s" % (r["step"], "OK " if r["ok"] else "ERR", r.get("out") or r.get("err") or ""))
    print("PIPELINE: %s" % ("sent/ok" if s["ok"] else "send did not succeed"))
    return 0 if s["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
