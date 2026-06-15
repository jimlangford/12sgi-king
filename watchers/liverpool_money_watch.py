#!/usr/bin/env python3
"""liverpool_money_watch.py - Kilo Aupuni Liverpool / Onondaga County money.

Builds money_liverpool.html from REAL public records on data.ny.gov:

  NYS Board of Elections campaign-finance disclosure (Socrata 4j2b-6a2j,
  "Campaign Finance Disclosure Reports Contributions: Beginning 1999"),
  the same dataset used by nys_money_parity.py, FILTERED to contributors
  whose filed city is Liverpool, NY (the Liverpool / Onondaga County area).

The recipient-side committee location is not in the dataset, but the
CONTRIBUTOR location is (flng_ent_city / flng_ent_zip). So this page answers:
where does campaign money given BY the Liverpool area FLOW TO? Aggregated
server-side by recipient committee (cand_comm_name).

Money fields on Socrata are TEXT with outliers; aggregation is done with
Socrata SoQL sum()/count() server-side and cleaned in python (cast to float,
drop nulls / absurd values). Every line is a documented public record framed
as a question, never an accusation. Source id + URL on the page.
"""
import os, json, ssl, urllib.request, urllib.parse, html
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)", "Accept": "application/json"}

NYS_DOMAIN = "data.ny.gov"
CONTRIB = "4j2b-6a2j"
OUTLIER = 2_000_000_000
# Liverpool, NY contributor city (all spelling/case variants begin "LIVERPOOL").
CITY_WHERE = "upper(flng_ent_city) like 'LIVERPOOL%'"

esc = lambda s: html.escape(str(s or ""))
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)

def soql(dataset, params, timeout=180):
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"https://{NYS_DOMAIN}/resource/{dataset}.json?{qs}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return None

def fetch_recipients():
    rows = soql(CONTRIB, {
        "$select": "cand_comm_name,sum(org_amt) as total,count(1) as n",
        "$where": f"{CITY_WHERE} AND org_amt IS NOT NULL",
        "$group": "cand_comm_name", "$order": "total desc", "$limit": 400})
    out = []
    for r in rows:
        t = num(r.get("total")); n = num(r.get("n"))
        name = (r.get("cand_comm_name") or "").strip()
        if t is None or t <= 0 or t >= OUTLIER or not name:
            continue
        out.append({"name": name, "total": t, "n": int(n or 0)})
    return out

def fetch_totals():
    r = soql(CONTRIB, {
        "$select": "sum(org_amt) as t,count(1) as n,count(distinct cand_comm_name) as rc",
        "$where": f"{CITY_WHERE} AND org_amt IS NOT NULL"})
    d = r[0] if r else {}
    return num(d.get("t")) or 0.0, int(num(d.get("n")) or 0), int(num(d.get("rc")) or 0)

def fetch_types():
    rows = soql(CONTRIB, {
        "$select": "cntrbr_type_desc,sum(org_amt) as t,count(1) as n",
        "$where": f"{CITY_WHERE} AND org_amt IS NOT NULL",
        "$group": "cntrbr_type_desc", "$order": "t desc", "$limit": 50})
    out = []
    for r in rows:
        t = num(r.get("t"))
        if t is None or t <= 0 or t >= OUTLIER:
            continue
        out.append({"type": (r.get("cntrbr_type_desc") or "(unspecified)").strip() or "(unspecified)",
                    "total": t, "n": int(num(r.get("n")) or 0)})
    return out

