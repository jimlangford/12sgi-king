#!/usr/bin/env python3
"""subcontract_chain.py - Kilo Aupuni: the SUBCONTRACTOR tier for Maui County.

Down-and-up the federal money chain. USASpending.gov records not just who a federal
PRIME award went to, but who the prime paid BENEATH them - the SUBRECIPIENTS
(subcontractors on prime contracts, subgrantees on prime grants). This tool pulls the
Maui County (place of performance FIPS 15009 / HI county 009) subaward tier and links
every subrecipient UP to the prime that paid it, so anyone can ask: who is really paid
behind the prime, and does the same firm keep surfacing beneath many different primes?

Source (public, no key): USASpending.gov
  Prime awards:  POST /api/v2/search/spending_by_award/  (place of performance = Maui)
  Subaward tier: POST /api/v2/search/spending_by_award/  with spending_level="subawards"
    (each row carries Sub-Awardee Name, Sub-Award Amount, Sub-Award Description, and the
     Prime Recipient Name + Prime Award ID + prime_award_generated_internal_id it sits under).
  (The per-award endpoint /api/v2/subawards/ exists but returns per-prime rows only; the
   spending_level="subawards" search is the current, efficient way to get the whole county
   subaward tier already joined up to its prime - confirmed by live probe 2026-07-08.)

CIVIC DISCIPLINE (same standard as the rest of Kilo Aupuni):
 - SOURCED-ONLY: every record links to its USASpending public page. Being a prime or a
   recurring sub is lawful and ordinary - every line is a QUESTION to verify against the
   record, never a finding or an accusation. No number, name, or statute is invented.
 - PROVENANCE: every record carries source_type="sourced" (from an official API filing) and
   renders a small visible badge. Federal subaward data comes from SAM.gov/FSRS filings, so it
   is all "sourced" - none of it is "transcribed" (derived from meeting audio/video).
 - The COUNTY (non-federal) sub tier - a Maui County vendor's own subcontractors on a
   county-funded job - is NOT in any public open dataset (Hawaiʻi has no NYC-style Local
   Law 44 subcontractor-disclosure feed). That gap is named honestly on the page, not invented.

Stdlib + urllib only. Windowless-safe (guards every print with `if sys.stdout`). UTF-8 everywhere.
"""
import os, re, sys, json, time, argparse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_DIR = os.path.join(PROJECT, "reports", "mauios")
HTML_F  = os.path.join(OUT_DIR, "subcontracts_maui.html")
JSON_F  = os.path.join(OUT_DIR, "subcontracts_maui.json")
ALIAS_F = os.path.join(OUT_DIR, "subcontractors_maui.html")   # matches county_awards.dim_links convention
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
API     = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
AWARD_URL = "https://www.usaspending.gov/award/"              # + generated_internal_id
DS_URL  = "https://www.usaspending.gov/search"
HST     = timezone(timedelta(hours=-10))

# Federal fiscal window - default = the four FYs spanning the Aug-2023 Lahaina fire and the
# federal disaster response (the most oversight-relevant Maui federal money). Overridable by env/CLI.
START   = os.environ.get("KA_SUB_START", "2021-10-01")
END     = os.environ.get("KA_SUB_END",   "2026-09-30")

# award_type_codes groups (USASpending rejects mixing procurement + assistance in one request).
GROUPS = {
    "contracts": ["A", "B", "C", "D"],     # subcontracts sit under prime contracts
    "grants":    ["02", "03", "04", "05"], # subgrants sit under prime grants (pass-through $)
}

# Place of performance = Maui County. USASpending county code is the 3-digit within-state FIPS 15.
def maui_loc(county="009"):
    return {"country": "USA", "state": "HI", "county": county}

PRIME_FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
                "Award Type", "generated_internal_id"]
SUB_FIELDS   = ["Sub-Award ID", "Sub-Awardee Name", "Sub-Award Amount", "Sub-Award Date",
                "Prime Recipient Name", "Prime Award ID", "Awarding Agency",
                "Sub-Award Description", "prime_award_generated_internal_id"]


def now_hst(): return datetime.now(HST)

def say(msg):
    if sys.stdout:
        try: sys.stdout.write(msg + "\n")
        except Exception: pass

def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "kilo-aupuni", "event": f"{tag}: {msg}"}
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass

def esc(s):
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def usd(n):
    try: return "{:,.0f}".format(float(n or 0))
    except Exception: return "0"

def fnum(n):
    try: return float(n or 0)
    except Exception: return 0.0

def norm(name):
    """Fold case/punct/suffix noise so 'ECC CONSTRUCTORS LLC' and 'Ecc Constructors, L.L.C.'
    group together. Returns (key, display)."""
    if not name: return None, None
    disp = str(name).strip()
    k = disp.upper()
    k = re.sub(r"[.,&'`]", " ", k)
    k = re.sub(r"\b(INC|LLC|L L C|CORP|CORPORATION|CO|COMPANY|LTD|LP|L P|GROUP|THE|PC|P C|DBA)\b", " ", k)
    k = re.sub(r"\s+", " ", k).strip()
    return (k or disp.upper()), disp

def post(body):
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency)"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())

def fetch_primes(codes, county, max_pages):
    """Page prime awards for one award-type group (place of performance = Maui)."""
    out, page = [], 1
    while page <= max_pages:
        body = {"filters": {"time_period": [{"start_date": START, "end_date": END}],
                            "place_of_performance_locations": [maui_loc(county)],
                            "award_type_codes": codes},
                "fields": PRIME_FIELDS, "page": page, "limit": 100,
                "sort": "Award Amount", "order": "desc"}
        try:
            d = post(body)
        except Exception as e:
            dispatch("FINDING", f"subcontract_chain prime page {page} ({codes}) failed: {e}")
            break
        out.extend(d.get("results", []))
        if not d.get("page_metadata", {}).get("hasNext"): break
        page += 1
        time.sleep(0.35)
    return out

def fetch_subs(codes, county, max_pages):
    """Page the subaward tier for one group. spending_level='subawards' returns each
    subrecipient row already carrying the prime it sits under."""
    out, page = [], 1
    while page <= max_pages:
        body = {"filters": {"time_period": [{"start_date": START, "end_date": END}],
                            "place_of_performance_locations": [maui_loc(county)],
                            "award_type_codes": codes},
                "spending_level": "subawards", "fields": SUB_FIELDS,
                "page": page, "limit": 100, "sort": "Sub-Award Amount", "order": "desc"}
        try:
            d = post(body)
        except Exception as e:
            dispatch("FINDING", f"subcontract_chain sub page {page} ({codes}) failed: {e}")
            break
        out.extend(d.get("results", []))
        if not d.get("page_metadata", {}).get("hasNext"): break
        page += 1
        time.sleep(0.35)
    return out


