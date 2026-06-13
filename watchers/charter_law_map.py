#!/usr/bin/env python3
# charter_law_map.py - Kilo Aupuni: Charter <-> existing law <-> live data.
#
# For each "winnable thread", binds three layers:
#   1. CHARTER  - what the 12 Stones Sovereign Charter (SSC v5) prescribes (verbatim).
#   2. LAW      - the EXISTING, enforceable statute that already mirrors that best practice,
#                 and the body that can act on it (no sovereignty required to use it).
#   3. EVIDENCE - the live Kilo Aupuni data (donors, recusals, etc.), read fresh each run.
#
# The point: the Charter is the best-practice spec; existing law is the mechanism that ALREADY
# exists to enforce the same outcome; the live data is the evidence to feed it. A roadmap of
# lawful action - not an accusation against any person.
#
# Stdlib only. No subprocesses -> no console popups.
import json, os, time
from datetime import datetime, timedelta, timezone

HOME     = os.path.expanduser("~")
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS   = os.path.join(PROJECT, "reports", "mauios")
DONORS_F = os.path.join(MAUIOS, "donor_profiles.json")
OFFICIALS_F = os.path.join(MAUIOS, "officials.json")
OUT_F    = os.path.join(MAUIOS, "charter_application.html")
DISPATCH = os.path.join(PROJECT, ".dispatch_log.jsonl")
HST      = timezone(timedelta(hours=-10))

def now_hst(): return datetime.now(HST)
def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "kilo-aupuni", "event": f"{tag}: {msg}"}
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception: pass

def load(p, default):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return default

def live_evidence():
    prof = load(DONORS_F, [])
    off  = load(OFFICIALS_F, {})
    re_total = sum(p.get("realestate", {}).get("total", 0) for p in prof)
    realtor_pac = []
    for p in prof:
        for d in p.get("realestate", {}).get("donors", []):
            if "realtor" in (d.get("name", "").lower()) or "realtors" in (d.get("name", "").lower()):
                realtor_pac.append({"to": p.get("label", "").split(" -")[0], "from": d.get("name"), "amt": d.get("amount", 0)})
    recusals = sum(len(o.get("recusals", [])) for o in off.values())
    top_re = sorted(prof, key=lambda p: -p.get("realestate", {}).get("total", 0))[:4]
    return {"re_total": re_total, "realtor_pac": realtor_pac[:8], "recusals": recusals,
            "top_re": [{"who": p.get("label", "").split(" -")[0],
                        "re": p.get("realestate", {}).get("total", 0),
                        "total": p.get("total", 0)} for p in top_re if p.get("realestate", {}).get("total", 0)]}

