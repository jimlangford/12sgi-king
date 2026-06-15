#!/usr/bin/env python3
# build_site.py - assemble the public static site for GitHub Pages.
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
    ("contracts_x_donors.html",          "Contracts x Donors",           "Maui county contract awardees (HANDS) name-matched to campaign donors of tracked officials. Public records, framed as questions."),
    ("maui_contract_awards.html",        "Maui Contract Awards",         "Every public Notice of Award to a Maui County jurisdiction (HANDS) - the vendor side of the money."),
    ("statewide_money_patterns.html",    "Statewide Money (2008+)",      "Campaign money across all 4 counties + State; the donor network."),
    ("money_behind_officials.html",      "Money Behind Officials",       "Campaign finance per tracked official, real-estate donors flagged."),
    ("officials_scorecard.html",         "Maui Officials Scorecard",     "Council votes + recusals from the minutes."),
    ("lege/legislator_scorecard.html",   "HI Legislator Scorecard",      "Per-member roll-call votes, 2010+ (LegiScan)."),
    ("charter_application.html",         "Charter -> Law -> Evidence",   "12 Stones Charter bound to existing enforceable law + live data."),
    ("commission_antitrust.html",        "Commission Antitrust Thread",  "NAR/Sitzer-Burnett timeline + estimated commission load."),
    ("bill9/bill9_testimony_scan.html",  "Bill 9 Testimony Scan",        "STR-ban testimony: industry lobbying flagged, no collusion language."),
    ("parity_check.html",                "Pairs That No Longer Answer",  "Kumulipo parity: county awards shadowed by donations to the deciders, as leverage. The civic-capture the Overseer (N53) voices. Public records, framed as questions."),
    ("wildfire_recovery_watch.html",     "Wildfire Recovery Watch",      "Where the $22M+ in post-August-2023 Maui wildfire recovery money went, ranked by firm - repeat players flagged, set beside the deciders. Public records, framed as questions."),
    ("lobby_money_watch.html",           "Lobby + Money",                "Entities that BOTH register to lobby the State and donate to tracked Maui officials - a double channel of influence. Led by Lanai Resorts (5 council members). Public records, framed as questions."),
    ("jurisdictions.html",               "govOS Jurisdictions",          "Every govOS tenant - the Hawaii counties + State, and the New York tenants (NYC, NY State, Liverpool) - with the contract record loaded for each. One civic engine, many governments."),
    ("ka_leo_voice.html",                "Ka Leo - The Louder Voice",    "How much louder money makes some voices, per official - rigor in the numbers, aloha in the asking; an invitation to return each pair to pono. Public records, framed as questions."),
]
# extra civic pages copied + nav-injected but NOT shown as their own nav pill (reached via the hub)
EXTRA_PAGES = ["contracts_state.html", "contracts_honolulu.html", "contracts_kauai.html", "contracts_hawaii.html",
               "contracts_nyc.html", "contracts_nys.html", "contracts_liverpool.html",
               # item 2: money / lobby / parity dimensions per tenant (built + verified by the workflow)
               "money_nyc.html", "lobby_nyc.html", "parity_nyc.html",
               "money_nys.html", "parity_nys.html",
               "money_state.html", "parity_state.html",
               "money_honolulu.html", "parity_honolulu.html",
               # item-2 gaps (workflow 2): lobby crosses for HI State / Honolulu / NY State
               "lobby_state.html", "lobby_honolulu.html", "lobby_nys.html",
               # workflow 3: matrix close + subcontractor chains + Ka Leo fan-out (ka_leo_nyc withheld - failed verify)
               "money_liverpool.html", "subcontractors_nyc.html",
               "ka_leo_state.html", "ka_leo_honolulu.html", "ka_leo_nys.html",
               "ka_leo_nyc.html",   # rebuilt on real CFB aggregates (no fabricated donors) - no longer withheld
               # per-tenant Charter <-> Law crosswalk (12 Stones SSC v5 up through the Holy See); State = the proof tenant
               "crosswalk_state.html",
               "crosswalk_maui.html", "crosswalk_honolulu.html", "crosswalk_hawaii.html", "crosswalk_kauai.html",
               "crosswalk_nys.html", "crosswalk_nyc.html", "crosswalk_liverpool.html",
               # phase 2 — the Holy See: apex crosswalk (SSC <-> Canon Law) + its finances (real FY2024 reports)
               "crosswalk_holysee.html", "money_holysee.html", "rebuild_first.html",
               # world financial-center cities (per-country national layer up the shared apex)
               "crosswalk_london.html", "crosswalk_tokyo.html", "crosswalk_hongkong.html", "crosswalk_singapore.html",
               "crosswalk_zurich.html", "crosswalk_frankfurt.html", "crosswalk_paris.html", "crosswalk_dubai.html",
               # agenda watch — every tenant's upcoming meetings, daily-checked (index + per-tenant)
               "agendas.html", "agenda_explainer.html",
               "agendas_state.html", "agendas_maui.html", "agendas_honolulu.html", "agendas_hawaii.html", "agendas_kauai.html",
               "agendas_nyc.html", "agendas_nys.html", "agendas_liverpool.html",
               "agendas_london.html", "agendas_tokyo.html", "agendas_hongkong.html", "agendas_singapore.html",
               "agendas_zurich.html", "agendas_frankfurt.html", "agendas_paris.html", "agendas_dubai.html",
               # N53 integrity engine — past minutes / supplemental materials / roll-call corpus
               "n53_engine.html", "archive.html", "testimony_money.html", "testimony_record.html",
               "archive_state.html", "archive_maui.html", "archive_honolulu.html", "archive_hawaii.html", "archive_kauai.html",
               "archive_nyc.html", "archive_nys.html", "archive_liverpool.html",
               "archive_london.html", "archive_tokyo.html", "archive_hongkong.html", "archive_singapore.html",
               "archive_zurich.html", "archive_frankfurt.html", "archive_paris.html", "archive_dubai.html",
               # tenant-aware records-request page (generated by request_records.py — each tenant's own access law)
               "request_records.html", "sage_bridge.html"]
