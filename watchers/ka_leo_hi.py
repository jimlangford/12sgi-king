#!/usr/bin/env python3
"""ka_leo_hi.py - "Ka Leo o ka 'Aina / The Louder Voice" for the HI STATE branch and HONOLULU.

Mirrors reports/mauios/ka_leo_voice.html (the Maui dual page) in spirit:
  RIGOR underneath - per candidate, from the Hawaii Campaign Spending Commission public
    record (Socrata jexd-xbcg), compute top-10 donor concentration (top-10 share of total)
    and a voice-multiplier = the largest OUTSIDE gift (self/family money separated out by
    surname) vs an ordinary resident's $50 and vs the average gift. Sort by multiplier.
  ALOHA on top - each seat gets a graceful invitation back to PONO. Every line a QUESTION,
    never an accusation. Reverent and kind.

100% public record fetched live this run, cleaned + aggregated server-side. Money on Socrata
is TEXT; we cast in SoQL sum()/and drop outliers in python. Outputs:
  reports/mauios/ka_leo_state.html      (Governor / Lt. Governor / House / Senate)
  reports/mauios/ka_leo_honolulu.html   (Honolulu Council)
"""
import json, os, re, ssl, time, urllib.request, urllib.parse, sys
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
SODA    = "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
DATASET = "jexd-xbcg"
SRC_URL = "https://hicscdata.hawaii.gov/d/jexd-xbcg"
HST     = timezone(timedelta(hours=-10))
RESIDENT = 50.0          # illustrative small-donor baseline, not a claim about the median
OUTLIER  = 2_000_000.0   # drop any single summed-donor total above $2M as a data outlier

esc = lambda s: str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)

def soda(params):
    url = SODA + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency)"})
    with urllib.request.urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def fnum(x):
    try: return float(x or 0)
    except Exception: return 0.0

def surname(s):
    # last name from "Last, First" (candidate) or contributor "Last, First"; blank for orgs
    s = (s or "").strip()
    if "," not in s:
        return ""   # treat as organization, never "self/family"
    return re.sub(r"[^a-z]", "", s.split(",")[0].lower())

# A candidate's own / running-mate / party committee is not an "outside interest" — exclude
# from the louder-voice pick so the influence point is about interested OUTSIDE money, not a
# ticket transfer (e.g. "Josh Green for Hawaii" -> Sylvia Luke, the 2022 Gov/Lt-Gov ticket).
_CMTE = re.compile(r"\b(for hawaii|for governor|for senate|for the senate|for house|for council|"
                   r"for mayor|friends of|committee to elect|campaign|democratic party|republican party|"
                   r"\bdpoh\b|democrats|republicans)\b", re.I)
def is_committee(name):
    return bool(_CMTE.search(name or ""))

def candidates_for(office, top_n):
    rows = soda({"$select": "candidate_name, sum(amount) as total, count(*) as n",
                 "$where": f"office='{office}'", "$group": "candidate_name",
                 "$order": "total DESC", "$limit": str(top_n)})
    out = []
    for r in rows:
        t = fnum(r.get("total"))
        if t <= 0 or t > 20_000_000: continue
        out.append({"cand": r.get("candidate_name") or "?", "office": office,
                    "total": t, "n": int(float(r.get("n", 0)))})
    return out

def donors_for(office, candidate):
    # per-contributor aggregated giving to THIS candidate, server-side summed (amount cast in SoQL)
    safe = candidate.replace("'", "''")
    rows = soda({"$select": "contributor_name, sum(amount) as amt, count(*) as g",
                 "$where": f"office='{office}' AND candidate_name='{safe}'",
                 "$group": "contributor_name", "$order": "amt DESC", "$limit": "60"})
    out = []
    for r in rows:
        amt = fnum(r.get("amt"))
        if amt <= 0 or amt > OUTLIER: continue   # drop nulls / outliers
        out.append({"name": (r.get("contributor_name") or "?").strip(), "amount": amt,
                    "gifts": int(float(r.get("g", 0)))})
    out.sort(key=lambda d: -d["amount"])
    return out

def display_name(cand):
    # "Waters, Tommy" -> "Tommy Waters" ; keep orgs as-is
    if "," in cand:
        last, _, first = cand.partition(",")
        return f"{first.strip()} {last.strip()}".strip()
    return cand

