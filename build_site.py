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
               "agendas.html", "agenda_explainer.html", "agenda_patterns.html",
               "agendas_state.html", "agendas_maui.html", "agendas_honolulu.html", "agendas_hawaii.html", "agendas_kauai.html",
               "agendas_nyc.html", "agendas_nys.html", "agendas_liverpool.html",
               "agendas_london.html", "agendas_tokyo.html", "agendas_hongkong.html", "agendas_singapore.html",
               "agendas_zurich.html", "agendas_frankfurt.html", "agendas_paris.html", "agendas_dubai.html",
               # minutes watch — the people's record per tenant (dignified, sourced; private evidence stays in _status)
               "meetings_calendar.html", "meetings_maui.html", "meetings_honolulu.html", "meetings_hawaii.html", "meetings_kauai.html", "meetings_nyc.html", "bfed_agenda_today.html", "bfed_eligibility_today.html", "minutes_hi-maui.html", "minutes_hi-state.html", "minutes_hi-hawaii.html",
               "minutes_hi-kauai.html", "minutes_hi-honolulu.html", "minutes_ny.html",
               # N53 integrity engine — past minutes / supplemental materials / roll-call corpus
               "n53_engine.html", "archive.html", "testimony_money.html", "testimony_record.html",
               "archive_state.html", "archive_maui.html", "archive_honolulu.html", "archive_hawaii.html", "archive_kauai.html",
               "archive_nyc.html", "archive_nys.html", "archive_liverpool.html",
               "archive_london.html", "archive_tokyo.html", "archive_hongkong.html", "archive_singapore.html",
               "archive_zurich.html", "archive_frankfurt.html", "archive_paris.html", "archive_dubai.html",
               # tenant-aware records-request page (generated by request_records.py — each tenant's own access law)
               "request_records.html", "sage_bridge.html",
               # ʻŌlelo glossary (community-review) + the system self-check integrity page
               "olelo_glossary.html", "selfheal.html",
               # SIMPLIFIED LANDING (tenant picker) + per-tenant index pages + the federal/audit lenses (2026-06-15)
               "tenants_hub.html",
               "tenant_hi-state.html", "tenant_hi-maui.html", "tenant_hi-hawaii.html",
               "tenant_hi-kauai.html", "tenant_hi-honolulu.html", "tenant_ny.html",
               "federal_money.html", "federal_money_hawaii.html", "federal_money_honolulu.html",
               "federal_money_kauai.html", "federal_officials.html", "audit_balance.html",
               # county 'Who governs' rosters — sourced from each council's official site (2026-06-16)
               "officials_honolulu.html", "officials_hawaii.html", "officials_kauai.html",
               # public outreach: seeking a 501(c)(3) fiscal-sponsor partner (2026-06-15)
               "partner.html"]
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
    # tenant overview pages — the per-government entry points (the Governments nav group)
    "tenant_hi-maui.html": "Maui County", "tenant_hi-honolulu.html": "Honolulu",
    "tenant_hi-hawaii.html": "Hawaiʻi County", "tenant_hi-kauai.html": "Kauaʻi County",
    "tenant_hi-state.html": "State of Hawaiʻi", "tenant_ny.html": "New York",
    "jurisdictions.html": "All governments →",
}
# Citizen-first IA: organized around what a voting community member needs to participate —
# know your officials, follow the money, read the record. (Testify/Take-action lead via the CTA + a Participate link.)
NAV_GROUPS = [
    # FIRST: pick a government. Tenant-switching is the primary nav so the reports aren't Maui-locked —
    # from any page you can jump to any tenant's overview (Jimmy 2026-06-16: "stop the Maui-focused nav").
    ("Governments", ["tenant_hi-maui.html", "tenant_hi-honolulu.html", "tenant_hi-hawaii.html",
                     "tenant_hi-kauai.html", "tenant_hi-state.html", "tenant_ny.html", "jurisdictions.html"]),
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
            '<a class="gn-link%s" href="olelo_glossary.html">ʻŌlelo</a>' % (" cur" if current=="olelo_glossary.html" else "") +
            '<a class="gn-link%s" href="jurisdictions.html">Jurisdictions</a>' % jc +
            '<a class="gn-link%s" href="request_records.html">Request Records</a>' % (" cur" if current == "request_records.html" else "") +
            '<a class="gn-cta" href="take_action.html">Take part</a>'
            '</div></nav>' + NAV_JS)

