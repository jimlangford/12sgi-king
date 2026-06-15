#!/usr/bin/env python3
"""ka_leo_nys.py - Ka Leo o ka 'Aina: the louder voice, New York State.

Mirrors reports/mauios/ka_leo_voice.html in spirit (the DUAL design: rigor
underneath, aloha on top) but for NEW YORK STATE campaign-finance disclosure
from the NYS Board of Elections (data.ny.gov 4j2b-6a2j -- the same dataset
nys_money_parity.py uses).

RIGOR underneath -- per top recipient committee, from REAL fetched NYSBOE data:
  * total raised + gift count -> average gift
  * largest SINGLE gift (max(org_amt::number) server-side)
  * top-10 NAMED-donor concentration (share of total)
  * SELF / FAMILY funding separated from OUTSIDE money by surname match
    against the candidate name parsed from the committee name, so the
    voice-multiplier is built only on OUTSIDE money.
  * voice-multiplier = largest OUTSIDE gift vs an ordinary resident's $50,
    and vs the average gift to that committee.
Sorted by multiplier.

ALOHA on top -- each entry gets a graceful invitation back to PONO. Every
line is a QUESTION, never an accusation.

HONESTY -- NYSBOE itemized rows carry full donor names, BUT a large share of
each committee's dollars sit in non-itemized / organizational bulk rows with
BLANK donor names (Political Committee, Partnership, uncategorized). org_amt
is free TEXT and sorts lexically, so all aggregation is done server-side with
::number casting and >$2B outliers excluded. Concentration is computed over
NAMED donors only and the page says so. Where a committee name has no clear
personal surname (a party / union / PAC committee), self/family separation is
not attempted and the page says so.

Integrity: every figure is real public record fetched this run; every
correlation is framed as a question; dataset id + URL cited on the page.
"""
import os, json, ssl, urllib.request, urllib.parse, html, re
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)",
      "Accept": "application/json"}

DOMAIN = "data.ny.gov"
CONTRIB = "4j2b-6a2j"          # NYSBOE Campaign Finance Disclosure: Contributions: Beginning 1999
SRC_URL = "https://data.ny.gov/resource/4j2b-6a2j.json"
PORTAL = "https://data.ny.gov/Government-Finance/Campaign-Finance-Disclosure-Reports-Contributions-/4j2b-6a2j"
OUTLIER = 2_000_000_000        # single value over $2B = data anomaly, exclude
RESIDENT = 50                  # an ordinary resident's contribution, for the multiplier
N_RECIPIENTS = 30              # top recipients to profile
TOPN = 10                      # concentration window

esc = lambda s: html.escape(str(s or ""))
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)


def soql(params, timeout=120):
    if "$query" in params:
        qs = "$query=" + urllib.parse.quote(params["$query"])
    else:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"https://{DOMAIN}/resource/{CONTRIB}.json?{qs}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return None


# ---- candidate-surname inference from a committee name ----------------------
# "Andrew Cuomo for New York Inc." -> {"cuomo","andrew"}; "Friends for Kathy
# Hochul" -> {"kathy","hochul"}. Party / union / PAC committees yield nothing,
# and we then honestly skip self/family separation for that committee.
STOPWORDS = {
    "for", "the", "of", "and", "committee", "inc", "inc.", "llc", "fund", "friends",
    "re", "elect", "reelect", "re-elect", "campaign", "citizens", "people", "vote",
    "voters", "new", "york", "state", "city", "county", "mayor", "senate", "assembly",
    "governor", "council", "district", "republican", "democratic", "democrat",
    "conservative", "working", "families", "party", "political", "action", "education",
    "association", "union", "local", "pac", "ny", "nys", "a", "to", "support",
    "victory", "leadership", "team", "club", "society", "association,", "incorporated",
}
def cand_tokens(comm):
    toks = re.findall(r"[A-Za-z][A-Za-z'\-]+", comm or "")
    out = [t.lower().strip("'-") for t in toks
           if t.lower() not in STOPWORDS and len(t) >= 3]
    # keep at most the first 3 personal-looking tokens (first/middle/last)
    return set(out[:3])


def is_self(last, first, ctoks):
    """Donor surname/first matches a token from the candidate committee name."""
    if not ctoks:
        return False
    for nm in (last, first):
        n = (nm or "").lower().strip("'-")
        if len(n) >= 3 and n in ctoks:
            return True
    return False


