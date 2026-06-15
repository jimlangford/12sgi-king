#!/usr/bin/env python3
"""testimony_money.py — "Follow the Money by Testimony".

Who is paid to influence the Council, and do they also fund the deciders? This is the verbal-
testimony / advocacy layer of the money×votes picture, built on FULLY PUBLIC, machine-readable
records:

  - PROFESSIONAL TESTIMONY = registered lobbyists (Hawaiʻi State Ethics Commission registry,
    opendata.hawaii.gov), already cross-referenced by lobby_money_watch.py to campaign donations.
    For each org that lobbies AND donates: its lobbyists (the people who advocate to Council), the
    officials it funded, and whether the same name ALSO won County contracts (lobby + donate +
    contract = the tightest "follow the money" chain).
  - CITIZEN TESTIMONY CHANNEL = links to the live agendas + the County's eComment portal so the
    public can see what's being decided and testify.

HONEST DATA NOTE (verified 2026-06-15): Maui does NOT publish individual citizen testifier names in
any machine-readable form — not in Legistar, not in the minutes PDFs (which record votes, not
testifier rolls), and eComment/SpeakUp is submission-oriented (positions + counts, no public named
roster). So a per-citizen "this testifier gave $X" link is NOT built — that would require fabricating
names. The professional-lobbyist→money link IS shown because it is genuinely public. Every connection
is a PUBLIC-RECORD QUESTION for further reporting, never an accusation.

Stdlib only. Output: reports/mauios/testimony_money.html
"""
import os, json, re, html
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
LOBBY   = os.path.join(MAUIOS, "lobby_money_watch.json")
VDJ     = os.path.join(MAUIOS, "vendor_donor_join.json")
OUT     = os.path.join(MAUIOS, "testimony_money.html")
HST     = timezone(timedelta(hours=-10))
esc     = lambda s: html.escape(str(s or ""))
def now_hst(): return datetime.now(HST)

GENERIC = {"the","inc","llc","ltd","co","company","corp","corporation","of","and","hawaii","hawaiʻi",
           "maui","county","group","associates","association","assn","services","service","dba","lp","llp"}
def toks(name):
    return {w for w in re.split(r"[^a-z0-9ʻ]+", (name or "").lower()) if w and w not in GENERIC and len(w) > 2}

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def vendor_set():
    d = load(VDJ, {})
    out = []
    for m in (d.get("matched") or d.get("matches") or []):
        v = m.get("vendor")
        if v: out.append((v, toks(v)))
    return out

def also_contractor(org, vendors):
    ot = toks(org)
    if not ot: return None
    for v, vt in vendors:
        if len(ot & vt) >= 1 and (ot & vt):   # share a distinctive token
            return v
    return None

def chain_card(e, vendors):
    org = e.get("org", "")
    lobbyists = e.get("lobbyists") or []
    dons = e.get("donations") or []
    years = e.get("lobby_years") or []
    contractor = also_contractor(org, vendors)
    adv = ", ".join(esc(l) for l in lobbyists[:8]) or "(lobbyist names on file)"
    don_html = "".join(
        '<li><b>%s</b>%s%s</li>' % (
            esc(d.get("official", "").split(" -")[0]),
            (" &mdash; as " + esc(d.get("donor"))) if d.get("donor") and d.get("donor") != org else "",
            (" &middot; $%s" % esc("{:,.0f}".format(d["amount"])) if isinstance(d.get("amount"), (int, float)) and d.get("amount") else ""))
        for d in dons[:12]) or "<li>(donation detail on file)</li>"
    triple = ('<div class="triple">&#9888; Also appears among County <b>contract winners</b> (%s) &mdash; '
              'lobby + donate + contract. A question for the record: does the work answer the money?</div>' % esc(contractor)) if contractor else ""
    return """<div class="chain">
  <div class="ch-org">%s%s</div>
  <div class="ch-row"><span class="lab">advocates to Council</span> %s</div>
  <div class="ch-row"><span class="lab">funded these deciders</span><ul>%s</ul></div>
  %s
  <div class="ch-q">The question (public record): an organization that pays advocates to shape a vote
  <b>and</b> funds the members who cast it &mdash; whose voice does the outcome answer?</div>
</div>""" % (esc(org), (' <span class="yrs">lobbied %s</span>' % esc(", ".join(years[:3]))) if years else "",
             adv, don_html, triple)