COPYRIGHT = ('<div class="sgi-copyright" style="text-align:center;font:11px/1.6 Consolas,monospace;'
             'color:#9a957f;padding:20px 12px;border-top:1px solid rgba(255,255,255,.08);margin-top:34px">'
             '&copy; 2026 James RCS Langford &middot; 12 Stones Global &middot; all rights reserved</div>')

def inject_nav(html, current):
    """Insert the nav right after <body>; if there's no body tag, prepend it. Also append the
    James RCS Langford copyright footer to every served page (idempotent)."""
    if "govos-nav" not in html:           # nav not yet injected
        nav = nav_bar(current)
        m = re.search(r"<body[^>]*>", html, re.I)
        html = (html[:m.end()] + "\n" + nav + html[m.end():]) if m else (nav + html)
    if "sgi-copyright" not in html:        # append copyright once, before </body>
        i = html.lower().rfind("</body>")
        html = (html[:i] + COPYRIGHT + html[i:]) if i != -1 else (html + COPYRIGHT)
    return html


# ── per-tenant report TEMPLATE + inline TENANT-SWITCHER (Jimmy 2026-06-16, built on the consolidated
#    tenant_registry). On any report that exists per-tenant, surface a "choose a government" row so you can
#    select a different tenant FROM THE SAME REPORT. Reads the ONE registry (tenant_registry.json) — no
#    hardcoded tenant list. A tenant without that report yet shows a calm "building" chip (honest, not a dead
#    link). Same class of presentation on every tenant — the productizable separation.
_SWITCHER = None
def _switcher_maps():
    """(reverse {file -> (class_key, class_label, tenant_id)}, byclass {class_key -> [(tid,name,file|None)]})."""
    global _SWITCHER
    if _SWITCHER is not None: return _SWITCHER
    rev, byclass, clabels = {}, {}, {}
    try:
        reg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tenant_registry.json"), encoding="utf-8"))
        clabels = {c["key"]: c["label"] for c in reg.get("report_classes", [])}
        for c in reg.get("report_classes", []):
            k = c["key"]; byclass[k] = []
            for t in reg.get("civic_tenants", []):
                files = t["reports"].get(k) or []
                # build_site flattens published subdir paths ("lege/x.html" -> "lege_x.html"); match that
                # so the switcher chips never 404 (the seed-drift/flatten gotcha).
                f = files[0].replace("/", "_") if files else None
                byclass[k].append((t["id"], t["name"], f))
                if f: rev.setdefault(f, (k, clabels.get(k, k), t["id"]))
    except Exception:
        pass
    _SWITCHER = (rev, byclass)
    return _SWITCHER

_SWITCH_CSS = ("<style id=tenant-switch-css>.tenant-switch{display:flex;align-items:center;gap:7px;flex-wrap:wrap;"
    "max-width:1100px;margin:10px auto 0;padding:9px 14px;background:#eef2f7;border:1px solid #bacde6;border-radius:11px;"
    "font-family:'Segoe UI',system-ui,sans-serif}.ts-label{font-size:11.5px;color:#41536b;font-weight:600;margin-right:4px}"
    ".ts-chip{font-size:12px;text-decoration:none;color:#1259a3;background:#fff;border:1px solid #bacde6;border-radius:99px;"
    "padding:4px 11px;white-space:nowrap}.ts-chip:hover{border-color:#00356b;color:#00356b}"
    ".ts-chip.cur{background:#00356b;color:#fff;border-color:#00356b;font-weight:600}"
    ".ts-chip.ts-off{color:#9fb1c4;background:#f3f7fc;cursor:default}</style>")