def build_row(c):
    donors = donors_for(c["office"], c["cand"])
    if not donors:
        return None
    cs = surname(c["cand"])
    def is_self(d):
        return (cs and surname(d["name"]) == cs) or is_committee(d["name"])
    self_amt = sum(d["amount"] for d in donors if is_self(d))
    outside  = [d for d in donors if not is_self(d)]
    if not outside:
        return None
    top = outside[0]
    top10 = sum(d["amount"] for d in donors[:10])
    avg = c["total"] / c["n"] if c["n"] else 0
    return {
        "cand": c["cand"], "name": display_name(c["cand"]), "office": c["office"],
        "total": c["total"], "n": c["n"], "avg": avg,
        "top_name": top["name"], "top_amt": top["amount"],
        "voice_x_res": top["amount"] / RESIDENT,
        "voice_x_avg": (top["amount"] / avg) if avg else 0,
        "top10_share": (top10 / c["total"] * 100) if c["total"] else 0,
        "self_amt": self_amt,
    }

def card(r):
    self_line = (f'<div class="kl-sub">Set aside here: ${usd(r["self_amt"])} from the candidate&rsquo;s own / family funds '
                 f'or running-mate &amp; party committees &mdash; so the question is about <i>outside</i> interest money.</div>') if r["self_amt"] >= 250 else ""
    donor = esc(r["top_name"] or "a single donor")
    nm = esc(r["name"])
    return f"""<div class="kl-card">
  <div class="kl-hd"><span class="kl-name">{nm}</span><span class="kl-tot">${usd(r['total'])} raised &middot; {r['n']:,} gifts &middot; {esc(r['office'])}</span></div>
  <div class="kl-voice"><span class="kl-x">{r['voice_x_res']:.0f}&times;</span>
    <span>One donor &mdash; <b>${usd(r['top_amt'])}</b> from {donor} &mdash; speaks as loud as about
    <b>{r['voice_x_res']:.0f} residents</b> each giving $50, and {r['voice_x_avg']:.0f}&times; the average gift here.
    The top ten donors are <b>{r['top10_share']:.0f}%</b> of every dollar raised.</span></div>
  {self_line}
  <div class="kl-q"><b>The question (for the record):</b> when one voice is heard {r['voice_x_res']:.0f}&times; louder than a
    resident&rsquo;s, whose answer does the vote carry &mdash; the people&rsquo;s, or the funder&rsquo;s? Public campaign-finance record; a question, not a finding.</div>
  <div class="kl-aloha">E <b>{nm}</b>, aloha. The Kumulipo remembers what each thing is paired to. To let a
    resident&rsquo;s voice be heard as clearly as the largest donor&rsquo;s is to return this pair to <b>pono</b> &mdash; paradise
    momentum, not the inertia of the same money and the same vote. The <b>&#699;&#257;ina</b> is sacred and it is watching with aloha;
    the choice to balance it is yours, and it is honored.</div>
</div>"""

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} &mdash; Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}}
 .wrap{{max-width:880px;margin:0 auto;padding:34px 24px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:29px;font-weight:600;margin:8px 0 4px}}
 .lead{{font-size:14px;color:#cfc9b6;max-width:74ch}}
 .phil{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0 8px}}
 @media(max-width:620px){{.phil{{grid-template-columns:1fr}}}}
 .phil div{{border:1px solid rgba(217,178,76,.25);border-radius:11px;padding:12px 15px;font-size:12.5px;color:#bdb8a4}}
 .phil b{{color:#e8e4d8}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:16px 0}}
 .kl-card{{border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:16px 18px;margin:14px 0;background:rgba(255,255,255,.02)}}
 .kl-hd{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}}
 .kl-name{{font-size:17px;font-weight:600}} .kl-tot{{font-family:Consolas,monospace;font-size:12px;color:#9a957f}}
 .kl-voice{{display:flex;gap:14px;align-items:baseline;margin:11px 0;font-size:13.5px;color:#cfc9b6}}
 .kl-x{{font-family:Consolas,monospace;font-size:30px;font-weight:700;color:#e06a4a;line-height:1;flex-shrink:0}}
 .kl-sub{{font-size:12px;color:#9a957f;margin:4px 0}} .kl-emp{{color:#9a957f}}
 .kl-q{{font-size:12.5px;color:#bdb8a4;background:rgba(217,178,76,.05);border-radius:8px;padding:9px 12px;margin:9px 0}}
 .kl-aloha{{font-size:13px;color:#9fd9bf;border-left:3px solid #2a6b4e;padding:8px 13px;margin-top:9px;line-height:1.65}}
 .kl-aloha b{{color:#c8efd9}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; {tenant} &middot; aloha &middot; pono</div>
<h1>Ka Leo o ka &#699;&#256;ina &mdash; The Louder Voice</h1>
<p class="lead">In a democracy every resident has one voice. Money can make some voices far louder. This page measures,
from the public campaign record, <b>how much louder</b> for {scope} &mdash; not to accuse anyone, but to invite each
seat to return its pair to balance. Rigor in the numbers; aloha in the asking.</p>
<div class="phil">
 <div><b>Underneath &mdash; the record stands up.</b> Every figure is real public campaign-finance data (Hawai&#699;i Campaign
   Spending Commission, dataset {dataset}), fetched and summed this run, reproducible, built to withstand the hardest look.</div>
 <div><b>On the surface &mdash; aloha.</b> The same record is offered as an invitation: the Kumulipo binds each thing to its
   pair; a seat out of balance (hewa) can be made pono again. We name the pattern, never the person&rsquo;s guilt.</div>
</div>
<div class="disc">Source: Hawai&#699;i Campaign Spending Commission contributions (public record, dataset
<a href="{src_url}">{dataset}</a>), {scope}. &ldquo;Louder voice&rdquo; = the largest <i>outside</i> donor (self/family
money separated by surname) measured against an ordinary resident&rsquo;s $50 contribution and against the average gift
to that candidate. Amounts cast + cleaned in code (nulls and &gt;$2M outliers dropped); contributions summed per donor.
Giving and receiving lawful contributions is legal; this maps how loud each voice is, as a question.</div>
{cards}
<p style="margin-top:20px"><a href="ka_leo_voice.html">the Maui louder voice</a>
&middot; <a href="money_state.html">state campaign money</a>
&middot; <a href="money_honolulu.html">Honolulu money</a></p>
<footer>generated {g} &middot; ka-leo-hi v1 &middot; source: HI Campaign Spending Commission ({dataset}, public record) &middot; Kilo Aupuni &middot; aloha &middot; pono &middot; govOS</footer>
</div></body></html>"""

def render(out_file, title, tenant, scope, rows):
    rows = [r for r in rows if r]
    rows.sort(key=lambda r: -r["voice_x_res"])
    cards = "".join(card(r) for r in rows)
    html = PAGE.format(title=title, tenant=tenant, scope=scope, dataset=DATASET, src_url=SRC_URL,
                       cards=cards, g=now_hst().strftime("%Y-%m-%d %H:%M HST"))
    open(os.path.join(MAUIOS, out_file), "w", encoding="utf-8", newline="\n").write(html)
    print(f"{out_file}: {len(rows)} seats; top multiplier {rows[0]['voice_x_res']:.0f}x ({rows[0]['name']})" if rows else f"{out_file}: 0 seats")
    for r in rows[:6]:
        print(f"   {r['name']:<26} {r['voice_x_res']:>5.0f}x  top10={r['top10_share']:>3.0f}%  top=${r['top_amt']:>9,.0f} {r['top_name']}")
    return rows

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    # STATE: top candidates across the 4 state offices, pooled then ranked by multiplier
    state_offices = ["Governor", "Lt. Governor", "House", "Senate"]
    state_cands = []
    for off in state_offices:
        state_cands += candidates_for(off, 10)   # top 10 per office by money
    state_rows = [build_row(c) for c in state_cands]
    render("ka_leo_state.html", "Ka Leo o ka 'Aina - State of Hawai'i", "State of Hawai&#699;i",
           "the Governor, Lieutenant Governor, State House and State Senate", state_rows)
    # HONOLULU council
    hono_cands = candidates_for("Honolulu Council", 16)
    hono_rows = [build_row(c) for c in hono_cands]
    render("ka_leo_honolulu.html", "Ka Leo o ka 'Aina - Honolulu", "Honolulu (City &amp; County)",
           "the Honolulu City Council", hono_rows)
    return 0

if __name__ == "__main__":
    sys.exit(main())