def page(recips, types, grand_total, grand_n, n_recips):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    top = recips[:200]
    rows = "".join(
        f'<div class="m"><span class="a">${usd(r["total"])}</span><span class="n">{r["n"]:,}</span>'
        f'<span class="c">{esc(r["name"])}</span></div>' for r in top)
    trow = "".join(
        f'<div class="m"><span class="a">${usd(t["total"])}</span><span class="n">{t["n"]:,}</span>'
        f'<span class="c">{esc(t["type"])}</span></div>' for t in types)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Liverpool / Onondaga Campaign Money - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:920px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 70px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;gap:28px;margin:16px 0;flex-wrap:wrap}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .sec{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#d9b24c;border-bottom:1px solid rgba(217,178,76,.2);padding-bottom:6px;margin:26px 0 11px}}
 .m{{display:grid;grid-template-columns:150px 70px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:right}}
 .m .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; Liverpool, NY / Onondaga County &middot; where the money goes</div>
<h1>Liverpool &amp; Onondaga &mdash; Campaign Money, by Recipient</h1>
<p class="lead">Campaign contributions disclosed to the <b>New York State Board of Elections</b> by donors whose
filed address city is <b>Liverpool, NY</b> (Onondaga County), aggregated by recipient committee. Who the
money from this area flows <i>to</i> &mdash; the receiving side of a Central New York village's influence map.
Itemized + reported contributions since 1999. Top 200 recipients by dollars.</p>
<div class="kpi">
 <div><div class="n">${usd(grand_total)}</div><div class="l">given by Liverpool donors</div></div>
 <div><div class="n">{grand_n:,}</div><div class="l">contribution records</div></div>
 <div><div class="n">{n_recips:,}</div><div class="l">recipient committees</div></div>
</div>
<div class="disc">Source: NYS Board of Elections via data.ny.gov, dataset <b>4j2b-6a2j</b>
("Campaign Finance Disclosure Reports Contributions: Beginning 1999") &mdash;
<a href="https://data.ny.gov/d/4j2b-6a2j">https://data.ny.gov/d/4j2b-6a2j</a>.
Filtered server-side to <code>flng_ent_city LIKE 'LIVERPOOL%'</code> (all case/spelling variants), summing the
disclosed <code>org_amt</code> field. The dataset records the <i>contributor's</i> city, not the recipient
committee's, so this is money given <b>by</b> the Liverpool area, not necessarily spent there. The amount field
is free text, so zero/blank amounts were dropped and any single value over $2B treated as a data-entry anomaly.
Giving to campaigns is lawful and normal &mdash; this maps where a village's political money flows, to be read
beside who decides. Documented public record, framed as questions, never findings of wrongdoing.</div>
<h2 class="sec">Top recipients of Liverpool-area giving</h2>
<div class="m"><span style="text-align:right">received</span><span style="text-align:right">#</span><span>recipient committee</span></div>
{rows}
<h2 class="sec">By contributor type</h2>
<div class="m"><span style="text-align:right">given</span><span style="text-align:right">#</span><span>contributor type</span></div>
{trow}
<p style="margin-top:16px"><a href="money_nys.html">&larr; NYS campaign money (statewide)</a>
&middot; <a href="parity_nys.html">vendors &times; donors parity</a>
&middot; <a href="jurisdictions.html">all govOS jurisdictions</a></p>
<footer>generated {g} &middot; liverpool-money v1 &middot; source: NYS Board of Elections / data.ny.gov 4j2b-6a2j (public record), filtered to Liverpool NY contributors &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    recips = fetch_recipients()
    grand_total, grand_n, n_recips = fetch_totals()
    types = fetch_types()
    out = os.path.join(MAUIOS, "money_liverpool.html")
    open(out, "w", encoding="utf-8", newline="\n").write(
        page(recips, types, grand_total, grand_n, n_recips))
    json.dump({"generated": now_hst().isoformat(),
               "source": "data.ny.gov 4j2b-6a2j (NYSBOE), filter flng_ent_city LIKE 'LIVERPOOL%'",
               "url": "https://data.ny.gov/d/4j2b-6a2j",
               "grand_total": round(grand_total, 2), "records": grand_n, "recipients": n_recips,
               "top": recips[:50], "types": types},
              open(os.path.join(MAUIOS, "money_liverpool.json"), "w", encoding="utf-8"), indent=1)
    print(f"money_liverpool: ${grand_total:,.2f} across {n_recips:,} recipients / {grand_n:,} records")
    if recips:
        print(f"   top recipient: {recips[0]['name']} ${recips[0]['total']:,.2f} ({recips[0]['n']} records)")
    print("wrote", out)
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
