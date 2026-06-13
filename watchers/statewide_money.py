#!/usr/bin/env python3
# statewide_money.py - Kilo Aupuni: cross-jurisdiction campaign-finance PATTERNS.
#
# The one deep-history source that genuinely spans every level of Hawaii government:
# the Campaign Spending Commission dataset (Socrata jexd-xbcg), covering Governor,
# Lt. Gov, State House & Senate, all 4 county Councils (Maui/Honolulu/Hawaii/Kauai),
# Mayors, Prosecuting Attorney, and OHA - back to 2008.
#
# It pulls aggregate PATTERNS (server-side SoQL $group, so it's fast even over ~2M rows):
#   1. money by office / jurisdiction
#   2. the biggest donors statewide + how many distinct candidates each funds (the network)
#   3. real-estate / development-sector money by jurisdiction
#   4. year-by-year trend 2008..now
# Integrity: 100% public record; spread/lobby patterns are QUESTIONS, not accusations.
#
# Stdlib only. No popups.
import json, os, ssl, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
OUT_F   = os.path.join(MAUIOS, "statewide_money_patterns.html")
DATA_F  = os.path.join(MAUIOS, "statewide_money.json")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
SODA    = "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
HST     = timezone(timedelta(hours=-10))
RE_KW   = "real estate','realtor','realty','broker','developer','development','properties','construction','contractor"

def now_hst(): return datetime.now(HST)
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def usd(x):
    try: return f"${float(x):,.0f}"
    except Exception: return "$0"
def dispatch(tag,msg):
    try:
        with open(DISPATCH,"a",encoding="utf-8") as f:
            f.write(json.dumps({"ts":int(time.time()),"iso":now_hst().strftime("%Y-%m-%d %H:%M:%S"),
                                "source":"kilo-aupuni","event":f"{tag}: {msg}"},ensure_ascii=False)+"\n")
    except Exception: pass

def soda(params):
    url = SODA + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent":"12sgi-kilo-aupuni/1.0 (civic transparency)"})
    with urllib.request.urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8","replace"))

def fnum(x):
    try: return float(x or 0)
    except Exception: return 0.0

def by_office():
    rows = soda({"$select":"office, sum(amount) as total, count(*) as n","$group":"office","$order":"total DESC"})
    return [{"office":r.get("office") or "(unspecified)","total":fnum(r.get("total")),"n":int(float(r.get("n",0)))} for r in rows]

def top_donors(limit=40):
    rows = soda({"$select":"contributor_name, sum(amount) as total, count(distinct candidate_name) as cands, count(*) as gifts",
                 "$group":"contributor_name","$order":"total DESC","$limit":str(limit)})
    return [{"name":r.get("contributor_name") or "?","total":fnum(r.get("total")),
             "cands":int(float(r.get("cands",0))),"gifts":int(float(r.get("gifts",0)))} for r in rows]

def by_year():
    rows = soda({"$select":"date_trunc_y(date) as yr, sum(amount) as total, count(*) as n","$group":"yr","$order":"yr ASC"})
    out=[]
    for r in rows:
        yr=(r.get("yr") or "")[:4]
        if yr.isdigit(): out.append({"yr":yr,"total":fnum(r.get("total")),"n":int(float(r.get("n",0)))})
    return out

