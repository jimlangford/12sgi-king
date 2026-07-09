#!/usr/bin/env python3
"""tenant_onboard_ratchet.py — the standing guarantee that civic-tenant ingestion/onboarding is NEVER
forgotten (Jimmy 2026-06-18: "keep ingesting and onboarding civic tenants ... check you are doing that and
not forgetting all the time").

The 6 per-tenant audit tasks + the daily cycle already INGEST. This RATCHETS the onboarding so it stays
visible and keeps advancing:
  - reads tenant_depth.json (per-tenant % of the 9 Maui-reference dimensions covered),
  - appends today's snapshot to a trend log (so progress is a number, not a feeling),
  - flags any STALL (a <100% tenant unchanged for >=7 days) or REGRESSION (% dropped) as a dispatch FINDING,
  - keeps a STANDING board item for each tenant still short of full depth + its exact missing dimension,
    deduped (filed once per gap, not spammed daily), so the backlog is always on the board until 6/6.

Read-only over the depth data; CPU only. Output: reports/_status/tenant_onboard_trend.jsonl + a per-run
summary. Run daily in the cycle.
"""
import os, sys, json, time, subprocess
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
ST = os.path.join(PROJ, "reports", "_status")
DEPTH = os.path.join(ST, "tenant_depth.json")
TREND = os.path.join(ST, "tenant_onboard_trend.jsonl")
FILED = os.path.join(ST, "tenant_onboard_filed.json")   # dedup: gaps already on the board
HST = timezone(timedelta(hours=-10))


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def _dispatch(msg):
    try:
        subprocess.run([sys.executable, os.path.join(PROJ, "app", "server", "dispatch.py"), PROJ,
                        "--log-event", msg, "--source", "kilo-aupuni"],
                       capture_output=True, timeout=30, creationflags=(0x08000000 if os.name == "nt" else 0))
    except Exception:
        pass


def _file_board(text):
    """File a WBITEM to the board (deduped by caller)."""
    _dispatch("WBITEM: [upgrade] " + text)


def _trend_for(tid):
    """Return the most recent prior snapshot pct for a tenant + the days since it last changed."""
    last_pct, last_change_date, days = None, None, 0
    try:
        rows = [json.loads(l) for l in open(TREND, encoding="utf-8") if l.strip()]
    except Exception:
        rows = []
    hist = [(r.get("date"), (r.get("tenants") or {}).get(tid)) for r in rows if (r.get("tenants") or {}).get(tid) is not None]
    if hist:
        last_pct = hist[-1][1]
        # walk back to the last time it differed
        cur = hist[-1][1]
        for date, pct in reversed(hist):
            if pct != cur:
                break
            last_change_date = date
        try:
            if last_change_date:
                d0 = datetime.strptime(last_change_date, "%Y-%m-%d")
                days = (datetime.now(HST).replace(tzinfo=None) - d0).days
        except Exception:
            days = 0
    return last_pct, days


def main():
    today = datetime.now(HST).strftime("%Y-%m-%d")
    dep = load(DEPTH, {})
    tenants = dep.get("tenants", [])
    if not tenants:
        print("tenant_onboard_ratchet: no tenant_depth data"); return 1

    snap = {t["id"]: t.get("pct", 0) for t in tenants}
    full = [t for t in tenants if t.get("pct", 0) >= 100]
    short = [t for t in tenants if t.get("pct", 0) < 100]
    # the thin/missing dimension names live at the top level (flaws_thin = [[tenant, dim], ...])
    miss_map = {}
    for ft in (dep.get("flaws_thin") or []):
        if isinstance(ft, (list, tuple)) and len(ft) >= 2:
            miss_map.setdefault(ft[0], []).append(ft[1])
    for t in tenants:
        gap = t.get("total", 9) - t.get("covered", 0)
        t["thin_dims"] = ", ".join(miss_map.get(t["id"], [])) or (("%d dimension(s) below full depth" % gap) if gap else "")

    # flag stalls / regressions vs the trend
    alerts = []
    for t in short:
        prev, days = _trend_for(t["id"])
        if prev is not None and t.get("pct", 0) < prev:
            alerts.append("REGRESSION: %s onboarding dropped %d%% -> %d%%" % (t["name"], prev, t["pct"]))
        elif prev is not None and t.get("pct", 0) == prev and days >= 7:
            alerts.append("STALL: %s stuck at %d%% for %d days (missing: %s)"
                          % (t["name"], t["pct"], days, t.get("thin_dims") or t.get("missing") or "see tenant_depth"))

    # append today's snapshot to the trend (the ratchet record)
    try:
        with open(TREND, "a", encoding="utf-8") as f:
            f.write(json.dumps({"date": today, "ts": int(time.time()), "tenants": snap,
                                "at_full": len(full), "of": len(tenants)}, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # keep a STANDING board item per still-short tenant + its missing dimension (deduped)
    filed = load(FILED, {})
    for t in short:
        miss = t.get("thin_dims") or t.get("missing") or t.get("thin") or ""
        key = "%s|%s|%d" % (t["id"], miss, t.get("pct", 0))
        if filed.get(key):
            continue
        _file_board("Onboard tenant %s to full depth (%d%%, %d/%d dims) — missing: %s :: keep ingesting until 6/6 "
                    "tenants at Maui depth. Civic lane; agenda-system ids for minutes = server-quad-os."
                    % (t["name"], t.get("pct", 0), t.get("covered", 0), t.get("total", 9), miss or "the remaining dimensions"))
        filed[key] = today
    try:
        json.dump(filed, open(FILED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass

    # one FINDING when the headline changes (or an alert fires) — loud on movement, quiet otherwise
    prev_headline = None
    try:
        rows = [json.loads(l) for l in open(TREND, encoding="utf-8") if l.strip()]
        if len(rows) >= 2:
            prev_headline = rows[-2].get("at_full")
    except Exception:
        pass
    if alerts:
        for a in alerts:
            _dispatch("BLOCKER (onboarding ratchet): " + a)
    elif prev_headline is not None and prev_headline != len(full):
        _dispatch("FINDING (onboarding ratchet): civic tenants at full depth %d/%d (was %d). Remaining: %s"
                  % (len(full), len(tenants), prev_headline,
                     "; ".join("%s %d%%" % (t["name"], t["pct"]) for t in short) or "none — all onboarded"))

    print("tenant_onboard_ratchet: %d/%d tenants at full depth; %d short%s"
          % (len(full), len(tenants), len(short), (" | ALERTS: " + "; ".join(alerts)) if alerts else ""))
    for t in short:
        print("  short: %-14s %d%% (%d/%d) missing=%s" % (t["id"], t.get("pct", 0), t.get("covered", 0),
                                                          t.get("total", 9), t.get("thin_dims") or t.get("missing") or "?"))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