def build(county, prime_pages, sub_pages):
    # 1) prime universe (denominator for coverage) --------------------------------
    prime_awards = []
    prime_gid_seen = set()
    for group, codes in GROUPS.items():
        for r in fetch_primes(codes, county, prime_pages):
            gid = r.get("generated_internal_id") or r.get("Award ID")
            if gid and gid in prime_gid_seen: continue
            if gid: prime_gid_seen.add(gid)
            prime_awards.append({"award_id": r.get("Award ID"), "gid": r.get("generated_internal_id"),
                                 "recipient": (r.get("Recipient Name") or "UNKNOWN").strip(),
                                 "amount": fnum(r.get("Award Amount")),
                                 "agency": r.get("Awarding Agency"), "group": group})

    # 2) subaward tier ------------------------------------------------------------
    records = []            # flat, JSON-facing (schema the task requires)
    seen_sub = set()
    for group, codes in GROUPS.items():
        for r in fetch_subs(codes, county, sub_pages):
            prime_gid = r.get("prime_award_generated_internal_id") or ""
            sub_id = r.get("Sub-Award ID")
            k = (sub_id, prime_gid)
            if sub_id and k in seen_sub: continue
            if sub_id: seen_sub.add(k)
            src = (AWARD_URL + prime_gid) if prime_gid else DS_URL
            records.append({
                "prime_name": (r.get("Prime Recipient Name") or "UNKNOWN").strip(),
                "prime_award_id": r.get("Prime Award ID"),
                "prime_gid": prime_gid,
                "sub_name": (r.get("Sub-Awardee Name") or "UNKNOWN").strip(),
                "sub_amount": fnum(r.get("Sub-Award Amount")),
                "description": re.sub(r"\s+", " ", (r.get("Sub-Award Description") or "")).strip()[:240],
                "sub_date": r.get("Sub-Award Date"),
                "agency": r.get("Awarding Agency"),
                "group": group,
                "source_url": src,
                "source_type": "sourced",   # federal SAM.gov/FSRS filing, not a transcript
            })

    # 3) chain aggregation (group subs by prime; rank subs; find recurring subs) ---
    prime_key = {}                      # gid-or-normname -> display prime name
    prime_total = defaultdict(float)    # primekey -> total sub $ routed down
    prime_subs  = defaultdict(set)      # primekey -> set(subkey)
    prime_award = {}                    # primekey -> a prime award id + gid for the source link
    prime_group = {}                    # primekey -> group
    sub_key = {}                        # subkey -> display sub name
    sub_total = defaultdict(float)      # subkey -> total $ received
    sub_primes = defaultdict(set)       # subkey -> set(primekey) it appears beneath
    chain_amt = defaultdict(float)      # (primekey, subkey) -> $ together
    chain_desc = {}                     # (primekey, subkey) -> a description
    for rec in records:
        pk = rec["prime_gid"] or norm(rec["prime_name"])[0] or rec["prime_name"]
        sk = norm(rec["sub_name"])[0] or rec["sub_name"]
        prime_key.setdefault(pk, rec["prime_name"])
        prime_award.setdefault(pk, (rec["prime_award_id"], rec["prime_gid"], rec["source_url"]))
        prime_group.setdefault(pk, rec["group"])
        sub_key.setdefault(sk, rec["sub_name"])
        prime_total[pk] += rec["sub_amount"]
        prime_subs[pk].add(sk)
        sub_total[sk] += rec["sub_amount"]
        sub_primes[sk].add(pk)
        chain_amt[(pk, sk)] += rec["sub_amount"]
        if rec["description"] and (pk, sk) not in chain_desc:
            chain_desc[(pk, sk)] = rec["description"]

    total_sub = sum(r["sub_amount"] for r in records)
    by_group = {g: {"subs": 0, "amount": 0.0} for g in GROUPS}
    for r in records:
        by_group[r["group"]]["subs"] += 1
        by_group[r["group"]]["amount"] += r["sub_amount"]

    primes_with_subs = len(prime_key)
    # how many of the top scanned prime awards actually reported subs (coverage lens)
    primes_scanned = len(prime_awards)
    scanned_gids = {p["gid"] for p in prime_awards if p.get("gid")}
    scanned_with_subs = len(scanned_gids & {rec["prime_gid"] for rec in records if rec["prime_gid"]})

    primes_ranked = sorted(prime_total.items(), key=lambda kv: -kv[1])[:50]
    subs_ranked   = sorted(sub_total.items(), key=lambda kv: -kv[1])[:50]
    recurring     = sorted([s for s in sub_primes if len(sub_primes[s]) >= 2],
                           key=lambda k: (-len(sub_primes[k]), -sub_total[k]))[:40]
    chains_ranked = sorted(chain_amt.items(), key=lambda kv: -kv[1])[:50]

    stats = {
        "primes_scanned": primes_scanned, "scanned_with_subs": scanned_with_subs,
        "primes_with_subs": primes_with_subs, "n_subrecipients": len(sub_key),
        "n_subawards": len(records), "total_sub": total_sub, "by_group": by_group,
    }
    ctx = dict(prime_key=prime_key, prime_total=prime_total, prime_subs=prime_subs,
               prime_award=prime_award, prime_group=prime_group, sub_key=sub_key,
               sub_total=sub_total, sub_primes=sub_primes, chain_amt=chain_amt,
               chain_desc=chain_desc, primes_ranked=primes_ranked, subs_ranked=subs_ranked,
               recurring=recurring, chains_ranked=chains_ranked)
    return records, stats, ctx


PROV_CSS = (".prov{font-family:Consolas,monospace;font-size:9px;letter-spacing:.5px;text-transform:uppercase;"
            "border-radius:8px;padding:0 6px;border:1px solid;vertical-align:middle}"
            ".prov.sourced{color:#43d39e;border-color:rgba(67,211,158,.45)}"
            ".prov.transcribed{color:#e0863a;border-color:rgba(224,134,58,.45)}")