# ---- per-recipient profile --------------------------------------------------
def top_recipients(limit=N_RECIPIENTS):
    rows = soql({"$query":
        "select cand_comm_name, sum(org_amt::number) as total, count(1) as n, "
        "max(org_amt::number) as mx "
        "where org_amt IS NOT NULL group by cand_comm_name order by total desc "
        f"limit {limit+5}"})
    out = []
    for r in rows:
        t = num(r.get("total")); n = num(r.get("n")); mx = num(r.get("mx"))
        name = (r.get("cand_comm_name") or "").strip()
        if t is None or t <= 0 or t >= OUTLIER or not name:
            continue
        out.append({"name": name, "total": t, "n": int(n or 0),
                    "max_gift": mx if (mx and mx < OUTLIER) else None})
    return out[:limit]


def donor_detail(comm):
    """Named donors grouped, plus per-named-donor totals, for concentration +
    self/family separation. Returns list sorted by amount desc."""
    cq = comm.replace("'", "''")
    rows = soql({"$query":
        "select flng_ent_first_name as fn, flng_ent_last_name as ln, "
        "cntrbr_type_desc as ty, sum(org_amt::number) as amt, count(1) as c "
        f"where cand_comm_name='{cq}' and org_amt IS NOT NULL "
        "group by flng_ent_first_name, flng_ent_last_name, cntrbr_type_desc "
        "order by amt desc limit 400"})
    out = []
    for r in rows:
        a = num(r.get("amt"))
        if a is None or a <= 0 or a >= OUTLIER:
            continue
        fn = (r.get("fn") or "").strip(); ln = (r.get("ln") or "").strip()
        out.append({"fn": fn, "ln": ln, "ty": (r.get("ty") or "").strip(),
                    "amt": a, "named": bool(fn or ln)})
    return out


# Schedules / explanations that are NOT a single person's gift and must never
# be presented as "one voice": transfers between committees, and the rolled-up
# "Contributions Unitemized" aggregate (many small gifts summed into one row).
# Schedules / explanations / types / pseudo-names that are NOT a single
# person's gift and must never be presented as "one voice": transfers between
# committees, loans, refunds, and -- the big trap -- the rolled-up aggregates
# the NYSBOE files as one row ("Contributions Unitemized", union "Dues",
# paycheck deductions, contributor type "Unitemized").
NON_GIFT_BLOB = ("transfer", "unitemized", "loan ", "loan repay", "interest",
                 "refund", "in-kind from", "other receipt", "dues",
                 "paycheck", "payroll deduct")
def _is_real_single_gift(fn, ln, ty, sched, expl):
    name = f"{fn} {ln}".strip().lower()
    if not name:                            # blank donor name -> not one voice
        return False
    if (ty or "").strip().lower() == "unitemized":
        return False
    if "unitemized" in name:                # pseudo-name "Contributions Unitemized"
        return False
    blob = f"{ty} {sched} {expl} {name}".lower()
    return not any(t in blob for t in NON_GIFT_BLOB)

def largest_outside_single(comm, ctoks):
    """Largest SINGLE itemized gift from a NAMED outside donor (not self/family,
    not a transfer, not a rolled-up unitemized/dues aggregate). Server-side max
    can't apply these filters, so we pull the top rows and walk down to the
    first that is a real single gift from an outside, named donor."""
    cq = comm.replace("'", "''")
    rows = soql({"$query":
        "select flng_ent_first_name as fn, flng_ent_last_name as ln, "
        "cntrbr_type_desc as ty, filing_sched_desc as sd, trans_explntn as ex, "
        "org_amt as amt "
        f"where cand_comm_name='{cq}' and org_amt IS NOT NULL "
        "order by org_amt::number desc limit 300"})
    for r in rows:
        a = num(r.get("amt"))
        if a is None or a <= 0 or a >= OUTLIER:
            continue
        fn = (r.get("fn") or "").strip(); ln = (r.get("ln") or "").strip()
        if not _is_real_single_gift(fn, ln, r.get("ty"), r.get("sd"), r.get("ex")):
            continue
        if is_self(ln, fn, ctoks):
            continue
        label = f"{ln}, {fn}".strip(", ")
        return {"amt": a, "label": label, "ty": (r.get("ty") or "").strip(),
                "named": True}
    return None