DATA = ["statewide_money.json", "donor_profiles.json", "officials.json", "parity_check.json",
        "lege/legislators.json", "twin_metrics.json",
        "hands_maui_awards.json", "vendor_donor_join.json", "sage_bridge.json"]

# ── govOS top navigation: a professional grouped top-bar injected into every civic page
#    (wordmark + dropdown menus + CTA; responsive with a mobile menu). ──
NAV_LABEL = {
    "county_dashboard.html": "Maui County Dashboard",
    "patterns_money_x_votes.html": "Money × Votes",
    "money_behind_officials.html": "Money Behind Officials",
    "statewide_money_patterns.html": "Statewide Money",
    "contracts_x_donors.html": "Contracts × Donors",
    "maui_contract_awards.html": "Contract Awards",
    "lobby_money_watch.html": "Lobby + Money",
    "officials_scorecard.html": "Officials Scorecard",
    "lege_legislator_scorecard.html": "Legislator Scorecard",
    "accountability_record.html": "Accountability Record",
    "sole_source_watch.html": "Sole-Source Watch",
    "commission_antitrust.html": "Antitrust Thread",
    "bill9_bill9_testimony_scan.html": "Bill 9 Testimony",
    "charter_application.html": "Charter → Law → Evidence",
    "parity_check.html": "Parity — Pairs That No Longer Answer",
    "wildfire_recovery_watch.html": "Wildfire Recovery",
    "ka_leo_voice.html": "Ka Leo — The Louder Voice",
    "crosswalk_state.html": "Charter ⇄ Law (State of Hawaiʻi)",
    "crosswalk_maui.html": "Charter ⇄ Law (Maui County)",
    "crosswalk_honolulu.html": "Charter ⇄ Law (Honolulu)",
    "crosswalk_hawaii.html": "Charter ⇄ Law (Hawaiʻi County)",
    "crosswalk_kauai.html": "Charter ⇄ Law (Kauaʻi County)",
    "crosswalk_nys.html": "Charter ⇄ Law (New York State)",
    "crosswalk_nyc.html": "Charter ⇄ Law (New York City)",
    "crosswalk_liverpool.html": "Charter ⇄ Law (Village of Liverpool)",
    "crosswalk_holysee.html": "Charter ⇄ Law (Holy See ✦ apex)",
    "money_holysee.html": "Holy See Finances",
    "rebuild_first.html": "Who Rebuilt First (Lahaina/Kula)",
    "n53_engine.html": "N53 — Ka Luna Kiaʻi (integrity engine)",
    "archive.html": "Past Record — Minutes & Votes",
    "testimony_money.html": "Follow the Money by Testimony",
    "testimony_record.html": "Who Testified — the record",
    "crosswalk_london.html": "London (City of London + GLA)",
    "crosswalk_tokyo.html": "Tokyo",
    "crosswalk_hongkong.html": "Hong Kong",
    "crosswalk_singapore.html": "Singapore",
    "crosswalk_zurich.html": "Zürich (Switzerland)",
    "crosswalk_frankfurt.html": "Frankfurt (Germany)",
    "crosswalk_paris.html": "Paris (France)",
    "crosswalk_dubai.html": "Dubai (UAE + DIFC)",
    # Charter / law / budget reference layer (govOS-styled pages in the King civic tree).
    # Full paths so the nav links resolve at site root AND on king-local (king/civic/... exists on both).
    "king/civic/templates/mauios-gov/MauiOS%20Government%20OS.html": "govOS — Charter Hub",
    "king/civic/templates/title19-crosswalk/Title19%20Crosswalk.html": "Charter ⇄ Law Crosswalk",
    "king/civic/templates/budget-transparency/Budget%20Transparency.html": "Budget — Every Dollar",
    "king/civic/templates/county-code/Maui%20County%20Code%20%26%20Rules.html": "Maui County Code",
    "king/civic/templates/state-law/State%20of%20Hawai%CA%BBi%20Law%20Index.html": "Hawaiʻi Law Index",
    "king/civic/templates/hawaii-crosswalk/Hawai%CA%BBi%20County%20Crosswalk.html": "Hawaiʻi County Crosswalk",
    "king/civic/templates/agenda-explainer/Agenda%20Explainer.html": "Agenda Explainer",
}
# Citizen-first IA: organized around what a voting community member needs to participate —
# know your officials, follow the money, read the record. (Testify/Take-action lead via the CTA + a Participate link.)
NAV_GROUPS = [
    ("Your Officials", ["officials_scorecard.html", "money_behind_officials.html", "ka_leo_voice.html"]),
    ("Follow the Money", ["county_dashboard.html", "patterns_money_x_votes.html", "contracts_x_donors.html",
                          "lobby_money_watch.html", "maui_contract_awards.html", "statewide_money_patterns.html",
                          "wildfire_recovery_watch.html", "rebuild_first.html", "money_holysee.html"]),
    ("The Record", ["n53_engine.html", "archive.html", "testimony_record.html", "testimony_money.html", "parity_check.html", "accountability_record.html",
                    "sole_source_watch.html", "commission_antitrust.html", "bill9_bill9_testimony_scan.html",
                    "charter_application.html", "lege_legislator_scorecard.html"]),
    # The 12 Stones Sovereign Charter crosswalked to each tenant's full legal hierarchy up
    # through the Holy See. Leads with the new per-tenant crosswalk engine (crosswalk_<id>.html);
    # the King-civic charter/budget/code/law reference pages follow (full paths, resolve on both servers).
    ("Charter & Law", ["crosswalk_state.html", "crosswalk_maui.html", "crosswalk_honolulu.html",
                       "crosswalk_hawaii.html", "crosswalk_kauai.html", "crosswalk_nys.html",
                       "crosswalk_nyc.html", "crosswalk_liverpool.html", "crosswalk_holysee.html",
                       # unique non-crosswalk reference pages (real budget data + the publish loop)
                       "king/civic/templates/budget-transparency/Budget%20Transparency.html",
                       "king/civic/templates/agenda-explainer/Agenda%20Explainer.html"]),
    # world financial-center cities — same SSC charter, each city's real charter/code + national law,
    # up the shared apex to the Holy See. "Act local, think global."
    ("World Centers", ["crosswalk_london.html", "crosswalk_tokyo.html", "crosswalk_hongkong.html",
                       "crosswalk_singapore.html", "crosswalk_zurich.html", "crosswalk_frankfurt.html",
                       "crosswalk_paris.html", "crosswalk_dubai.html"]),
]
NAV_CSS = ("<style>"
    ".govos-nav{position:sticky;top:0;z-index:9999;display:flex;align-items:center;gap:2px;height:54px;"
    "padding:0 18px;background:#0b0f0d;border-bottom:1px solid rgba(217,178,76,.26);"
    "font-family:'Segoe UI',system-ui,-apple-system,Roboto,sans-serif;font-size:13px;box-shadow:0 1px 0 rgba(0,0,0,.4)}"
    ".govos-nav *{box-sizing:border-box}"
    ".gn-brand{display:flex;align-items:center;gap:9px;text-decoration:none;margin-right:16px;white-space:nowrap}"
    ".gn-brand .mk{color:#d9b24c;font-size:17px;line-height:1}"
    ".gn-brand b{color:#efe9da;font-weight:600;font-size:15px;letter-spacing:.2px}"
    ".gn-brand .sub{color:#8a8674;font-size:9.5px;letter-spacing:1.5px;text-transform:uppercase;border-left:1px solid #34301f;padding-left:9px}"
    ".gn-menu{display:flex;align-items:center;gap:1px;flex:1}"
    ".gn-group{position:relative}"
    ".gn-top{display:flex;align-items:center;gap:6px;background:none;border:0;color:#cfc9b6;font:inherit;font-size:13px;padding:8px 12px;border-radius:7px;cursor:pointer}"
    ".gn-top .ar{font-size:9px;color:#8a8674}"
    ".gn-top:hover,.gn-group:hover .gn-top{color:#efe9da;background:rgba(255,255,255,.045)}"
    ".gn-top.active{color:#f4c95d}"
    ".gn-panel{position:absolute;top:calc(100% + 5px);left:0;min-width:240px;background:#121714;border:1px solid #2a2f29;"
    "border-radius:11px;padding:6px;box-shadow:0 16px 38px rgba(0,0,0,.55);display:none;flex-direction:column;gap:1px;z-index:50}"
    ".gn-group:hover .gn-panel,.gn-group.open .gn-panel{display:flex}"
    ".gn-panel a{display:block;color:#cfc9b6;text-decoration:none;padding:8px 11px;border-radius:6px;font-size:13px;white-space:nowrap}"
    ".gn-panel a:hover{background:rgba(217,178,76,.1);color:#efe9da}"
    ".gn-panel a.cur{color:#f4c95d;background:rgba(217,178,76,.13)}"
    ".gn-link{color:#cfc9b6;text-decoration:none;padding:8px 12px;border-radius:7px}"
    ".gn-link:hover{color:#efe9da;background:rgba(255,255,255,.045)}"
    ".gn-link.cur{color:#f4c95d}"
    ".gn-lead{color:#9fd9bf;font-weight:600;text-decoration:none;padding:8px 12px;border-radius:7px;margin-right:4px}"
    ".gn-lead:hover{background:rgba(67,211,158,.12)}.gn-lead.cur{color:#c8efd9}"
    ".gn-cta{margin-left:auto;background:#d9b24c;color:#0c100e;font-weight:600;text-decoration:none;padding:8px 16px;border-radius:8px;font-size:13px;white-space:nowrap}"
    ".gn-cta:hover{background:#e7c361}"
    ".gn-burger{display:none;margin-left:auto;background:none;border:0;color:#efe9da;font-size:21px;cursor:pointer;padding:4px 8px;line-height:1}"
    "@media(max-width:880px){"
    ".gn-burger{display:block}"
    ".gn-menu{display:none;position:absolute;top:54px;left:0;right:0;flex-direction:column;align-items:stretch;"
    "background:#0b0f0d;border-bottom:1px solid #2a2f29;padding:8px;gap:2px;max-height:82vh;overflow:auto}"
    ".govos-nav.open .gn-menu{display:flex}"
    ".gn-top{width:100%;justify-content:space-between}"
    ".gn-panel{position:static;box-shadow:none;border:0;background:rgba(255,255,255,.03);min-width:0;margin:1px 0 3px 10px}"
    ".gn-group:hover .gn-panel{display:none}.gn-group.open .gn-panel{display:flex}"
    ".gn-cta{margin:6px 0 2px;text-align:center}"
    "}</style>")
