#!/usr/bin/env python3
"""vatican_finances.py — "Follow the Money: the Holy See" — govOS money dashboard for the apex tenant.

Every figure is from a NAMED public Holy See financial report (2024 fiscal year, published 2025) or a
court of record. No figure is invented; each carries its source and year. Same Kilo Aupuni rule as the
rest of the system: name the pattern and the document, frame accountability as a QUESTION, never an
accusation. Output: reports/mauios/money_holysee.html
"""
import os, html
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
OUT     = os.path.join(MAUIOS, "money_holysee.html")
HST     = timezone(timedelta(hours=-10))
esc     = lambda s: html.escape(str(s or ""))
def now_hst(): return datetime.now(HST)

# ── verified 2024 figures (FY2024, published 2025). (value, sub, source) ─────────────────────
HEADLINE = [
    ("&euro;1.6M", "consolidated SURPLUS, FY2024", "a turnaround from a &euro;51.2M deficit in 2023",
     "Holy See Consolidated Financial Statement 2024 (Secretariat for the Economy, pub. Nov 2025)"),
    ("&euro;62.2M", "APSA net profit, FY2024", "&euro;46.1M of it contributed to cover the Holy See's deficit",
     "APSA Financial Statement 2024 (pub. Jul 2025)"),
    ("&euro;32.8M", "IOR (Vatican Bank) net profit", "+7% over 2023; client assets &euro;5.7B, net assets &euro;731.9M",
     "IOR Annual Report 2024 (pub. Jun 2025)"),
    ("&euro;58M / &euro;75.4M", "Peter's Pence: in / out", "a ~&euro;17M (≈$20.4M) shortfall — gifts plus reserves cover papal works",
     "Peter's Pence FY2024 figures (pub. 2025)"),
]

# the financial-governance bodies Pope Francis built/reformed (2014 onward)
BODIES = [
    ("Council for the Economy", "2014", "15 members (8 cardinals/bishops + 7 lay experts) — sets economic policy & oversight for all Holy See and Vatican City State entities."),
    ("Secretariat for the Economy", "2014", "The finance ministry of the Curia — prepares the budget and publishes the annual Consolidated Financial Statement (transparency)."),
    ("Office of the Auditor General", "2014", "Independent audit of the Holy See's entities and consolidated accounts."),
    ("APSA", "reformed", "Administration of the Patrimony of the Apostolic See — manages real estate, investments, and the patrimony; reports net results yearly."),
    ("IOR", "reformed", "Institute for the Works of Religion (the 'Vatican Bank') — deposits/asset management; publishes an annual report since 2013."),
    ("ASIF", "renamed 2020", "Supervisory and Financial Information Authority — anti-money-laundering supervision and financial intelligence (formerly AIF)."),
]

# the accountability thread — a matter of public court record, framed as a question
THREAD = {
    "title": "The London-property case — the test of the reforms",
    "facts": [
        "In Dec. 2023 the Vatican City State criminal tribunal convicted a cardinal of embezzlement and aggravated fraud (5½-year sentence) over a speculative London real-estate deal (60 Sloane Avenue). It was the first time a cardinal was tried by the Vatican's criminal court. (An appeal is ongoing; a partial mistrial was declared in 2025.)",
        "The same period saw Peter's Pence disclosures clarify that much of the collection has long gone to the Curia's operating budget rather than only to charity — which is why the reformed Secretariat for the Economy now publishes the consolidated statement at all.",
    ],
    "question": "When the body that decides how the patrimony is invested is also the body that audits the result, what keeps the two honest? The reforms (Council, Secretariat, Auditor General, ASIF) are the Holy See's own answer — the open question is whether disclosure now reaches the faithful the way Canon Law c. 1287 §2 already requires.",
}

def card(v, sub, extra, src):
    return """<div class="hc">
  <div class="hv">%s</div><div class="hs">%s</div><div class="he">%s</div>
  <div class="src">source: %s</div></div>""" % (v, esc(sub), esc(extra), esc(src))

def body_row(name, tag, desc):
    return '<div class="br"><div class="bn">%s <span class="bt">%s</span></div><div class="bd">%s</div></div>' % (esc(name), esc(tag), esc(desc))

