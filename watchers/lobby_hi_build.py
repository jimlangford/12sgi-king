#!/usr/bin/env python3
"""lobby_hi_build.py - Kilo Aupuni: HI STATE + HONOLULU lobby x money double-channel.

Crosses the HI State Ethics Commission lobbyist-registration Organizations (cached
reports/mauios/_lobby_src/lob_reg.csv) against the HI Campaign Spending Commission
contribution records (hicscdata.hawaii.gov dataset jexd-xbcg, public), aggregated per
contributor per office group. Entities that BOTH register to lobby AND donate to the
deciders are a "double channel" of influence - documented public record, framed as a
question, never an accusation.

Outputs: reports/mauios/lobby_state.html, reports/mauios/lobby_honolulu.html

Reuses the tight org-name match from lobby_money_watch.py.
Sources:
 - opendata.hawaii.gov  (HSEC lobbyist registration statements -> lob_reg.csv)
 - hicscdata.hawaii.gov (CSC "Campaign Contributions Received..." dataset jexd-xbcg)
"""
import os, json, csv, re, ssl, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
CACHE = os.path.join(MAUIOS, "_lobby_src", "lob_reg.csv")
CSC_BASE = "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "Mozilla/5.0 (kilo-aupuni civic transparency; public record)"}
esc = lambda s: str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)

# State office groups vs Honolulu. (Mayor pools all counties statewide -> excluded.)
STATE_OFFICES = ["Governor", "House", "Senate", "Lt. Governor", "OHA", "Prosecuting Attorney"]
HONOLULU_OFFICES = ["Honolulu Council"]

def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()

SUFFIX = re.compile(r"\b(llc|inc|ltd|lp|llp|corp|company|co|pac|political action committee|"
                    r"dba .*|incorporated|limited)\b.*$")
def org_key(org):
    n = norm(org)
    k = SUFFIX.sub("", n).strip()
    return k if len(k) >= 8 and len(k.split()) >= 2 else (n if len(n) >= 8 else "")

def load_orgs():
    rows = list(csv.DictReader(open(CACHE, encoding="utf-8-sig", errors="replace")))
    orgs = {}
    for r in rows:
        o = (r.get("Organization") or "").strip()
        if not o:
            continue
        d = orgs.setdefault(o, {"org": o, "lobbyists": set(), "years": set()})
        if r.get("Full Name"):
            d["lobbyists"].add(r["Full Name"].strip())
        if r.get("Lobby Year"):
            d["years"].add(str(r["Lobby Year"]).strip())
    return rows, orgs

def fetch_donors(offices):
    """Aggregate monetary contributions per contributor for the given office set,
    via Socrata SoQL group-by. Returns list of {name,total,gifts,office_breakdown}."""
    inlist = ",".join("'" + o.replace("'", "''") + "'" for o in offices)
    where = (f"office in({inlist}) AND contributor_name IS NOT NULL "
             f"AND amount IS NOT NULL AND non_monetary_yes_or_no='N'")
    params = {
        "$select": "contributor_name,sum(amount) as total,count(1) as gifts",
        "$where": where,
        "$group": "contributor_name",
        "$having": "sum(amount) > 0",
        "$order": "total DESC",
        "$limit": "50000",
    }
    url = CSC_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    data = json.load(urllib.request.urlopen(req, timeout=180, context=ssl.create_default_context()))
    out = []
    for r in data:
        try:
            tot = float(r.get("total") or 0)
        except (TypeError, ValueError):
            continue
        if tot <= 0:
            continue
        nm = (r.get("contributor_name") or "").strip()
        if not nm:
            continue
        out.append({"name": nm, "total": round(tot, 2), "gifts": int(float(r.get("gifts") or 0)),
                    "blob": norm(nm)})
    return out