NAV_JS = ("<script>(function(){var n=document.querySelector('.govos-nav');if(!n)return;"
    "var b=n.querySelector('.gn-burger');if(b)b.addEventListener('click',function(){n.classList.toggle('open');});"
    "n.querySelectorAll('.gn-top').forEach(function(t){t.addEventListener('click',function(e){e.preventDefault();"
    "var g=t.parentNode,was=g.classList.contains('open');"
    "n.querySelectorAll('.gn-group').forEach(function(x){x.classList.remove('open');});if(!was)g.classList.add('open');});});"
    "document.addEventListener('click',function(e){if(!n.contains(e.target))"
    "n.querySelectorAll('.gn-group').forEach(function(x){x.classList.remove('open');});});})();</script>")

def nav_bar(current):
    """Professional grouped top-bar for `current` (a flat filename, '' for the hub)."""
    groups = ""
    for glabel, files in NAV_GROUPS:
        active = " active" if current in files else ""
        links = "".join('<a class="%s" href="%s">%s</a>' % ("cur" if f == current else "", f, NAV_LABEL.get(f, f))
                        for f in files)
        groups += ('<div class="gn-group"><button class="gn-top%s">%s<span class="ar">&#9662;</span></button>'
                   '<div class="gn-panel">%s</div></div>') % (active, glabel.replace("&", "&amp;"), links)
    jc = " cur" if current == "jurisdictions.html" else ""
    ac = " cur" if current == "agendas.html" else ""
    return (NAV_CSS +
            '<nav class="govos-nav">'
            '<a class="gn-brand" href="reports.html"><span class="mk">&#10022;</span>'
            '<b>govOS</b><span class="sub">Kilo Aupuni</span></a>'
            '<button class="gn-burger" aria-label="Menu">&#9776;</button>'
            '<div class="gn-menu">'
            '<a class="gn-lead%s" href="testify.html">&#9878; Testify</a>' % (' cur' if current == 'testify.html' else '') + groups +
            '<a class="gn-link%s" href="agendas.html">Agendas</a>' % ac +
            '<a class="gn-link%s" href="agenda_explainer.html">Explainer</a>' % (" cur" if current=="agenda_explainer.html" else "") +
            '<a class="gn-link%s" href="sage_bridge.html">Sage</a>' % (" cur" if current=="sage_bridge.html" else "") +
            '<a class="gn-link%s" href="jurisdictions.html">Jurisdictions</a>' % jc +
            '<a class="gn-link%s" href="request_records.html">Request Records</a>' % (" cur" if current == "request_records.html" else "") +
            '<a class="gn-cta" href="take_action.html">Take action</a>'
            '</div></nav>' + NAV_JS)

