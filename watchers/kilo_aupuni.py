#!/usr/bin/env python3
# kilo_aupuni.py - Kilo Aupuni: the govOS department-coverage watch engine.
#   kilo   = the practice of careful, sustained observation (kilo hoku = star-watching)
#   aupuni = government / nation
# Orchestrates one watcher per county public-data source and rolls every
# watcher's output into ONE county-wide situational-awareness dashboard.
#
#   (no args)          aggregate all watcher outputs -> reports/mauios/county_dashboard.html
#   --run-watchers     also run each LIVE watcher first (council-watch), then aggregate
#
# Watcher #1 = council-watch (CivicClerk, ALL legislative bodies) - LIVE.
# Gap watchers (permits/MAPPS, procurement, real property, docs) are PLANNED;
# their verified sources live in departments.json and are built in later phases.
#
# Stdlib only. No subprocess that pops a window. Windowless by design (no-popup policy).
import json, os, re, sys, time
from datetime import datetime, timedelta, timezone

HOME     = os.path.expanduser("~")
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
REG_F    = os.path.join(TOOL_DIR, "departments.json")
OUT_DIR  = os.path.join(PROJECT, "reports", "mauios")
DASH_F   = os.path.join(OUT_DIR, "county_dashboard.html")
DISPATCH = os.path.join(PROJECT, ".dispatch_log.jsonl")
COUNCIL_INDEX = os.path.join(PROJECT, "reports", "council", "index.jsonl")
BIDS_INDEX    = os.path.join(PROJECT, "reports", "mauios", "bids_index.jsonl")
PERMITS_INDEX = os.path.join(PROJECT, "reports", "mauios", "permits_index.jsonl")
OFFICIALS_F   = os.path.join(PROJECT, "reports", "mauios", "officials.json")
DONORS_F      = os.path.join(PROJECT, "reports", "mauios", "donor_profiles.json")
TWIN_F        = os.path.join(PROJECT, "reports", "mauios", "twin_metrics.json")
# Practice 12: Digital Twin instrumentation. Practice 6 follow-ups recorded in departments.json.
PLATFORM_DASH = os.path.join(HOME, "iCloudDrive", "12 stones AI", "12stones-platform",
                             "public", "dashboards", "kilo-aupuni.html")
HST      = timezone(timedelta(hours=-10))

def now_hst(): return datetime.now(HST)

def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "kilo-aupuni", "event": f"{tag}: {msg}"}
    try:
        os.makedirs(os.path.dirname(DISPATCH), exist_ok=True)
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def load_registry():
    with open(REG_F, encoding="utf-8") as f:
        return json.load(f)