def inject_switcher(html, current_file):
    rev, byclass = _switcher_maps()
    info = rev.get((current_file or "").replace("/", "_"))
    if not info:
        return html                         # not a per-tenant report — leave it
    ck, clabel, cur_tid = info
    chips = ""
    for tid, name, f in byclass.get(ck, []):
        if f:
            chips += '<a class="ts-chip%s" href="%s">%s</a>' % (" cur" if tid == cur_tid else "", f, name)
        else:
            chips += '<span class="ts-chip ts-off" title="this government&#39;s page is being gathered">%s</span>' % name
    sw = (_SWITCH_CSS if "tenant-switch-css" not in html else "") + \
         ('<div class="tenant-switch"><span class="ts-label">%s &mdash; choose a government:</span>%s</div>' % (clabel, chips))
    m = re.search(r"</nav>", html, re.I)    # right under the top nav
    return (html[:m.end()] + "\n" + sw + html[m.end():]) if m else (sw + html)

# ── Yale-blue civic recolor (2026-06-16, Option A — Jimmy: new graphics on ALL sites) ──
# COLOR-ONLY skin remap: the old warm-dark / green-gold chrome hexes -> the new light
# Yale-blue civic palette (matches go.html's 12sgi-design 2026-06-16 export). Applied as a
# post-generation pass over emitted .html/.css ONLY (never .js, never structure/markup) so
# every page and every tenant flips palette while ALL data/search/processing stays identical.
# Cosmology/zone hexes are deliberately NOT remapped (Mauka #4ade80 · Kula #fbbf24 ·
# Makai #38bdf8 · joker #9b8cff stay canon), so node/zone data colors are preserved.
_RECOLOR = [
    # backgrounds: dark -> white / near-white
    ("#0c100e", "#ffffff"), ("#0c0b09", "#ffffff"), ("#080c12", "#ffffff"), ("#0a0e14", "#ffffff"),
    ("#0b0f0d", "#f3f7fc"), ("#0b0e14", "#f3f7fc"),
    # panels: dark -> light blue
    ("#121714", "#e7eef8"), ("#151d19", "#e7eef8"), ("#16140f", "#e7eef8"), ("#15110d", "#e7eef8"),
    ("#1e1b14", "#dae5f3"), ("#1a1610", "#dae5f3"), ("#2a261c", "#ccddef"),
    # lines/borders: dark -> light blue line
    ("#2a2f29", "#bacde6"), ("#34301f", "#bacde6"), ("#243029", "#bacde6"),
    # ink: cream/light -> navy
    ("#efe9da", "#13243d"), ("#e8e4d8", "#13243d"), ("#eef3ef", "#13243d"), ("#f0ead8", "#13243d"),
    ("#cfc9b6", "#41536b"), ("#bdb8a4", "#41536b"), ("#b3a98f", "#41536b"),
    ("#9a957f", "#6d7f97"), ("#8a8674", "#6d7f97"), ("#756b56", "#6d7f97"), ("#9fb1a6", "#6d7f97"),
    # accents: gold -> Yale navy/blue
    ("#d9b24c", "#00356b"), ("#e3ad33", "#00356b"), ("#f4c95d", "#1259a3"), ("#f3d589", "#1259a3"),
    ("#e7c361", "#1259a3"), ("#f0cf7a", "#1259a3"),
    # aloha teal / sea accents -> new ok-green / accent
    ("#9fd9bf", "#1f8a5b"), ("#c8efd9", "#1f8a5b"), ("#e3ecdf", "#41536b"), ("#5fc0d8", "#1259a3"), ("#3a8fb7", "#00356b"),
    # moon/Po offering: light-purple TEXT (unreadable on the new white bg) -> readable dark indigo;
    # purple border/bg -> readable indigo on a faint light tint. (Jimmy: "gold and purple is hard to read".)
    ("#ecdfff", "#2e2a5c"), ("#efe4ff", "#2e2a5c"), ("#cdb4f0", "#5b5fb0"),
    ("rgba(205,180,240", "rgba(91,95,176"),
    # stray cream/ivory texts the first pass missed -> navy
    ("#f4eeda", "#13243d"), ("#f6f0dc", "#13243d"), ("#f4c95d", "#1259a3"),
    # status: keep semantics
    ("#6abf86", "#1f8a5b"), ("#56c08a", "#1f8a5b"), ("#d29922", "#b07d1a"),
    ("#e06a4a", "#c0322c"), ("#e5736b", "#c0322c"),
    # rgba tints (keep the alpha; swap the color): gold/teal -> navy/green
    ("rgba(217,178,76", "rgba(0,53,107"), ("rgba(227,173,51", "rgba(0,53,107"),
    ("rgba(159,217,191", "rgba(31,138,91"), ("rgba(67,211,158", "rgba(31,138,91"),
    # light-on-dark hairline borders -> dark-on-light so they remain visible on white
    ("rgba(255,255,255,.1)", "rgba(0,53,107,.12)"), ("rgba(255,255,255,.08)", "rgba(0,53,107,.1)"),
    ("rgba(255,255,255,.06)", "rgba(0,53,107,.08)"), ("rgba(255,255,255,.045)", "rgba(0,53,107,.05)"),
]
def recolor(text):
    """Color-only remap (case-insensitive on hexes). Never alters markup/JS/data."""
    for old, new in _RECOLOR:
        if old.startswith("#"):
            text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
        else:
            text = text.replace(old, new)
    return text