def inject_nav(html, current):
    """Insert the nav right after <body>; if there's no body tag, prepend it."""
    if "govos-nav" in html:           # already injected (idempotent safety)
        return html
    nav = nav_bar(current)
    m = re.search(r"<body[^>]*>", html, re.I)
    if m:
        return html[:m.end()] + "\n" + nav + html[m.end():]
    return nav + html

# Wherever a page's records are THIN or UNAVAILABLE, give the public the way to get them.
# A page that carries any thinness marker (and doesn't already link the request page) gets a
# standard "request the records, send them back" banner before </body>. One place, whole govOS.
_THIN_MARKERS = ("pending verification", "ingestion pending", "parse pending", "votes-parse pending",
                 "source identified", "daily checker pending", "no machine-readable", "source check needed",
                 "thin in hands", "awaiting", ">building<", "building</span>", "source pending",
                 "not yet wired", "pending a free api key", "feed pending", "links pending",
                 "next wave", "minutes/materials links", "roll-call parsing of those minutes is marked pending",
                 "files almost nothing", "no fire-recovery permits", "deeper pull")
_REC_TIDS = ("state","maui","honolulu","hawaii","kauai","nys","nyc","liverpool","london","tokyo",
             "hongkong","singapore","zurich","frankfurt","paris","dubai","holysee")
