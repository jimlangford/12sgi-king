#!/usr/bin/env python3
"""liverpool_village_finance.py — Kilo Aupuni: Village of Liverpool actual budget.

Replaces the Onondaga-County-proxy contracts page with the REAL Village of Liverpool
financial record, published by the NYS Office of the State Comptroller (OSC) in its
"Financial Data for Local Governments" bulk export (Open Book New York / Local
Government Interactive Data). Every village files an Annual Financial Report (AFR /
"Annual Update Document") with OSC; OSC publishes it as revenue, expenditure, balance
sheet and debt line items per municipality per fiscal year.

Source: NYS Comptroller, Financial Data for Local Governments (village class export),
https://wwe1.osc.state.ny.us/localgov/findata/financial-data-for-local-governments.cfm
Open Book New York: https://www.openbooknewyork.com/
Entity: Village of Liverpool, Onondaga County (municipal code 310473902750),
fiscal year June 1 - May 31.

Public records. Documented facts + open questions, never accusations.
Output: reports/mauios/contracts_liverpool.html (+ liverpool_village_finance.json).
"""
import os, io, csv, json, zipfile, ssl, urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
CACHE = os.path.join(MAUIOS, "_liverpool_src_village_2023.zip")
OUT_HTML = os.path.join(MAUIOS, "contracts_liverpool.html")
OUT_JSON = os.path.join(MAUIOS, "liverpool_village_finance.json")
DL_URL = "https://wwe1.osc.state.ny.us/localgov/findata/detailedzip.cfm"
ENTITY = "village of liverpool"
ET = timezone(timedelta(hours=-4))  # village is in NY; HST footer for govOS continuity
UA = {"User-Agent": "Mozilla/5.0 (kilo-aupuni civic transparency; public record)"}
esc = lambda s: str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
usd = lambda n: f"{n:,.0f}"


def ensure_zip():
    if os.path.exists(CACHE) and os.path.getsize(CACHE) > 1_000_000:
        return
    os.makedirs(MAUIOS, exist_ok=True)
    body = "radRebDebt=reb&radSingleAllYear=scay&selMuniClass=village&selSingYear=2025".encode()
    req = urllib.request.Request(DL_URL, data=body, headers=UA)
    blob = urllib.request.urlopen(req, timeout=180, context=ssl.create_default_context()).read()
    assert blob[:2] == b"PK", "OSC did not return a zip"
    open(CACHE, "wb").write(blob)


def fnum(r):
    try:
        return float(r.get("AMOUNT") or 0)
    except Exception:
        return 0.0


def liverpool_rows(z, year):
    name = f"{year}_Village.csv"
    if name not in z.namelist():
        return []
    data = z.read(name).decode("utf-8-sig", "replace")
    return [r for r in csv.DictReader(io.StringIO(data))
            if (r.get("ENTITY_NAME") or "").strip().lower() == ENTITY]


def section_total(rows, sec):
    return sum(fnum(r) for r in rows if (r.get("ACCOUNT_CODE_SECTION") or "") == sec)


def by_level1(rows, sec):
    agg = defaultdict(float)
    for r in rows:
        if (r.get("ACCOUNT_CODE_SECTION") or "") == sec:
            agg[r.get("LEVEL_1_CATEGORY") or "(uncategorized)"] += fnum(r)
    return sorted(((k, v) for k, v in agg.items() if v), key=lambda x: -x[1])


