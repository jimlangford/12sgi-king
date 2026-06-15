#!/usr/bin/env python3
"""subcontractors_nyc.py - Kilo Aupuni: NYC prime->subcontractor money chains.

Source: NYC Open Data (Socrata) dataset 6anw-twe4 "Local Law 44 - Development Team"
        https://data.cityofnewyork.us/Housing-Development/Local-Law-44-Development-Team/6anw-twe4
Local Law 44 of 2009 requires that for City-financed affordable-housing projects (HPD/HDC),
the development team be disclosed: the BORROWER LEGAL ENTITY, the GENERAL CONTRACTOR (the prime),
and every SUB CONTRACTOR working under them. This is the only NYC open dataset that names the
firms BEHIND a prime on a public project.

It is a disclosure-of-WHO law, NOT a payments ledger: there are no dollar amounts. So this page
maps the CHAINS (prime -> sub relationships, recurrence across projects), honestly labeled as the
relationship map, not the dollars. Every line is framed as a question to verify, never an accusation.
"""
import os, json, ssl, time, urllib.request, urllib.parse, html, re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)", "Accept": "application/json"}
DOMAIN = "data.cityofnewyork.us"
DATASET = "6anw-twe4"
DS_URL = "https://data.cityofnewyork.us/Housing-Development/Local-Law-44-Development-Team/6anw-twe4"
esc = lambda s: html.escape(str(s or ""))


def now_hst():
    return datetime.now(HST)


def socrata(params):
    qs = urllib.parse.urlencode(params)
    url = f"https://{DOMAIN}/resource/{DATASET}.json?{qs}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fetch_type(t):
    rows, off, PAGE = [], 0, 50000
    while True:
        batch = socrata({"$select": "projectid,entityname,parententityname,tradetype,borough",
                         "$where": f"type='{t}'", "$limit": PAGE, "$offset": off})
        rows += batch
        if len(batch) < PAGE:
            break
        off += PAGE
        time.sleep(0.3)
    return rows


def norm(name):
    """Normalize a firm name for grouping: strip case/punct/suffix noise so 'KOENIG IRON WORKS'
    and 'Koenig Iron Works' fold together. Returns (key, display)."""
    if not name:
        return None, None
    disp = name.strip()
    k = disp.upper()
    k = re.sub(r"[.,&'`]", " ", k)
    k = re.sub(r"\b(INC|LLC|L L C|CORP|CORPORATION|CO|COMPANY|LTD|LP|L P|GROUP|THE|PC|P C|DBA)\b", " ", k)
    k = re.sub(r"\s+", " ", k).strip()
    return (k or disp.upper()), disp