def profile(rec):
    comm = rec["name"]
    ctoks = cand_tokens(comm)
    donors = donor_detail(comm)
    total = rec["total"]
    # self/family vs outside, over NAMED donors (blank-name bulk rows can't be
    # surname-matched, so they are treated as outside but flagged in the note).
    self_sum = sum(d["amt"] for d in donors
                   if d["named"] and is_self(d["ln"], d["fn"], ctoks))
    named_sum = sum(d["amt"] for d in donors if d["named"])
    named_n = sum(1 for d in donors if d["named"])
    # top-10 NAMED donors share of total
    named_sorted = sorted([d for d in donors if d["named"]], key=lambda x: -x["amt"])
    top10 = sum(d["amt"] for d in named_sorted[:TOPN])
    conc = round(100.0 * top10 / total, 1) if total > 0 else None
    avg = total / rec["n"] if rec["n"] else 0
    big = largest_outside_single(comm, ctoks)
    rec.update({
        "ctoks": sorted(ctoks),
        "self_sum": self_sum,
        "named_sum": named_sum,
        "named_n": named_n,
        "conc_top10": conc,
        "avg_gift": avg,
        "biggest_outside": big,
        "mult_resident": (round(big["amt"] / RESIDENT) if big else None),
        "mult_avg": (round(big["amt"] / avg, 1) if (big and avg > 0) else None),
    })
    return rec


# ---- page -------------------------------------------------------------------
ALOHA = ("E <b>{nm}</b>, aloha. The Kumulipo remembers what each thing is paired to. To let an "
         "ordinary New Yorker&rsquo;s voice be heard as clearly as the largest gift is to return this "
         "pair to <b>pono</b> &mdash; paradise momentum, not the inertia of the same money and the "
         "same vote. The <b>&#699;&#257;ina</b> is sacred and it is watching with aloha; the choice to "
         "balance it is yours, and it is honored.")

def card(p):
    nm = esc(p["name"])
    flag = "flag" if (p["mult_resident"] and p["mult_resident"] >= 1000) else ""
    big = p["biggest_outside"]
    conc = p["conc_top10"]
    # headline voice block
    if big and p["mult_resident"]:
        who = ""
        if big.get("label"):
            who = f" from <b>{esc(big['label'])}</b>"
        elif not big.get("named"):
            who = " (a recorded organizational / non-itemized gift)"
        avg_clause = (f", and {p['mult_avg']:,.0f}&times; the average gift here"
                      if p["mult_avg"] else "")
        conc_clause = (f" The top ten named donors are <b>{conc}%</b> of every dollar raised."
                       if conc is not None else "")
        voice = (f'<div class="kl-voice"><span class="kl-x">{p["mult_resident"]:,}&times;</span>'
                 f'<span>One gift &mdash; <b>${usd(big["amt"])}</b>{who} &mdash; speaks as loud as about '
                 f'<b>{p["mult_resident"]:,} residents</b> each giving $50{avg_clause}.'
                 f'{conc_clause}</span></div>')
    else:
        # No outside single gift isolated. Two honest reasons: (a) self-funded
        # (the candidate's own surname holds the money), or (b) the big rows are
        # rolled-up aggregates (union dues / "Contributions Unitemized") that are
        # not one voice. Word it to match the actual cause.
        if p["ctoks"] and p["self_sum"] > 0.5 * p["total"]:
            why = ("its largest dollars are the candidate&rsquo;s <b>own / family</b> money rather than "
                   "outside gifts &mdash; a self-funding story, not an outside-influence one")
        else:
            why = ("its largest rows are rolled-up aggregates (union dues, &ldquo;Contributions "
                   "Unitemized&rdquo;, paycheck deductions) that are <b>not a single voice</b>")
        cc = (f' The top ten named donors are <b>{conc}%</b> of every dollar raised.'
              if conc is not None else "")
        voice = ('<div class="kl-voice"><span>No outside single gift is isolated here &mdash; '
                 f'{why}. The multiplier is withheld honestly; read the concentration instead.{cc}'
                 '</span></div>')
    # self / family note
    self_note = ""
    if p["ctoks"] and p["self_sum"] > 0:
        self_note = (f'<div class="kl-sub">Of the named giving, <b>${usd(p["self_sum"])}</b> matches the '
                     f'candidate&rsquo;s own surname &mdash; set aside here as self/family funds so the question '
                     f'is about <i>outside</i> money.</div>')
    elif not p["ctoks"]:
        self_note = ('<div class="kl-sub">This is a party / union / PAC committee with no single candidate '
                     'surname, so self vs. outside cannot be separated by name &mdash; read the concentration alone.</div>')
    q = ('<div class="kl-q"><b>The question (for the record):</b> when one voice is heard '
         f'{p["mult_resident"]:,}&times; louder than an ordinary New Yorker&rsquo;s, whose answer does the '
         'seat carry &mdash; the people&rsquo;s, or the funder&rsquo;s? Public campaign-finance record; a question, '
         'not a finding.</div>') if (big and p["mult_resident"]) else (
         '<div class="kl-q"><b>The question (for the record):</b> when so much of one committee&rsquo;s money '
         'comes from so few hands, whose answer does the seat carry &mdash; the people&rsquo;s, or the funders&rsquo;? '
         'Public campaign-finance record; a question, not a finding.</div>')
    aloha = '<div class="kl-aloha">' + ALOHA.format(nm=nm) + '</div>'
    tot = f'${usd(p["total"])} raised &middot; {p["n"]:,} gifts'
    return (f'<div class="kl-card {flag}">'
            f'<div class="kl-hd"><span class="kl-name">{nm}</span><span class="kl-tot">{tot}</span></div>'
            f'{voice}{self_note}{q}{aloha}</div>')