def realestate_by_office():
    where = ("upper(occupation) like '%REAL ESTATE%' or upper(occupation) like '%REALTOR%' or "
             "upper(occupation) like '%DEVELOP%' or upper(occupation) like '%BROKER%' or "
             "upper(employer) like '%REALTY%' or upper(employer) like '%DEVELOPMENT%' or "
             "upper(employer) like '%PROPERTIES%' or upper(contributor_name) like '%REALTOR%'")
    rows = soda({"$select":"office, sum(amount) as total, count(*) as n","$where":where,"$group":"office","$order":"total DESC"})
    return [{"office":r.get("office") or "(unspecified)","total":fnum(r.get("total")),"n":int(float(r.get("n",0)))} for r in rows]

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    off = by_office(); donors = top_donors(); years = by_year(); re_off = realestate_by_office()
    grand = sum(o["total"] for o in off)
    re_grand = sum(o["total"] for o in re_off)
    json.dump({"asOf":now_hst().strftime("%Y-%m-%d %H:%M HST"),"by_office":off,
               "top_donors":donors,"by_year":years,"realestate_by_office":re_off,
               "grand_total":grand,"realestate_total":re_grand},
              open(DATA_F,"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    # ---- html ----
    def rows_money(items,label):
        mx=max((i["total"] for i in items),default=1) or 1
        return "".join(
            f'<div class="m"><span class="a">{usd(i["total"])}</span>'
            f'<span class="bar"><span style="width:{max(2,round(i["total"]/mx*100))}%"></span></span>'
            f'<span class="c">{esc(i.get(label) or "?")} &middot; {i["n"]:,} gifts</span></div>'
            for i in items)
    donor_rows = "".join(
        f'<div class="m"><span class="a">{usd(d["total"])}</span>'
        f'<span class="c">{esc(d["name"])} &mdash; funds <b>{d["cands"]}</b> distinct candidates ({d["gifts"]:,} gifts)</span></div>'
        for d in donors)
    yr_rows = "".join(
        f'<div class="m"><span class="a">{esc(y["yr"])}</span>'
        f'<span class="bar"><span style="width:{max(2,round(y["total"]/(max(z["total"] for z in years) or 1)*100))}%"></span></span>'
        f'<span class="c">{usd(y["total"])} &middot; {y["n"]:,} gifts</span></div>'
        for y in years) if years else ""
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Statewide Money Patterns - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.5}}
 .wrap{{max-width:960px;margin:0 auto;padding:32px 22px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:6px 12px;margin:12px 0}}
 .kpi{{display:flex;gap:28px;margin:10px 0}} .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}} .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:5px;margin:24px 0 10px}}
 .m{{display:grid;grid-template-columns:120px 160px 1fr;gap:12px;align-items:center;border-bottom:1px solid rgba(255,255,255,.06);padding:5px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .bar{{background:rgba(255,255,255,.06);border-radius:4px;height:11px;overflow:hidden}} .m .bar span{{display:block;height:11px;background:linear-gradient(90deg,#d9b24c,rgba(217,178,76,.3))}}
 .m .c{{font-size:12.5px;color:#bdb8a4}} .m .c b{{color:#e8e4d8}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · statewide money patterns</div>
<h1>Hawaii Campaign Money — Every Level, 2008 →</h1>
<p class="lead">Cross-jurisdiction contribution patterns from the Campaign Spending Commission public record:
State (Gov, Lt. Gov, House, Senate), all four county Councils, Mayors, Prosecuting Attorney, OHA.</p>
<div class="disc">Public record. Spread (one donor funding many candidates across jurisdictions) and sector
concentration are <b>patterns to investigate</b> — lawful giving, not proof of anything. The question is
whether the money tracks the votes.</div>
<div class="kpi"><div><div class="n">{usd(grand)}</div><div class="l">total tracked 2008→</div></div>
 <div><div class="n">{usd(re_grand)}</div><div class="l">real-estate / dev sector</div></div></div>
<div class="sect">Money by office / jurisdiction</div>
{rows_money(off,"office")}
<div class="sect">Real-estate / development money by jurisdiction</div>
{rows_money(re_off,"office")}
<div class="sect">Biggest donors statewide — and how many candidates each funds (the network)</div>
{donor_rows}
<div class="sect">Year by year (2008 →)</div>
{yr_rows}
<footer>generated {g} · statewide-money v1 · source: Hawaii Campaign Spending Commission (jexd-xbcg) · public record · MauiOS</footer>
</div></body></html>"""
    with open(OUT_F,"w",encoding="utf-8") as f: f.write(html)
    dispatch("SHIPPED", f"statewide-money patterns: {usd(grand)} tracked across {len(off)} offices/jurisdictions "
             f"(2008-->now), {usd(re_grand)} real-estate sector; top-donor network mapped "
             f"-> reports/mauios/statewide_money_patterns.html")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