_REC_MAUI = {"county_dashboard.html","money_behind_officials.html","officials_scorecard.html",
             "patterns_money_x_votes.html","contracts_x_donors.html","maui_contract_awards.html",
             "parity_check.html","lobby_money_watch.html","ka_leo_voice.html","wildfire_recovery_watch.html",
             "rebuild_first.html","testimony_record.html","testimony_money.html","bill9_bill9_testimony_scan.html"}
def _records_anchor(current):
    m = re.search(r"_(" + "|".join(_REC_TIDS) + r")\.html$", current or "")
    if m: return "#" + m.group(1)
    return "#maui" if current in _REC_MAUI else ""
def add_records_cta(html, current=""):
    # skip the target page itself, or pages that already carry the banner / an anchored gap-link
    # (the plain "Request Records" NAV link does NOT count — every page has that).
    if current == "request_records.html" or "request them and send" in html or "request_records.html#" in html:
        return html
    low = html.lower()
    if not any(m in low for m in _THIN_MARKERS):
        return html
    href = "request_records.html" + _records_anchor(current)   # point each page to ITS tenant's records office
    cta = ('<div style="max-width:1100px;margin:18px auto 0;padding:11px 16px;border:1px dashed '
        'rgba(217,178,76,.45);border-radius:10px;background:rgba(217,178,76,.05);font-family:Consolas,monospace;'
        'font-size:12px;color:#cfc9b6;line-height:1.55">&#128196; Some records on this page are <b>thin or pending</b>. '
        'They are public &mdash; under this jurisdiction&rsquo;s own access law you can '
        '<a href="%s" style="color:#d9b24c;font-weight:700">request them and send them back</a> to turn a gap into a '
        'fact on the ledger.</div>') % href
    m = re.search(r"</body>", html, re.I)
    return (html[:m.start()] + cta + html[m.start():]) if m else (html + cta)

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
            html = open(src, encoding="utf-8", errors="replace").read()
            html = inject_nav(html, flat)          # govOS top nav on every civic page
            html = add_records_cta(html, flat)     # request-the-record banner where data is thin/pending
            with open(os.path.join(SITE, flat), "w", encoding="utf-8", newline="\n") as f:
                f.write(html)
            present.append((flat, name, blurb))
    # extra per-tenant pages: copied + nav-injected, reached from the jurisdictions hub (not nav pills)
    for rel in EXTRA_PAGES:
        src = os.path.join(MAUIOS, rel)
        if os.path.exists(src):
            with open(os.path.join(SITE, rel), "w", encoding="utf-8", newline="\n") as f:
                f.write(add_records_cta(inject_nav(open(src, encoding="utf-8", errors="replace").read(), rel), rel))
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
        # infra markers in their real leak form (loopback-prefixed ports, not bare
        # numbers) so legit content like a budget "val:8000000" doesn't false-trip.
        _markers = ("ngrok", "uvicorn", "RAIS_API_KEYS", "127.0.0.1:8765", "127.0.0.1:8780",
                    "127.0.0.1:8000", "localhost:87", "render_pause",
                    "roster_loop", "tunnel_keepalive", "kohya", "sdxl_train",
                    "sage_node_system", "GPU handoff", "Google login")
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
        # [king-landing] The old Vue shell renders {{ template }} literals on static hosting and
        # says nothing of the 16-tenant global work. Replace the /king/ landing with a clean static
        # page that reflects the live global system (the owner Vue app is preserved at king/app.html).
        _kl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "king_landing.html")
        if os.path.exists(_kl):
            _kidx = os.path.join(_kdst, "index.html")
            if os.path.exists(_kidx):
                shutil.copy(_kidx, os.path.join(_kdst, "app.html"))   # keep the owner shell, reachable
            shutil.copy(_kl, _kidx)
            print("  + king/index.html: clean static landing (global system + live progress); old shell -> king/app.html")
    # [redundancy] always-on failover launcher: routes to the live system (Tailscale)
    # when the laptop is up, else falls back to this GitHub mirror.
    _go = os.path.join(os.path.dirname(os.path.abspath(__file__)), "go.html")
    if os.path.exists(_go):
        shutil.copy(_go, os.path.join(SITE, "go.html"))
        # also under king/ so the King shell's "Studio ->" door (href="go.html") resolves.
        # The root go.html is root-relative to the site (govOS dashboards live at root: e.g.
        # jurisdictions.html, county_dashboard.html, ./ = govOS home, king/ = the King app).
        # When the SAME file is served at /king/go.html, every root-relative link must go up
        # one level. Generic rule (no per-link maintenance): keep absolute/anchor links as-is;
        #   king/  -> ./    (the King shell IS this dir)
        #   ./     -> ../   (govOS home lives at site root, one up)
        #   X.html -> ../X.html  (all govOS dashboards/tenant pages live at site root)
        if os.path.isdir(os.path.join(SITE, "king")):
            def _king_href(m):
                h = m.group(1)
                if h.startswith(("http", "#", "../", "mailto:")):
                    return 'href="%s"' % h
                if h == "king/":
                    return 'href="./"'
                if h in ("./", "."):
                    return 'href="../"'
                return 'href="../%s"' % h    # root-level govOS page -> up one from /king/
            _kgo = re.sub(r'href="([^"]*)"', _king_href, open(_go, encoding="utf-8").read())
            with open(os.path.join(SITE, "king", "go.html"), "w", encoding="utf-8", newline="\n") as f:
                f.write(_kgo)
        print("  + go.html: live/mirror failover launcher (root + king/)")
    # [no-access] friendly 404 — GitHub Pages serves /404.html for any missing OR owner-only path
    # (e.g. case_files.html), explaining it's a private surface by design instead of a bare 404.
    _404 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "404.html")
    if os.path.exists(_404):
        shutil.copy(_404, os.path.join(SITE, "404.html"))
        print("  + 404.html: 'no access — private surface' explanation (served by GitHub Pages on any 404)")
    _ta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "take_action.html")
    if os.path.exists(_ta):
        _tah = inject_nav(open(_ta, encoding="utf-8", errors="replace").read(), "take_action.html")
        with open(os.path.join(SITE, "take_action.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(_tah)
        print("  + take_action.html: demand-the-records + supporter signup (+nav)")
    _tf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testify.html")
    if os.path.exists(_tf):
        with open(os.path.join(SITE, "testify.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(inject_nav(open(_tf, encoding="utf-8", errors="replace").read(), "testify.html"))
        print("  + testify.html: citizen testimony -> County Clerk + govOS (+nav)")
    # request_records.html is now GENERATED (request_records.py, tenant-aware) + flows through EXTRA_PAGES.
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
<p style="margin:16px 0;display:flex;gap:12px;flex-wrap:wrap"><a href="take_action.html" style="display:inline-block;background:#d9b24c;color:#0c100e;font-weight:700;font-family:Consolas,monospace;font-size:13px;letter-spacing:.5px;padding:12px 22px;border-radius:10px;text-decoration:none">&#9878; Demand the records &mdash; file a UIPA request &amp; sign up &rarr;</a><a href="king/" style="display:inline-block;background:rgba(217,178,76,.12);border:1px solid #d9b24c;color:#f4c95d;font-family:Consolas,monospace;font-size:13px;letter-spacing:.5px;padding:12px 22px;border-radius:10px;text-decoration:none">&#10022; Open the govOS app &rarr;</a></p>
<div class="grid">{cards}</div>
{prod}
<div class="eyebrow" style="margin-top:30px">Raw data</div>
<p>{" · ".join(f'<a class="data" href="data/{os.path.basename(d)}">{os.path.basename(d)}</a>' for d in DATA if os.path.exists(os.path.join(MAUIOS,d)))}</p>
<footer>generated {g} · Kilo Aupuni · sources: CivicClerk · Hawaii Campaign Spending Commission · LegiScan · capitol.hawaii.gov · public record</footer>
</div></body></html>"""
    index = inject_nav(index, "")     # nav on the hub too (home pill highlights nothing)
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(index)
    # the nav's "🌺 govOS" home points at reports.html — make it the named hub in BOTH
    # contexts (public site root + king-local, where index.html is the King shell).
    with open(os.path.join(SITE, "reports.html"), "w", encoding="utf-8") as f:
        f.write(index)
    print(f"built site -> {SITE}: {len(present)} dashboards + {len([d for d in DATA if os.path.exists(os.path.join(MAUIOS,d))])} data files")

    # [private-mirror] Unification: the LOCAL/owner King (king-local) must be a SUPERSET
    # of the public build — same civic dashboards + data, plus the owner-only surfaces it
    # already has. We mirror the public artifacts into it so PRIVATE serves the same
    # information, and (running locally) it updates BEFORE the git push reaches GitHub
    # Pages — "private first, public mirror." On CI this dir is absent, so it no-ops.
    KLOCAL = os.path.expanduser(os.path.join("~", "AppData", "Local", "king-extract", "deploy", "king-local"))
    if os.path.isdir(KLOCAL):
        import glob
        for h in glob.glob(os.path.join(SITE, "*.html")):
            b = os.path.basename(h)
            # SINGLE SOURCE: local root == public root (the civic landing front door).
            # The King System app lives at /king/ on BOTH (one tap from the landing).
            shutil.copy(h, os.path.join(KLOCAL, b))
        for sub in ("data", "donors", "king"):   # +king: civic/templates tree so go.html resolves on the private server (true superset)
            s = os.path.join(SITE, sub)
            if os.path.isdir(s):
                shutil.copytree(s, os.path.join(KLOCAL, sub), dirs_exist_ok=True)
        print(f"  + king-local (PRIVATE superset): mirrored {len(present)} dashboards + data + king/ -> served first via Tailscale")
        # [OWNER ONLY] the prosecutorial back end — copied to king-local (private/Tailscale) ONLY.
        # Deliberately NOT in PAGES/EXTRA_PAGES/seed and NOT mirrored to SITE, so it can never reach
        # public GitHub Pages. Front end stays Aloha + factual; this rigor is owner-private.
        _cf = os.path.join(MAUIOS, "case_files.html")
        if os.path.exists(_cf):
            shutil.copy(_cf, os.path.join(KLOCAL, "case_files.html"))
            print("  + king-local OWNER-ONLY: case_files.html (prosecutorial back end — never public)")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