def build():
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    cards = "".join(card(*h) for h in HEADLINE)
    bodies = "".join(body_row(*b) for b in BODIES)
    facts = "".join("<li>%s</li>" % esc(f) for f in THREAD["facts"])
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Follow the Money — Holy See — govOS · Kilo Aupuni</title>
<style>
 body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}
 .wrap{max-width:1000px;margin:0 auto;padding:30px 22px 70px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:28px;font-weight:600;margin:8px 0 4px} h2{font-size:18px;margin:28px 0 6px;color:#f0ead8}
 .lead{font-size:14px;color:#cfc9b6;max-width:78ch}
 .disc{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}
 .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:11px;margin:14px 0}
 .hc{border:1px solid rgba(255,255,255,.1);border-radius:13px;padding:14px 16px;background:rgba(255,255,255,.02)}
 .hv{font-family:Consolas,monospace;font-size:25px;font-weight:700;color:#d9b24c;line-height:1.1}
 .hs{font-size:13px;color:#e8e4d8;font-weight:600;margin-top:5px} .he{font-size:12px;color:#bdb8a4;margin-top:3px}
 .src{font-family:Consolas,monospace;font-size:9.5px;color:#7f8a82;margin-top:8px}
 .br{border-left:2px solid rgba(159,217,191,.4);padding:6px 12px;margin:8px 0}
 .bn{font-size:13.5px;font-weight:600;color:#e8e4d8} .bt{font-family:Consolas,monospace;font-size:10px;color:#9fd9bf;margin-left:6px}
 .bd{font-size:12.5px;color:#bdb8a4}
 .thread{border:1px solid rgba(224,106,74,.35);border-radius:13px;padding:15px 18px;margin:14px 0;background:rgba(224,106,74,.05)}
 .thread ul{margin:8px 0;padding-left:18px;font-size:13px;color:#cfc9b6} .thread li{margin:6px 0}
 .q{font-size:13px;color:#bdb8a4;background:rgba(217,178,76,.06);border-radius:8px;padding:10px 13px;margin-top:10px}
 .aloha{font-size:13px;color:#9fd9bf;border-left:3px solid #2a6b4e;padding:9px 13px;margin:18px 0;line-height:1.65} .aloha b{color:#c8efd9}
 a{color:#d9b24c}
 footer{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; Holy See / Vatican City State &middot; aloha &middot; pono</div>
<h1>Follow the Money &mdash; the Holy See</h1>
<p class="lead">The apex tenant, on its own public record. Since Pope Francis&rsquo;s 2014 reforms the Holy See
publishes audited accounts &mdash; so the same transparency the rest of govOS asks of every county can be
asked here too. Every figure below names its source report and year. A map, framed as questions &mdash; never an accusation.</p>
<div class="disc">Sources: Holy See Consolidated Financial Statement (Secretariat for the Economy), APSA
Financial Statement, IOR Annual Report, Peter&rsquo;s Pence figures &mdash; all FY2024, published 2025 &mdash;
and the Vatican City State tribunal&rsquo;s public verdict. Figures are as reported; euro/dollar conversions move with the rate.</div>

<h2>FY2024 — the headline numbers</h2>
<div class="cards">%s</div>

<h2>Who governs the money — the reform architecture</h2>
<p class="lead">Pope Francis created three new control bodies in 2014 and reformed the older ones, so that
policy, execution, and audit are no longer the same hand.</p>
<div>%s</div>

<h2>%s</h2>
<div class="thread"><ul>%s</ul>
  <div class="q"><b>The question (for the record):</b> %s</div></div>

<div class="aloha">Aloha. To put the patrimony in the light is not an accusation &mdash; it is the same care the
<b>&#699;āina</b> asks of every steward. Canon Law already commands a public accounting to the faithful;
govOS simply holds the door open. The invitation is paradise momentum: let the disclosure meet the people.</div>

<p style="margin-top:8px"><a href="crosswalk_holysee.html">Holy See &mdash; Charter &#8644; Canon Law crosswalk</a>
&middot; <a href="jurisdictions.html">all govOS jurisdictions</a>
&middot; <a href="parity_check.html">parity — pairs that no longer answer</a></p>
<footer>generated %s &middot; vatican-finances v1 &middot; FY2024 figures from named Holy See reports (pub. 2025) &middot; Kilo Aupuni &middot; aloha &middot; pono</footer>
</div></body></html>""" % (cards, bodies, esc(THREAD["title"]), facts, esc(THREAD["question"]), g)

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    open(OUT, "w", encoding="utf-8", newline="\n").write(build())
    print("money_holysee.html: %d headline figures, %d governance bodies (all sourced)" % (len(HEADLINE), len(BODIES)))
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