def main():
    ensure_zip()
    z = zipfile.ZipFile(CACHE)
    years = [str(y) for y in range(2016, 2027)]
    trend = []
    for y in years:
        rows = liverpool_rows(z, y)
        if not rows:
            continue
        rev = section_total(rows, "REVENUE")
        exp = section_total(rows, "EXPENDITURE")
        trend.append({"year": y, "period_end": rows[0].get("PERIOD_END"),
                      "revenue": round(rev), "expenditure": round(exp),
                      "balance": round(rev - exp), "lines": len(rows)})
    # latest fully-reported year = last with both rev & exp > 0
    latest = [t for t in trend if t["revenue"] and t["expenditure"]][-1]
    lrows = liverpool_rows(z, latest["year"])
    rev_cat = by_level1(lrows, "REVENUE")
    exp_cat = by_level1(lrows, "EXPENDITURE")
    muni_code = (lrows[0].get("MUNICIPAL_CODE") or "").strip()
    county = (lrows[0].get("COUNTY") or "").strip()

    out = {"generated": datetime.now(ET).isoformat(), "entity": "Village of Liverpool",
           "municipal_code": muni_code, "county": county,
           "source": ("NYS Comptroller, Financial Data for Local Governments "
                      "(village class export); Open Book New York"),
           "latest_fy": latest, "trend": trend,
           "revenue_by_category": [{"cat": k, "amount": round(v)} for k, v in rev_cat],
           "expenditure_by_category": [{"cat": k, "amount": round(v)} for k, v in exp_cat]}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(OUT_HTML, "w", encoding="utf-8").write(build_page(out))
    print(f"liverpool: FY{latest['year']} rev ${latest['revenue']:,} exp ${latest['expenditure']:,}; "
          f"{len(trend)} yrs of AFR data -> reports/mauios/contracts_liverpool.html")
    return 0