def recolor_tree(root):
    """Walk a built tree and recolor every .html/.css in place (skip .js/.json — no logic touched)."""
    n = 0
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            if fn.rsplit(".", 1)[-1].lower() not in ("html", "css"):
                continue
            p = os.path.join(dp, fn)
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
                r = recolor(t)
                if r != t:
                    open(p, "w", encoding="utf-8", newline="\n").write(r)
                    n += 1
            except Exception:
                pass
    return n

# Plain-language door-in for the everyday Maui / Hawaiian person. A short "In plain words: ..."
# banner injected right after the nav on every page. Content from narratives.json (exact filename,
# then longest matching prefix, then default). See docs/SAGE_REALM_MODEL.md §8.
_NARR = {}
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "narratives.json"), encoding="utf-8") as _nf:
        _NARR = json.load(_nf)
except Exception:
    _NARR = {"exact": {}, "prefix": {}, "default": ""}
def _narrative_for(flat):
    ex = _NARR.get("exact", {})
    if flat in ex:
        return ex[flat]
    pref = _NARR.get("prefix", {})
    best = ""
    for p, text in pref.items():
        if flat.startswith(p) and len(p) > len(best):
            best, btext = p, text
    if best:
        return btext
    return _NARR.get("default", "")
def add_narrative(html, flat):
    """Inject the plain-words banner just after the nav (idempotent)."""
    if "govos-narrative" in html:
        return html
    text = _narrative_for(flat)
    if not text:
        return html
    box = ('<div class="govos-narrative" style="max-width:1100px;margin:14px auto 0;padding:12px 18px;'
        'border-left:3px solid #9fd9bf;border-radius:8px;background:rgba(159,217,191,.06);'
        'font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:15px;line-height:1.5;color:#e3ecdf">'
        '<b style="color:#9fd9bf">In plain words:</b> ' + text + '</div>')
    # place after the nav if present, else after <body>, else prepend
    m = re.search(r"</nav>", html, re.I)
    if m:
        return html[:m.end()] + "\n" + box + html[m.end():]
    m = re.search(r"<body[^>]*>", html, re.I)
    if m:
        return html[:m.end()] + "\n" + box + html[m.end():]
    return box + html

