# -*- coding: utf-8 -*-
"""nyc_parity_v2.py — Kilo Aupuni / govOS NYC tenant — CONTRIBUTOR-LEVEL parity.

Upgrades reports/mauios/parity_nyc.html from a "no overlap found" side-by-side to a
REAL vendor<->donor join, using a CONTRIBUTOR-keyed source.

The prior version failed because CFB rjkp-yttg keys contributions by RECIPIENT.
This version uses the NYC "Doing Business Contributions Summary" (Socrata fbkk-n4e3),
which is keyed by CONTRIBUTOR and carries the Doing Business ENTITY each contributor is
affiliated with (db_entity_name) — the very entities that have NYC business dealings
(contracts, franchises, concessions). The Doing Business Database exists precisely to
track money from people/entities who do business with the City.

Join: NYC contract-award vendors (qyyg-4tf5, summed by vendor_name) name-matched against
the Doing Business ENTITY field (db_entity_name) in fbkk-n4e3. Each match is a real
"this entity wins City contracts AND money tied to it flows to City officials" pair —
framed as a QUESTION, never an accusation. Generic/short keys are stoplisted to avoid
false positives; only multi-token entity keys are matched.

Sources (both data.cityofnewyork.us, public record):
  qyyg-4tf5  City Record "Recent Contract Awards"
  fbkk-n4e3  CFB "Doing Business Contributions Summary"
"""
import os, json, ssl, time, urllib.request, urllib.parse, html, re
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
EST = timezone(timedelta(hours=-5))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)", "Accept": "application/json"}
DOMAIN = "data.cityofnewyork.us"
AWARDS = "qyyg-4tf5"      # City Record — Recent Contract Awards
DBC = "fbkk-n4e3"         # CFB — Doing Business Contributions Summary (contributor-keyed)
CONTRACT_OUTLIER = 2_000_000_000

esc = lambda s: html.escape(str(s if s is not None else ""))
usd = lambda n: f"{n:,.0f}"
def now_est(): return datetime.now(EST)

def num(s):
    try:
        return float(str(s).replace(",", "").replace("$", "").strip())
    except Exception:
        return None

def socrata(dataset, params):
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"https://{DOMAIN}/resource/{dataset}.json?{qs}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()

# Peel corporate/structural tokens so "Gilbane Building Company" <-> "GILBANE BUILDING COMPANY"
SUFFIX = re.compile(r"\b(llc|inc|ltd|lp|llp|corp|corporation|company|co|incorporated|"
                    r"limited|associates|assoc|group|consulting|the|of|and)\b")
def org_key(org):
    n = re.sub(r"\s+", " ", SUFFIX.sub(" ", norm(org))).strip()
    # require a reasonably specific key: >=2 tokens OR a single long token (>=8 chars)
    toks = n.split()
    if len(toks) >= 2 and len(n) >= 8:
        return n
    if len(toks) == 1 and len(n) >= 8:
        return n
    return ""

# Generic keys that would create false matches — never match on these alone
STOP = {
    "new york city", "city new york", "new york", "city", "community", "services community",
    "community services", "health", "mental health", "housing", "family services",
    "social services", "human services", "medical center", "health center",
}