def build_overlap(orgs, donors):
    keyed = [(org_key(o), v) for o, v in orgs.items()]
    keyed = [(k, v) for k, v in keyed if k]
    overlap = {}
    for k, v in keyed:
        for d in donors:
            if k in d["blob"]:
                ent = overlap.setdefault(v["org"], {"org": v["org"], "lobby_years": sorted(v["years"]),
                                                    "lobbyists": sorted(v["lobbyists"]), "donations": []})
                ent["donations"].append({"donor": d["name"], "amount": d["total"], "gifts": d["gifts"]})
    res = []
    seen = set()
    for ent in overlap.values():
        # dedupe donor rows that matched on the same key
        uniq = {}
        for x in ent["donations"]:
            uniq[x["donor"]] = x
        ent["donations"] = sorted(uniq.values(), key=lambda d: -d["amount"])
        ent["total"] = round(sum(x["amount"] for x in ent["donations"]), 2)
        ent["n_donor_names"] = len(ent["donations"])
        res.append(ent)
    res.sort(key=lambda e: -e["total"])
    return res

def page(jur, scope_label, source_label, source_url, res, n_orgs, n_rows, n_donors, donor_total):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    tot = sum(e["total"] for e in res)
    rows = ""
    for e in res:
        dons = "".join(
            f'<div class="aw"><span class="a">${usd(x["amount"])}</span>'
            f'<span class="t">{esc(x["donor"])} <span class="dept">&middot; {x["gifts"]} gift'
            f'{"s" if x["gifts"]!=1 else ""} to {scope_label} candidates</span></span></div>'
            for x in e["donations"])
        yrs = (e["lobby_years"][0] + "&ndash;" + e["lobby_years"][-1][-4:]) if len(e["lobby_years"]) > 1 \
              else (e["lobby_years"][0] if e["lobby_years"] else "")
        rows += (f'<div class="vh"><span class="a">${usd(e["total"])}</span>'
                 f'<span class="n">{e["n_donor_names"]} name{"s" if e["n_donor_names"]!=1 else ""}</span>'
                 f'<span class="c">{esc(e["org"])} <span class="dept">&middot; registered State lobbyist '
                 f'{esc(yrs)}</span></span></div>{dons}')
    empty = ('<div class="aw"><span class="t">No registered-lobbyist Organization name matched a '
             f'{scope_label} contributor name on this run. That is an honest null, not an absence of '
             'influence &mdash; many entities lobby through trade associations or give through PACs whose '
             'names do not equal the lobbying Organization. The match here is deliberately strict.</span></div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(scope_label)} Lobby + Money - Double Channel - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:940px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 70px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:28px 0 6px;font-weight:600}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .vh{{display:grid;grid-template-columns:120px 80px 1fr;gap:12px;align-items:baseline;padding:11px 0 5px;border-top:1px solid rgba(217,178,76,.18);margin-top:8px}}
 .vh .a{{font-family:Consolas,monospace;font-size:14px;color:#d9b24c;text-align:right;font-weight:700}}
 .vh .n{{font-family:Consolas,monospace;font-size:11px;color:#e0863a;text-align:center}}
 .vh .c{{font-size:14px;color:#e8e4d8;font-weight:600}}
 .aw{{display:grid;grid-template-columns:120px 1fr;gap:12px;align-items:baseline;padding:2px 0;font-size:12px}}
 .aw .a{{font-family:Consolas,monospace;color:#9a957f;text-align:right}} .aw .t{{color:#bdb8a4}} .dept{{color:#756b56}}
 .q{{background:rgba(217,178,76,.05);border:1px solid rgba(217,178,76,.25);border-radius:10px;padding:12px 15px;margin:16px 0;font-size:13px;color:#cfc9b6}}
 .q b{{color:#e8e4d8}} a{{color:#d9b24c}}
 footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; {esc(scope_label)} &middot; two channels of influence</div>
<h1>{esc(scope_label)} &mdash; who lobbies <i>and</i> pays the deciders</h1>
<p class="lead">Entities that appear in <b>both</b> public records at once: registered to lobby the State of
Hawai&#699;i (Ethics Commission) <b>and</b> a campaign donor to {esc(scope_label)} candidates (Campaign
Spending Commission). Lobbying is lawful; donating is lawful. Doing both is a <b>double channel</b> &mdash;
two ways the same interest reaches the same decider &mdash; so it belongs on the map, as a question.</p>
<div class="kpi">
 <div><div class="n">{len(res)}</div><div class="l">lobby+donate orgs</div></div>
 <div><div class="n">${usd(tot)}</div><div class="l">their {scope_label} donations</div></div>
 <div><div class="n">{n_orgs:,}</div><div class="l">orgs in lobbyist registry</div></div>
 <div><div class="n">{n_donors:,}</div><div class="l">{scope_label} contributors scanned</div></div>
</div>
<div class="disc">Sources: Hawai&#699;i State Ethics Commission lobbyist registration statements
(opendata.hawaii.gov, {n_rows:,} filings &rarr; {n_orgs:,} Organizations) &times; {esc(source_label)}
(<a href="{esc(source_url)}">{esc(source_url)}</a>), filtered to {esc(scope_label)} offices and aggregated
per contributor in Python. Matched strictly on entity name (corporate suffixes peeled). Lawful activity
&mdash; documented facts and open questions, not findings of wrongdoing. NOTE: the lobbyist registry is
<b>State</b>-level; an entity that lobbies only informally, or gives only through a PAC whose name differs
from its own, will not surface here. A strict match undercounts on purpose.</div>
<div class="q"><b>The question.</b> When the same named entity both funds a candidate's campaign and pays to
lobby the laws and budgets that office controls, two influence channels converge on one decider. The record
below shows which entities do both, and the size of the donation channel. Read it beside their bills, their
votes, and their disclosures &mdash; that is where the question gets answered.</div>
<h2>Both lobbying &amp; donating &mdash; by donation size</h2>
{rows or empty}
<p style="margin-top:22px"><a href="lobby_money_watch.html">Maui lobby &times; money</a>
&middot; <a href="{('money_honolulu.html' if jur=='honolulu' else 'statewide_money.html')}">who funds {scope_label}</a>
&middot; <a href="jurisdictions.html">all govOS jurisdictions</a></p>
<footer>generated {g} &middot; lobby-hi v1 &middot; source: opendata.hawaii.gov (HSEC lobbyist registrations) + hicscdata.hawaii.gov (CSC jexd-xbcg) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def main():
    rows, orgs = load_orgs()
    out = {}
    for jur, offices, scope, fname in [
        ("state", STATE_OFFICES, "Hawaiʻi State", "lobby_state.html"),
        ("honolulu", HONOLULU_OFFICES, "Honolulu", "lobby_honolulu.html"),
    ]:
        donors = fetch_donors(offices)
        donor_total = round(sum(d["total"] for d in donors), 2)
        res = build_overlap(orgs, donors)
        src_label = 'HI Campaign Spending Commission "Campaign Contributions Received By Hawaii State and County Candidates" (dataset jexd-xbcg)'
        src_url = "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
        html = page(jur, scope, src_label, src_url, res, len(orgs), len(rows), len(donors), donor_total)
        open(os.path.join(MAUIOS, fname), "w", encoding="utf-8").write(html)
        out[jur] = {"file": fname, "n_overlap": len(res), "overlap_total": round(sum(e["total"] for e in res), 2),
                    "n_donors": len(donors), "donor_total": donor_total,
                    "top": [{"org": e["org"], "total": e["total"], "names": e["n_donor_names"]} for e in res[:12]]}
        print(f"=== {scope} ({jur}) -> {fname}")
        print(f"    {len(donors):,} contributors (${donor_total:,.0f}); "
              f"{len(res)} orgs lobby+donate (${out[jur]['overlap_total']:,.0f})")
        for e in res[:12]:
            print(f"      ${e['total']:>9,.0f}  {e['n_donor_names']}nm  {e['org']}")
    json.dump({"generated": now_hst().isoformat(), "registry_orgs": len(orgs),
               "filings": len(rows), "result": out},
              open(os.path.join(MAUIOS, "lobby_hi.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
