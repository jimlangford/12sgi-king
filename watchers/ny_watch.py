#!/usr/bin/env python3
"""ny_watch.py — Kilo Aupuni New York tenants (contracts spine, wave 1).
Pulls NYC Open Data (Socrata) 'Recent Contract Awards' (qyyg-4tf5), cleans the text/outlier
amounts in Python, aggregates by vendor -> contracts_nyc.html. NY State (OpenBookNY) and the
Village of Liverpool (Onondaga + NYS) are stubbed with their confirmed sources for the next
pass. Public records, framed as documented facts + open questions.
"""
import os, json, ssl, time, urllib.request, urllib.parse, html
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
NYC_DOMAIN = "data.cityofnewyork.us"
NYC_CONTRACTS = "qyyg-4tf5"
NYS_DOMAIN = "data.ny.gov"
NYS_DC = "rb9h-9fit"   # State Design & Construction Capital Projects Vendor Payments (has a county field)
OUTLIER = 2_000_000_000   # > $2B single award = treat as a data anomaly, exclude from totals (flagged honestly)
esc = lambda s: html.escape(str(s or ""))
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)

def socrata(domain, dataset, params):
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"https://{domain}/resource/{dataset}.json?{qs}"
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def fetch_nyc_awards():
    rows, off, PAGE = [], 0, 50000
    while True:
        batch = socrata(NYC_DOMAIN, NYC_CONTRACTS, {
            "$select": "vendor_name,contract_amount,agency_name,short_title,start_date",
            "$where": "type_of_notice_description='Award'",
            "$limit": PAGE, "$offset": off})
        rows += batch
        if len(batch) < PAGE:
            break
        off += PAGE; time.sleep(0.3)
    return rows

def num(s):
    try: return float(str(s).replace(",", "").strip())
    except Exception: return None

def aggregate(rows):
    by, excluded, excl_sum, nulls = {}, 0, 0.0, 0
    for r in rows:
        amt = num(r.get("contract_amount"))
        name = (r.get("vendor_name") or "").strip()
        if amt is None or amt <= 0:
            nulls += 1; continue
        if amt >= OUTLIER:
            excluded += 1; excl_sum += amt; continue
        if not name:
            continue
        e = by.setdefault(name, {"vendor": name, "total": 0.0, "count": 0, "agency": r.get("agency_name")})
        e["total"] += amt; e["count"] += 1
    vendors = sorted(by.values(), key=lambda x: -x["total"])
    return vendors, {"excluded_outliers": excluded, "excluded_sum": excl_sum, "nulls": nulls}

def page(vendors, n_awards, dollars, flags):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    rows = "".join(
        f'<div class="m"><span class="a">${usd(v["total"])}</span><span class="n">{v["count"]}</span>'
        f'<span class="c">{esc(v["vendor"])} &middot; {esc(v["agency"])}</span></div>'
        for v in vendors[:200])
    note = (f' Excluded {flags["excluded_outliers"]} award notices with a single amount over $2B '
            f'(${usd(flags["excluded_sum"])}) as likely data-entry anomalies in the City Record feed; '
            f'{flags["nulls"]} rows had no/zero amount.') if flags["excluded_outliers"] or flags["nulls"] else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>New York City Contract Awards - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:920px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:82ch}}
 .kpi{{display:flex;gap:28px;margin:14px 0;flex-wrap:wrap}} .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .m{{display:grid;grid-template-columns:150px 50px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}} .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:center}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York City &middot; the vendor side of the money</div>
<h1>New York City — Contract Awards</h1>
<p class="lead">Award notices to NYC vendors from <b>NYC Open Data</b> (City Record "Recent Contract Awards").
Who the City pays — the vendor side of the money map. Top 200 vendors by dollars.</p>
<div class="kpi">
 <div><div class="n">{n_awards:,}</div><div class="l">clean award notices</div></div>
 <div><div class="n">{len(vendors):,}</div><div class="l">vendors</div></div>
 <div><div class="n">${usd(dollars)}</div><div class="l">total awarded (cleaned)</div></div>
