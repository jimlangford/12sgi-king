#!/usr/bin/env python3
"""nys_lobby_watch.py - Kilo Aupuni: New York STATE lobbying (gap: lobby_nys).

Builds lobby_nys.html from REAL public records on data.ny.gov:

  Lobbying client spending  - Socrata qym9-xzj6 ("Client Semi-Annual Report:
  Beginning 2019"), filed with the NYS Commission on Ethics and Lobbying in
  Government (COELIG, formerly JCOPE). Each filing reports a client's lobbying
  compensation + reimbursement for a semi-annual period. Aggregated to the top
  lobbying clients by reported spend.

  Cross vs campaign money - the matched client names are crossed against NYS
  Board of Elections organizational campaign donors (Socrata 4j2b-6a2j, the
  same dataset used by nys_money_parity.py) to surface entities that BOTH pay
  to lobby Albany AND donate to NY campaigns: a double channel of influence,
  framed as a question.

DEDUP GOTCHA (verified): qym9-xzj6 has 66.8M rows but only 59,688 distinct
filings - the per-filing compensation value is repeated across every itemized
expense row of that filing (one form had comp=357,892 repeated 2.8M times).
Naive sum(current_period_compensation) inflates by orders of magnitude. We
take MAX(comp), MAX(reimbursement) per form_submission_id (filing-level), then
sum per client in python.

Integrity: every correlation is a QUESTION against public records, never an
accusation; sources cited; honest pending if a source fails.
"""
import os, json, ssl, time, urllib.request, urllib.parse, html, re
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
ET = timezone(timedelta(hours=-4))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)", "Accept": "application/json"}

DOMAIN = "data.ny.gov"
CLIENT = "qym9-xzj6"   # Client Semi-Annual Report: Beginning 2019 (COELIG / ex-JCOPE)
CONTRIB = "4j2b-6a2j"  # NYSBOE Campaign Finance Disclosure Contributions: Beginning 1999
OUTLIER = 2_000_000_000

ORG_TYPES = ("Corporation",
             "Professional/Limited Liability Company (PLLC/LLC)",
             "Partnership including LLPs",
             "Sole Proprietorship",
             "Association")

esc = lambda s: html.escape(str(s or ""))
usd = lambda n: f"{n:,.0f}"
def now_et(): return datetime.now(ET)

def soql(dataset, params, timeout=180):
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"https://{DOMAIN}/resource/{dataset}.json?{qs}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def num(s):
    try:
        return float(str(s).replace(",", "").replace("$", "").strip())
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

STOP = {"city of", "town of", "county of", "state of", "department of", "the",
        "new york", "village of", "board of", "office of", "association",
        "coalition", "committee"}

def clean_client(name):
    # beneficial_client often has a trailing ";" and may list a coalition after it
    n = (name or "").strip().rstrip(";").strip()
    # take the first listed beneficial client if semicolon-separated
    if ";" in n:
        n = n.split(";")[0].strip()
    return n

# ---------------------------------------------------------------- lobby clients
def fetch_filings():
    """Filing-level dedup, two stages.

    Stage 1 (server): the raw table fans each filing across its itemized-expense
    rows, so take MAX(comp)/MAX(reimb) per form_submission_id to collapse the
    fan-out to one value per filing.

    Stage 2 (python, see aggregate_clients): the SAME reporting period for a
    client can have an Original AND one or more Amendment filings, each with its
    own form_submission_id but identical (or superseding) amounts. Summing every
    form double-counts amended periods, so we keep ONE value per
    (beneficial_client, reporting_year, reporting_period) - MAX across the
    original + amendments - before summing per client.
    """
    rows, off, PAGE = [], 0, 50000
    while True:
        batch = soql(CLIENT, {
            "$select": ("form_submission_id,beneficial_client,reporting_year,reporting_period,"
                        "max(current_period_compensation) as comp,"
                        "max(current_period_reimbursement) as reimb"),
            "$group": "form_submission_id,beneficial_client,reporting_year,reporting_period",
            "$order": "form_submission_id", "$limit": PAGE, "$offset": off})
        rows += batch
        if len(batch) < PAGE:
            break
        off += PAGE; time.sleep(0.3)
    return rows

def aggregate_clients(filings):
    # Stage 2 dedup: collapse original + amendment(s) of one period to a single
    # period record (MAX comp/reimb), keyed by (client, year, period).
    periods = {}
    for r in filings:
        comp = num(r.get("comp")) or 0.0
        reimb = num(r.get("reimb")) or 0.0
        name = clean_client(r.get("beneficial_client"))
        yr = (r.get("reporting_year") or "").strip()
        per = (r.get("reporting_period") or "").strip()
        if not name or name.upper() == "NULL":
            continue
        if comp >= OUTLIER or reimb >= OUTLIER:
            continue
        pk = (name, yr, per)
        e = periods.get(pk)
        if not e:
            periods[pk] = {"name": name, "yr": yr, "comp": comp, "reimb": reimb}
        else:
            e["comp"] = max(e["comp"], comp)
            e["reimb"] = max(e["reimb"], reimb)

    by, years = {}, set()
    n_periods = 0
    for (name, yr, per), p in periods.items():
        n_periods += 1
        if yr:
            years.add(yr)
        e = by.setdefault(name, {"client": name, "comp": 0.0, "reimb": 0.0,
                                 "filings": 0, "years": set(), "key": org_key(name)})
        e["comp"] += p["comp"]; e["reimb"] += p["reimb"]; e["filings"] += 1
        if yr:
            e["years"].add(yr)
    out = []
    for e in by.values():
        e["total"] = e["comp"] + e["reimb"]
        e["years"] = sorted(e["years"])
        out.append(e)
    out.sort(key=lambda x: -x["total"])
    return out, n_periods, sorted(years)

