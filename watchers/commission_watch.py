#!/usr/bin/env python3
# commission_watch.py - Kilo Aupuni: real-estate COMMISSION antitrust thread (Thread 2).
#
# HONEST SCOPE (read this):
#   Per-deal commission RATES are NOT public - MLS data is proprietary (RAM/HiCentral),
#   and the County tax roll records sale price, not commission. So this tool does NOT
#   claim actual commissions. It does two legitimate things:
#     1. Timeline of the DOCUMENTED antitrust facts (NAR/Sitzer-Burnett) - verified, cited.
#     2. ESTIMATES the aggregate commission LOAD on Maui = units_sold * median_price *
#        conventional_rate, from PUBLIC annual sales stats you supply in commission_inputs.json
#        (Realtors Assoc. of Maui / DBEDT / Redfin). Clearly labelled an estimate.
#   The antitrust QUESTION it frames: did the ~5-6% convention hold flat across 2008..2024
#   (the hallmark of a non-competitive fixed rate) and only move after the Aug-2024 rule
#   change? That pattern is what DOJ/AG look at - this gives the order-of-magnitude stakes.
#
# To prove an ACTUAL agreement you need MLS commission data (RAM subscription) or discovery;
# to get it lawfully, request it via the Real Estate Commission / DCCA-RICO or in litigation.
#
# Stdlib only. No popups.
import json, os, time
from datetime import datetime, timedelta, timezone

HOME    = os.path.expanduser("~")
TOOL_DIR= os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
IN_F    = os.path.join(TOOL_DIR, "commission_inputs.json")
OUT_F   = os.path.join(MAUIOS, "commission_antitrust.html")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
HST     = timezone(timedelta(hours=-10))

# Verified public facts (per public reporting; see sources in the report footer).
TIMELINE = [
    ("pre-2019", "Industry convention: a ~5-6% total commission, customarily split buyer/seller side, "
                 "advertised on the MLS - the practice later challenged as an unlawful restraint."),
    ("Apr 2019", "Sitzer/Burnett (Burnett v. NAR et al.) filed in W.D. Missouri - homesellers allege the "
                 "NAR/brokerage commission rules are price-fixing under the Sherman Act."),
    ("Oct 31 2023", "Federal jury finds NAR + brokerages liable; awards $1,785,310,872 (~$1.78B), "
                    "automatically trebled toward ~$5.36B."),
    ("Mar 15 2024", "NAR agrees to settle for $418M + sweeping rule changes; brokerage co-defendants "
                    "settle for hundreds of millions more."),
    ("Aug 17 2024", "NAR rule changes take effect: commissions no longer advertised on the MLS; written "
                    "buyer-broker agreements required - the structural fix meant to restore price competition."),
]

def now_hst(): return datetime.now(HST)
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def usd(x):
    try: return f"${float(x):,.0f}"
    except Exception: return "n/a"
def dispatch(tag,msg):
    try:
        with open(DISPATCH,"a",encoding="utf-8") as f:
            f.write(json.dumps({"ts":int(time.time()),"iso":now_hst().strftime("%Y-%m-%d %H:%M:%S"),
                                "source":"kilo-aupuni","event":f"{tag}: {msg}"},ensure_ascii=False)+"\n")
    except Exception: pass

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    cfg = json.load(open(IN_F, encoding="utf-8"))
    rate = cfg.get("conventional_rate", 0.055)
    rows = []
    have_data = False
    for y in cfg.get("years", []):
        units, med = y.get("units"), y.get("median")
        if units and med:
            have_data = True
            r = rate if y["year"] < 2025 else cfg.get("post2024_rate_hypothesis", rate)
            load = units * med * r
            rows.append((y["year"], units, med, r, load, bool(y.get("illustrative"))))
        else:
            rows.append((y["year"], None, None, None, None, False))
    tl = "".join(f'<div class="m"><span class="a">{esc(d)}</span><span class="c">{esc(t)}</span></div>' for d,t in TIMELINE)
    er = ""
    for yr,u,m,r,load,illus in rows:
        if u and m:
            tag = ' <span style="color:#e06a4a">(illustrative — replace)</span>' if illus else ""
            er += (f'<div class="m"><span class="a">{yr}</span><span class="c">{u:,} sales &times; {usd(m)} median '
                   f'&times; {r*100:.1f}% &asymp; <b>{usd(load)}</b> est. commission load{tag}</span></div>')
        else:
            er += f'<div class="m"><span class="a">{yr}</span><span class="c" style="color:#9a957f">awaiting public sales figures (RAM/DBEDT)</span></div>'
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Commission Antitrust Thread - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.55}}
 .wrap{{max-width:900px;margin:0 auto;padding:32px 22px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:25px;margin:8px 0 2px}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(224,106,74,.5);padding:8px 12px;margin:14px 0;background:rgba(224,106,74,.05)}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:5px;margin:24px 0 10px}}
 .m{{display:flex;gap:12px;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:12px;color:#d9b24c;min-width:120px}} .m .c{{font-size:13px;color:#bdb8a4}} .m .c b{{color:#e8e4d8}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · commission antitrust thread</div>
<h1>Real-Estate Commission — Antitrust Thread (2008 →)</h1>
<div class="disc"><b>Honesty first.</b> Per-deal commission rates are NOT public (MLS-proprietary).
This is (1) the documented antitrust timeline and (2) an ESTIMATE of aggregate commission load at the
conventional rate, from public sales volume. It does not assert any Maui broker fixed prices. Proving an
agreement needs MLS data via the Real Estate Commission / DCCA-RICO or litigation discovery. Lobbying
(e.g., Bill 9) is NOT collusion (Noerr-Pennington).</div>
<div class="sect">The documented antitrust record (verified)</div>
{tl}
<div class="sect">Estimated Maui commission load — the stakes (fill from public stats)</div>
{er}
<div class="disc">The antitrust QUESTION: did the ~5-6% convention hold flat 2008→Aug-2024 (hallmark of a
fixed, non-competitive rate) and only move after the rule change? If RAM/MLS data shows rates stuck at
~6% regardless of competition, that is the pattern regulators examine — referable to DOJ Antitrust, the
HI Attorney General (HRS 480), and the Real Estate Commission (HRS 467 / DCCA-RICO).</div>
<footer>generated {g} · commission-watch v1 · timeline per public reporting (NAR/Sitzer-Burnett, Inman/NAR/RISMedia) ·
 load = public sales volume × conventional rate (estimate) · actual rates require MLS · MauiOS</footer>
</div></body></html>"""
    with open(OUT_F, "w", encoding="utf-8") as f:
        f.write(html)
    dispatch("SHIPPED", "commission-watch rebuilt: NAR/Sitzer-Burnett antitrust timeline (verified) + "
             f"estimated Maui commission-load framework ({'live figures' if have_data else 'awaiting public sales inputs'}) "
             "-> reports/mauios/commission_antitrust.html. NOTE: per-deal rates not public; needs MLS via Real Estate Commission/RICO.")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