def main():
    os.makedirs(MAUIOS, exist_ok=True)
    gcs = fetch_type("GENERAL CONTRACTOR")
    subs = fetch_type("SUB CONTRACTOR")

    # Prime per project = the GENERAL CONTRACTOR (prefer entityname, fall back to parententityname).
    prime_by_proj = {}          # projectid -> (primekey, primedisp)
    prime_disp = {}             # primekey -> display
    for r in gcs:
        nm = r.get("entityname") or r.get("parententityname")
        k, d = norm(nm)
        if not k:
            continue
        prime_disp.setdefault(k, d)
        # keep the first non-empty prime seen for the project
        prime_by_proj.setdefault(r["projectid"], (k, d))

    sub_disp = {}               # subkey -> display
    # chain aggregation
    prime_subs = defaultdict(set)        # primekey -> set(subkey)   (distinct subs under a prime)
    prime_projs = defaultdict(set)       # primekey -> set(projectid)
    sub_primes = defaultdict(set)        # subkey -> set(primekey)   (distinct primes a sub works under)
    sub_projs = defaultdict(set)         # subkey -> set(projectid)
    chain_count = defaultdict(int)       # (primekey, subkey) -> distinct projects together
    chain_seen = set()                   # (prime, sub, proj) dedupe
    pair_trade = {}                      # (prime,sub) -> a trade label if known
    orphan_sub_projs = 0

    for r in subs:
        sk, sd = norm(r.get("entityname") or r.get("parententityname"))
        if not sk:
            continue
        sub_disp.setdefault(sk, sd)
        proj = r["projectid"]
        sub_projs[sk].add(proj)
        prime = prime_by_proj.get(proj)
        if not prime:
            orphan_sub_projs += 1
            continue
        pk, pd = prime
        prime_disp.setdefault(pk, pd)
        prime_subs[pk].add(sk)
        prime_projs[pk].add(proj)
        sub_primes[sk].add(pk)
        key = (pk, sk)
        if (pk, sk, proj) not in chain_seen:
            chain_seen.add((pk, sk, proj))
            chain_count[key] += 1
        if r.get("tradetype"):
            pair_trade[key] = r["tradetype"].split(",")[0].strip()

    n_projects = len(set(list(prime_by_proj.keys()) + [r["projectid"] for r in subs]))
    n_primes = len(prime_subs)
    n_subs = len(sub_disp)
    total_chains = sum(chain_count.values())

    # --- Ranking 1: primes routing work to the most distinct subs ---
    primes_ranked = sorted(prime_subs.keys(),
                           key=lambda k: (-len(prime_subs[k]), -len(prime_projs[k])))[:60]
    # --- Ranking 2: subs that appear behind the most DISTINCT primes (the firm really paid behind many primes) ---
    subs_ranked = sorted([s for s in sub_primes if len(sub_primes[s]) >= 2],
                         key=lambda k: (-len(sub_primes[k]), -len(sub_projs[k])))[:60]
    # --- Ranking 3: the heaviest single prime->sub chains (most projects together) ---
    chains_ranked = sorted(chain_count.items(), key=lambda kv: -kv[1])[:50]

    g = now_hst().strftime("%Y-%m-%d %H:%M HST")

    def prow(k):
        return (f'<div class="m"><span class="a">{len(prime_subs[k])}</span>'
                f'<span class="n">{len(prime_projs[k])}</span>'
                f'<span class="c">{esc(prime_disp.get(k))}</span></div>')

    def srow(k):
        return (f'<div class="m"><span class="a">{len(sub_primes[k])}</span>'
                f'<span class="n">{len(sub_projs[k])}</span>'
                f'<span class="c">{esc(sub_disp.get(k))}</span></div>')

    def crow(kv):
        (pk, sk), c = kv
        trade = pair_trade.get((pk, sk))
        t = f' &middot; <span style="color:#9a957f">{esc(trade)}</span>' if trade else ""
        return (f'<div class="row"><span class="a">{c} proj</span>'
                f'<span class="c"><b>{esc(prime_disp.get(pk))}</b> &rarr; {esc(sub_disp.get(sk))}{t}'
                f'<br><span style="color:#9a957f;font-size:11.5px">Across {c} City-financed project(s), '
                f'who is really paid behind {esc(prime_disp.get(pk))} when {esc(sub_disp.get(sk))} appears '
                f'on the team? (a disclosed relationship to read, not a finding)</span></span></div>')

    prime_rows = "".join(prow(k) for k in primes_ranked)
    sub_rows = "".join(srow(k) for k in subs_ranked)
    chain_rows = "".join(crow(kv) for kv in chains_ranked)

    out = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Who Is Paid Behind the Prime - NYC Subcontractor Chains - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 80px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:82ch}}
 .kpi{{display:flex;gap:28px;margin:16px 0;flex-wrap:wrap}} .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .sec{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#d9b24c;border-bottom:1px solid rgba(217,178,76,.2);padding-bottom:6px;margin:26px 0 6px}}
 .secnote{{font-size:12.5px;color:#bdb8a4;margin:0 0 10px}}
 .m{{display:grid;grid-template-columns:70px 60px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:13px;color:#d9b24c;text-align:right}} .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:center}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 .m .h{{font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;text-transform:uppercase}}
 .row{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .row .a{{font-family:Consolas,monospace;font-size:12px;color:#e06a4a;white-space:nowrap;min-width:62px;text-align:right}}
 .row .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}} footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York City &middot; who is paid behind the prime</div>
<h1>Who Is Really Paid Behind the Prime?</h1>
<p class="lead">When the City hires a prime contractor, the money does not stop there &mdash; it flows down to
the <b>subcontractors</b> who actually do the work. Most of that chain is invisible. New York's
<b>Local Law 44</b> forces one window open: for every City-financed affordable-housing project, the
development team must be disclosed &mdash; the borrower, the <b>general contractor</b> (the prime), and
every <b>subcontractor</b> under them. This maps those chains: which primes route work to the most subs,
and which subs surface behind the most <i>different</i> primes &mdash; the firms quietly present on team
after team, no matter whose name is on the contract.</p>
<div class="kpi">
 <div><div class="n">{n_projects:,}</div><div class="l">City-financed projects</div></div>
 <div><div class="n">{n_primes:,}</div><div class="l">prime contractors</div></div>
 <div><div class="n">{n_subs:,}</div><div class="l">subcontractors disclosed</div></div>
 <div><div class="n">{total_chains:,}</div><div class="l">prime&rarr;sub chains</div></div>
</div>
<div class="disc">Source: NYC Open Data, Local Law 44 - Development Team (dataset {DATASET},
<a href="{DS_URL}">{DS_URL}</a>). This is a disclosure-of-<b>who</b> law, <b>not</b> a payments ledger &mdash;
it names the firms on each team but carries <b>no dollar amounts</b>. So this page maps the <b>relationships</b>
(who works behind whom, and how often), not the money itself. Being a prime or a recurring sub is lawful and
ordinary &mdash; every line is a <b>question to verify</b> against the record, never an accusation. Firm names
folded case/suffix variants ("KOENIG IRON WORKS" = "Koenig Iron Works"). {orphan_sub_projs:,} subcontractor
rows were on projects with no disclosed general contractor and are excluded from the chain joins.</div>

<h2 class="sec">Primes routing the widest sub networks</h2>
<p class="secnote">General contractors ranked by how many <b>distinct subcontractors</b> they pull onto their
teams across City-financed projects. A wide network is normal for a big builder &mdash; the question is
whether the same subs keep reappearing.</p>
<div class="m"><span class="h" style="text-align:right">subs</span><span class="h" style="text-align:center">projects</span><span class="h">prime contractor (general contractor)</span></div>
{prime_rows}

<h2 class="sec">Subs that surface behind the most <i>different</i> primes</h2>
<p class="secnote">Subcontractors ranked by the number of <b>distinct prime contractors</b> they appear under. A
firm present on many teams &mdash; no matter whose name is on the City contract &mdash; is the firm "really
paid behind the prime." The question each time: who is this, and why are they on so many different teams?</p>
<div class="m"><span class="h" style="text-align:right">primes</span><span class="h" style="text-align:center">projects</span><span class="h">subcontractor</span></div>
{sub_rows}

<h2 class="sec">The heaviest single chains</h2>
<p class="secnote">Specific prime&rarr;sub pairs that recur on the most projects together &mdash; a standing
relationship between one prime and one sub.</p>
{chain_rows}

<p style="margin-top:18px"><a href="jurisdictions.html">&larr; all govOS jurisdictions</a> &middot; <a href="reports.html">all reports</a> &middot; <a href="contracts_nyc.html">NYC contract awards</a></p>
<footer>generated {g} &middot; subcontractors-nyc v1 &middot; source: NYC Open Data Local Law 44 ({DATASET}, public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

    open(os.path.join(MAUIOS, "subcontractors_nyc.html"), "w", encoding="utf-8").write(out)
    json.dump({"generated": now_hst().isoformat(), "source": f"NYC Open Data {DATASET}",
               "projects": n_projects, "primes": n_primes, "subs": n_subs,
               "chains": total_chains, "orphan_sub_rows": orphan_sub_projs},
              open(os.path.join(MAUIOS, "subcontractors_nyc.json"), "w", encoding="utf-8"), indent=1)
    print(f"subcontractors-nyc: {n_projects} projects / {n_primes} primes / {n_subs} subs / {total_chains} chains")
    # verification echo: top sub-behind-many-primes + top chain
    if subs_ranked:
        s = subs_ranked[0]
        print(f"  top recurring sub: {sub_disp[s]} -> {len(sub_primes[s])} distinct primes, {len(sub_projs[s])} projects")
    if chains_ranked:
        (pk, sk), c = chains_ranked[0]
        print(f"  top chain: {prime_disp[pk]} -> {sub_disp[sk]} on {c} projects")
    if primes_ranked:
        p = primes_ranked[0]
        print(f"  top prime: {prime_disp[p]} -> {len(prime_subs[p])} distinct subs across {len(prime_projs[p])} projects")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