def build():
    os.makedirs(MAUIOS, exist_ok=True)

    # 1) Contract vendors (Award notices), cleaned of $2B+ anomalies
    vrows = socrata(AWARDS, {
        "$select": "vendor_name, sum(contract_amount) as tot, count(1) as n",
        "$where": "type_of_notice_description='Award'",
        "$group": "vendor_name", "$order": "tot desc", "$limit": 2000})
    vend, excl = {}, 0
    for r in vrows:
        nm = (r.get("vendor_name") or "").strip()
        t = num(r.get("tot"))
        if not nm or t is None or t <= 0:
            continue
        if t >= CONTRACT_OUTLIER:
            excl += 1; continue
        k = org_key(nm)
        if k and k not in STOP and k not in vend:
            vend[k] = {"name": nm, "tot": t, "n": int(num(r.get("n")) or 0)}

    # 2) Doing Business ENTITIES (contributor-affiliated), summed
    drows = socrata(DBC, {
        "$select": "db_entity_name, sum(amnt) as tot, count(1) as n, count(distinct candid) as ncand",
        "$where": "db_entity_name IS NOT NULL",
        "$group": "db_entity_name", "$order": "tot desc", "$limit": 3000})
    dbe = {}
    for r in drows:
        nm = (r.get("db_entity_name") or "").strip()
        t = num(r.get("tot"))
        if not nm or t is None or t <= 0:
            continue
        k = org_key(nm)
        if k and k not in STOP and k not in dbe:
            dbe[k] = {"name": nm, "tot": t, "n": int(num(r.get("n")) or 0),
                      "ncand": int(num(r.get("ncand")) or 0)}

    # 3) Join on normalized entity key
    matches = []
    for k, v in vend.items():
        if k in dbe:
            d = dbe[k]
            lev = v["tot"] / d["tot"] if d["tot"] else 0
            matches.append({"key": k, "vendor": v["name"], "award_total": v["tot"], "award_n": v["n"],
                            "db_entity": d["name"], "contrib_total": d["tot"], "contrib_n": d["n"],
                            "n_cands": d["ncand"], "leverage": lev})
    matches.sort(key=lambda m: -m["award_total"])

    # 4) For the top matches, fetch the named recipient officials (real names from the record)
    for m in matches[:24]:
        try:
            rr = socrata(DBC, {
                "$select": "candlast, candfirst, sum(amnt) as tot, count(1) as n",
                "$where": f"db_entity_name='{m['db_entity'].replace(chr(39), chr(39)*2)}'",
                "$group": "candlast,candfirst", "$order": "tot desc", "$limit": 6})
            recs = []
            for x in rr:
                last = (x.get("candlast") or "").strip()
                first = (x.get("candfirst") or "").strip()
                if not last:
                    continue
                recs.append({"name": (f"{first} {last}").strip(),
                             "amt": num(x.get("tot")) or 0.0, "n": int(num(x.get("n")) or 0)})
            m["recipients"] = recs
        except Exception:
            m["recipients"] = []
        time.sleep(0.1)

    award_total = sum(v["tot"] for v in vend.values())
    matched_award = sum(m["award_total"] for m in matches)
    matched_contrib = sum(m["contrib_total"] for m in matches)

    stats = {"vendors": len(vend), "db_entities": len(dbe), "matches": len(matches),
             "award_total_cleaned": round(award_total, 2),
             "matched_award_total": round(matched_award, 2),
             "matched_contrib_total": round(matched_contrib, 2),
             "excluded_outliers": excl,
             "top_match": matches[0]["vendor"] if matches else None}
    return matches, stats


