#!/usr/bin/env python3
"""nys_money_parity.py - Kilo Aupuni New York State money + parity.

Builds two civic-transparency pages from REAL public records on data.ny.gov:

 1) money_nys.html  - NYS Board of Elections campaign-finance disclosure
    (Socrata 4j2b-6a2j "Campaign Finance Disclosure Reports Contributions:
    Beginning 1999"). Aggregated SERVER-SIDE by recipient committee
    (cand_comm_name) -> top recipients of campaign money in NY.

 2) parity_nys.html - crosses NYS contract vendors (data.ny.gov rb9h-9fit,
    the D&C capital-project vendor payments already used for contracts_nys)
    against NYS organizational campaign donors (corporations / LLCs / LLPs
    / sole proprietorships from 4j2b-6a2j). Overlaps are framed as QUESTIONS:
    a name that BOTH receives State capital payments AND donates to NY
    campaigns is a double channel - on the map as a question, not a finding.

Money fields on Socrata are TEXT with outliers; aggregation is done with
Socrata SoQL sum()/count() server-side (12.7M contribution rows make a full
client pull impractical), and the cross-join pulls only the org-contributor
slice, cleaned in python (cast to float, drop nulls/absurd values).

Integrity: every correlation is a question against public records, never an
accusation; sources cited on every page; honest pending if a source fails.
"""
import os, json, ssl, time, urllib.request, urllib.parse, html, re
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)", "Accept": "application/json"}

NYS_DOMAIN = "data.ny.gov"
CONTRIB = "4j2b-6a2j"   # Campaign Finance Disclosure Reports Contributions: Beginning 1999 (NYSBOE)
VENDORS = "rb9h-9fit"   # State D&C capital-project vendor payments (used for contracts_nys)
OUTLIER = 2_000_000_000  # single value over $2B = data anomaly, exclude (flagged honestly)

# org-type contributors that could plausibly also be State vendors
ORG_TYPES = ("Corporation",
             "Professional/Limited Liability Company (PLLC/LLC)",
             "Partnership including LLPs",
             "Sole Proprietorship",
             "Association")

esc = lambda s: html.escape(str(s or ""))
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)

def soql(dataset, params, timeout=120):
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"https://{NYS_DOMAIN}/resource/{dataset}.json?{qs}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def num(s):
    try:
        v = float(str(s).replace(",", "").strip())
        return v
    except Exception:
        return None

def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()

SUFFIX = re.compile(r"\b(llc|inc|ltd|lp|llp|pllc|corp|corporation|company|co|"
                    r"incorporated|limited|associates|assoc|group|pc)\b.*$")
def org_key(name):
    n = norm(name)
    k = SUFFIX.sub("", n).strip()
    return k if len(k) >= 6 and len(k.split()) >= 1 else (n if len(n) >= 6 else "")

# generic tokens that would create false matches if used as a key (stoplist)
STOP = {"city of", "town of", "county of", "state of", "department of", "the",
        "new york", "village of", "board of", "office of"}

# ---------------------------------------------------------------- money_nys
def fetch_recipients():
    rows = soql(CONTRIB, {
        "$select": "cand_comm_name,sum(org_amt) as total,count(1) as n",
        "$where": "org_amt IS NOT NULL",
        "$group": "cand_comm_name", "$order": "total desc", "$limit": 250})
    out = []
    for r in rows:
        t = num(r.get("total")); n = num(r.get("n"))
        name = (r.get("cand_comm_name") or "").strip()
        if t is None or t <= 0 or t >= OUTLIER or not name:
            continue
        out.append({"name": name, "total": t, "n": int(n or 0)})
    return out

def fetch_totals():
    r = soql(CONTRIB, {"$select": "sum(org_amt) as t,count(1) as n,count(distinct cand_comm_name) as rc",
                       "$where": "org_amt IS NOT NULL"})
    d = r[0] if r else {}
    return num(d.get("t")) or 0.0, int(num(d.get("n")) or 0), int(num(d.get("rc")) or 0)

def money_page(recips, grand_total, grand_n, n_recips):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    top = recips[:200]
    rows = "".join(
        f'<div class="m"><span class="a">${usd(r["total"])}</span><span class="n">{r["n"]:,}</span>'
        f'<span class="c">{esc(r["name"])}</span></div>' for r in top)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>New York State Campaign Money - Kilo Aupuni</title>
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
 .m{{display:grid;grid-template-columns:150px 70px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:right}}
 .m .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York State &middot; who the money is given to</div>
