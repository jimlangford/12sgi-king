#!/usr/bin/env python3
"""ka_leo.py — "Ka Leo o ka ʻĀina / The Louder Voice".
The dual page James asked for: prosecutorial RIGOR in the data (how monetary donations buy an
amplified voice — concentration + a voice-multiplier vs an ordinary resident), and ALOHA in the
framing (each broken pair invited back to Pono — paradise momentum, not karmic inertia).
100% public campaign-finance records (Hawaii CSC via donor_profiles.json). Every correlation a
QUESTION, never an accusation; an invitation to balance, never a charge. Output: reports/mauios/ka_leo_voice.html
"""
import os, json, re
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
DP = os.path.join(MAUIOS, "donor_profiles.json")
PARITY = os.path.join(MAUIOS, "parity_check.json")
OUT = os.path.join(MAUIOS, "ka_leo_voice.html")
HST = timezone(timedelta(hours=-10))
RESIDENT = 50.0   # a stated illustrative small-donor baseline (not a claim about the median)
esc = lambda s: str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)

def surname(s):
    return re.sub(r"[^a-z]", "", (s or "").split(",")[0].lower())

def compute():
    dp = json.load(open(DP, encoding="utf-8"))
    # officials named in a broken parity pair (to mark the seats the ledger already flags)
    flagged = set()
    try:
        pj = json.load(open(PARITY, encoding="utf-8"))
        for p in pj.get("hewa", {}).get("pairs", []):
            for o in p.get("officials", []):
                flagged.add(o.lower())
    except Exception:
        pass
    rows = []
    for o in dp:
        key = o.get("key") or "?"
        total = o.get("total") or 0
        n = o.get("rows") or 0
        td = sorted(o.get("top_donors") or [], key=lambda d: -(d.get("amount") or 0))
        avg = (total / n) if n else 0
        # largest OUTSIDE (non-self/family) donor — the interested-party voice
        self_amt = sum(d.get("amount", 0) for d in td if surname(d.get("name")) == surname(key))
        outside = [d for d in td if surname(d.get("name")) != surname(key)]
        top = outside[0] if outside else (td[0] if td else {})
        top10 = sum(d.get("amount", 0) for d in td[:10])
        rows.append({
            "key": key, "total": total, "n": n, "avg": avg,
            "top_name": top.get("name"), "top_amt": top.get("amount", 0),
            "top_emp": top.get("employer"), "top_occ": top.get("occupation"),
            "voice_x_avg": (top.get("amount", 0) / avg) if avg else 0,
            "voice_x_res": (top.get("amount", 0) / RESIDENT),
            "top10_share": (top10 / total * 100) if total else 0,
            "self_amt": self_amt,
            "flagged": key.lower() in flagged,
        })
    rows.sort(key=lambda r: -r["voice_x_res"])
    return rows

def card(r):
    pair = ('<div class="kl-pair">The ledger already flags a pair on this seat &mdash; '
            '<a href="parity_check.html">see where it no longer answers</a>.</div>') if r["flagged"] else ""
    self_line = (f'<div class="kl-sub">Of the rest, ${usd(r["self_amt"])} is the candidate’s own / family funds &mdash; '
                 f'set aside here so the question is about <i>outside</i> money.</div>') if r["self_amt"] else ""
    donor = esc(r["top_name"] or "a single donor")
    emp = f' <span class="kl-emp">&middot; {esc(r["top_emp"])}</span>' if r.get("top_emp") else ""
    return f"""<div class="kl-card{' flag' if r['flagged'] else ''}">
  <div class="kl-hd"><span class="kl-name">{esc(r['key'])}</span><span class="kl-tot">${usd(r['total'])} raised &middot; {r['n']:,} gifts</span></div>
  <div class="kl-voice"><span class="kl-x">{r['voice_x_res']:.0f}&times;</span>
    <span>One gift &mdash; <b>${usd(r['top_amt'])}</b> from {donor}{emp} &mdash; speaks as loud as about
    <b>{r['voice_x_res']:.0f} residents</b> each giving $50, and {r['voice_x_avg']:.0f}&times; the average gift here.
    The top ten donors are <b>{r['top10_share']:.0f}%</b> of every dollar raised.</span></div>
  {self_line}{pair}
  <div class="kl-q"><b>The question (for the record):</b> when one voice is heard {r['voice_x_res']:.0f}&times; louder than a
    resident&rsquo;s, whose answer does the vote carry &mdash; the people&rsquo;s, or the funder&rsquo;s? Public campaign-finance record; a question, not a finding.</div>
  <div class="kl-aloha">E <b>{esc(r['key'])}</b>, aloha. The Kumulipo remembers what each thing is paired to. To let a
    resident&rsquo;s voice be heard as clearly as the largest donor&rsquo;s is to return this pair to <b>pono</b> &mdash; paradise
    momentum, not the inertia of the same money and the same vote. The <b>&#699;&#257;ina</b> is sacred and it is watching with aloha;
    the choice to balance it is yours, and it is honored.</div>
</div>"""

