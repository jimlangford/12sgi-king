# -*- coding: utf-8 -*-
"""state_build.py - State of Hawaii (id: state) govOS pages.
 1) money_state.html  - state-level offices (Governor, Lt. Governor, House, Senate)
                        totals + top donors, from reports/mauios/statewide_money.json
                        (HI Campaign Spending Commission).
 2) parity_state.html - top State HANDS vendors (state jurisdiction buckets) set beside
                        the State top_donors - overlaps as QUESTIONS, honest if no match.
All figures are real public record, cleaned in python. Correlations framed as questions.
"""
import os, json, re, html
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
MONEY = os.path.join(MAUIOS, "statewide_money.json")
HANDS = os.path.join(MAUIOS, "_hands_statewide.json")
HST = timezone(timedelta(hours=-10))
esc = lambda s: html.escape(str(s if s is not None else ""))
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)

# State-level offices (NOT county councils / mayors / prosecutors)
STATE_OFFICES = {"Governor", "Lt. Governor", "House", "Senate"}
# HANDS jurisdiction buckets that ARE the State (exclude County / Honolulu / HART)
STATE_JURIS = {"Executive", "Department of Education", "Education", "Judiciary",
               "University of Hawaii", "Office of Hawaiian Affairs",
               "Hawaii Health Systems Corporation", "School Facilities Authority",
               "House of Representatives", "Legislative Reference Bureau"}

def money_num(s):
    try:
        return float(re.sub(r"[^0-9.\-]", "", str(s)))
    except Exception:
        return None

# ---------- name-match helpers for parity ----------
def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()

SUFFIX = re.compile(r"\b(llc|inc|ltd|lp|llp|corp|corporation|company|co|pac|"
                    r"incorporated|limited|associates|assoc|group|fund|"
                    r"political|action|committee|account|hawaii|hawaiian)\b")
# Generic words that must NEVER form a match by themselves (else "services" links
# UnitedHealthcare to a tobacco PAC). Stoplist per Kilo Aupuni integrity rule.
STOP = {"services", "service", "health", "healthcare", "care", "medical", "center",
        "centers", "system", "systems", "state", "island", "islands", "pacific",
        "national", "american", "united", "general", "public", "workers", "worker",
        "industry", "industries", "resources", "solutions", "construction",
        "engineering", "engineers", "consulting", "consultants", "management",
        "development", "international", "association", "council", "regional",
        "union", "local", "professional", "products", "company", "client",
        "therapeutic", "behavioral", "staffing", "insurance", "financial",
        "global", "energy", "water", "power", "design", "school", "education"}
# > $2B single combined award = multi-vendor / multi-year notice anomaly; exclude
# from totals (flagged honestly), same defense as ny_watch.py OUTLIER.
OUTLIER = 2_000_000_000
def key_tokens(name):
    n = norm(name)
    n = SUFFIX.sub(" ", n)
    toks = [t for t in n.split() if len(t) >= 4 and t not in STOP]
    return set(toks)