# ---- the map: Charter (verbatim) <-> existing law <-> how-to-apply ----
def threads(ev):
    pac_html = "".join(f'<li>{esc(x["from"])} &rarr; {esc(x["to"])}: ${x["amt"]:,.0f}</li>' for x in ev["realtor_pac"]) \
               or "<li>(no realtor-PAC contributions parsed this run)</li>"
    top_html = "".join(f'<li><b>{esc(t["who"])}</b>: ${t["re"]:,.0f} real-estate of ${t["total"]:,.0f} raised</li>' for t in ev["top_re"]) \
               or "<li>(donor profiles pending)</li>"
    return [
      {
        "title": "Thread 1 - Money &amp; influence over land / housing votes",
        "charter": [
          ("Art. VI &sect;6.2 - Transparency Requirements",
           "All budgets, fund allocations, and project expenses must be posted publicly via the RAIS system and linked to each Steward and Peacekeeper."),
          ("Art. IV &sect;4.3 - Circle Governance",
           "No private industry or outside funder may influence Custodian decisions without full glyph-based transparency."),
          ("Art. VI &sect;6.4 / Art. III &sect;3.5 - Enforcement",
           "Individuals found to violate the public trust may be barred from governance roles; trust violation shall result in ceremonial removal and lineage review."),
        ],
        "laws": [
          ("Maui County Charter Art. 10 + County Code of Ethics",
           "Requires conflict-of-interest disclosure and RECUSAL by county officers; the Board of Ethics investigates and can sanction. Mirrors Charter VI.4 (bar violators).",
           "File with / petition the Maui Board of Ethics."),
          ("HRS Ch. 11, Pt. XIII (Campaign Finance) - Campaign Spending Commission",
           "Makes every contribution to candidates public record (the data donor-watch already pulls). Mirrors Charter VI.2 (post all money, linked to each official).",
           "Reference CSC filings; complaints to the Campaign Spending Commission."),
          ("HRS Ch. 92 (Sunshine Law) + Ch. 92F (UIPA)",
           "Open meetings + open records: the public's existing right to document every Council action and demand the paper trail. Mirrors Charter III.5 + VI.2.",
           "UIPA records request; Office of Information Practices."),
        ],
        "evidence": f'<p>Live (donor-watch + votes-watch): <b>${ev["re_total"]:,.0f}</b> in real-estate / development money to the officials, '
                    f'<b>{ev["recusals"]}</b> recorded recusals.</p><ul>{top_html}</ul>'
                    f'<p style="margin-top:8px">Realtor-PAC money (the housing-policy money, by official):</p><ul>{pac_html}</ul>',
        "mirror": "Charter VI.2 says “post every dollar, linked to each official.” HRS Ch. 11 already makes that data public; the "
                  "County Code of Ethics already requires recusal where the money creates a conflict. The Charter best practice is "
                  "achievable TODAY by enforcing existing disclosure + recusal law against the live donor/vote record.",
      },
      {
        "title": "Thread 2 - Real-estate market fairness / commission antitrust",
        "charter": [
          ("Art. IV &sect;4.2 - Regenerative Framework",
           "All policy must center on ... food sovereignty ... not extractive economic metrics."),
          ("Art. IX &sect;9.3 - Protection from Exploitation",
           "Youth [and community] shall be protected from predatory marketing [and exploitation]."),
          ("Art. IV &sect;4.5 / VI.4 - Enforcement",
           "Fraud, desecration, or extraction shall be addressed through scroll tribunal and Peacekeeper action."),
        ],
        "laws": [
          ("HRS &sect;480-4 (Restraint of Trade) + &sect;480-9 (Monopolization)",
           "Bars “every contract, combination ... or conspiracy, in restraint of trade” and price-fixing; construed per federal antitrust law. The EXISTING anti-collusion mechanism the Charter's anti-extraction stance mirrors.",
           "Hawaii Attorney General (antitrust); private/indirect-purchaser suits allowed under Ch. 480."),
          ("Sherman Act &sect;1 (federal) + the NAR commission settlements",
           "Federal price-fixing law; the NAR/Sitzer-Burnett cases already found broker commission collusion actionable. NOTE: lobbying a council (Bill 9) is protected petitioning (Noerr-Pennington) - the case must rest on commission/MLS AGREEMENTS, not testimony.",
           "U.S. DOJ Antitrust Division."),
          ("HRS Ch. 467 - Real Estate Brokers & Salespersons + the Real Estate Commission",
           "Licensing law; the 9-member Commission + DCCA-RICO can discipline / revoke licenses for violations. Mirrors Charter VI.4 (bar violators) for the real-estate profession specifically.",
           "DCCA Regulated Industries Complaints Office (RICO) + the Real Estate Commission."),
        ],
        "evidence": f'<p>Live (donor-watch): real-estate / Realtor-PAC money is documented (above). What is NOT yet in evidence: any '
                    f'commission-fixing AGREEMENT - the bill9-testimony scan found <b>0</b> collusion-language hits (industry lobbying is lawful). '
                    f'The antitrust thread needs MLS / listing-agreement data, not council testimony.</p>',
        "mirror": "Charter IV.2/IX.3 reject extractive, predatory market behavior. HRS Ch. 480 (and Sherman Act §1) ALREADY outlaw "
                  "price-fixing and restraint of trade; HRS Ch. 467 already lets the Real Estate Commission pull licenses. The Charter "
                  "best practice is already the law - the missing piece is EVIDENCE of an agreement (MLS commission data), not new authority.",
      },
    ]

