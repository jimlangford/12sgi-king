#!/usr/bin/env python3
# build_site.py - assemble the public static site for Cloudflare Pages / GitHub Pages.
# Collects the Kilo Aupuni report HTML + JSON from reports/mauios (+ council) and writes
# a flat ./site/ with an index.html linking everything. Runs locally OR on a CI runner.
#
#   python build_site.py            # -> ./site
#   KA_SITE=/path python build_site.py
import os, re, shutil, json
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
COUNCIL = os.path.join(PROJECT, "reports", "council")
SITE    = os.environ.get("KA_SITE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "site"))
HST     = timezone(timedelta(hours=-10))

# headline dashboards (filename in mauios -> public name + blurb)
PAGES = [
    ("county_dashboard.html",            "Maui County Dashboard",        "Coverage map + lens activity + money trail across every watcher."),
    ("accountability_record.html",       "Accountability Record",        "Public record: corruption rankings, federal convictions (Stant/Choy/English/Cullen), reforms recommended vs enacted."),
    ("sole_source_watch.html",           "Sole-Source Watch",            "Sole-source/exemption awards (the Stant mechanism) + the executive-branch gap + the lawful records path."),
    ("patterns_money_x_votes.html",      "Patterns: Money x Votes",      "RE/developer money received vs. lens-bill dissents; cross-jurisdiction donor web."),
    ("statewide_money_patterns.html",    "Statewide Money (2008+)",      "Campaign money across all 4 counties + State; the donor network."),
    ("money_behind_officials.html",      "Money Behind Officials",       "Campaign finance per tracked official, real-estate donors flagged."),
    ("officials_scorecard.html",         "Maui Officials Scorecard",     "Council votes + recusals from the minutes."),
    ("lege/legislator_scorecard.html",   "HI Legislator Scorecard",      "Per-member roll-call votes, 2010+ (LegiScan)."),
    ("charter_application.html",         "Charter -> Law -> Evidence",   "12 Stones Charter bound to existing enforceable law + live data."),
    ("commission_antitrust.html",        "Commission Antitrust Thread",  "NAR/Sitzer-Burnett timeline + estimated commission load."),
    ("bill9/bill9_testimony_scan.html",  "Bill 9 Testimony Scan",        "STR-ban testimony: industry lobbying flagged, no collusion language."),
]
DATA = ["statewide_money.json", "donor_profiles.json", "officials.json",
        "lege/legislators.json", "twin_metrics.json"]

def now_hst(): return datetime.now(HST)

def main():
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE, exist_ok=True)
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
    present = []
    for rel, name, blurb in PAGES:
        src = os.path.join(MAUIOS, rel)
        if os.path.exists(src):
            flat = rel.replace("/", "_")
            shutil.copy(src, os.path.join(SITE, flat))
            present.append((flat, name, blurb))
    for rel in DATA:
        src = os.path.join(MAUIOS, rel)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(SITE, "data", os.path.basename(rel)))

    # [links] copy linked supporting folders so per-official "full profile" pages resolve
    for sub in ("donors",):
        s = os.path.join(MAUIOS, sub)
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(SITE, sub))
            print(f"  + {sub}/: {len(os.listdir(s))} profile pages")

    # [king-system] publish the public King System shell at /king/
    _ksrc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "king_public_src")
    if os.path.isdir(_ksrc):
        _kdst = os.path.join(SITE, "king")
        shutil.copytree(_ksrc, _kdst)
        # [king-system] LEAK GATE: refuse to publish if any internal/infra marker slipped
        # into the public King build (durable re-leak guard for the cowork snapshot).
        _markers = ("ngrok", "uvicorn", "RAIS_API_KEYS", ":8765", ":8780", ":8000",
                    "render_pause", "roster_loop", "tunnel_keepalive", "kohya",
                    "sdxl_train", "sage_node_system", "GPU handoff", "Google login")
        _hits = []
        for _root, _dirs, _files in os.walk(_kdst):
            for _fn in _files:
                if _fn.rsplit(".", 1)[-1].lower() not in ("html", "js", "css", "json"):
                    continue
                try:
                    _txt = open(os.path.join(_root, _fn), encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                for _m in _markers:
                    if _m in _txt:
                        _hits.append("%s::%s" % (_fn, _m))
        if _hits:
            shutil.rmtree(_kdst, ignore_errors=True)
            raise SystemExit("LEAK GATE tripped — internal markers in public King build, refusing to publish: " + "; ".join(_hits[:20]))
        print("  + king/: public King System (leak-gate clean)")
    # [redundancy] always-on failover launcher: routes to the live system (Tailscale)
    # when the laptop is up, else falls back to this GitHub mirror.
    _go = os.path.join(os.path.dirname(os.path.abspath(__file__)), "go.html")
    if os.path.exists(_go):
        shutil.copy(_go, os.path.join(SITE, "go.html"))
        print("  + go.html: live/mirror failover launcher")
    _ta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "take_action.html")
    if os.path.exists(_ta):
        shutil.copy(_ta, os.path.join(SITE, "take_action.html"))
        print("  + take_action.html: demand-the-records + supporter signup")
    # [redundancy] production status (public-safe) from the local 15-min publisher
    _ps = os.path.join(os.path.dirname(os.path.abspath(__file__)), "production_status.json")
    prod = ""
    if os.path.exists(_ps):
        shutil.copy(_ps, os.path.join(SITE, "data", "production_status.json"))
        try:
            _p = json.load(open(_ps, encoding="utf-8"))
            _latest = ", ".join((_p.get("latest_films") or [])[:5])
            prod = ('<div class="eyebrow" style="margin-top:30px">Production</div>'
                    f'<p class="lead">{_p.get("films_produced", 0)} films produced'
                    + (f' · latest: {_latest}' if _latest else "")
                    + (f' · {_p["youtube_uploaded"]} on YouTube' if _p.get("youtube_uploaded") else "")
                    + f' <span style="color:#9a957f;font-size:11px">(updated {_p.get("updated", "")})</span></p>')
            print("  + production_status.json")
        except Exception:
            pass
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    cards = "".join(
        f'<a class="card" href="{fn}"><div class="t">{name}</div><div class="b">{blurb}</div></a>'
        for fn, name, blurb in present)
    index = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kilo Aupuni - Maui County / Hawaii Civic Transparency</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.5}}
 .wrap{{max-width:960px;margin:0 auto;padding:40px 24px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:30px;margin:10px 0 4px}}
 .lead{{font-size:14px;color:#bdb8a4;max-width:80ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:16px 0}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-top:18px}}
 .card{{display:block;border:1px solid rgba(217,178,76,.3);border-radius:12px;padding:15px 17px;background:rgba(217,178,76,.04);text-decoration:none;color:inherit;transition:border-color .15s}}
 .card:hover{{border-color:#d9b24c}} .card .t{{font-size:16px;font-weight:600;color:#e8e4d8}} .card .b{{font-size:12.5px;color:#9a957f;margin-top:5px}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:14px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
 a.data{{color:#d9b24c;font-family:Consolas,monospace;font-size:11px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · govOS civic transparency</div>
<h1>Kilo Aupuni — Watching the Government</h1>
<p class="lead">Public-record civic intelligence for Maui County and the State of Hawaii: council &amp;
legislative votes, campaign money, procurement, permits, and the patterns between them.</p>
<div class="disc">Everything here is built from public records and presented as <b>documented facts and
open questions</b> — not findings of wrongdoing. Correlations are leads to verify, not accusations.
Sources are linked on every page.</div>
<p style="margin:16px 0"><a href="take_action.html" style="display:inline-block;background:#d9b24c;color:#0c100e;font-weight:700;font-family:Consolas,monospace;font-size:13px;letter-spacing:.5px;padding:12px 22px;border-radius:10px;text-decoration:none">&#9878; Demand the records &mdash; file a UIPA request &amp; sign up &rarr;</a></p>
<div class="grid">{cards}</div>
{prod}
<div class="eyebrow" style="margin-top:30px">Raw data</div>
<p>{" · ".join(f'<a class="data" href="data/{os.path.basename(d)}">{os.path.basename(d)}</a>' for d in DATA if os.path.exists(os.path.join(MAUIOS,d)))}</p>
<footer>generated {g} · Kilo Aupuni · sources: CivicClerk · Hawaii Campaign Spending Commission · LegiScan · capitol.hawaii.gov · public record</footer>
</div></body></html>"""
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(index)
    print(f"built site -> {SITE}: {len(present)} dashboards + {len([d for d in DATA if os.path.exists(os.path.join(MAUIOS,d))])} data files")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