# ---------------------------------------------------------------- campaign cross
def fetch_org_donors():
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

def build_cross(clients, donors):
    dk = {}
    for d in donors:
        if not d["key"] or d["key"] in STOP:
            continue
        e = dk.get(d["key"])
        if not e:
            dk[d["key"]] = {"name": d["name"], "total": d["total"], "n": d["n"], "label_total": d["total"]}
        else:
            e["total"] += d["total"]; e["n"] += d["n"]
            if d["total"] > e["label_total"]:
                e["name"] = d["name"]; e["label_total"] = d["total"]
    out, seen = [], set()
    for c in clients:
        k = c["key"]
        if not k or k in STOP or k in seen:
            continue
        d = dk.get(k)
        if not d:
            continue
        seen.add(k)
        out.append({
            "client": c["client"], "lobby_total": c["total"], "lobby_filings": c["filings"],
            "donor": d["name"], "donor_given": d["total"], "donor_n": d["n"],
            "question": (f"An entity recorded as {c['client']} reported ${c['total']:,.0f} paid to lobby New "
                         f"York State; an organization recorded as {d['name']} gave ${d['total']:,.0f} to NY "
                         f"campaigns. Are these the same entity, and if so do the two channels - paying to "
                         f"shape the law and funding those who write it - converge on the same decisions? "
                         f"(public records - a correlation to verify, not a finding)")
        })
    out.sort(key=lambda x: -(x["lobby_total"] + x["donor_given"]))
    return out