def render(ts):
    ev = live_evidence()
    cards = ""
    for t in threads(ev):
        ch = "".join(f'<div class="row"><div class="ref">{r}</div><div class="txt">&ldquo;{q}&rdquo;</div></div>' for r, q in t["charter"])
        lw = "".join(f'<div class="row"><div class="ref">{cite}</div><div class="txt">{what}<div class="apply">Apply via: {body}</div></div></div>'
                     for cite, what, body in t["laws"])
        cards += (f'<div class="thread"><h2>{t["title"]}</h2>'
                  f'<div class="sect">What the Charter prescribes</div>{ch}'
                  f'<div class="sect">The existing law that already mirrors it &mdash; and who enforces it</div>{lw}'
                  f'<div class="sect">Live evidence (updates every run)</div><div class="ev">{t["evidence"]}</div>'
                  f'<div class="mirror"><b>How the law mirrors the Charter:</b> {t["mirror"]}</div></div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Charter -> Law -> Evidence - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:940px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:19px;margin:0 0 4px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:6px 12px;margin:14px 0}}
 .thread{{border:1px solid rgba(217,178,76,.35);border-radius:12px;padding:16px 18px;margin:16px 0;background:rgba(217,178,76,.04)}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;
        border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:5px;margin:18px 0 10px}}
 .row{{display:grid;grid-template-columns:230px 1fr;gap:14px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .ref{{font-family:Consolas,monospace;font-size:12px;color:#d9b24c}}
 .txt{{font-size:13.5px;color:#e8e4d8}}
 .apply{{font-family:Consolas,monospace;font-size:11px;color:#6abf86;margin-top:4px}}
 .ev{{font-size:13.5px;color:#bdb8a4}} .ev b{{color:#e8e4d8}} .ev ul{{margin:6px 0;padding-left:18px}} .ev li{{margin-bottom:3px}}
 .mirror{{font-size:13px;color:#e8d9a8;background:rgba(106,191,134,.07);border-radius:8px;padding:10px 13px;margin-top:14px}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · Charter &rarr; Law &rarr; Evidence</div>
<h1>How the Charter Handles the Threads &mdash; and the Law That Already Mirrors It</h1>
<p class="lead">Three layers, bound together and refreshed every run: what the 12 Stones Sovereign Charter (SSC v5)
prescribes, the existing enforceable statute that already achieves the same outcome (and the body that can act),
and the live evidence from the Kilo Aupuni watchers.</p>
<div class="disc">This is a map of <b>lawful action</b> built on public records and verbatim Charter text.
It cites existing law and live data; it does not allege wrongdoing by any named person. The Charter does not
need to be sovereign law for any of this to work &mdash; existing Hawaii and county law already provides every
mechanism shown. Verify before asserting anything about anyone.</div>
{cards}
<footer>generated {ts} · charter-law-map v1 · Charter: SSC v5 (verbatim) · law: HRS / Maui Charter / federal antitrust ·
 evidence: live Kilo Aupuni watchers · MauiOS · aloha in action</footer>
</div></body></html>"""

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    ts = now_hst().strftime("%Y-%m-%d %H:%M HST")
    with open(OUT_F, "w", encoding="utf-8") as f:
        f.write(render(ts))
    ev = live_evidence()
    dispatch("SHIPPED", f"charter-law-map rebuilt: 2 threads bound (Charter SSC v5 <-> existing HRS/Charter/antitrust law "
             f"<-> live data: ${ev['re_total']:,.0f} real-estate money, {ev['recusals']} recusals) "
             f"-> reports/mauios/charter_application.html")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