</div>
<div class="disc">Public award notices (NYC Open Data, dataset qyyg-4tf5). Receiving a City contract is lawful and
normal — this maps who is paid so it can be read beside who funds the officials.{note} Documented facts and open questions.</div>
<div class="m"><span style="text-align:right">awarded</span><span style="text-align:center">#</span><span>vendor &middot; agency</span></div>
{rows}
<p style="margin-top:16px"><a href="jurisdictions.html">&larr; all govOS jurisdictions</a> &middot; <a href="reports.html">all reports</a></p>
<footer>generated {g} &middot; ny-watch v1 &middot; source: NYC Open Data / City Record (public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def gpage(title, lead, source, vendors, n, dollars, scope_note=""):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    rows = "".join(
        f'<div class="m"><span class="a">${usd(v["total"])}</span><span class="n">{v["count"]}</span>'
        f'<span class="c">{esc(v["vendor"])} &middot; {esc(v.get("agency",""))}</span></div>'
        for v in vendors[:200])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:920px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;font-weight:600;margin:8px 0 2px}} .lead{{font-size:13.5px;color:#bdb8a4;max-width:82ch}}
 .kpi{{display:flex;gap:28px;margin:14px 0;flex-wrap:wrap}} .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .m{{display:grid;grid-template-columns:150px 50px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}} .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:center}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; the vendor side of the money</div>
<h1>{esc(title)}</h1>
<p class="lead">{lead}</p>
<div class="kpi">
 <div><div class="n">{n:,}</div><div class="l">payments</div></div>
 <div><div class="n">{len(vendors):,}</div><div class="l">vendors</div></div>
 <div><div class="n">${usd(dollars)}</div><div class="l">total paid</div></div>
</div>
<div class="disc">{scope_note} Source: {esc(source)} (public record). Receiving public contracts is lawful — this maps who is paid, to read beside who funds the deciders. Documented facts and open questions.</div>
<div class="m"><span style="text-align:right">paid</span><span style="text-align:center">#</span><span>vendor &middot; type</span></div>
{rows}
<p style="margin-top:16px"><a href="jurisdictions.html">&larr; all govOS jurisdictions</a> &middot; <a href="reports.html">all reports</a></p>
<footer>generated {g} &middot; ny-watch v1 &middot; source: {esc(source)} &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def fetch_nys_dc():
    rows, off, PAGE = [], 0, 50000
    while True:
        batch = socrata(NYS_DOMAIN, NYS_DC, {"$select": "vendor,paymentamount,county,typeofservice",
                                             "$limit": PAGE, "$offset": off})
        rows += batch
        if len(batch) < PAGE: break
        off += PAGE; time.sleep(0.3)
    return rows

def agg_nys(rows, county=None):
    by = {}
    for r in rows:
        if county and county.lower() not in (r.get("county") or "").lower():
            continue
        amt = num(r.get("paymentamount")); name = (r.get("vendor") or "").strip()
        if amt is None or amt <= 0 or amt >= OUTLIER or not name:
            continue
        e = by.setdefault(name, {"vendor": name, "total": 0.0, "count": 0, "agency": r.get("typeofservice")})
        e["total"] += amt; e["count"] += 1
    return sorted(by.values(), key=lambda x: -x["total"])

def write_tenant(tid, html_str, stats):
    open(os.path.join(MAUIOS, f"contracts_{tid}.html"), "w", encoding="utf-8").write(html_str)
    json.dump({"generated": now_hst().isoformat(), **stats},
              open(os.path.join(MAUIOS, f"contracts_{tid}.json"), "w", encoding="utf-8"), indent=1)

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    # --- NYC: City Record award notices ---
    rows = fetch_nyc_awards()
    vendors, flags = aggregate(rows)
    dollars = sum(v["total"] for v in vendors); n_awards = sum(v["count"] for v in vendors)
    open(os.path.join(MAUIOS, "contracts_nyc.html"), "w", encoding="utf-8").write(page(vendors, n_awards, dollars, flags))
    json.dump({"generated": now_hst().isoformat(), "source": "NYC Open Data qyyg-4tf5",
               "clean_awards": n_awards, "vendors": len(vendors), "dollars": round(dollars, 2), "flags": flags},
              open(os.path.join(MAUIOS, "contracts_nyc.json"), "w", encoding="utf-8"), indent=1)
    print(f"ny-watch NYC: {n_awards:,} clean awards / {len(vendors):,} vendors / ${dollars:,.0f}")

    # --- NY State + Liverpool (Onondaga slice) from the D&C capital-projects vendor payments ---
    try:
        nys = fetch_nys_dc()
        sv = agg_nys(nys); sd = sum(v["total"] for v in sv); sn = sum(v["count"] for v in sv)
        write_tenant("nys", gpage("New York State — Capital Project Vendor Payments",
            "State Design &amp; Construction capital-project vendor payments (NY Open Data, OSC). One slice of "
            "State spending &mdash; the vendors paid to build, ranked by dollars. Top 200.",
            "data.ny.gov rb9h-9fit (NYS Comptroller)", sv, sn, sd,
            "Scope: State D&amp;C capital-project payments only (not all NY State procurement; broader OpenBookNY coverage is the next pass)."),
            {"source": "data.ny.gov rb9h-9fit", "awards": sn, "vendors": len(sv), "dollars": round(sd, 2)})
        print(f"ny-watch NYS: {sn:,} payments / {len(sv):,} vendors / ${sd:,.0f}")
        lv = agg_nys(nys, county="onondaga"); ld = sum(v["total"] for v in lv); ln = sum(v["count"] for v in lv)
        write_tenant("liverpool", gpage("Liverpool Area (Onondaga County) — State Vendor Payments",
            "State capital-project vendor payments <b>in Onondaga County</b> &mdash; the county the Village of "
            "Liverpool sits in. Village-level procurement is not separately published in open data, so this is the "
            "nearest public slice of government contract money in the Liverpool area. Top 200.",
            "data.ny.gov rb9h-9fit (NYS Comptroller), Onondaga County", lv, ln, ld,
            "Scope: Onondaga County state capital-project payments &mdash; a proxy for the Liverpool area, NOT village-level spending."),
            {"source": "data.ny.gov rb9h-9fit (Onondaga)", "awards": ln, "vendors": len(lv), "dollars": round(ld, 2)})
        print(f"ny-watch Liverpool(Onondaga): {ln:,} payments / {len(lv):,} vendors / ${ld:,.0f}")
    except Exception as e:
        print(f"ny-watch NYS/Liverpool failed (left pending): {e}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