<h1>New York State &mdash; Campaign Money, by Recipient</h1>
<p class="lead">Campaign contributions disclosed to the <b>New York State Board of Elections</b>, aggregated by
recipient committee. Who the money flows <i>to</i> &mdash; the receiving side of NY's influence map.
Itemized + reported contributions since 1999. Top 200 recipients by dollars.</p>
<div class="kpi">
 <div><div class="n">${usd(grand_total)}</div><div class="l">total contributions disclosed</div></div>
 <div><div class="n">{grand_n:,}</div><div class="l">contribution records</div></div>
 <div><div class="n">{n_recips:,}</div><div class="l">recipient committees</div></div>
</div>
<div class="disc">Source: NYS Board of Elections via data.ny.gov, dataset <b>4j2b-6a2j</b>
("Campaign Finance Disclosure Reports Contributions: Beginning 1999"). Amounts are the disclosed
<code>org_amt</code> field, summed server-side; the field is free text, so zero/blank amounts were dropped
and any single value over $2B treated as a data-entry anomaly. Receiving campaign contributions is lawful
and normal &mdash; this maps who receives, to be read beside who gives and who decides. Documented public
record, framed as questions, never findings of wrongdoing.</div>
<div class="m"><span style="text-align:right">received</span><span style="text-align:right">#</span><span>recipient committee</span></div>
{rows}
<p style="margin-top:16px"><a href="parity_nys.html">vendors &times; donors parity &rarr;</a>
&middot; <a href="contracts_nys.html">NYS contract vendors</a>
&middot; <a href="jurisdictions.html">all govOS jurisdictions</a></p>
<footer>generated {g} &middot; nys-money v1 &middot; source: NYS Board of Elections / data.ny.gov 4j2b-6a2j (public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

# ---------------------------------------------------------------- parity_nys
def fetch_org_donors():
    """Org-type contributors aggregated by flng_ent_name (the corporate name field)."""
    where = "flng_ent_name IS NOT NULL AND org_amt IS NOT NULL AND cntrbr_type_desc in (" \
            + ",".join("'%s'" % t.replace("'", "''") for t in ORG_TYPES) + ")"
    rows = soql(CONTRIB, {
        "$select": "flng_ent_name,sum(org_amt) as total,count(1) as n",
        "$where": where, "$group": "flng_ent_name", "$order": "total desc", "$limit": 5000})
    out = []
    for r in rows:
        t = num(r.get("total")); n = num(r.get("n"))
        name = (r.get("flng_ent_name") or "").strip()
        if t is None or t <= 0 or t >= OUTLIER or not name:
            continue
        out.append({"name": name, "total": t, "n": int(n or 0), "key": org_key(name)})
    return out

def fetch_vendors():
    rows, off, PAGE = [], 0, 50000
    while True:
        batch = soql(VENDORS, {"$select": "vendor,paymentamount,typeofservice",
                               "$limit": PAGE, "$offset": off})
        rows += batch
        if len(batch) < PAGE:
            break
        off += PAGE; time.sleep(0.3)
    by = {}
    for r in rows:
        amt = num(r.get("paymentamount")); name = (r.get("vendor") or "").strip()
        if amt is None or amt <= 0 or amt >= OUTLIER or not name:
            continue
        e = by.setdefault(name, {"vendor": name, "total": 0.0, "count": 0,
                                 "service": r.get("typeofservice"), "key": org_key(name)})
        e["total"] += amt; e["count"] += 1
    return sorted(by.values(), key=lambda x: -x["total"])

def build_overlap(vendors, donors):
    # index donors by normalized key, SUMMING all spelling variants of the same
    # org together (e.g. "LaBella Associates DPC" / "LaBella Assoc." / "LaBella
    # Associates D.P.C." collapse to one key) so giving is not fragmented across
    # rows. Keep the most-common display label (largest single-variant total).
    dk = {}
    for d in donors:
        if not d["key"] or d["key"] in STOP:
            continue
        e = dk.get(d["key"])
        if not e:
            dk[d["key"]] = {"name": d["name"], "total": d["total"], "n": d["n"],
                            "label_total": d["total"]}
        else:
            e["total"] += d["total"]; e["n"] += d["n"]
            if d["total"] > e["label_total"]:
                e["name"] = d["name"]; e["label_total"] = d["total"]
    out = []
    seen = set()
    for v in vendors:
        k = v["key"]
        if not k or k in STOP or k in seen:
            continue
        d = dk.get(k)
        if not d:
            continue
        seen.add(k)
        lev = round(v["total"] / d["total"], 1) if d["total"] > 0 else None
        out.append({
            "key": k,
            "vendor": v["vendor"], "vendor_paid": v["total"], "vendor_n": v["count"],
            "donor": d["name"], "donor_given": d["total"], "donor_n": d["n"],
            "leverage": lev,
            "question": (f"{v['vendor']} received ${v['total']:,.0f} in State capital-project payments; an "
                         f"organization recorded as {d['name']} gave ${d['total']:,.0f} to NY campaigns. Are "
                         f"these the same entity, and if so does the public contract answer the public record "
                         f"or the campaign giving? (public records - a correlation to verify, not a finding)")
        })
    out.sort(key=lambda x: -(x["leverage"] or 0))
    return out

def parity_page(overlap, n_vendors, n_donors, vendor_dollars):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    total_paid = sum(o["vendor_paid"] for o in overlap)
    total_given = sum(o["donor_given"] for o in overlap)
    agg_lev = round(total_paid / total_given, 1) if total_given else None
    kp = (f'<div class="kp"><div class="kv" style="color:#e06a4a">{len(overlap)}</div>'
          f'<div class="kl">name-matched vendor&times;donor pairs</div></div>'
          f'<div class="kp"><div class="kv" style="color:#e06a4a">${usd(total_paid)}</div>'
          f'<div class="kl">State payments to matched names</div></div>'
          f'<div class="kp"><div class="kv" style="color:#d9b24c">${usd(total_given)}</div>'
          f'<div class="kl">campaign giving by matched names</div></div>'
          f'<div class="kp"><div class="kv" style="color:#e06a4a">{usd(agg_lev) if agg_lev else "n/a"}x</div>'
          f'<div class="kl">aggregate leverage</div></div>')
    rows = ""
    for o in overlap[:120]:
        lv = f'{o["leverage"]:,.0f}x' if o["leverage"] else "n/a"
        rows += (f'<div class="row"><span class="a">{lv}</span><span class="c"><b>{esc(o["vendor"])}</b> &mdash; '
                 f'${usd(o["vendor_paid"])} State payments / matched donor <b>{esc(o["donor"])}</b> '
                 f'gave ${usd(o["donor_given"])}. <span style="color:#9a957f">{esc(o["question"])}</span></span></div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>New York State - Vendors That Also Donate - Kilo Aupuni Parity</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 80px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:6px 12px;margin:14px 0}}
 .dash{{border:1px solid rgba(217,178,76,.25);border-radius:14px;padding:18px 20px;margin:18px 0 26px;background:rgba(217,178,76,.03)}}
 .sec{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#d9b24c;border-bottom:1px solid rgba(217,178,76,.2);padding-bottom:6px;margin:22px 0 11px}}
 .dash .sec:first-child{{margin-top:0}}
 .note{{font-size:12.5px;color:#bdb8a4;margin:0 0 12px;line-height:1.6}}
 .kps{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:6px}}
 @media (max-width:620px){{.kps{{grid-template-columns:repeat(2,1fr)}}}}
 .kp{{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:11px 13px}}
 .kv{{font-family:Consolas,monospace;font-size:20px;font-weight:700}} .kl{{font-size:10.5px;color:#9a957f;margin-top:2px}}
 .row{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .row .a{{font-family:Consolas,monospace;font-size:12.5px;color:#e06a4a;white-space:nowrap;min-width:78px;text-align:right}}
 .row .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York State &middot; the two-channel map</div>
<h1>New York State &mdash; Vendors That Also Donate</h1>
<p class="lead">Names that appear in <b>both</b> NY public records at once: paid by the State as a
capital-project vendor (Comptroller D&amp;C payments) <b>and</b> recorded as an organizational donor to a
NY campaign (Board of Elections). A name on both ledgers is a <b>double channel</b> &mdash; money out from
the State and money in to campaigns &mdash; so it belongs on the map, as a question.</p>
<div class="disc">Matched on normalized organization name across two public datasets: <b>data.ny.gov rb9h-9fit</b>
(State D&amp;C capital-project vendor payments) &times; <b>data.ny.gov 4j2b-6a2j</b> (NYSBOE campaign
contributions, organizational contributors only). A name match is <b>not</b> proof of the same legal
entity &mdash; common names can collide, so generic government tokens were stoplisted and every line is a
<b>question for verification</b>, never an allegation against any person or company. Both activities are
lawful.</div>
<div class="dash"><h2 class="sec">The overlap &mdash; what the two ledgers share</h2><div class="kps">{kp}</div>
<h2 class="sec">Vendors that also donate &mdash; sorted by leverage (payments &divide; giving)</h2>
<p class="note">A large State payment beside a small campaign gift is the loudest pair. The question, each
time: is it the same entity &mdash; and if so, does the contract answer the public, or the giving?</p>
{rows or '<div class="row"><span class="c">No name overlap on this run.</span></div>'}</div>
<div class="disc">Scope: the vendor side is State Design &amp; Construction capital-project payments only
(not all NY procurement); the donor side is organizational contributors only (corporations, LLC/PLLC,
LLP/partnership, sole proprietorships, associations &mdash; individuals, PACs and party committees are
excluded from the cross). Broader OpenBookNY procurement coverage is the next pass.</div>
<p style="margin-top:8px"><a href="money_nys.html">&larr; NYS campaign money by recipient</a>
&middot; <a href="contracts_nys.html">NYS contract vendors</a>
&middot; <a href="jurisdictions.html">all govOS jurisdictions</a></p>
<footer>generated {g} &middot; nys-parity v1 &middot; source: data.ny.gov rb9h-9fit &times; 4j2b-6a2j (public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    result = {}

    # ---- money_nys ----
    try:
        recips = fetch_recipients()
        grand_total, grand_n, n_recips = fetch_totals()
        open(os.path.join(MAUIOS, "money_nys.html"), "w", encoding="utf-8", newline="\n").write(
            money_page(recips, grand_total, grand_n, n_recips))
        json.dump({"generated": now_hst().isoformat(), "source": "data.ny.gov 4j2b-6a2j (NYSBOE)",
                   "grand_total": round(grand_total, 2), "records": grand_n, "recipients": n_recips,
                   "top": recips[:50]},
                  open(os.path.join(MAUIOS, "money_nys.json"), "w", encoding="utf-8"), indent=1)
        result["money"] = {"recipients": n_recips, "total": grand_total, "records": grand_n,
                           "top1": recips[0] if recips else None}
        print(f"money_nys: ${grand_total:,.0f} across {n_recips:,} recipients / {grand_n:,} records")
        print(f"   top recipient: {recips[0]['name']} ${recips[0]['total']:,.0f}")
    except Exception as e:
        result["money_error"] = str(e)
        print("money_nys FAILED:", e)

    # ---- parity_nys ----
    try:
        donors = fetch_org_donors()
        vendors = fetch_vendors()
        vendor_dollars = sum(v["total"] for v in vendors)
        overlap = build_overlap(vendors, donors)
        open(os.path.join(MAUIOS, "parity_nys.html"), "w", encoding="utf-8", newline="\n").write(
            parity_page(overlap, len(vendors), len(donors), vendor_dollars))
        json.dump({"generated": now_hst().isoformat(),
                   "source": "data.ny.gov rb9h-9fit x 4j2b-6a2j (public record)",
                   "vendors_scanned": len(vendors), "org_donors_scanned": len(donors),
                   "matched_pairs": len(overlap),
                   "total_paid_to_matched": round(sum(o["vendor_paid"] for o in overlap), 2),
                   "total_given_by_matched": round(sum(o["donor_given"] for o in overlap), 2),
                   "pairs": overlap[:120]},
                  open(os.path.join(MAUIOS, "parity_nys.json"), "w", encoding="utf-8"), indent=1)
        result["parity"] = {"vendors": len(vendors), "donors": len(donors), "matches": len(overlap),
                            "paid": sum(o["vendor_paid"] for o in overlap),
                            "given": sum(o["donor_given"] for o in overlap),
                            "top": overlap[0] if overlap else None}
        print(f"parity_nys: {len(overlap)} matched pairs from {len(vendors):,} vendors x {len(donors):,} org donors")
        for o in overlap[:6]:
            print(f"   {o['leverage']}x  {o['vendor'][:30]:30s} paid ${o['vendor_paid']:,.0f} / donor {o['donor'][:24]} gave ${o['donor_given']:,.0f}")
    except Exception as e:
        result["parity_error"] = str(e)
        print("parity_nys FAILED:", e)

    print("\nRESULT:", json.dumps(result, default=str)[:800])
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