# ---------------------------------------------------------------- page
def build_page(clients, n_clients, n_filings, years, cross, donor_pool):
    g = now_et().strftime("%Y-%m-%d %H:%M ET")
    yr_span = (years[0] + "–" + years[-1]) if len(years) > 1 else (years[0] if years else "")
    total_comp = sum(c["comp"] for c in clients)
    total_reimb = sum(c["reimb"] for c in clients)
    top = clients[:50]
    def crow(c):
        reimb_tag = f' <span class=ind>&middot; reimb ${usd(c["reimb"])}</span>' if c["reimb"] > 0 else ""
        return (f'<div class="m"><span class="a">${usd(c["total"])}</span>'
                f'<span class="n">{c["filings"]}</span>'
                f'<span class="c">{esc(c["client"])}{reimb_tag}</span></div>')
    rows = "".join(crow(c) for c in top)

    crows = "".join(
        f'<div class="row"><span class="a">${usd(o["lobby_total"])}</span>'
        f'<span class="c"><b>{esc(o["client"])}</b> &mdash; ${usd(o["lobby_total"])} reported to lobby Albany / '
        f'matched donor <b>{esc(o["donor"])}</b> gave ${usd(o["donor_given"])} to NY campaigns. '
        f'<span style="color:#9a957f">{esc(o["question"])}</span></span></div>'
        for o in cross[:40])
    cross_total_lobby = sum(o["lobby_total"] for o in cross)
    cross_total_given = sum(o["donor_given"] for o in cross)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>New York State - Who Pays to Lobby Albany - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 80px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:30px 0 4px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .sub{{font-size:12.5px;color:#bdb8a4;margin:2px 0 10px;max-width:84ch}}
 .m{{display:grid;grid-template-columns:150px 56px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:11.5px;color:#9a957f;text-align:right}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 .ind{{color:#756b56}} .hd .a,.hd .n,.hd .c{{color:#756b56}}
 .q{{background:rgba(217,178,76,.05);border:1px solid rgba(217,178,76,.25);border-radius:10px;padding:12px 15px;margin:16px 0;font-size:13px;color:#cfc9b6}}
 .q b{{color:#e8e4d8}}
 .row{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .row .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;white-space:nowrap;min-width:96px;text-align:right}}
 .row .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York State &middot; the third channel</div>
<h1>New York State &mdash; Who Pays to Lobby Albany</h1>
<p class="lead">Beyond donating and contracting, there is a third channel of influence: paid lobbying. This is
the <b>NYS Commission on Ethics and Lobbying in Government</b> (COELIG, formerly JCOPE) client disclosure
registry &mdash; the clients who hire lobbyists to shape State legislation, agency rules, and budget lines,
ranked by the compensation and reimbursement they reported. Who pays to be heard inside the Capitol.</p>
<div class="kpi">
 <div><div class="n">{n_clients:,}</div><div class="l">lobbying clients</div></div>
 <div><div class="n">${usd(total_comp)}</div><div class="l">compensation reported</div></div>
 <div><div class="n">${usd(total_reimb)}</div><div class="l">reimbursement reported</div></div>
 <div><div class="n">{n_filings:,}</div><div class="l">client filings &middot; {esc(yr_span)}</div></div>
</div>
<div class="disc">Source: NYS Commission on Ethics and Lobbying in Government (COELIG, formerly JCOPE),
"Client Semi-Annual Report: Beginning 2019" on data.ny.gov, dataset
<a href="https://data.ny.gov/d/{CLIENT}">{CLIENT}</a>. Compensation and reimbursement fields are stored as
text and were cast to number in code. The raw table fans every filing out across its itemized-expense rows
(66.8M rows for {n_filings:,} real filings), so each amount was taken <b>once per filing</b>
(<code>max</code> per <code>form_submission_id</code>) before summing per beneficial client &mdash; otherwise
totals inflate by orders of magnitude. Lobbying is lawful and registered by design; this maps who spends the
most to influence State government, to read beside who funds officials and who wins contracts. Documented
public record and open questions, never findings of wrongdoing.</div>

<h2>Top lobbying clients by reported spend</h2>
<p class="sub">Ranked by reported compensation + reimbursement, summed across all of a client's filings.
A client appearing here <i>and</i> in the campaign-finance or contract ledgers is where influence channels
converge &mdash; a question to carry into the parity view.</p>
<div class="m hd"><span class="a">comp + reimb</span><span class="n">filings</span><span class="c">beneficial client</span></div>
{rows}

<h2>Lobby + Money &mdash; clients that also donate to NY campaigns</h2>
<p class="sub">Names matched on normalized organization across two public datasets: COELIG lobbying clients
({CLIENT}) &times; NYSBOE organizational campaign donors ({CONTRIB}). A name match is <b>not</b> proof of the
same legal entity &mdash; common names collide, so generic tokens are stoplisted and every line is a question.
Matched against {len(donor_pool):,} organizational donor names.</p>
<div class="q"><b>The question.</b> When the same entity both pays lobbyists to shape Albany's laws and funds
the campaigns of those who vote on them, two channels of influence converge on one decision. The record
below shows {len(cross)} such names &mdash; ${usd(cross_total_lobby)} reported in lobbying beside
${usd(cross_total_given)} in campaign giving. Read each beside the votes and recusals; that is where the
question gets answered.</div>
{crows or '<div class="row"><span class="c">No name overlap on this run.</span></div>'}

<p style="margin-top:18px"><a href="money_nys.html">who funds NY officials</a>
&middot; <a href="parity_nys.html">vendors &times; donors parity</a>
&middot; <a href="contracts_nys.html">NYS contract vendors</a>
&middot; <a href="jurisdictions.html">all govOS jurisdictions</a></p>
<footer>generated {g} &middot; nys-lobby v1 &middot; source: data.ny.gov {CLIENT} (COELIG / ex-JCOPE) &times; {CONTRIB} (NYSBOE), public record &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    filings = fetch_filings()
    clients, n_filings, years = aggregate_clients(filings)
    try:
        donors = fetch_org_donors()
    except Exception as e:
        print("donor fetch failed (cross skipped):", e); donors = []
    cross = build_cross(clients, donors) if donors else []

    html_out = build_page(clients, len(clients), n_filings, years, cross, donors)
    open(os.path.join(MAUIOS, "lobby_nys.html"), "w", encoding="utf-8", newline="\n").write(html_out)
    json.dump({"generated": now_et().isoformat(),
               "source": f"data.ny.gov {CLIENT} (COELIG/JCOPE client semi-annual) x {CONTRIB} (NYSBOE)",
               "clients": len(clients), "filings": n_filings, "years": years,
               "total_comp": round(sum(c["comp"] for c in clients), 2),
               "total_reimb": round(sum(c["reimb"] for c in clients), 2),
               "top_clients": [{"client": c["client"], "total": round(c["total"], 2),
                                "filings": c["filings"]} for c in clients[:50]],
               "lobby_and_donate": cross[:40]},
              open(os.path.join(MAUIOS, "lobby_nys.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    print(f"lobby_nys: {len(clients):,} clients / {n_filings:,} filings / years {years[0]}-{years[-1]}")
    print(f"   comp ${sum(c['comp'] for c in clients):,.0f} + reimb ${sum(c['reimb'] for c in clients):,.0f}")
    for c in clients[:8]:
        print(f"   ${c['total']:>12,.0f}  {c['filings']:>3} filings  {c['client'][:50]}")
    print(f"   lobby+donate crosses: {len(cross)}")
    for o in cross[:6]:
        print(f"     lobby ${o['lobby_total']:>10,.0f} / donor {o['donor'][:28]} gave ${o['donor_given']:,.0f}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