def build_money():
    d = json.load(open(MONEY, encoding="utf-8"))
    by_office = [o for o in d["by_office"] if o["office"] in STATE_OFFICES]
    by_office.sort(key=lambda o: -o["total"])
    re_by = {o["office"]: o for o in d.get("realestate_by_office", [])}
    state_total = sum(o["total"] for o in by_office)
    state_n = sum(o["n"] for o in by_office)
    top_donors = d.get("top_donors", [])[:25]
    as_of = d.get("asOf", "")

    office_rows = ""
    for o in by_office:
        re_o = re_by.get(o["office"], {})
        re_t = re_o.get("total", 0)
        office_rows += (
            f'<div class="vh"><span class="a">${usd(o["total"])}</span>'
            f'<span class="n">{o["n"]:,} gifts</span>'
            f'<span class="c">{esc(o["office"])} '
            f'<span class="dept">&middot; incl. ${usd(re_t)} from real-estate / development donors</span></span></div>')

    donor_rows = ""
    for v in top_donors:
        donor_rows += (
            f'<div class="m"><span class="a">${usd(v["total"])}</span>'
            f'<span class="cn">{v.get("cands","?")} cands</span>'
            f'<span class="c">{esc(v["name"])} '
            f'<span class="dept">&middot; {v.get("gifts","?")} gifts</span></span></div>')

    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    h = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>State of Hawaii - Campaign Money - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:940px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:28px 0 6px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .vh{{display:grid;grid-template-columns:140px 92px 1fr;gap:12px;align-items:baseline;padding:11px 0 7px;border-top:1px solid rgba(217,178,76,.18);margin-top:6px}}
 .vh .a{{font-family:Consolas,monospace;font-size:15px;color:#d9b24c;text-align:right;font-weight:700}}
 .vh .n{{font-family:Consolas,monospace;font-size:11px;color:#e0863a;text-align:center}}
 .vh .c{{font-size:14px;color:#e8e4d8;font-weight:600}}
 .m{{display:grid;grid-template-columns:120px 70px 1fr;gap:12px;align-items:baseline;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .cn{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-align:center}}
 .m .c{{font-size:12.5px;color:#bdb8a4}} .dept{{color:#756b56}}
 .q{{background:rgba(217,178,76,.05);border:1px solid rgba(217,178,76,.25);border-radius:10px;padding:12px 15px;margin:18px 0;font-size:13px;color:#cfc9b6}}
 .q b{{color:#e8e4d8}} a{{color:#d9b24c}}
 footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; State of Hawai&#699;i &middot; who funds the state</div>
<h1>State of Hawai&#699;i &mdash; Campaign Money</h1>
<p class="lead">Campaign contributions to the four <b>State-level</b> offices &mdash; Governor, Lieutenant
Governor, State House and State Senate &mdash; from the <b>Hawai&#699;i Campaign Spending Commission</b>
public record. County councils, county mayors and prosecutors are tracked on their own tenant pages; this
page is the State branch only.</p>
<div class="kpi">
 <div><div class="n">${usd(state_total)}</div><div class="l">to state offices</div></div>
 <div><div class="n">{state_n:,}</div><div class="l">contributions</div></div>
 <div><div class="n">{len(by_office)}</div><div class="l">state offices</div></div>
 <div><div class="n">${usd(d.get("grand_total",0))}</div><div class="l">all HI offices (context)</div></div>
</div>
<div class="disc">Source: Hawai&#699;i Campaign Spending Commission contribution records (public record), as of {esc(as_of)}.
Amounts cleaned and summed in code. Giving to campaigns is lawful and ordinary &mdash; this maps where the
money concentrates so it can be read beside what the money decides. Documented facts and open questions.</div>

<h2>By state office &mdash; total contributions received</h2>
{office_rows}
<p class="disc" style="border:0;padding-left:0;margin-top:6px">The real-estate / development figure is the
subset of each office's money that comes from donors flagged as real-estate, development, construction or
land interests &mdash; the sectors with the most before-the-State business.</p>

<div class="q"><b>The question.</b> The same names recur at the top of nearly every Hawai&#699;i office:
trade-union PACs, the visitor-industry PAC, insurance, and a handful of development families. When one donor
funds dozens of candidates across both chambers and the executive, does each official answer the public who
elected them, or the donor who funds the whole field? The list below is the input side of that question.</div>

<h2>Top statewide donors &mdash; across all HI candidates</h2>
{donor_rows}

<footer>generated {g} &middot; state-build v1 &middot; source: Hawai&#699;i Campaign Spending Commission (public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""
    open(os.path.join(MAUIOS, "money_state.html"), "w", encoding="utf-8", newline="\n").write(h)
    return {"state_total": state_total, "state_n": state_n, "offices": by_office,
            "top_donors": top_donors, "as_of": as_of}


def build_parity(money):
    d = json.load(open(HANDS, encoding="utf-8"))
    by_vendor = {}
    skipped = 0
    excl_outliers = 0
    excl_sum = 0.0
    for r in d["rows"]:
        if r.get("jurisdiction") not in STATE_JURIS:
            continue
        amt = money_num(r.get("amount"))
        name = (r.get("vendorName") or "").strip()
        if amt is None or amt <= 0 or not name:
            skipped += 1
            continue
        # a single award >$2B is a multi-vendor / combined-notice anomaly (e.g. the
        # pooled Med-QUEST managed-care notice listing 5 insurers as one "vendor")
        if amt >= OUTLIER:
            excl_outliers += 1
            excl_sum += amt
            continue
        e = by_vendor.setdefault(name, {"vendor": name, "total": 0.0, "count": 0,
                                        "depts": set()})
        e["total"] += amt
        e["count"] += 1
        if r.get("department"):
            e["depts"].add(r["department"])
    vendors = sorted(by_vendor.values(), key=lambda v: -v["total"])
    state_award_total = sum(v["total"] for v in vendors)

    top_vendors = vendors[:30]
    donors = money["top_donors"]
    donor_keys = [(dn, key_tokens(dn["name"])) for dn in donors]

    # try to match each top State vendor name against the State top-donor names
    matched = []
    for v in top_vendors:
        vk = key_tokens(v["vendor"])
        best = None
        for dn, dk in donor_keys:
            overlap = vk & dk
            # require >=2 shared meaningful tokens (after stoplist) so a single
            # generic word can never manufacture a match
            if len(overlap) >= 2:
                best = {"donor": dn["name"], "donor_total": dn["total"],
                        "shared": sorted(overlap)}
                break
        if best:
            matched.append({"vendor": v, "match": best})

    # Build rows
    vrows = ""
    for v in top_vendors:
        dep = sorted(v["depts"])
        deptxt = dep[0] + (f" +{len(dep)-1} more" if len(dep) > 1 else "") if dep else ""
        vrows += (
            f'<div class="vh"><span class="a">${usd(v["total"])}</span>'
            f'<span class="n">{v["count"]}</span>'
            f'<span class="c">{esc(v["vendor"])} '
            f'<span class="dept">&middot; {esc(deptxt)}</span></span></div>')

    drows = ""
    for dn in donors[:15]:
        drows += (
            f'<div class="m"><span class="a">${usd(dn["total"])}</span>'
            f'<span class="cn">{dn.get("cands","?")}</span>'
            f'<span class="c">{esc(dn["name"])}</span></div>')

    if matched:
        mrows = ""
        for mm in matched:
            v = mm["vendor"]; b = mm["match"]
            q = (f"Does {v['vendor']}'s ${v['total']:,.0f} in State awards and "
                 f"{b['donor']}'s ${b['donor_total']:,.0f} to candidates describe the same interest? "
                 f"(shared name token(s): {', '.join(b['shared'])} - a correlation to verify, not a finding)")
            mrows += (f'<div class="row"><span class="a">match?</span><span class="c"><b>{esc(v["vendor"])}</b> '
                      f'(${usd(v["total"])} awarded) &harr; <b>{esc(b["donor"])}</b> '
                      f'(${usd(b["donor_total"])} donated). <span class="qn">{esc(q)}</span></span></div>')
        match_block = (f'<h2>Possible name overlaps &mdash; questions, not findings</h2>'
                       f'<p class="note">Loose name-token matches between the two lists. Each is a '
                       f'<b>question to verify by hand</b>, not a confirmed identity.</p>{mrows}')
    else:
        match_block = ('<h2>Name overlap &mdash; the honest result</h2>'
                       '<div class="q"><b>No clean name match.</b> Setting the top State HANDS vendors beside the '
                       'top statewide campaign donors, <b>no vendor name cleanly matches a top-donor name</b>. '
                       'This is expected and worth stating plainly: the biggest State <i>vendors</i> are engineering, '
                       'construction and professional-services firms, while the biggest statewide <i>donors</i> are '
                       'trade-union PACs, the visitor-industry PAC, insurance and development families &mdash; two '
                       'different populations at the very top. The money-and-contracts question lives one layer down '
                       '(a vendor’s owners, officers or affiliated PAC giving under a different name), which is '
                       'not resolvable from these two aggregate lists alone. Stated here so the gap is on the record, '
                       'not papered over.</div>')

    outlier_note = (f"Excluded {excl_outliers} combined award notice(s) over $2B "
                    f"(${usd(excl_sum)}, e.g. the pooled Med-QUEST managed-care notice that lists several "
                    f"insurers as one line) as multi-vendor data anomalies.") if excl_outliers else ""
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    h = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>State of Hawaii - Vendors beside Donors - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:30px 0 6px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .note{{font-size:12.5px;color:#bdb8a4;margin:0 0 10px}}
 .cols{{display:grid;grid-template-columns:1fr 1fr;gap:26px}}
 @media (max-width:680px){{.cols{{grid-template-columns:1fr}}}}
 .colh{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:#d9b24c;border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:5px;margin-bottom:6px}}
 .vh{{display:grid;grid-template-columns:120px 44px 1fr;gap:9px;align-items:baseline;padding:7px 0 5px;border-bottom:1px solid rgba(255,255,255,.06)}}
 .vh .a{{font-family:Consolas,monospace;font-size:13px;color:#d9b24c;text-align:right;font-weight:700}}
 .vh .n{{font-family:Consolas,monospace;font-size:11px;color:#e0863a;text-align:center}}
 .vh .c{{font-size:12.5px;color:#e8e4d8}}
 .m{{display:grid;grid-template-columns:90px 36px 1fr;gap:9px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .cn{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-align:center}}
 .m .c{{font-size:12.5px;color:#bdb8a4}} .dept{{color:#756b56}}
 .row{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .row .a{{font-family:Consolas,monospace;font-size:12px;color:#e06a4a;white-space:nowrap;min-width:54px;text-align:right}}
 .row .c{{font-size:12.5px;color:#bdb8a4}} .qn{{color:#9a957f}}
 .q{{background:rgba(217,178,76,.05);border:1px solid rgba(217,178,76,.25);border-radius:10px;padding:13px 16px;margin:16px 0;font-size:13px;color:#cfc9b6}}
 .q b{{color:#e8e4d8}} a{{color:#d9b24c}}
 footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; State of Hawai&#699;i &middot; vendors beside donors</div>
<h1>State of Hawai&#699;i &mdash; Vendors beside Donors</h1>
<p class="lead">Two public records set side by side: who the <b>State of Hawai&#699;i pays</b> (top vendors from
State-jurisdiction HANDS / HePS contract awards) and who <b>funds the State's campaigns</b> (top statewide
donors, Campaign Spending Commission). The civic-parity question: does an award answer the public, or a donor?
Where the same interest appears on both sides, that is a pair to read closely.</p>
<div class="kpi">
 <div><div class="n">${usd(state_award_total)}</div><div class="l">state awards (top-vendor scan)</div></div>
 <div><div class="n">{len(vendors):,}</div><div class="l">state vendors</div></div>
 <div><div class="n">{len(matched)}</div><div class="l">possible name overlaps</div></div>
</div>
<div class="disc">Sources: HANDS / HePS State-jurisdiction contract awards (Executive, Education, Judiciary,
University of Hawai&#699;i, OHA, etc.) &times; Hawai&#699;i Campaign Spending Commission top donors. County /
Honolulu / HART awards are excluded here. {outlier_note} Both activities are lawful &mdash; this is documented
facts and open questions, never a finding of wrongdoing.</div>

<div class="cols">
 <div><div class="colh">Top State vendors &mdash; paid by the State</div>
 <div class="vh"><span style="text-align:right;font-family:Consolas,monospace;font-size:11px;color:#9a957f">awarded</span><span style="text-align:center;font-family:Consolas,monospace;font-size:11px;color:#9a957f">#</span><span style="font-family:Consolas,monospace;font-size:11px;color:#9a957f">vendor</span></div>
 {vrows}</div>
 <div><div class="colh">Top statewide donors &mdash; who funds campaigns</div>
 <div class="m"><span style="text-align:right;font-family:Consolas,monospace;font-size:11px;color:#9a957f">donated</span><span style="text-align:center;font-family:Consolas,monospace;font-size:11px;color:#9a957f">cnd</span><span style="font-family:Consolas,monospace;font-size:11px;color:#9a957f">donor</span></div>
 {drows}</div>
</div>

{match_block}

<footer>generated {g} &middot; state-build v1 &middot; sources: HANDS/HePS (public award records) &times; HI Campaign Spending Commission (public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""
    open(os.path.join(MAUIOS, "parity_state.html"), "w", encoding="utf-8", newline="\n").write(h)
    return {"state_award_total": state_award_total, "n_vendors": len(vendors),
            "n_matched": len(matched), "top_vendors": top_vendors, "matched": matched}


def main():
    m = build_money()
    p = build_parity(m)
    print("=== money_state.html ===")
    print(f"state offices total: ${m['state_total']:,.0f} across {m['state_n']:,} contributions")
    for o in m["offices"]:
        print(f"  {o['office']:14s} ${o['total']:>14,.0f}  ({o['n']:,} gifts)")
    print(f"top donor: {m['top_donors'][0]['name']} ${m['top_donors'][0]['total']:,.0f}")
    print()
    print("=== parity_state.html ===")
    print(f"state award total (all state vendors): ${p['state_award_total']:,.0f} / {p['n_vendors']:,} vendors")
    print(f"top vendor: {p['top_vendors'][0]['vendor']} ${p['top_vendors'][0]['total']:,.0f}")
    print(f"name overlaps found: {p['n_matched']}")
    for mm in p["matched"]:
        print(f"   {mm['vendor']['vendor']} <-> {mm['match']['donor']} (shared {mm['match']['shared']})")


if __name__ == "__main__":
    main()