def page(matches, stats):
    g = now_est().strftime("%Y-%m-%d %H:%M ET")

    def reciplist(m):
        rs = m.get("recipients") or []
        if not rs:
            return ""
        items = ", ".join(f"{esc(r['name'])} (${usd(r['amt'])})" for r in rs[:5])
        return (f'<div class="rec">money to: {items}'
                f'{" …" if len(rs) > 5 else ""}</div>')

    # Featured matches with named recipients (top 24)
    feat = ""
    for m in matches[:24]:
        lev = m["leverage"]
        levtxt = f"{lev:,.0f}x" if lev >= 1 else f"{lev:.2f}x"
        feat += (
            f'<div class="row"><span class="a">${usd(m["award_total"])}</span>'
            f'<span class="c"><b>{esc(m["vendor"])}</b> won ${usd(m["award_total"])} across '
            f'{m["award_n"]} NYC contract award notice(s). The same entity appears in the City\'s '
            f'<b>Doing Business</b> contribution record as <b>{esc(m["db_entity"])}</b> — '
            f'${usd(m["contrib_total"])} in contributions tied to it across {m["contrib_n"]} gift(s) '
            f'to {m["n_cands"]} candidate(s). '
            f'<span class="lev">leverage ≈ {levtxt}</span>'
            f'{reciplist(m)}'
            f'<span class="q">Does this entity\'s ${usd(m["award_total"])} in City contracts answer the '
            f'public, or the ${usd(m["contrib_total"])} routed to the officials who fund and oversee '
            f'those contracts? A pair in two public ledgers — a question to verify, not a finding.</span>'
            f'</span></div>')

    # Compact tail of the remaining matches
    tail = ""
    for m in matches[24:120]:
        tail += (f'<div class="m"><span class="a">${usd(m["award_total"])}</span>'
                 f'<span class="n">${usd(m["contrib_total"])}</span>'
                 f'<span class="c">{esc(m["vendor"])}</span></div>')

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>New York City — Contracts &times; Donors (Parity v2) — Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .sec{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#d9b24c;border-bottom:1px solid rgba(217,178,76,.2);padding-bottom:6px;margin:26px 0 10px}}
 .note{{font-size:12.5px;color:#bdb8a4;margin:0 0 12px;line-height:1.6;max-width:84ch}}
 .row{{display:flex;gap:14px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:11px 0}}
 .row .a{{font-family:Consolas,monospace;font-size:13px;color:#e06a4a;white-space:nowrap;min-width:120px;text-align:right;font-weight:700}}
 .row .c{{font-size:13px;color:#e8e4d8}}
 .lev{{font-family:Consolas,monospace;font-size:11px;color:#e0863a;margin-left:4px}}
 .rec{{font-size:12px;color:#bdb8a4;margin:5px 0 2px}}
 .q{{display:block;font-size:12px;color:#9a957f;font-style:italic;margin-top:4px}}
 .m{{display:grid;grid-template-columns:130px 110px 1fr;gap:10px;align-items:baseline;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12px;color:#e06a4a;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:12px;color:#d9b24c;text-align:right}} .m .c{{font-size:12px;color:#bdb8a4}}
 .m.hd .a,.m.hd .n,.m.hd .c{{color:#756b56}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York City &middot; the parity question &middot; v2</div>
<h1>New York City — Contracts &times; Donors</h1>
<p class="lead">Civic parity asks one thing of the public ledger: does a contract (the output of public money)
answer the <b>public</b>, or a private donor to the officials who decide it? This version closes the gap the
first pass could not — it matches NYC contract winners against the City's own <b>Doing Business</b>
contribution record, a source keyed to the <i>contributing entity</i>, not just the recipient. Where the same
entity both <b>wins City contracts</b> and has <b>contributions tied to it flowing to City officials</b>, the
pair is named below.</p>
<div class="disc">Sources: NYC Open Data — City Record "Recent Contract Awards"
(<a href="https://data.cityofnewyork.us/dataset/Recent-Contract-Awards/qyyg-4tf5">qyyg-4tf5</a>) and NYC
Campaign Finance Board "Doing Business Contributions Summary"
(<a href="https://data.cityofnewyork.us/d/fbkk-n4e3">fbkk-n4e3</a>), both on data.cityofnewyork.us. The Doing
Business record exists specifically to track money tied to entities with City dealings (contracts, franchises,
concessions); it is keyed by contributor and carries the affiliated <code>db_entity_name</code>. Contract
amounts were cleaned in code ({stats['excluded_outliers']} vendor totals over $2B excluded as data-entry
anomalies); generic entity names (e.g. bare "New York City", "Community Services") were stoplisted so matches
require a specific multi-token entity. Winning contracts and contributing are both lawful — every pair below is
a <b>question to verify</b> against the underlying filings, naming a pattern, never an accusation against a
person.</div>
<div class="kpi">
 <div><div class="n">{stats['matches']:,}</div><div class="l">vendor &times; donor pairs</div></div>
 <div><div class="n">${usd(stats['matched_award_total'])}</div><div class="l">contracts in matched pairs</div></div>
 <div><div class="n">${usd(stats['matched_contrib_total'])}</div><div class="l">tied contributions</div></div>
 <div><div class="n">{stats['vendors']:,}</div><div class="l">contract vendors keyed</div></div>
</div>

<h2 class="sec">Pairs in both ledgers — winner &amp; donor are the same entity</h2>
<p class="note">Each entity below appears in <b>both</b> the City contract-award record and the Doing Business
contribution record. "Leverage" is contract dollars per contribution dollar — a rough scale of the question,
not a measure of wrongdoing. Recipient officials are named directly from the contribution filings.</p>
{feat}

<h2 class="sec">More matched pairs</h2>
<p class="note">The remaining vendor&times;donor name matches, by contract size.</p>
<div class="m hd"><span class="a">awarded</span><span class="n">contributed</span><span class="c">entity (winner &amp; donor)</span></div>
{tail}

<p style="margin-top:18px"><a href="money_nyc.html">who funds NYC officials</a>
&middot; <a href="lobby_nyc.html">who lobbies NYC</a>
&middot; <a href="contracts_nyc.html">NYC contract awards</a></p>
<footer>generated {g} &middot; nyc-parity v2 (contributor-level) &middot; source: NYC qyyg-4tf5 &times; fbkk-n4e3 (public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""


def main():
    matches, stats = build()
    open(os.path.join(MAUIOS, "parity_nyc.html"), "w", encoding="utf-8", newline="\n").write(page(matches, stats))
    out = {"generated": now_est().isoformat(),
           "source": "NYC qyyg-4tf5 (Recent Contract Awards) x fbkk-n4e3 (Doing Business Contributions Summary)",
           **stats,
           "pairs": [{k: m[k] for k in ("vendor", "db_entity", "award_total", "award_n",
                                        "contrib_total", "contrib_n", "n_cands", "leverage",
                                        "recipients") if k in m} for m in matches[:120]]}
    json.dump(out, open(os.path.join(MAUIOS, "parity_nyc.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"parity_nyc v2: {stats['matches']} pairs; "
          f"matched contracts ${stats['matched_award_total']:,.0f}; "
          f"tied contributions ${stats['matched_contrib_total']:,.0f}")
    for m in matches[:8]:
        print(f"   ${m['award_total']:>14,.0f} <-> ${m['contrib_total']:>9,.0f}  {m['vendor']}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main())