# A quiet, site-wide line making the ʻŌlelo community-review posture visible on every page.
def add_olelo_notice(html):
    if "govos-olelo-foot" in html:
        return html
    foot = ('<div class="govos-olelo-foot" style="max-width:1100px;margin:26px auto 8px;padding:9px 16px;'
        'font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:12px;color:#9a957f;text-align:center">'
        '🌺 ʻŌlelo Hawaiʻi here is offered with humility and held under community review with ʻŌiwi resources at '
        'Maui County. <a href="olelo_glossary.html" style="color:#cdb4f0">See the glossary &rarr;</a></div>')
    m = re.search(r"</body>", html, re.I)
    return (html[:m.start()] + foot + html[m.start():]) if m else (html + foot)

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
            html = inject_switcher(html, flat)     # per-tenant report: choose a government (same report, any tenant)
            html = add_narrative(html, flat)       # plain-words door-in for the everyday person
            html = add_records_cta(html, flat)     # request-the-record banner where data is thin/pending
            html = add_olelo_notice(html)          # visible ʻŌlelo community-review posture
            with open(os.path.join(SITE, flat), "w", encoding="utf-8", newline="\n") as f:
                f.write(html)
            present.append((flat, name, blurb))
    # extra per-tenant pages: copied + nav-injected, reached from the jurisdictions hub (not nav pills)
    for rel in EXTRA_PAGES:
        src = os.path.join(MAUIOS, rel)
        if os.path.exists(src):
            with open(os.path.join(SITE, rel), "w", encoding="utf-8", newline="\n") as f:
                _h = inject_nav(open(src, encoding="utf-8", errors="replace").read(), rel)
                _h = inject_switcher(_h, rel)      # per-tenant report: choose a government switcher
                _h = add_narrative(_h, rel)
                _h = add_records_cta(_h, rel)
                _h = add_olelo_notice(_h)
                f.write(_h)
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
    # Quad-OS platform/packages page (productized: quadrants + subscriptions + multi-tenant onboarding).
    for _pf in ("platform.html", "packages.json"):
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), _pf)
        if os.path.exists(_p):
            shutil.copy(_p, os.path.join(SITE, _pf))
    if os.path.exists(os.path.join(SITE, "platform.html")):
        print("  + platform.html: Quad-OS platform — quadrants · subscriptions · onboarding")
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
<h1>Kilo Aupuni — Knowing Our Government</h1>
<p class="lead">Your government&rsquo;s public record, made plain &mdash; for the people of Maui and Hawai&#699;i.
Who represents you, who funds them, who the government pays, and what&rsquo;s being decided next &mdash;
gathered with care so any neighbor can follow along.</p>
<div class="disc">Everything here is built from public records and presented as <b>documented facts and
open questions</b> — not findings of wrongdoing. Correlations are leads to verify, not accusations.
Sources are linked on every page.</div>
<div class="eyebrow" style="margin-top:26px">Choose a government</div>
<p class="lead">One civic engine, many governments. Pick a tenant to enter its own pages — Maui is the deepest; the others fill as their watchers run.</p>
<div class="grid">
 <a class="card" href="tenant_hi-state.html"><div class="t">State of Hawai&#699;i</div><div class="b">Campaign money &middot; legislator votes &middot; state contracts &middot; federal dollars</div></a>
 <a class="card" href="tenant_hi-maui.html"><div class="t">Maui County</div><div class="b">Agendas &middot; votes &middot; donors &middot; contracts &middot; federal &middot; money&times;votes</div></a>
 <a class="card" href="tenant_hi-hawaii.html"><div class="t">Hawai&#699;i County</div><div class="b">Agendas &middot; campaign money (county slice)</div></a>
 <a class="card" href="tenant_hi-kauai.html"><div class="t">Kaua&#699;i County</div><div class="b">Agendas &middot; campaign money (county slice)</div></a>
 <a class="card" href="tenant_hi-honolulu.html"><div class="t">City &amp; County of Honolulu</div><div class="b">Agendas &middot; campaign money (county slice)</div></a>
 <a class="card" href="tenant_ny.html"><div class="t">New York</div><div class="b">Agendas (NYC + NY State) &middot; experimental</div></a>