def build(rows):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    cards = "".join(card(r) for r in rows)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ka Leo o ka ʻĀina — The Louder Voice — Kilo Aupuni</title>
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
 .kl-card.flag{{border-color:rgba(224,106,74,.4)}}
 .kl-hd{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}}
 .kl-name{{font-size:17px;font-weight:600}} .kl-tot{{font-family:Consolas,monospace;font-size:12px;color:#9a957f}}
 .kl-voice{{display:flex;gap:14px;align-items:baseline;margin:11px 0;font-size:13.5px;color:#cfc9b6}}
 .kl-x{{font-family:Consolas,monospace;font-size:30px;font-weight:700;color:#e06a4a;line-height:1;flex-shrink:0}}
 .kl-sub{{font-size:12px;color:#9a957f;margin:4px 0}} .kl-emp{{color:#9a957f}}
 .kl-pair{{font-size:12.5px;color:#e0863a;margin:6px 0}} .kl-pair a{{color:#e0863a}}
 .kl-q{{font-size:12.5px;color:#bdb8a4;background:rgba(217,178,76,.05);border-radius:8px;padding:9px 12px;margin:9px 0}}
 .kl-aloha{{font-size:13px;color:#9fd9bf;border-left:3px solid #2a6b4e;padding:8px 13px;margin-top:9px;line-height:1.65}}
 .kl-aloha b{{color:#c8efd9}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; aloha &middot; pono</div>
<h1>Ka Leo o ka &#699;&#256;ina &mdash; The Louder Voice</h1>
<p class="lead">In a democracy every resident has one voice. Money can make some voices far louder. This page measures,
from the public campaign record, <b>how much louder</b> &mdash; not to accuse anyone, but to invite each seat to
return its pair to balance. Rigor in the numbers; aloha in the asking.</p>
<div class="phil">
 <div><b>Underneath &mdash; the record stands up.</b> Every figure is real public campaign-finance data (Hawai&#699;i Campaign
   Spending Commission), reproducible, and built to withstand the hardest look. This is the evidence an auditor would hold.</div>
 <div><b>On the surface &mdash; aloha.</b> The same record is offered as an invitation: the Kumulipo binds each thing to its
   pair; a seat out of balance (hewa) can be made pono again. We name the pattern, never the person&rsquo;s guilt.</div>
</div>
<div class="disc">Source: Hawai&#699;i Campaign Spending Commission contributions (public record), per tracked Maui official.
&ldquo;Louder voice&rdquo; = the largest <i>outside</i> gift measured against an ordinary resident&rsquo;s $50 contribution and against the
average gift to that official. Giving and receiving lawful contributions is legal; this maps how loud each voice is, as a question.</div>
{cards}
<p style="margin-top:20px"><a href="parity_check.html">the pairs that no longer answer</a>
&middot; <a href="lobby_money_watch.html">who lobbies &amp; pays</a>
&middot; <a href="take_action.html">&#9878; demand the records</a></p>
<footer>generated {g} &middot; ka-leo v1 &middot; source: HI Campaign Spending Commission (public record) &middot; Kilo Aupuni &middot; aloha &middot; pono &middot; govOS</footer>
</div></body></html>"""

def main():
    rows = compute()
    open(OUT, "w", encoding="utf-8", newline="\n").write(build(rows))
    print(f"ka-leo: {len(rows)} officials; top voice-multiplier {rows[0]['voice_x_res']:.0f}x ({rows[0]['key']}) -> ka_leo_voice.html")
    for r in rows[:5]:
        print(f"   {r['key']:<22} {r['voice_x_res']:.0f}x  top10={r['top10_share']:.0f}%  top=${r['top_amt']:,.0f} {r['top_name']}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