def read_jsonl(p):
    rows = []
    try:
        with open(p, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try: rows.append(json.loads(ln))
                    except Exception: pass
    except FileNotFoundError:
        pass
    return rows

def dollars_to_float(amt):
    t = str(amt).lower().replace("$", "").replace(",", "").strip()
    mult = 1_000_000 if "million" in t else 1_000_000_000 if "billion" in t else 1
    try: return float(re.sub(r"[a-z\s]", "", t)) * mult
    except Exception: return 0.0

def council_rollup():
    rows = read_jsonl(COUNCIL_INDEX)
    lens = {}; big = []; dates = []
    for r in rows:
        if r.get("date"): dates.append(r["date"])
        for l in r.get("lenses", []):
            lens[l] = lens.get(l, 0) + 1
        for d in r.get("dollars", []):
            v = dollars_to_float(d.get("amt"))
            if v >= 1_000_000:
                big.append({"v": v, "amt": d.get("amt"), "ctx": d.get("ctx"),
                            "date": r.get("date"), "event": r.get("event")})
    big.sort(key=lambda x: -x["v"])
    span = (min(dates) + " .. " + max(dates)) if dates else "no data yet"
    return {"meetings": len(rows), "lens": lens, "big": big[:12], "span": span}

def run_live_watchers(reg):
    """Import-and-run each LIVE watcher in-process (no subprocess => no window)."""
    ran = []
    for w in reg["watchers"]:
        if w.get("status") != "live":
            continue
        name = w.get("watcher")
        try:
            if name == "council-watch":
                cw_dir = os.path.join(HOME, "Documents", "Claude", "tools", "council-watch")
                if cw_dir not in sys.path:
                    sys.path.insert(0, cw_dir)
                import council_watch
                council_watch.main()      # daily -7d..+21d watch
                ran.append(name)
            elif name == "bids-watch":
                if TOOL_DIR not in sys.path:
                    sys.path.insert(0, TOOL_DIR)
                import bids_watch
                bids_watch.main()         # new procurement postings
                ran.append(name)
            elif name == "mapps-watch":
                if TOOL_DIR not in sys.path:
                    sys.path.insert(0, TOOL_DIR)
                import mapps_watch
                mapps_watch.main()        # permits applied in last 30 days
                ran.append(name)
            elif name == "votes-watch":
                if TOOL_DIR not in sys.path:
                    sys.path.insert(0, TOOL_DIR)
                import votes_watch
                votes_watch.main()        # council minutes -> votes/recusals
                ran.append(name)
            elif name == "donor-watch":
                if TOOL_DIR not in sys.path:
                    sys.path.insert(0, TOOL_DIR)
                import donor_watch
                donor_watch.main()        # campaign finance -> money behind officials
                ran.append(name)
            elif name == "federal-money":
                if TOOL_DIR not in sys.path:
                    sys.path.insert(0, TOOL_DIR)
                import federal_money
                federal_money.main()      # federal $ into Maui + State of Hawaii (USASpending)
                ran.append(name)
            elif name == "charter-law-map":
                if TOOL_DIR not in sys.path:
                    sys.path.insert(0, TOOL_DIR)
                import charter_law_map
                charter_law_map.main()    # Charter <-> existing law <-> live evidence (runs last)
                ran.append(name)
        except Exception as e:
            dispatch("FINDING", f"Kilo Aupuni could not run {name}: {e}")
    return ran

def bids_rollup():
    rows = read_jsonl(BIDS_INDEX)
    lens = {}; money = []
    for r in rows:
        for l in r.get("lenses", []):
            lens[l] = lens.get(l, 0) + 1
        for d in r.get("dollars", []):
            v = dollars_to_float(d.get("amt"))
            if v >= 100_000:
                money.append({"v": v, "amt": d.get("amt"), "ctx": d.get("ctx"), "title": r.get("title")})
    money.sort(key=lambda x: -x["v"])
    return {"bids": len(rows), "lens": lens, "money": money[:10]}

def permits_rollup():
    rows = read_jsonl(PERMITS_INDEX)
    lens = {}; recovery = 0
    for r in rows:
        for l in r.get("lenses", []):
            lens[l] = lens.get(l, 0) + 1
            if "Recovery" in l: recovery += 1
    return {"permits": len(rows), "lens": lens, "recovery": recovery}

def votes_rollup():
    try:
        off = json.load(open(OFFICIALS_F, encoding="utf-8"))
    except Exception:
        return {"officials": 0, "recusals": 0, "by_member": []}
    by = []
    total = 0
    for name, o in off.items():
        rc = len(o.get("recusals", []))
        total += rc
        by.append({"name": name, "recusals": rc, "meetings": o.get("meetings", 0),
                   "items": [r.get("item") for r in o.get("recusals", []) if r.get("item")]})
    by.sort(key=lambda x: -x["recusals"])
    return {"officials": len(off), "recusals": total, "by_member": by}

def money_rollup():
    try:
        prof = json.load(open(DONORS_F, encoding="utf-8"))
    except Exception:
        return {"officials": 0, "re_total": 0.0, "rows": []}
    rows = []
    for p in prof:
        rows.append({"label": (p.get("label") or "").split(" -")[0], "key": p.get("key"),
                     "total": p.get("total", 0), "re": p.get("realestate", {}).get("total", 0),
                     "oos": p.get("out_of_state_pct", 0)})
    rows.sort(key=lambda r: -r["re"])
    return {"officials": len([r for r in rows if r["total"]]),
            "re_total": sum(r["re"] for r in rows), "rows": rows}

def build_dashboard(reg):
    roll = council_rollup()
    broll = bids_rollup()
    proll = permits_rollup()
    vroll = votes_rollup()
    mroll = money_rollup()
    live = [w for w in reg["watchers"] if w.get("status") == "live"]
    planned = [w for w in reg["watchers"] if w.get("status") != "live"]

    def wrow(w):
        st = (w.get("status") or "planned").upper()
        color = "#6abf86" if st == "LIVE" else "#d9b24c"
        src = (w.get("source") or {}).get("url", "")
        cu = (f'<a href="{esc(src)}" target="_blank" rel="noopener">{esc(src[:58])}</a>'
              if src.startswith("http") else esc(src[:58]))
        return (f'<div class="cr"><span class="cd">{esc(w["dept"])}</span>'
                f'<span class="cs" style="color:{color}">{st}</span>'
                f'<span class="cw">{esc(w.get("watcher",""))}</span>'
                f'<span class="cu">{cu}</span></div>')
    cov = "".join(wrow(w) for w in reg["watchers"])
    maxl = max(roll["lens"].values()) if roll["lens"] else 1
    def bar(n):
        wd = max(2, round(n / maxl * 100))
        return (f'<span style="display:inline-block;height:11px;border-radius:4px;width:{wd}%;'
                f'background:linear-gradient(90deg,#d9b24c,rgba(217,178,76,.3))"></span>')
    lens_rows = "".join(
        f'<div class="lr"><span class="ln">{esc(l)}</span><span class="tr">{bar(n)}</span>'
        f'<span class="ct">{n}</span></div>'
        for l, n in sorted(roll["lens"].items(), key=lambda kv: -kv[1])) or '<div class="lr"><span class="ln">no lens data yet</span></div>'
    big_rows = "".join(
        f'<div class="m"><span class="a">{esc(x["amt"])}</span>'
        f'<span class="c"><b>{esc(x["date"])} &middot; {esc(x["event"])}</b> &mdash; {esc(x["ctx"])}</span></div>'
        for x in roll["big"]) or '<div class="m"><span class="c">no million-plus lines ingested yet</span></div>'
    bid_money = "".join(
        f'<div class="m"><span class="a">{esc(x["amt"])}</span>'
        f'<span class="c"><b>{esc(x["title"])}</b> &mdash; {esc(x["ctx"])}</span></div>'
        for x in broll["money"]) or '<div class="m"><span class="c">postings rarely show dollars up front &mdash; lens + closing dates are the signal</span></div>'
    bid_lens = " &middot; ".join(f"{esc(l)} &times;{n}"
        for l, n in sorted(broll["lens"].items(), key=lambda kv: -kv[1])) or "none yet"
    permit_lens = " &middot; ".join(f"{esc(l)} &times;{n}"
        for l, n in sorted(proll["lens"].items(), key=lambda kv: -kv[1])) or "none yet"
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    live_n, planned_n = len(live), len(planned)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kilo Aupuni - Maui County situational dashboard</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:980px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:28px;font-weight:600;margin:8px 0 2px}}
 .when{{font-family:Consolas,monospace;font-size:12px;color:#9a957f}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;
        border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:6px;margin:30px 0 12px}}
 .cr{{display:grid;grid-template-columns:1fr 64px 130px 280px;gap:12px;align-items:baseline;
      border-bottom:1px solid rgba(255,255,255,.06);padding:8px 0;font-size:13px}}
 .cd{{font-weight:600}} .cs{{font-family:Consolas,monospace;font-size:11px;font-weight:700}}
 .cw{{font-family:Consolas,monospace;font-size:11px;color:#9a957f}}
 .cu{{font-family:Consolas,monospace;font-size:10.5px}} .cu a{{color:#9a957f}}
 .lr{{display:grid;grid-template-columns:200px 1fr 44px;gap:12px;align-items:center;padding:5px 0}}
 .ln{{font-size:13px;font-weight:600}} .ct{{font-family:Consolas,monospace;font-size:12px;color:#d9b24c;text-align:right}}
 .m{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:13px;color:#d9b24c;white-space:nowrap;min-width:120px}}
 .m .c{{font-size:12.5px;color:#bdb8a4}} .m .c b{{color:#e8e4d8;font-weight:600}}
 .kpi{{display:flex;gap:26px;margin:6px 0 2px}} .kpi div{{font-family:Consolas,monospace}}
 .kpi .n{{font-size:24px;color:#d9b24c}} .kpi .l{{font-size:11px;color:#9a957f;text-transform:uppercase;letter-spacing:1px}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; govOS department watch</div>
<h1>Maui County &mdash; Situational Dashboard</h1>
<div class="when">rolled up {g} &middot; regenerates on every watch run</div>
<div class="kpi">
 <div><div class="n">{live_n}</div><div class="l">live watchers</div></div>
 <div><div class="n">{planned_n}</div><div class="l">planned</div></div>
 <div><div class="n">{roll['meetings']}</div><div class="l">agendas ingested</div></div>
 <div><div class="n">{broll['bids']}</div><div class="l">bids tracked</div></div>
 <div><div class="n">{proll['permits']}</div><div class="l">permits tracked</div></div>
</div>
<div class="sect">Department coverage map</div>
{cov}
<div class="sect">The money behind officials &mdash; ${esc(f"{mroll['re_total']:,.0f}")} real-estate / development across {mroll['officials']} officials</div>
<div class="when" style="margin-bottom:6px"><a href="money_behind_officials.html">&rarr; full campaign-finance map</a> &middot; <a href="charter_application.html">&rarr; Charter &rarr; Law &rarr; Evidence (how to act, lawfully)</a> &middot; source: Hawaii Campaign Spending Commission</div>
{"".join('<div class="m"><span class="a">$' + format(int(r["re"]), ",") + '</span><span class="c"><b>' + esc(r["label"]) + '</b> &mdash; real-estate / dev money of $' + format(int(r["total"]), ",") + ' total raised &middot; ' + str(r["oos"]) + '% out-of-state</span></div>' for r in mroll["rows"][:6] if r["re"]) or '<div class="m"><span class="c">campaign-finance profiles pending</span></div>'}
<div class="sect">Votes &amp; recusals &mdash; follow the money ({vroll['recusals']} recusal(s) across {vroll['officials']} officials)</div>
<div class="when" style="margin-bottom:6px"><a href="officials_scorecard.html">&rarr; full officials scorecard</a> &middot; recusals = formal conflict-of-interest declarations (facts; questions, not accusations)</div>
{"".join(f'<div class="m"><span class="a">{esc(b["name"])}</span><span class="c">{b["recusals"]} recusal(s) / {b["meetings"]} mtgs' + ((' &mdash; ' + esc(", ".join([i for i in b["items"] if i][:4]))) if b["recusals"] else '') + '</span></div>' for b in vroll['by_member'] if b['recusals']) or '<div class="m"><span class="c">no recusals parsed in the ingested minutes window yet</span></div>'}
<div class="sect">Permits &amp; planning (MAPPS) &mdash; {proll['permits']} cases &middot; {proll['recovery']} Lahaina-recovery flagged</div>
<div class="when">lens mix: {permit_lens}</div>
<div class="sect">Procurement &mdash; open bids &amp; RFPs (where money leaves the building)</div>
<div class="when" style="margin-bottom:8px">lens mix: {bid_lens}</div>
{bid_money}
<div class="sect">Lens activity (from live coverage) &middot; what the county keeps touching</div>
{lens_rows}
<div class="sect">Largest dollar figures across ingested agendas</div>
{big_rows}
<footer>generated {g} &middot; Kilo Aupuni v1 (Phase 1) &middot; live: council-watch / CivicClerk all bodies &middot;
 span {esc(roll['span'])} &middot; govOS &middot; aloha in action</footer>
</div></body></html>"""
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(DASH_F, "w", encoding="utf-8") as f:
        f.write(html)
    return roll, broll, proll, vroll, mroll, live, planned

def emit_twin(roll, broll, proll, vroll, mroll, live, planned, ran):
    """Practice 12: Digital Twin instrumentation - every run emits metrics."""
    twin = {
        "module": "kilo-aupuni", "version": "1.1",
        "run_iso": now_hst().strftime("%Y-%m-%d %H:%M:%S HST"),
        "watchers_live": [w["key"] for w in live],
        "watchers_planned": [w["key"] for w in planned],
        "ran_this_cycle": ran,
        "metrics": {
            "agendas_ingested": roll["meetings"],
            "agenda_span": roll["span"],
            "bids_tracked": broll["bids"],
            "permits_tracked": proll["permits"],
            "permits_recovery_flagged": proll["recovery"],
            "officials_tracked": vroll["officials"],
            "recusals_tracked": vroll["recusals"],
            "campaign_realestate_total": mroll["re_total"],
            "lens_activity_council": roll["lens"],
            "lens_activity_bids": broll["lens"],
            "lens_activity_permits": proll["lens"],
        },
    }
    with open(TWIN_F, "w", encoding="utf-8") as f:
        json.dump(twin, f, indent=1, ensure_ascii=False)

def publish_platform():
    """Phase 6: drop the dashboard into 12stones-platform/public/dashboards/ so the
    next gov.12sgi.com deploy serves it. Best-effort - absence of the repo is not an error."""
    try:
        d = os.path.dirname(PLATFORM_DASH)
        if os.path.isdir(d):
            with open(DASH_F, encoding="utf-8") as src, open(PLATFORM_DASH, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            return True
    except Exception as e:
        dispatch("FINDING", f"Kilo Aupuni could not publish dashboard to 12stones-platform: {e}")
    return False

def main():
    reg = load_registry()
    ran = []
    if "--run-watchers" in sys.argv:
        ran = run_live_watchers(reg)
    roll, broll, proll, vroll, mroll, live, planned = build_dashboard(reg)
    emit_twin(roll, broll, proll, vroll, mroll, live, planned, ran)
    pub = publish_platform()
    dispatch("SHIPPED", f"Kilo Aupuni dashboard rebuilt: {len(live)} live / {len(planned)} planned watchers; "
             f"{roll['meetings']} agendas + {broll['bids']} bids + {proll['permits']} permits + "
             f"{vroll['officials']} officials/{vroll['recusals']} recusals + "
             f"${mroll['re_total']:,.0f} RE campaign $"
             + (f"; ran: {', '.join(ran)}" if ran else "")
             + "; twin metrics emitted"
             + ("; published to 12stones-platform/public/dashboards/" if pub else "")
             + " -> reports/mauios/county_dashboard.html")
    return 0

if __name__ == "__main__":
    sys.exit(main())
