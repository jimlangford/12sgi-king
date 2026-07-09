#!/usr/bin/env python3
"""tenant_discover.py — auto-create a civic tenant when REAL data for a new county/municipality is found
(Jimmy 2026-06-18: "allow new tenants to be created if the data you find allows for a new county or
municipality to be added").

HARD GATE — never fabricate a jurisdiction. A tenant is created ONLY when its government data is VERIFIED
real: a reachable Legistar/CivicClerk agenda system that returns actual events (the strongest proof a
jurisdiction has an ingestable government), and/or federal dollars on record for the place. Candidates come
from config/tenant_candidates.json (a thread/Jimmy adds a jurisdiction it found data for); the scan verifies
each and, if it passes and isn't already a tenant, ADDS it to tools/kilo-aupuni/tenants.json — starting
PRIVATE (publish=false) with the universal civic steps, so the onboarding ratchet drives it to depth and
publishing stays behind the publish-confirm gate.

  python tenant_discover.py --scan                         # evaluate candidates; auto-create the verified ones
  python tenant_discover.py --candidate la-county --name "Los Angeles County" --legistar lacounty [--apply]
SAFE BY DEFAULT: dry-run unless --apply (or --scan, which applies verified candidates). Stdlib only.
"""
import os, sys, json, ssl, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
TEN = os.path.join(HERE, "tenants.json")
CAND = os.path.join(PROJ, "config", "tenant_candidates.json")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
NW = 0x08000000 if os.name == "nt" else 0
# universal civic steps that apply to ANY jurisdiction at creation; HI/NY-specific steps add as sources wire
UNIVERSAL_STEPS = ["federal_money", "audit_balance"]


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def _jj(url, timeout=30):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout,
                      context=ssl.create_default_context()).read().decode("utf-8", "replace"))


def verify(cand):
    """The GATE: prove the jurisdiction has REAL, ingestable government data. Returns (ok, evidence)."""
    ev = []
    cl = cand.get("legistar")
    if cl:
        try:
            rows = _jj("https://webapi.legistar.com/v1/%s/Events?%s" % (cl, urllib.parse.urlencode({"$top": "3"})))
            if isinstance(rows, list) and rows:
                ev.append("Legistar '%s': %d events (e.g. %s)" % (cl, len(rows), str(rows[0].get("EventBodyName", ""))[:40]))
        except Exception as e:
            ev.append("Legistar '%s' probe failed: %s" % (cl, str(e)[:50]))
    cc = cand.get("civicclerk")
    if cc:
        try:
            d = _jj("https://%s/v1/Events?$top=1" % cc)
            if (d.get("value") or d):
                ev.append("CivicClerk '%s': events present" % cc)
        except Exception as e:
            ev.append("CivicClerk '%s' probe failed: %s" % (cc, str(e)[:50]))
    ok = any("events" in e or ("Legistar" in e and "failed" not in e) for e in ev)
    return ok, ev


def tenants():
    return load(TEN, {"tenants": []})


def exists(tid):
    return any(t.get("id") == tid for t in tenants().get("tenants", []))


def _next_hour(reg):
    used = {t.get("sched_hour") for t in reg.get("tenants", [])}
    for h in range(0, 24):
        if h not in used:
            return h
    return 12


def create(cand, evidence):
    reg = tenants()
    rec = {"id": cand["id"], "code": cand.get("code", ""), "name": cand["name"],
           "sched_hour": _next_hour(reg), "publish": False, "depth": "new",
           "steps": list(cand.get("steps") or UNIVERSAL_STEPS),
           "lenses": cand.get("lenses") or ["federal dollars", "upcoming agendas (if Legistar)"],
           "discovered": datetime.now(HST).strftime("%Y-%m-%d"), "evidence": evidence,
           "agenda_system": {"legistar": cand.get("legistar"), "civicclerk": cand.get("civicclerk")}}
    reg["tenants"].append(rec)
    tmp = TEN + ".tmp"
    json.dump(reg, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, TEN)
    return rec


def _dispatch(msg):
    try:
        import subprocess
        subprocess.run([sys.executable, os.path.join(PROJ, "app", "server", "dispatch.py"), PROJ,
                        "--log-event", msg, "--source", "kilo-aupuni"],
                       capture_output=True, timeout=30, creationflags=NW)
    except Exception:
        pass


def evaluate(cand, apply):
    tid = cand.get("id")
    if not tid or not cand.get("name"):
        return {"id": tid, "result": "skip", "why": "needs id + name"}
    if exists(tid):
        return {"id": tid, "result": "exists"}
    ok, ev = verify(cand)
    if not ok:
        return {"id": tid, "result": "rejected", "why": "no verified government data", "evidence": ev}
    if not apply:
        return {"id": tid, "result": "would-create", "evidence": ev}
    rec = create(cand, ev)
    # register its Legistar id with agenda_intel + put it on the board; the onboarding ratchet takes over
    _dispatch("WBITEM: [upgrade] NEW civic tenant auto-created: %s (%s) :: verified real government data (%s); "
              "added to tenants.json PRIVATE (publish=false), universal steps, onboarding ratchet now drives it "
              "to depth. server-quad-os: add its agenda-system id to agenda_intel.TENANTS for agenda+packet ingest."
              % (rec["name"], tid, "; ".join(ev)[:140]))
    _dispatch("FINDING: tenant_discover created tenant %s from verified data (publish=false, onboarding starts). Hawaii has 4 counties + state (all tenants); this is expansion beyond, gated on real data." % tid)
    return {"id": tid, "result": "created", "record": rec}


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan", action="store_true", help="evaluate config/tenant_candidates.json (auto-creates verified)")
    ap.add_argument("--candidate"); ap.add_argument("--name"); ap.add_argument("--legistar")
    ap.add_argument("--civicclerk"); ap.add_argument("--code", default="")
    ap.add_argument("--apply", action="store_true")
    a, _ = ap.parse_known_args()
    results = []
    if a.candidate:
        results.append(evaluate({"id": a.candidate, "name": a.name or a.candidate, "code": a.code,
                                 "legistar": a.legistar, "civicclerk": a.civicclerk}, a.apply))
    if a.scan:
        for c in (load(CAND, []) or []):
            results.append(evaluate(c, True))   # scan applies verified candidates (Jimmy: allow creation if data allows)
    if not results:
        print("tenant_discover: nothing to evaluate (use --candidate ... or --scan with config/tenant_candidates.json)")
        return 0
    for r in results:
        print("  %-16s -> %s %s" % (r.get("id"), r.get("result"), ("| " + "; ".join(r.get("evidence", []))[:100]) if r.get("evidence") else ""))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
