#!/usr/bin/env python3
"""county_awards.py — Kilo Aupuni multi-tenant contract awards.
Buckets the STATEWIDE HANDS award record (cached by hands_awards.py / re-fetched) by
jurisdiction into per-tenant contract pages: State of Hawaiʻi, City & County of Honolulu,
plus a jurisdictions hub covering every govOS tenant (HI counties + the New York tenants,
with honest status where a tenant's records aren't in HANDS). Public records, framed as
questions. Output: reports/mauios/contracts_<tenant>.html + jurisdictions.html.
"""
import os, sys, json
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hands_awards as H  # reuse fetch + money/usd/esc helpers

PROJECT = H.PROJECT if hasattr(H, "PROJECT") else os.path.join(
    os.path.expanduser("~"), "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
CACHE = os.path.join(MAUIOS, "_hands_statewide.json")
HST = timezone(timedelta(hours=-10))
usd, esc = H.usd, H.esc
def now_hst(): return datetime.now(HST)

def bucket(r):
    s = ((r.get("jurisdiction") or "") + " " + (r.get("department") or "")).lower()
    if "maui" in s: return "maui"
    if "honolulu" in s or "rapid transit" in s: return "honolulu"
    if "kauai" in s: return "kauai"
    if "county of hawaii" in s or "hawaii county" in s: return "hawaii"
    return "state"

# every govOS tenant — drives the jurisdictions hub
TENANTS = [
    {"id": "state",    "label": "State of Hawaiʻi",            "code": "000", "page": "contracts_state.html",       "source": "HANDS", "status": "live"},
    {"id": "honolulu", "label": "City & County of Honolulu",   "code": "004", "page": "contracts_honolulu.html",    "source": "HANDS", "status": "live"},
    {"id": "maui",     "label": "Maui County",                 "code": "001", "page": "maui_contract_awards.html", "source": "HANDS", "status": "live"},
    {"id": "kauai",    "label": "Kauaʻi County",               "code": "003", "page": "contracts_kauai.html",       "source": "HANDS", "status": "thin", "note": "Kauaʻi County files almost nothing to the State HANDS system — county procurement is posted on its own site. Real coverage needs the county source (next wave)."},
    {"id": "hawaii",   "label": "Hawaiʻi County (Big Island)", "code": "002", "page": "contracts_hawaii.html",      "source": "HANDS", "status": "thin", "note": "No Hawaiʻi County awards appear in State HANDS — county procurement is posted on its own site. Real coverage needs the county source (next wave)."},
    {"id": "nyc",      "label": "New York City",               "code": "NY-NYC",       "page": None, "source": "NYC Open Data (Checkbook NYC + NYC CFB)", "status": "pending", "note": "Different ecosystem: NYC Open Data (Socrata) — Checkbook contracts + Campaign Finance Board. Source confirmed; fetcher is the next wave."},
    {"id": "nys",      "label": "New York State",              "code": "NY-STATE",     "page": None, "source": "OpenBookNY (Comptroller) + NYS BOE", "status": "pending", "note": "NYS Comptroller OpenBookNY contracts + State Board of Elections campaign finance. Source confirmed; fetcher is the next wave."},
    {"id": "liverpool","label": "Village of Liverpool, NY",    "code": "NY-LIV",       "page": None, "source": "Onondaga County + NYS", "status": "pending", "note": "Small village — little standalone open data; leans on Onondaga County records + NYS OpenBook/BOE. Source path identified; thin by nature."},
]

def page(label, vendors, n_awards, dollars):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    rows = "".join(
        f'<div class="m"><span class="a">${usd(v["total"])}</span><span class="n">{v["count"]}</span>'
        f'<span class="c">{esc(v["vendor"])} &middot; {esc((v["awards"][0] or {}).get("dept",""))}</span></div>'
        for v in vendors[:200])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(label)} Contract Awards - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:920px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:82ch}}
 .kpi{{display:flex;gap:28px;margin:14px 0;flex-wrap:wrap}} .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .m{{display:grid;grid-template-columns:140px 50px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}} .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:center}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; {esc(label)} &middot; the vendor side of the money</div>
<h1>{esc(label)} — Contract Awards</h1>
<p class="lead">Every public Notice of Award to a <b>{esc(label)}</b> entity in the State HANDS record
(hands.ehawaii.gov). Who the government pays — set beside who funds the deciders. Top 200 vendors by dollars.</p>
<div class="kpi">
 <div><div class="n">{n_awards:,}</div><div class="l">award notices</div></div>
 <div><div class="n">{len(vendors):,}</div><div class="l">vendors</div></div>
 <div><div class="n">${usd(dollars)}</div><div class="l">total awarded</div></div>