def build_page(o):
    g = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    lf = o["latest_fy"]
    fy = lf["year"]
    pe = lf["period_end"]
    # revenue rows
    revtot = sum(c["amount"] for c in o["revenue_by_category"]) or 1
    exptot = sum(c["amount"] for c in o["expenditure_by_category"]) or 1
    rev_rows = "".join(
        f'<div class="m"><span class="a">${usd(c["amount"])}</span>'
        f'<span class="n">{c["amount"]*100/revtot:.0f}%</span>'
        f'<span class="c">{esc(c["cat"])}</span></div>'
        for c in o["revenue_by_category"])
    exp_rows = "".join(
        f'<div class="m"><span class="a">${usd(c["amount"])}</span>'
        f'<span class="n">{c["amount"]*100/exptot:.0f}%</span>'
        f'<span class="c">{esc(c["cat"])}</span></div>'
        for c in o["expenditure_by_category"])
    # trend rows (most recent first)
    tr_rows = ""
    for t in reversed(o["trend"]):
        bal = t["balance"]
        bc = "#7bbd6a" if bal >= 0 else "#e06a4a"
        sign = "+" if bal >= 0 else "−"
        tr_rows += (f'<div class="tr"><span class="y">FY{t["year"]}</span>'
                    f'<span class="a">${usd(t["revenue"])}</span>'
                    f'<span class="a">${usd(t["expenditure"])}</span>'
                    f'<span class="a" style="color:{bc}">{sign}${usd(abs(bal))}</span></div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Village of Liverpool — Where the Money Comes From and Goes - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:920px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:30px 0 4px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;gap:28px;margin:16px 0;flex-wrap:wrap}} .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .sub{{font-size:12.5px;color:#bdb8a4;margin:2px 0 8px;max-width:84ch}}
 .m{{display:grid;grid-template-columns:150px 50px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}} .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:center}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 .tr{{display:grid;grid-template-columns:84px 1fr 1fr 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .tr .y{{font-family:Consolas,monospace;font-size:12px;color:#bdb8a4}} .tr .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .tr.hd .y,.tr.hd .a{{color:#756b56;font-size:11px;text-transform:uppercase}}
 .q{{background:rgba(217,178,76,.05);border:1px solid rgba(217,178,76,.25);border-radius:10px;padding:12px 15px;margin:18px 0;font-size:13px;color:#cfc9b6}} .q b{{color:#e8e4d8}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; the village ledger itself</div>
<h1>Village of Liverpool &mdash; Where the Money Comes From and Goes</h1>
<p class="lead">The actual <b>Village of Liverpool</b> budget &mdash; not a county proxy. Every New York village files an
Annual Financial Report with the State Comptroller; this is Liverpool's own ledger, by revenue source and by
function, for the fiscal year ending <b>{esc(pe)}</b> (the village runs June&nbsp;1&ndash;May&nbsp;31).
Municipal code {esc(o["municipal_code"])}, {esc(o["county"])} County.</p>
<div class="kpi">
 <div><div class="n">${usd(lf["revenue"])}</div><div class="l">total revenue FY{fy}</div></div>
 <div><div class="n">${usd(lf["expenditure"])}</div><div class="l">total expenditure FY{fy}</div></div>
 <div><div class="n" style="color:{'#7bbd6a' if lf['balance']>=0 else '#e06a4a'}">{'+' if lf['balance']>=0 else '−'}${usd(abs(lf['balance']))}</div><div class="l">rev minus exp</div></div>
 <div><div class="n">{len(o["trend"])}</div><div class="l">years on file</div></div>
</div>
<div class="disc">Source: NYS Office of the State Comptroller, <b>Financial Data for Local Governments</b>
(village-class bulk export; the same data behind <a href="https://www.openbooknewyork.com/">Open Book New York</a>
and the OSC Local Government Interactive Data tool). Figures are the village's self-reported Annual Financial
Report line items, summed in code from account-level records. Spending public money is the job of a village &mdash;
this maps where it comes from and where it goes, so residents can read it. Documented facts and open questions.</div>

<h2>Where the money comes from &mdash; revenue by source, FY{fy}</h2>
<p class="sub">Liverpool's own revenue, by category. The share of the budget that is local property tax versus state
aid versus fees tells you who the village answers to for its money.</p>
<div class="m" style="border-bottom:1px solid rgba(217,178,76,.25)"><span class="a" style="color:#756b56">amount</span><span class="n" style="color:#756b56">%</span><span class="c" style="color:#756b56">revenue source</span></div>
{rev_rows}

<h2>Where the money goes &mdash; expenditure by function, FY{fy}</h2>
<p class="sub">What the village actually buys with that money, by function. The largest functions are where contracts,
payroll, and procurement decisions concentrate &mdash; the lines worth asking the village clerk to itemize.</p>
<div class="m" style="border-bottom:1px solid rgba(217,178,76,.25)"><span class="a" style="color:#756b56">amount</span><span class="n" style="color:#756b56">%</span><span class="c" style="color:#756b56">function</span></div>
{exp_rows}

<h2>The trend &mdash; revenue vs. expenditure by year</h2>
<p class="sub">Multiple fiscal years from the same OSC export. A village that consistently spends more than it takes in,
or leans harder each year on one revenue source, is a question for the next budget hearing.</p>
<div class="tr hd"><span class="y">fiscal yr</span><span class="a">revenue</span><span class="a">expenditure</span><span class="a">rev &minus; exp</span></div>
{tr_rows}

<div class="q"><b>The question.</b> This is village-level money at last &mdash; Liverpool's own AFR, not the
Onondaga-County proxy that stood here before. The named gaps that still need the <b>village clerk</b>: the actual
<b>check register / vendor payments</b> (who specifically is paid, by name), the <b>adopted budget vs. actuals</b>,
and any <b>capital-project contracts</b>. Those are a New York FOIL request to the Village of Liverpool Clerk,
43 Second Street, Liverpool NY 13088 &mdash; or the village site
<a href="https://www.villageofliverpool.org/">villageofliverpool.org</a>. Read this ledger beside who funds the
trustees who adopt it.</div>

<p style="margin-top:16px"><a href="jurisdictions.html">&larr; all govOS jurisdictions</a> &middot; <a href="reports.html">all reports</a></p>
<footer>generated {g} &middot; ny-village-finance v1 &middot; source: NYS Comptroller Financial Data for Local Governments / Open Book New York (village AFR, public record) &middot; Village of Liverpool, Onondaga County &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""


if __name__ == "__main__":
    import sys
    sys.exit(main())