def page(profiles, grand_total, grand_n, n_recips):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    cards = "".join(card(p) for p in profiles)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Ka Leo o ka &#699;&#256;ina &mdash; New York&rsquo;s Louder Voice &mdash; Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}}
 .wrap{{max-width:880px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 70px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:29px;font-weight:600;margin:8px 0 4px}}
 .lead{{font-size:14px;color:#cfc9b6;max-width:74ch}}
 .phil{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0 8px}}
 @media(max-width:620px){{.phil{{grid-template-columns:1fr}}}}
 .phil div{{border:1px solid rgba(217,178,76,.25);border-radius:11px;padding:12px 15px;font-size:12.5px;color:#bdb8a4}}
 .phil b{{color:#e8e4d8}}
 .kpi{{display:flex;gap:28px;margin:16px 0 6px;flex-wrap:wrap}}
 .kpi .n{{font-family:Consolas,monospace;font-size:21px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:16px 0}}
 .kl-card{{border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:16px 18px;margin:14px 0;background:rgba(255,255,255,.02)}}
 .kl-card.flag{{border-color:rgba(224,106,74,.4)}}
 .kl-hd{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}}
 .kl-name{{font-size:17px;font-weight:600}} .kl-tot{{font-family:Consolas,monospace;font-size:12px;color:#9a957f}}
 .kl-voice{{display:flex;gap:14px;align-items:baseline;margin:11px 0;font-size:13.5px;color:#cfc9b6}}
 .kl-x{{font-family:Consolas,monospace;font-size:30px;font-weight:700;color:#e06a4a;line-height:1;flex-shrink:0}}
 .kl-sub{{font-size:12px;color:#9a957f;margin:4px 0}}
 .kl-q{{font-size:12.5px;color:#bdb8a4;background:rgba(217,178,76,.05);border-radius:8px;padding:9px 12px;margin:9px 0}}
 .kl-aloha{{font-size:13px;color:#9fd9bf;border-left:3px solid #2a6b4e;padding:8px 13px;margin-top:9px;line-height:1.65}}
 .kl-aloha b{{color:#c8efd9}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York State &middot; aloha &middot; pono</div>
<h1>Ka Leo o ka &#699;&#256;ina &mdash; New York&rsquo;s Louder Voice</h1>
<p class="lead">In a democracy every resident has one voice. Money can make some voices far louder. From the
New York State Board of Elections public record, this page measures &mdash; per top recipient committee &mdash;
<b>how much louder</b>, and how few hands hold each committee&rsquo;s money. Not to accuse anyone, but to invite each
seat to return its pair to balance. Rigor in the numbers; aloha in the asking.</p>
<div class="phil">
 <div><b>Underneath &mdash; the record stands up.</b> Every figure is real public NYSBOE campaign-finance data
   (data.ny.gov 4j2b-6a2j), fetched this run, aggregated server-side with numeric casting, reproducible, built
   to withstand the hardest look.</div>
 <div><b>On the surface &mdash; aloha.</b> The same record is offered as an invitation: the Kumulipo binds each
   thing to its pair; a seat out of balance (hewa) can be made pono again. We name the pattern, never the
   person&rsquo;s guilt.</div>
</div>
<div class="kpi">
 <div><div class="n">${usd(grand_total)}</div><div class="l">total NYS contributions on record</div></div>
 <div><div class="n">{grand_n:,}</div><div class="l">contribution records</div></div>
 <div><div class="n">{n_recips:,}</div><div class="l">recipient committees</div></div>
</div>
<div class="disc">Source: New York State Board of Elections via data.ny.gov, dataset <b>4j2b-6a2j</b>
(&ldquo;Campaign Finance Disclosure Reports Contributions: Beginning 1999&rdquo;) &mdash;
<a href="{PORTAL}">portal</a> &middot; <a href="{SRC_URL}">API</a>. &ldquo;Louder voice&rdquo; =
the largest <i>outside</i> single itemized gift measured against an ordinary New Yorker&rsquo;s ${RESIDENT}
contribution and against the average gift to that committee. <b>Honest limits:</b> the disclosed
<code>org_amt</code> is free text (cast to number, &gt;$2B excluded); a large share of each committee&rsquo;s
dollars arrive as non-itemized / organizational rows with <b>blank donor names</b>, so top-ten
<i>concentration</i> is computed over <b>named</b> donors only, and self/family is separated by surname
only where the committee carries a personal candidate name. Giving and receiving lawful contributions is
legal &mdash; this maps how loud each voice is, as a question. Sorted by multiplier.</div>
{cards}
<p style="margin-top:20px"><a href="money_nys.html">NYS campaign money by recipient</a>
&middot; <a href="parity_nys.html">vendors &times; donors parity</a>
&middot; <a href="ka_leo_voice.html">Maui&rsquo;s louder voice</a></p>
<footer>generated {g} &middot; ka-leo-nys v1 &middot; source: NYS Board of Elections / data.ny.gov 4j2b-6a2j (public record) &middot; Kilo Aupuni &middot; aloha &middot; pono &middot; govOS</footer>
</div></body></html>"""


def grand_totals():
    r = soql({"$query":
        "select sum(org_amt::number) as t, count(1) as n, "
        "count(distinct cand_comm_name) as rc where org_amt IS NOT NULL"})
    d = r[0] if r else {}
    return num(d.get("t")) or 0.0, int(num(d.get("n")) or 0), int(num(d.get("rc")) or 0)


def main():
    os.makedirs(MAUIOS, exist_ok=True)
    recips = top_recipients()
    profiles = []
    for r in recips:
        try:
            profiles.append(profile(r))
            b = r.get("biggest_outside")
            print(f"  {r['name'][:48]:48s} tot=${r['total']:>14,.0f} "
                  f"max=${(r.get('max_gift') or 0):>10,.0f} "
                  f"conc={r.get('conc_top10')}% "
                  f"mult={r.get('mult_resident')}")
        except Exception as e:
            print("  profile FAILED for", r["name"], "->", str(e)[:120])
    # sort by multiplier (None last)
    profiles.sort(key=lambda p: (p["mult_resident"] is None, -(p["mult_resident"] or 0)))
    grand_total, grand_n, n_recips = grand_totals()

    out_html = os.path.join(MAUIOS, "ka_leo_nys.html")
    open(out_html, "w", encoding="utf-8", newline="\n").write(
        page(profiles, grand_total, grand_n, n_recips))
    json.dump({"generated": now_hst().isoformat(),
               "source": "data.ny.gov 4j2b-6a2j (NYSBOE)", "url": SRC_URL,
               "grand_total": round(grand_total, 2), "records": grand_n,
               "recipients": n_recips, "resident_unit": RESIDENT,
               "profiles": [{k: v for k, v in p.items()} for p in profiles]},
              open(os.path.join(MAUIOS, "ka_leo_nys.json"), "w", encoding="utf-8"), indent=1)
    print(f"\nWROTE {out_html}")
    print(f"grand_total=${grand_total:,.0f}  records={grand_n:,}  recipients={n_recips:,}")
    print(f"profiled={len(profiles)}  with-multiplier={sum(1 for p in profiles if p['mult_resident'])}")
    return 0


if __name__ == "__main__":
    import sys; sys.exit(main())