</div>
<div class="disc">Public award notices (HANDS). Receiving a contract is lawful and normal — this is the map of
who is paid, so it can be set beside who funds the officials. Documented facts and open questions, not an allegation.</div>
<div class="m"><span style="text-align:right">awarded</span><span style="text-align:center">#</span><span>vendor &middot; department</span></div>
{rows}
<p style="margin-top:16px"><a href="jurisdictions.html">&larr; all govOS jurisdictions</a> &middot; <a href="reports.html">all reports</a></p>
<footer>generated {g} &middot; county-awards v1 &middot; source: HANDS award notices (public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def hub(stats):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    badge = {"live": '<span style="color:#43d39e">live</span>', "thin": '<span style="color:#e0863a">thin in HANDS</span>',
             "pending": '<span style="color:#9a957f">source identified · next wave</span>'}
    cards = ""
    for t in TENANTS:
        st = stats.get(t["id"], {})
        link = f'<a href="{t["page"]}">open &rarr;</a>' if (t["page"] and t["status"] in ("live", "thin")) else '<span style="color:#756b56">building</span>'
        kpi = (f'<div class="tk">${usd(st.get("dollars",0))} &middot; {st.get("awards",0):,} awards &middot; {st.get("vendors",0):,} vendors</div>'
               if t["status"] in ("live", "thin") else f'<div class="tk" style="color:#756b56">{esc(t.get("source",""))}</div>')
        note = f'<div class="tn">{esc(t.get("note",""))}</div>' if t.get("note") else ""
        cards += (f'<div class="card"><div class="ch"><span class="code">{esc(t["code"])}</span>'
                  f'<b>{esc(t["label"])}</b> {badge.get(t["status"],"")}</div>{kpi}{note}'
                  f'<div class="cl">{link}</div></div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>govOS Jurisdictions - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-top:18px}}
 .card{{border:1px solid rgba(217,178,76,.28);border-radius:12px;padding:14px 16px;background:rgba(217,178,76,.04)}}
 .ch{{font-size:15px}} .code{{font-family:Consolas,monospace;font-size:10px;color:#756b56;border:1px solid #34301f;border-radius:10px;padding:1px 7px;margin-right:8px}}
 .tk{{font-family:Consolas,monospace;font-size:12px;color:#d9b24c;margin-top:7px}}
 .tn{{font-size:11.5px;color:#9a957f;margin-top:6px;line-height:1.5}}
 .cl{{margin-top:9px;font-family:Consolas,monospace;font-size:12px}} a{{color:#d9b24c}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:16px 0}}
 footer{{margin-top:30px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; govOS tenants</div>
<h1>govOS — Jurisdictions</h1>
<p class="lead">One civic-transparency engine, many governments. Each tenant gets the same treatment:
contracts, campaign money, lobbying, and the parity check. <b>Live</b> = real records loaded;
<b>thin</b> = the jurisdiction files little to the shared system (its own source is the next wave);
<b>source identified</b> = the data ecosystem is mapped and the fetcher is queued.</p>
<div class="grid">{cards}</div>
<div class="disc">Hawaiʻi tenants share the State HANDS + Campaign Spending Commission records. New York
tenants (NYC, NY State, Village of Liverpool) use a different ecosystem (NYC Open Data, NYS Comptroller
OpenBookNY, NYS Board of Elections, Onondaga County) — wired in the next wave.</div>
<p><a href="reports.html">&larr; all reports</a></p>
<footer>generated {g} &middot; jurisdictions v1 &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def main():
    if not os.path.exists(CACHE):
        rows, total = H.pull_all()
        json.dump({"generated": now_hst().isoformat(), "total": total, "rows": rows},
                  open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    else:
        rows = json.load(open(CACHE, encoding="utf-8"))["rows"]
    buckets = {}
    for r in rows:
        buckets.setdefault(bucket(r), []).append(r)
    stats = {}
    for t in TENANTS:
        if t["status"] == "pending":
            continue
        brows = buckets.get(t["id"], [])
        vendors = H.build_vendors(brows)
        dollars = sum(v["total"] for v in vendors)
        stats[t["id"]] = {"awards": len(brows), "vendors": len(vendors), "dollars": dollars}
        # State + Honolulu (+ thin Kauai) get a generated page; Maui keeps its own existing page
        if t["id"] in ("state", "honolulu", "kauai", "hawaii") and t["page"]:
            open(os.path.join(MAUIOS, t["page"]), "w", encoding="utf-8").write(page(t["label"], vendors, len(brows), dollars))
    # Maui stats for the hub (from its existing dataset)
    mb = buckets.get("maui", []); mv = H.build_vendors(mb)
    stats["maui"] = {"awards": len(mb), "vendors": len(mv), "dollars": sum(v["total"] for v in mv)}
    open(os.path.join(MAUIOS, "jurisdictions.html"), "w", encoding="utf-8").write(hub(stats))
    json.dump({"generated": now_hst().isoformat(), "tenants": stats},
              open(os.path.join(MAUIOS, "jurisdictions.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for t in TENANTS:
        s = stats.get(t["id"])
        print(f"  {t['id']:<9} {t['status']:<8} " + (f"{s['awards']:>5} awards  ${s['dollars']:>16,.0f}" if s else "(pending)"))
    print("-> contracts_state/honolulu/kauai/hawaii.html + jurisdictions.html")
    return 0

if __name__ == "__main__":
    sys.exit(main())