def render_html(stats, ctx):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    pk_disp = ctx["prime_key"]; sk_disp = ctx["sub_key"]
    prime_award = ctx["prime_award"]

    def prime_link(pk):
        _, gid, url = prime_award.get(pk, (None, None, DS_URL))
        return url or DS_URL

    def prow(kv):
        pk, tot = kv
        url = prime_link(pk)
        n = len(ctx["prime_subs"][pk])
        return (f'<div class="m"><span class="a">${usd(tot)}</span><span class="n">{n}</span>'
                f'<span class="c"><a href="{esc(url)}">{esc(pk_disp.get(pk))}</a> '
                f'<span class="prov sourced">sourced</span></span></div>')

    def srow(kv):
        sk, tot = kv
        n = len(ctx["sub_primes"][sk])
        return (f'<div class="m"><span class="a">${usd(tot)}</span><span class="n">{n}</span>'
                f'<span class="c">{esc(sk_disp.get(sk))} <span class="prov sourced">sourced</span></span></div>')

    def crow(kv):
        (pk, sk), amt = kv
        url = prime_link(pk)
        desc = ctx["chain_desc"].get((pk, sk), "")
        d = f' &middot; <span style="color:#9a957f">{esc(desc)}</span>' if desc else ""
        return (f'<div class="row"><span class="a">${usd(amt)}</span>'
                f'<span class="c"><b><a href="{esc(url)}">{esc(pk_disp.get(pk))}</a></b> &rarr; '
                f'{esc(sk_disp.get(sk))} <span class="prov sourced">sourced</span>{d}'
                f'<br><span style="color:#9a957f;font-size:11.5px">Federal money that flowed from '
                f'{esc(pk_disp.get(pk))} (the prime) down to {esc(sk_disp.get(sk))} on Maui work. '
                f'Who is this subrecipient, and does the chain match the public purpose? '
                f'(a disclosed relationship to read, not a finding)</span></span></div>')

    prime_rows = "".join(prow(kv) for kv in ctx["primes_ranked"]) or \
        '<div class="m"><span class="c" style="color:#9a957f">No prime with reported Maui subawards in the window.</span></div>'
    sub_rows = "".join(srow(kv) for kv in ctx["subs_ranked"]) or \
        '<div class="m"><span class="c" style="color:#9a957f">No subrecipients found.</span></div>'
    rec_rows = "".join(srow((s, ctx["sub_total"][s])) for s in ctx["recurring"]) or \
        '<div class="m"><span class="c" style="color:#9a957f">No subrecipient appears beneath more than one prime in this window.</span></div>'
    chain_rows = "".join(crow(kv) for kv in ctx["chains_ranked"]) or \
        '<div class="row"><span class="c" style="color:#9a957f">No prime&rarr;sub chains in the window.</span></div>'

    bg = stats["by_group"]
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Who Is Paid Behind the Prime - Maui Federal Subcontractor Chains - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 80px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:82ch}}
 .kpi{{display:flex;gap:26px;margin:16px 0;flex-wrap:wrap}} .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .gap{{font-size:12.5px;color:#e8dcc0;border-left:2px solid rgba(224,134,58,.6);background:rgba(224,134,58,.05);padding:9px 13px;margin:16px 0;font-style:normal}}
 .sec{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#d9b24c;border-bottom:1px solid rgba(217,178,76,.2);padding-bottom:6px;margin:26px 0 6px}}
 .secnote{{font-size:12.5px;color:#bdb8a4;margin:0 0 10px}}
 .m{{display:grid;grid-template-columns:130px 52px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}} .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:center}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 .m .h{{font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;text-transform:uppercase}}
 .row{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .row .a{{font-family:Consolas,monospace;font-size:12px;color:#e06a4a;white-space:nowrap;min-width:92px;text-align:right}}
 .row .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}} footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
 {PROV_CSS}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; Maui County &middot; who is paid behind the prime</div>
<h1>Who Is Really Paid Behind the Prime? <span class="prov sourced" style="font-size:11px">sourced</span></h1>
<p class="lead">When a federal award lands on Maui, the money does not stop at the prime contractor &mdash; it flows
down to the <b>subrecipients</b> (subcontractors on contracts, subgrantees on grants) who do part of the work.
USASpending.gov publishes that lower tier from the recipients' own SAM.gov / FSRS filings. This maps those chains
for Maui County (place of performance FIPS&nbsp;15009): which primes route the most money down, which firms surface
beneath the most <i>different</i> primes, and the heaviest single prime&rarr;sub links &mdash; every one a
<b>question to verify</b> against the public record, never an accusation.</p>
<div class="kpi">
 <div><div class="n">${usd(stats['total_sub'])}</div><div class="l">subaward $ (Maui)</div></div>
 <div><div class="n">{stats['n_subawards']:,}</div><div class="l">subawards</div></div>
 <div><div class="n">{stats['primes_with_subs']:,}</div><div class="l">primes with subs</div></div>
 <div><div class="n">{stats['n_subrecipients']:,}</div><div class="l">subrecipients</div></div>
</div>
<div class="disc">Source: USASpending.gov subaward tier (<a href="{DS_URL}">spending_by_award, spending_level=subawards</a>),
place of performance = Maui County (FIPS&nbsp;15009), window {esc(START)}&ndash;{esc(END)}. Split:
contracts ${usd(bg['contracts']['amount'])} across {bg['contracts']['subs']:,} subcontracts &middot;
grants ${usd(bg['grants']['amount'])} across {bg['grants']['subs']:,} subgrants. Every record carries a
<span class="prov sourced">sourced</span> provenance badge (federal SAM.gov/FSRS filing, not a meeting transcript).
Being a prime or a recurring sub is lawful and ordinary &mdash; the map exists so the chain can be read, not so anyone
is accused. Firm names fold case/suffix variants ("ECC CONSTRUCTORS LLC" = "Ecc Constructors, L.L.C.").
Coverage: {stats['n_subawards']:,} subawards join {stats['primes_with_subs']:,} distinct primes to
{stats['n_subrecipients']:,} subrecipients. For context, {stats['primes_scanned']:,}+ Maui prime awards were scanned
separately &mdash; the prime tier and the subaward tier are each recorded against place of performance independently, so
they are two lenses on the same county, not a subset of one another.</div>

<div class="gap"><b>Named gap &mdash; the county (non-federal) sub tier is not public.</b> This page is the
<i>federal</i> subcontractor chain only. A Maui County vendor's own subcontractors on a <i>county-funded</i> job are
<b>not</b> published in any open dataset: Hawaiʻi has no equivalent of New York City's Local Law&nbsp;44
subcontractor-disclosure feed. Until the County discloses development-team / subcontractor rosters (or a records
request obtains them), the county sub tier is a known blank &mdash; stated here, not invented.</div>

<h2 class="sec">Primes routing the most money down</h2>
<p class="secnote">Prime recipients ranked by total federal dollars passed to subrecipients on Maui work
(the <b>$</b> column), with the count of <b>distinct subs</b> beneath them. A wide, well-funded chain is normal for a
big prime &mdash; the question is who the subs are and whether the flow matches the public purpose. Each prime links
to its USASpending award page (open the <i>Sub-Awards</i> tab to verify).</p>
<div class="m"><span class="h" style="text-align:right">sub $ routed</span><span class="h" style="text-align:center">subs</span><span class="h">prime recipient</span></div>
{prime_rows}

<h2 class="sec">Subrecipients receiving the most (across all primes)</h2>
<p class="secnote">Subrecipients ranked by total federal dollars received on Maui work, with the number of
<b>distinct primes</b> they sit beneath. The question each time: who is this firm, and why here?</p>
<div class="m"><span class="h" style="text-align:right">received</span><span class="h" style="text-align:center">primes</span><span class="h">subrecipient</span></div>
{sub_rows}

<h2 class="sec">Subs that surface beneath the most <i>different</i> primes</h2>
<p class="secnote">Firms present beneath two or more <b>distinct</b> primes &mdash; the subs "really paid behind the
prime" no matter whose name is on the federal award. A recurring sub is often just a specialized trade; the question is
simply who they are and why they recur.</p>
<div class="m"><span class="h" style="text-align:right">received</span><span class="h" style="text-align:center">primes</span><span class="h">subrecipient</span></div>
{rec_rows}

<h2 class="sec">The heaviest single chains</h2>
<p class="secnote">Specific prime&rarr;sub pairs carrying the most money together &mdash; a standing flow from one
prime to one sub on Maui.</p>
{chain_rows}

<p style="margin-top:18px"><a href="federal_money.html">&larr; Maui federal prime awards</a> &middot;
<a href="jurisdictions.html">all govOS jurisdictions</a> &middot;
<a href="subcontractors_nyc.html">NYC subcontractor chains</a> &middot;
<a href="reports.html">all reports</a></p>
<footer>generated {g} &middot; subcontract-chain v1 &middot; source: USASpending.gov subaward tier (public record) &middot;
provenance: sourced (SAM.gov/FSRS filings) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Maui federal subcontractor chain (USASpending).")
    ap.add_argument("--county", default="009", help="HI county FIPS3 (default 009 = Maui)")
    ap.add_argument("--prime-pages", type=int, default=int(os.environ.get("KA_SUB_PRIME_PAGES", "4")),
                    help="max pages of prime awards to scan per group (100/page)")
    ap.add_argument("--sub-pages", type=int, default=int(os.environ.get("KA_SUB_PAGES", "6")),
                    help="max pages of subawards to pull per group (100/page)")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    records, stats, ctx = build(args.county, args.prime_pages, args.sub_pages)

    payload = {
        "generated": now_hst().strftime("%Y-%m-%d %H:%M:%S HST"),
        "source": "USASpending.gov /api/v2/search/spending_by_award/ (spending_level=subawards); "
                  "prime tier same endpoint. Place of performance = Maui County FIPS 15009.",
        "source_url": DS_URL,
        "window": {"start": START, "end": END},
        "county_fips": "15" + args.county,
        "provenance_note": "All records source_type='sourced' (federal SAM.gov/FSRS filings). "
                           "None are 'transcribed'. The county (non-federal) subcontractor tier is "
                           "NOT publicly available (no Hawaiʻi Local Law 44 equivalent) - a named gap.",
        "coverage": {"primes_scanned_for_context": stats["primes_scanned"],
                     "primes_in_subaward_tier": stats["primes_with_subs"],
                     "scanned_primes_also_in_subtier": stats["scanned_with_subs"],
                     "subrecipients": stats["n_subrecipients"],
                     "subawards_found": stats["n_subawards"],
                     "total_subaward_usd": round(stats["total_sub"], 2),
                     "by_group": stats["by_group"],
                     "coverage_note": "The prime tier and the subaward tier are recorded against place of "
                                      "performance independently; they are two lenses on Maui, not subset/superset. "
                                      "Grants dominate the subaward $ (federal disaster pass-through)."},
        "note": "Down-and-up the federal money chain: each record links a subrecipient UP to its prime. "
                "Presence of a sub relationship is lawful and a question for oversight, never an accusation.",
        "records": sorted(records, key=lambda r: -r["sub_amount"]),
    }
    tmp = JSON_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, JSON_F)

    html = render_html(stats, ctx)
    for path in (HTML_F, ALIAS_F):
        t = path + ".tmp"
        with open(t, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
        os.replace(t, path)

    dispatch("SHIPPED", f"subcontract_chain: Maui federal subaward tier ${stats['total_sub']:,.0f} across "
                        f"{stats['n_subawards']} subawards, {stats['primes_with_subs']} primes, "
                        f"{stats['n_subrecipients']} subrecipients (county non-federal tier = named public gap)")
    say(f"subcontract-chain (Maui): ${stats['total_sub']:,.0f} in subawards / {stats['n_subawards']} subawards / "
        f"{stats['primes_with_subs']} primes with subs / {stats['n_subrecipients']} subrecipients")
    say(f"  coverage: {stats['primes_scanned']}+ prime awards scanned (context); subaward tier joins "
        f"{stats['primes_with_subs']} primes; contracts {stats['by_group']['contracts']['subs']} subs / "
        f"grants {stats['by_group']['grants']['subs']} subs")
    if ctx["primes_ranked"]:
        pk, tot = ctx["primes_ranked"][0]
        say(f"  top prime routing down: {ctx['prime_key'][pk]} -> ${tot:,.0f} across {len(ctx['prime_subs'][pk])} subs")
    if ctx["recurring"]:
        s = ctx["recurring"][0]
        say(f"  top recurring sub: {ctx['sub_key'][s]} -> beneath {len(ctx['sub_primes'][s])} distinct primes, ${ctx['sub_total'][s]:,.0f}")
    say(f"  -> {HTML_F}")
    say(f"  -> {JSON_F}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