</div>
<div class="eyebrow" style="margin-top:30px">All dashboards</div>
<div class="grid">{cards}</div>
{prod}
<div class="eyebrow" style="margin-top:30px">Raw data</div>
<p>{" · ".join(f'<a class="data" href="data/{os.path.basename(d)}">{os.path.basename(d)}</a>' for d in DATA if os.path.exists(os.path.join(MAUIOS,d)))}</p>
<footer>generated {g} · Kilo Aupuni · sources: CivicClerk · Hawaii Campaign Spending Commission · LegiScan · capitol.hawaii.gov · public record<br>&copy; 2026 James RCS Langford · 12 Stones Global · all rights reserved</footer>
</div></body></html>"""
    index = inject_nav(index, "")     # nav on the hub too (home pill highlights nothing)
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
        f.write(index)
    # the nav's "🌺 govOS" home points at reports.html — make it the named hub in BOTH
    # contexts (public site root + king-local, where index.html is the King shell).
    with open(os.path.join(SITE, "reports.html"), "w", encoding="utf-8") as f:
        f.write(index)
    print(f"built site -> {SITE}: {len(present)} dashboards + {len([d for d in DATA if os.path.exists(os.path.join(MAUIOS,d))])} data files")

    # [self-heal] go.html links to quadrant_progress.html (the Quad-OS progress page, generated to
    # reports/_status by quadrant_selfheal). Publish it so those links resolve (was 2 broken of 7721);
    # it's leak-clean and gets recolored by the pass below.
    for _qpn in ("quadrant_progress.html", "quadrant_progress_log.html"):
        _qp = os.path.join(PROJECT, "reports", "_status", _qpn)
        if os.path.exists(_qp):
            shutil.copy(_qp, os.path.join(SITE, _qpn))
            print(f"  + {_qpn}: published (resolves go.html / progress links)")

    # [recolor] Yale-blue civic skin across EVERY emitted page + tenant (color-only; logic untouched).
    # Runs before the king-local mirror so the private superset inherits the same new palette.
    _rc = recolor_tree(SITE)
    print(f"  + recolor: Yale-blue civic palette applied to {_rc} html/css files (all tenants; data/JS untouched)")

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
        # [OWNER ONLY] system status (so go.html's status link resolves PORTLESS via /king/ — the :8781 port
        # is never shown publicly) + the real-estate loop breakdown. Private; never in SITE/EXTRA_PAGES.
        for _src, _name in ((os.path.join(PROJECT, "reports", "_status", "system_status.html"), "system_status.html"),
                            (os.path.join(PROJECT, "reports", "_status", "ram_loop.html"), "ram_loop.html")):
            if os.path.exists(_src):
                shutil.copy(_src, os.path.join(KLOCAL, _name))
                print(f"  + king-local OWNER-ONLY: {_name} (private — never public)")
        # [OWNER ONLY] recusal/conflict dollar evidence (the Po behind the public eligibility questions) -
        # king-local/Tailscale ONLY; deliberately NOT in PAGES/EXTRA_PAGES/seed so it never reaches Pages.
        _re = os.path.join(MAUIOS, "recusal_evidence.html")
        if os.path.exists(_re):
            shutil.copy(_re, os.path.join(KLOCAL, "recusal_evidence.html"))
            print("  + king-local OWNER-ONLY: recusal_evidence.html (donor-tie dollar evidence — never public)")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