def build():
    d = load(LOBBY, {})
    chains = d.get("lobby_and_donate") or []
    vendors = vendor_set()
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    triples = sum(1 for e in chains if also_contractor(e.get("org", ""), vendors))
    body = "".join(chain_card(e, vendors) for e in chains) or '<div class="none">No lobby×donation overlap parsed this run — see lobby_money_watch for the registry scan.</div>'
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Follow the Money by Testimony — govOS · Kilo Aupuni</title>
<style>
 body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}
 .wrap{max-width:980px;margin:0 auto;padding:30px 22px 70px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:27px;font-weight:600;margin:8px 0 4px} h2{font-size:17px;margin:24px 0 6px;color:#f0ead8}
 .lead{font-size:14px;color:#cfc9b6;max-width:80ch}
 .kpis{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}
 .kpi{border:1px solid rgba(255,255,255,.1);border-radius:11px;padding:10px 14px;background:rgba(255,255,255,.02)}
 .kpv{font-family:Consolas,monospace;font-size:22px;font-weight:700;color:#d9b24c} .kpl{font-size:11px;color:#9a957f}
 .chain{border:1px solid rgba(255,255,255,.1);border-radius:13px;padding:14px 16px;margin:11px 0;background:rgba(255,255,255,.02)}
 .ch-org{font-size:16px;font-weight:600;color:#f0ead8} .yrs{font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
 .ch-row{font-size:13px;color:#cfc9b6;margin:6px 0} .lab{font-family:Consolas,monospace;font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#9fd9bf;display:block;margin-bottom:2px}
 .ch-row ul{margin:3px 0;padding-left:18px} .ch-row li{font-size:13px}
 .triple{font-size:12.5px;color:#e9b48a;background:rgba(224,106,74,.08);border:1px solid rgba(224,106,74,.3);border-radius:8px;padding:8px 11px;margin:8px 0}
 .ch-q{font-size:12.5px;color:#bdb8a4;background:rgba(217,178,76,.05);border-radius:8px;padding:9px 12px;margin-top:8px}
 .citizen{border:1px solid rgba(159,217,191,.3);border-radius:13px;padding:14px 16px;margin:16px 0;background:rgba(159,217,191,.04)}
 .citizen a{color:#9fd9bf}
 .disc{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}
 .none{font-size:13px;color:#9a957f;font-style:italic} a{color:#d9b24c}
 footer{margin-top:30px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; Maui County &middot; aloha &middot; pono</div>
<h1>Follow the Money by Testimony</h1>
<p class="lead">Some voices at the Council are paid to be there. This traces the <b>professional advocacy</b> layer
on fully public record: organizations that register <b>lobbyists</b> to influence Maui County <b>and</b> donate to
the officials who decide &mdash; and, where the same name appears, also win County <b>contracts</b>. Lawful activity,
documented as a question &mdash; never an accusation.</p>
<div class="kpis">
 <div class="kpi"><div class="kpv">%d</div><div class="kpl">orgs: lobby + donate</div></div>
 <div class="kpi"><div class="kpv">%d</div><div class="kpl">also contract winners</div></div>
 <div class="kpi"><div class="kpv">%s</div><div class="kpl">registry filings scanned</div></div></div>
<h2>The chains — paid advocacy that also funds the deciders</h2>
%s
<div class="citizen"><b>Your voice counts too.</b> The other testimony is the people's. See what's on the
agenda and testify before the vote &mdash; <a href="agendas_maui.html">upcoming Maui agendas</a> &middot;
<a href="https://mauicounty.granicusideas.com/meetings" target="_blank" rel="noopener">eComment (submit testimony) &#8599;</a> &middot;
<a href="testify.html">testify through govOS</a>.</div>
<div class="disc">This page is the <b>professional advocacy</b> layer (registered lobbyists &times; campaign finance &times; contracts).
The <b>named citizen testimony</b> record &mdash; who testified and what they urged &mdash; is parsed separately from the
Maui County committee transcripts on <a href="testimony_record.html">Who Testified</a>, where any testifier or org that
also appears in a public donation/contract/lobby record is flagged as a question. All public record; correlations are
questions for further reporting, never accusations.</div>
<p style="margin-top:10px"><a href="lobby_money_watch.html">lobby + money (full registry scan)</a> &middot;
<a href="money_behind_officials.html">money behind officials</a> &middot;
<a href="contracts_x_donors.html">contracts &times; donors</a> &middot;
<a href="n53_engine.html">N53 — the votes side</a></p>
<footer>generated %s &middot; testimony-money v1 &middot; source: HSEC lobbyist registry (opendata.hawaii.gov) &times; donor profiles &times; HANDS awards &middot; public record &middot; Kilo Aupuni &middot; aloha &middot; pono</footer>
</div></body></html>""" % (len(chains), triples,
        "{:,}".format(d.get("filings_scanned", 0)) if d.get("filings_scanned") else "—", body, g)

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    open(OUT, "w", encoding="utf-8", newline="\n").write(build())
    d = load(LOBBY, {}); n = len(d.get("lobby_and_donate") or [])
    print("testimony-money: %d lobby+donate chains rendered" % n)
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
