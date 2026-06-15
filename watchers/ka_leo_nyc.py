#!/usr/bin/env python3
"""ka_leo_nyc.py — "Ka Leo / The Louder Voice", New York City.
Real NYC Campaign Finance Board data (Socrata rjkp-yttg). That dataset keys contributions by
RECIPIENT and carries NO contributor-name field — so this page makes NO claim about who any
donor is (that's why earlier attempts fabricated; we don't). It measures only what IS in the
record: per recipient, the total, the gift count, the average gift, and the loudest single gift,
expressed as a multiple of an ordinary $50 resident's voice. The true amplifiers surface honestly:
independent-expenditure committees taking six-figure single gifts. Rigor in the numbers, aloha in
the asking. Output: reports/mauios/ka_leo_nyc.html
"""
import os, json, ssl, urllib.request, urllib.parse, html
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
MAUIOS = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS", "reports", "mauios")
OUT = os.path.join(MAUIOS, "ka_leo_nyc.html")
DATASET = "rjkp-yttg"; DOMAIN = "data.cityofnewyork.us"
RESIDENT = 50.0
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)", "Accept": "application/json"}
esc = lambda s: html.escape(str(s or "")); usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(timezone(timedelta(hours=-10)))

def soql(params):
    url = f"https://{DOMAIN}/resource/{DATASET}.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()))

def fetch():
    rows = soql({"$select": "recipname,sum(amnt) as total,count(amnt) as n,max(amnt) as mx",
                 "$where": "amnt > 0 AND amnt < 250000", "$group": "recipname",
                 "$order": "total desc", "$limit": "16"})
    out = []
    for r in rows:
        t = float(r.get("total") or 0); n = int(float(r.get("n") or 0)); mx = float(r.get("mx") or 0)
        if t <= 0 or n <= 0:
            continue
        avg = t / n
        out.append({"name": r.get("recipname"), "total": t, "n": n, "avg": avg, "mx": mx,
                    "voice": mx / RESIDENT, "ie": avg > 5000 or n < 1000})
    return out

def card(r):
    kind = "independent-expenditure committee" if r["ie"] else "candidate campaign"
    sig = ' &mdash; the signature of money routed through a committee, not many neighbors' if r["ie"] else ''
    return f"""<div class="kl-card{' flag' if r['ie'] else ''}">
  <div class="kl-hd"><span class="kl-name">{esc(r['name'])}</span><span class="kl-tot">${usd(r['total'])} &middot; {r['n']:,} gifts &middot; {kind}</span></div>
  <div class="kl-voice"><span class="kl-x">{r['voice']:.0f}&times;</span>
    <span>The loudest single gift here, <b>${usd(r['mx'])}</b>, speaks as loud as about <b>{r['voice']:.0f} residents</b>
    giving $50. The average gift is <b>${usd(r['avg'])}</b>{sig}.</span></div>
  <div class="kl-q"><b>The question (for the record):</b> when a single voice can be heard {r['voice']:.0f}&times; louder than a
    resident&rsquo;s, whose answer does the outcome carry? NYC Campaign Finance Board record; a question, not a finding.</div>
  <div class="kl-aloha">Aloha. Balance does not silence the loud &mdash; it lets the quiet be heard too. New York already
    built one answer: its <b>public-matching program</b> multiplies a small neighbor&rsquo;s gift by up to 8&times;. To lean further
    into that &mdash; to let the people&rsquo;s voice rise to meet the committees&rsquo; &mdash; is paradise momentum, not the inertia of
    the loudest check. The choice is honored.</div>
</div>"""

def build(rows):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ka Leo — The Louder Voice, New York City — Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}}
 .wrap{{max-width:880px;margin:0 auto;padding:34px 24px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:28px;font-weight:600;margin:8px 0 4px}}
 .lead{{font-size:14px;color:#cfc9b6;max-width:76ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:16px 0}}
 .kl-card{{border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:16px 18px;margin:14px 0;background:rgba(255,255,255,.02)}}
 .kl-card.flag{{border-color:rgba(224,106,74,.4)}}
 .kl-hd{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}}
 .kl-name{{font-size:17px;font-weight:600}} .kl-tot{{font-family:Consolas,monospace;font-size:12px;color:#9a957f}}
 .kl-voice{{display:flex;gap:14px;align-items:baseline;margin:11px 0;font-size:13.5px;color:#cfc9b6}}
 .kl-x{{font-family:Consolas,monospace;font-size:30px;font-weight:700;color:#e06a4a;line-height:1;flex-shrink:0}}
 .kl-q{{font-size:12.5px;color:#bdb8a4;background:rgba(217,178,76,.05);border-radius:8px;padding:9px 12px;margin:9px 0}}
 .kl-aloha{{font-size:13px;color:#9fd9bf;border-left:3px solid #2a6b4e;padding:8px 13px;margin-top:9px;line-height:1.65}}
 .kl-aloha b{{color:#c8efd9}} a{{color:#d9b24c}}
 footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York City &middot; aloha &middot; pono</div>
<h1>Ka Leo &mdash; The Louder Voice, New York City</h1>
<p class="lead">How much louder money makes some voices in NYC elections, from the public Campaign Finance Board
record. Candidate campaigns run on many small gifts near the legal limit; the truly amplified voices are the
<b>independent-expenditure committees</b> taking six-figure single gifts. Rigor in the numbers, aloha in the asking.</p>
<div class="disc">Source: NYC Campaign Finance Board &ldquo;Campaign Contributions&rdquo; (NYC Open Data, dataset rjkp-yttg).
This dataset keys gifts by <b>recipient</b> and carries <b>no contributor-name field</b> &mdash; so this page names
<b>no donor</b> and makes no claim about who gave; it measures only the sizes that are in the record (self-funding /
transfers of $250k+ excluded). A loud single gift is lawful; this maps how loud, as a question.</div>
{''.join(card(r) for r in rows)}
<p style="margin-top:20px"><a href="money_nyc.html">who funds NYC officials</a>
&middot; <a href="parity_nyc.html">contract winners who also give</a>
&middot; <a href="jurisdictions.html">all govOS jurisdictions</a></p>
<footer>generated {g} &middot; ka-leo-nyc v1 &middot; source: NYC Campaign Finance Board (rjkp-yttg, public record) &middot; Kilo Aupuni &middot; aloha &middot; pono</footer>
</div></body></html>"""

def main():
    rows = fetch()
    open(OUT, "w", encoding="utf-8", newline="\n").write(build(rows))
    print(f"ka-leo-nyc: {len(rows)} recipients; loudest voice {rows[0]['voice']:.0f}x" if rows else "no rows")
    for r in rows[:6]:
        print(f"   {r['name'][:30]:<30} loudest ${r['mx']:>8,.0f} = {r['voice']:.0f}x  avg ${r['avg']:,.0f}  ({'IE cmte' if r['ie'] else 'candidate'})")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
