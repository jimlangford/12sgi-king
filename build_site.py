#!/usr/bin/env python3
# build_site.py - assemble the public static site for GitHub Pages.
# Collects the Kilo Aupuni report HTML + JSON from reports/mauios (+ council) and writes
# a flat ./site/ with an index.html linking everything. Runs locally OR on a CI runner.
#
#   python build_site.py            # -> ./site
#   KA_SITE=/path python build_site.py
import os, re, shutil, json, sys
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
COUNCIL = os.path.join(PROJECT, "reports", "council")

# civic_shell = the unified home-page chrome (single source = tools/kilo-aupuni/civic_shell.py). CI-safe:
# falls back to None if the project tree isn't present, so the build never breaks on a runner.
sys.path.insert(0, os.path.join(PROJECT, "tools", "kilo-aupuni"))
try:
    import civic_shell as _civic_shell   # vendored at repo root for CI (build-mirror; source = project tools/kilo-aupuni)
except Exception:
    _civic_shell = None
# build rev: 2026-06-21 civic_shell chrome live on public (CI rebuild trigger)
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
    ("council_votes_maui.html",          "Council Votes - Nay Narratives","Every Maui Council split vote + the dissenter's own recorded words, beside the campaign money behind each seat. Public records, framed as questions."),
    ("testifiers_maui.html",             "Who Testifies x Money",        "Named public testifiers from the minutes, cross-referenced to campaign donors and the real-estate record. Public records, framed as questions."),
    ("federal_money.html",               "Federal Dollars - Maui & State","Federal contracts + grants landing in Hawai&#699;i, the Maui share called out, broken down by awarding agency. Public records, framed as questions."),
    ("beta_requests.html",               "govOS Beta - Build It With Your Council","Maui Council members request features (Stripe Identity - free, no charge), guided by constituents who sign up by district. Shapes the software; the public record stays public."),
    ("explainer.html",                   "Explain Your Government","Pick a date - the Hawaiian moon + sun + the agenda - then ask our AI to explain any part of Maui County government (Title 19, permits, parcels, the money) as a shareable reel. Relationships + recusals explored gracefully, in aloha."),
    ("lege/legislator_scorecard.html",   "HI Legislator Scorecard",      "Per-member roll-call votes, 2010+ (LegiScan)."),
    ("charter_application.html",         "Charter -> Law -> Evidence",   "12 Stones Charter bound to existing enforceable law + live data."),
    ("commission_antitrust.html",        "Commission Antitrust Thread",  "NAR/Sitzer-Burnett timeline + estimated commission load."),
    ("bill9/bill9_testimony_scan.html",  "Bill 9 Testimony Scan",        "STR-ban testimony: industry lobbying flagged, no collusion language."),
    ("parity_check.html",                "Pairs That No Longer Answer",  "Kumulipo parity: county awards shadowed by donations to the deciders, as leverage. The civic-capture the Overseer (N53) voices. Public records, framed as questions."),
    ("wildfire_recovery_watch.html",     "Wildfire Recovery Watch",      "Where the $22M+ in post-August-2023 Maui wildfire recovery money went, ranked by firm - repeat players flagged, set beside the deciders. Public records, framed as questions."),
    ("lobby_money_watch.html",           "Lobby + Money",                "Entities that BOTH register to lobby the State and donate to tracked Maui officials - a double channel of influence. Led by Lanai Resorts (5 council members). Public records, framed as questions."),
    ("jurisdictions.html",               "govOS Jurisdictions",          "Every govOS tenant - the Hawaii counties + State, and the New York tenants (NYC, NY State, Liverpool) - with the contract record loaded for each. One civic engine, many governments."),
    ("ka_leo_voice.html",                "Ka Leo - The Louder Voice",    "How much louder money makes some voices, per official - rigor in the numbers, aloha in the asking; an invitation to return each pair to pono. Public records, framed as questions."),
    ("sunshine_maui.html",              "Sunshine Law Compliance Watch", "HRS §92-7: did the county post meeting notices 6+ calendar days in advance? Factual record of every Maui Council committee meeting — notice period computed from the Legistar publication timestamp. Flagged entries cited by source; not legal determinations."),
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
               "request_records.html", "sage_bridge.html", "sage_twin.html", "tenant_12stonescharter.html",
               # ʻŌlelo glossary (community-review) + the system self-check integrity page
               "olelo_glossary.html", "selfheal.html",
               # SIMPLIFIED LANDING (tenant picker) + per-tenant index pages + the federal/audit lenses (2026-06-15)
               "tenants_hub.html",
               "tenant_hi-state.html", "tenant_hi-maui.html", "tenant_hi-hawaii.html",
               "tenant_hi-kauai.html", "tenant_hi-honolulu.html", "tenant_nyc.html", "tenant_nys.html",
               # World-center tenants onboarded 2026-06-20 (charter-crosswalk sourced; rest honest-building)
               "tenant_london.html", "tenant_tokyo.html", "tenant_hongkong.html", "tenant_singapore.html",
               "tenant_zurich.html", "tenant_frankfurt.html", "tenant_paris.html", "tenant_dubai.html",
               "tenant_liverpool.html",
               # ⚖ public oversight pages — prosecutor-prepared, JRCSL-audited (sourced/question-framed),
               # made public with aloha (aloha_oversight.py). The private case files NEVER publish; only what clears.
               "oversight_hi-state.html", "oversight_hi-maui.html", "oversight_hi-hawaii.html",
               "oversight_hi-kauai.html", "oversight_hi-honolulu.html", "oversight_help.html",
               # govOS Audit — the per-tenant combined view (funders -> votes/recusals -> contracts -> the questions),
               # one page (govos_audit.py). Maui sourced; others honest-empty until their officials are sourced.
               "govos_audit_hi-state.html", "govos_audit_hi-maui.html", "govos_audit_hi-hawaii.html",
               "govos_audit_hi-kauai.html", "govos_audit_hi-honolulu.html", "govos_audit_ny.html",
               "title19.html",  # Maui submission-calculator hub (onboarding estimate, all departments)
               # federal_money.html (the Maui+State front page) is now a carded dashboard in PAGES; county sub-pages stay here
               "federal_money_hawaii.html", "federal_money_honolulu.html",
               "federal_money_kauai.html", "federal_officials.html", "audit_balance.html",
               # county 'Who governs' rosters — sourced from each council's official site (2026-06-16)
               "officials_honolulu.html", "officials_hawaii.html", "officials_kauai.html",
               # county campaign-money pages (sourced CSC donor totals + real-estate slice; honest contract-gap note)
               "money_hawaii.html", "money_kauai.html", "money_maui.html",
               # PUBLIC real-estate report — giving × recorded property sales, as questions + curse-breaker (2026-06-16)
               "realestate_maui.html",
               # per-tenant real-estate × money pages — the rest of the tenants (Jimmy: do the rest until complete)
               "realestate_honolulu.html", "realestate_hawaii.html", "realestate_kauai.html", "realestate_state.html",
               # the PEOPLE/ORGANIZATIONS behind the money — grouped by donor employer (Jimmy: next trace)
               "orgs_maui.html", "orgs_honolulu.html", "orgs_hawaii.html", "orgs_kauai.html",
               # THE LOOP, ON THE RECORD — donor orgs joined to the meetings their names appear in (2,293 minutes)
               "connections_maui.html", "connections_honolulu.html", "connections_hawaii.html", "connections_kauai.html",
               # testifiers_maui.html + council_votes_maui.html are now carded dashboards in PAGES (fuller treatment)
               # public outreach: seeking a 501(c)(3) fiscal-sponsor partner (2026-06-15)
               "partner.html",
               "feature_board.html",   # "Build Our Government Software" — public request + vote board (free tier)
               # commerce/consumer-protection legal pages (required before charging — FTC/ROSCA + Stripe)
               "terms.html", "privacy.html", "refunds.html"]
DATA = ["statewide_money.json", "donor_profiles.json", "officials.json", "parity_check.json",
        "feature_board.json",   # the AI-sorted public request board data the page renders
        "daily_aloha.json",   # public-safe daily moon offering per tenant (king_message.py) — pure aloha, no figures
        "lege/legislators.json", "twin_metrics.json",
        "hands_maui_awards.json", "vendor_donor_join.json", "sage_bridge.json"]

# OPEN DATA — the raw public records behind every dashboard, indexed as a downloadable catalog (defeats
# "you made it up"). Metadata for the DCAT/data.json catalog + datasets.html front door. Keyed by basename.
# SOURCED public records only — never the private prosecutorial back end. (Civic-app best practice, 2026-06-18.)
DATASET_META = {
    "statewide_money.json":  ("Statewide campaign money", "Contributions across Hawaiʻi races, by office and giver — from the public Campaign Spending Commission record.", ["campaign-finance", "money"], "HI Campaign Spending Commission (hicscdata)"),
    "donor_profiles.json":   ("Donor profiles", "Per-donor giving aggregated from public campaign-finance filings.", ["campaign-finance", "donors"], "HI Campaign Spending Commission"),
    "officials.json":        ("Officials roster", "Elected officials by tenant — who governs, sourced from each government's roster.", ["officials", "roster"], "County/State official rosters"),
    "parity_check.json":     ("Tenant parity check", "Coverage-parity audit across tenants — which data dimensions are present per government.", ["transparency", "audit"], "govOS self-audit"),
    "daily_aloha.json":      ("Daily aloha / moon offering", "The public daily kaulana-mahina offering per tenant — pure aloha, no figures.", ["culture", "moon"], "moon_calendar (kaulana mahina)"),
    "legislators.json":      ("Legislators", "State legislators with district + identifiers.", ["legislature", "officials"], "HI State Legislature open data"),
    "twin_metrics.json":     ("Twin metrics", "Dashboard summary metrics powering the civic overview tiles.", ["metrics"], "govOS dashboards"),
    "hands_maui_awards.json":("Maui contract awards", "County contract awards (HANDS public awards API) used in the contracts × donors join.", ["contracts", "spending"], "Maui County HANDS awards API"),
    "vendor_donor_join.json":("Contracts × donors join", "Public-records join of county contract awards to campaign donors — framed as a question, not a verdict.", ["contracts", "money", "join"], "HANDS awards × CSC donors (public records)"),
    "sage_bridge.json":      ("Sage bridge", "The Sage/Kumulipo node bridge linking agenda dates to cultural offerings.", ["culture", "sage"], "Sage node system"),
}

# ── govOS top navigation: a professional grouped top-bar injected into every civic page
#    (wordmark + dropdown menus + CTA; responsive with a mobile menu). ──
NAV_LABEL = {
    "datasets.html": "Open Data",
    "feature_board.html": "Build the Software",
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
    "realestate_maui.html": "Real Estate × Money (Maui — deep loop)",
    "realestate_honolulu.html": "Money × Votes (Honolulu)",
    "realestate_hawaii.html": "Money × Votes (Hawaiʻi County)",
    "realestate_kauai.html": "Money × Votes (Kauaʻi)",
    "realestate_state.html": "Money × Votes (State)",
    "orgs_maui.html": "Organizations Behind the Money (Maui)",
    "orgs_honolulu.html": "Organizations Behind the Money (Honolulu)",
    "orgs_hawaii.html": "Organizations Behind the Money (Hawaiʻi County)",
    "orgs_kauai.html": "Organizations Behind the Money (Kauaʻi)",
    "testifiers_maui.html": "Who Testifies × Money (Maui)",
    "council_votes_maui.html": "Council Votes — the Nay Narratives (Maui)",
    "connections_maui.html": "The Loop, On the Record (Maui)",
    "connections_honolulu.html": "The Loop, On the Record (Honolulu)",
    "connections_hawaii.html": "The Loop, On the Record (Hawaiʻi County)",
    "connections_kauai.html": "The Loop, On the Record (Kauaʻi)",
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
    "king/civic/templates/title19-system/Title19%20System.html": "Title 19 System — through the Charter",
    "king/civic/templates/title19-service/Title19%20Service.html": "Title 19 — Plain-Language Service (free)",
    "king/civic/templates/title16-service/Title16%20Service.html": "Title 16 — Buildings & Permits (free)",
    "king/civic/templates/title18-service/Title18%20Service.html": "Title 18 — Subdivisions (free)",
    "king/civic/templates/title03-service/Title3%20Service.html": "Title 3 — Real Property Tax (free)",
    "king/civic/templates/title05-service/Title5%20Service.html": "Title 5 — Business Licenses (free)",
    "king/civic/templates/title14-service/Title14%20Service.html": "Title 14 — Water / Public Services (free)",
    "king/civic/templates/title10-service/Title10%20Service.html": "Title 10 — Vehicles & Traffic (free)",
    "king/civic/templates/title12-service/Title12%20Service.html": "Title 12 — Streets & Sidewalks (free)",
    "king/civic/templates/title20-service/Title20%20Service.html": "Title 20 — Environmental Protection (free)",
    "king/civic/templates/title06-service/Title6%20Service.html": "Title 6 — Animals (free)",
    "king/civic/templates/title08-service/Title8%20Service.html": "Title 8 — Health & Safety (free)",
    "king/civic/templates/title09-service/Title9%20Service.html": "Title 9 — Public Peace & Welfare (free)",
    "king/civic/templates/title11-service/Title11%20Service.html": "Title 11 — Public Transit (free)",
    "king/civic/templates/title13-service/Title13%20Service.html": "Title 13 — Parks & Recreation (free)",
    "king/civic/templates/title22-service/Title22%20Service.html": "Title 22 — Department of Agriculture (free)",
    "king/civic/templates/title01-service/Title1%20Service.html": "Title 1 — General Provisions (free)",
    "king/civic/templates/title02-service/Title2%20Service.html": "Title 2 — Administration & Personnel (free)",
    "king/civic/templates/title19-substantial-change/Title19%20Substantial%20Change.html": "Title 19 — Substantial Change Procedure",
    "king/civic/templates/budget-transparency/Budget%20Transparency.html": "Budget — Every Dollar",
    "king/civic/templates/county-code/Maui%20County%20Code%20%26%20Rules.html": "Maui County Code",
    "king/civic/templates/state-law/State%20of%20Hawai%CA%BBi%20Law%20Index.html": "Hawaiʻi Law Index",
    "king/civic/templates/hawaii-crosswalk/Hawai%CA%BBi%20County%20Crosswalk.html": "Hawaiʻi County Crosswalk",
    "king/civic/templates/agenda-explainer/Agenda%20Explainer.html": "Agenda Explainer",
    # tenant overview pages — the per-government entry points (the Governments nav group)
    "tenant_12stonescharter.html": "⚖ 12 Stones Charter",
    "tenant_hi-maui.html": "Maui County", "tenant_hi-honolulu.html": "Honolulu",
    "tenant_hi-hawaii.html": "Hawaiʻi County", "tenant_hi-kauai.html": "Kauaʻi County",
    "tenant_hi-state.html": "State of Hawaiʻi", "tenant_nyc.html": "New York City", "tenant_nys.html": "New York State",
    # world-center city tenants (Jimmy 2026-06-23: going global — keep + link all)
    "tenant_london.html": "London", "tenant_tokyo.html": "Tokyo",
    "tenant_hongkong.html": "Hong Kong SAR", "tenant_singapore.html": "Singapore",
    "tenant_zurich.html": "Zürich", "tenant_frankfurt.html": "Frankfurt",
    "tenant_paris.html": "Paris", "tenant_dubai.html": "Dubai",
    "tenant_liverpool.html": "Liverpool",
    "jurisdictions.html": "All governments →",
}
# Citizen-first IA: organized around what a voting community member needs to participate —
# know your officials, follow the money, read the record. (Testify/Take-action lead via the CTA + a Participate link.)
NAV_GROUPS = [
    # FIRST: pick a government. Tenant-switching is the primary nav so the reports aren't Maui-locked —
    # from any page you can jump to any tenant's overview (Jimmy 2026-06-16: "stop the Maui-focused nav").
    # World-center tenants added 2026-06-23 (Jimmy: going global — keep + link all).
    ("Governments", ["tenant_12stonescharter.html", "tenant_hi-maui.html", "tenant_hi-honolulu.html", "tenant_hi-hawaii.html",
                     "tenant_hi-kauai.html", "tenant_hi-state.html", "tenant_nyc.html", "tenant_nys.html",
                     "tenant_london.html", "tenant_tokyo.html", "tenant_hongkong.html", "tenant_singapore.html",
                     "tenant_zurich.html", "tenant_frankfurt.html", "tenant_paris.html", "tenant_dubai.html",
                     "tenant_liverpool.html", "jurisdictions.html"]),
    ("Your Officials", ["officials_scorecard.html", "money_behind_officials.html", "ka_leo_voice.html"]),
    ("Follow the Money", ["county_dashboard.html", "patterns_money_x_votes.html", "contracts_x_donors.html",
                          "lobby_money_watch.html", "maui_contract_awards.html", "statewide_money_patterns.html",
                          "wildfire_recovery_watch.html", "rebuild_first.html", "money_holysee.html"]),
    ("The Record", ["n53_engine.html", "archive.html", "testimony_record.html", "testimony_money.html", "parity_check.html", "accountability_record.html",
                    "sole_source_watch.html", "commission_antitrust.html", "bill9_bill9_testimony_scan.html",
                    "charter_application.html", "lege_legislator_scorecard.html", "datasets.html", "feature_board.html"]),
    # The 12 Stones Sovereign Charter crosswalked to each tenant's full legal hierarchy up
    # through the Holy See. Leads with the new per-tenant crosswalk engine (crosswalk_<id>.html);
    # the King-civic charter/budget/code/law reference pages follow (full paths, resolve on both servers).
    ("Charter & Law", ["crosswalk_state.html", "crosswalk_maui.html", "crosswalk_honolulu.html",
                       "crosswalk_hawaii.html", "crosswalk_kauai.html", "crosswalk_nys.html",
                       "crosswalk_nyc.html", "crosswalk_liverpool.html", "crosswalk_holysee.html",
                       # unique non-crosswalk reference pages (real budget data + the publish loop)
                       "king/civic/templates/budget-transparency/Budget%20Transparency.html",
                       "king/civic/templates/agenda-explainer/Agenda%20Explainer.html",
                       "king/civic/templates/title19-service/Title19%20Service.html",
                       "king/civic/templates/title16-service/Title16%20Service.html",
                       "king/civic/templates/title18-service/Title18%20Service.html",
                       "king/civic/templates/title03-service/Title3%20Service.html",
                       "king/civic/templates/title05-service/Title5%20Service.html",
                       "king/civic/templates/title14-service/Title14%20Service.html",
                       "king/civic/templates/title10-service/Title10%20Service.html",
                       "king/civic/templates/title12-service/Title12%20Service.html",
                       "king/civic/templates/title20-service/Title20%20Service.html",
                       "king/civic/templates/title06-service/Title6%20Service.html",
                       "king/civic/templates/title08-service/Title8%20Service.html",
                       "king/civic/templates/title09-service/Title9%20Service.html",
                       "king/civic/templates/title11-service/Title11%20Service.html",
                       "king/civic/templates/title13-service/Title13%20Service.html",
                       "king/civic/templates/title22-service/Title22%20Service.html",
                       "king/civic/templates/title01-service/Title1%20Service.html",
                       "king/civic/templates/title02-service/Title2%20Service.html"]),
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
    ".gn-here{font-size:11px;color:#8a8674;margin-right:12px;white-space:nowrap;align-self:center}.gn-here b{color:#d9b24c}"
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

# Tenant-aware nav: the dropdown groups follow the ACTIVE tenant (Jimmy 2026-06-16: "pick a tenant and adjust"
# — the nav was Maui-centric). Each group is a set of REPORT CLASSES; nav_bar resolves them to the current
# tenant's files from the ONE registry. Pick a different government (the Governments group / the pulldown) and
# you land on its page, where the nav re-resolves to that tenant. Non-tenant pages default to the home tenant.
def _esc(s): return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
NAV_GROUP_CLASSES = [
    ("Your Officials", ["govern", "money"]),
    ("Follow the Money", ["money", "contracts", "crossref", "federal", "audit"]),
    ("The Record", ["minutes", "agendas", "charter"]),
]
_HOME_TENANT = "hi-maui"
def _tenant_of(current):
    """Which tenant a flat filename belongs to (registry rev map or tenant_<id>.html); home tenant otherwise."""
    rev, byclass, treg, order = _switcher_maps()
    cf = (current or "").replace("/", "_")
    if cf in rev: return rev[cf][2]
    m = re.match(r"tenant_(.+)\.html$", cf)
    if m and treg and m.group(1) in treg: return m.group(1)
    return _HOME_TENANT

_NAVMAP_JSON = None
def _navmap_json():
    """{tid:{name, groups:[[glabel,[[linklabel,file],...]],...]}} — drives the client-side nav re-resolve so the
    bar follows the tenant the visitor PICKED (localStorage govos.tenant), on EVERY page, not just Maui."""
    global _NAVMAP_JSON
    if _NAVMAP_JSON is not None: return _NAVMAP_JSON
    rev, byclass, treg, order = _switcher_maps()
    m = {}
    for tid in treg:
        gs = []
        for glabel, classes in NAV_GROUP_CLASSES:
            seen = set(); links = []
            for ck in classes:
                for (t, _n, f) in byclass.get(ck, []):
                    if t == tid and f and f not in seen:
                        seen.add(f); links.append([_CLABELS.get(ck, ck), f])
            if links: gs.append([glabel, links])
        m[tid] = {"name": treg[tid]["name"], "groups": gs}
    _NAVMAP_JSON = json.dumps(m, ensure_ascii=False)
    return _NAVMAP_JSON

def _nav_tenant_js():
    """Re-resolve the nav to the visitor's PICKED tenant (persisted) on load, and persist on any government pick."""
    return ('<script id="navmap">window.__NAV__=%s;</script>'
        '<script>(function(){var N=window.__NAV__||{},nav=document.querySelector(".govos-nav");if(!nav)return;'
        'var t;try{t=localStorage.getItem("govos.tenant");}catch(e){}if(!t||!N[t])t=nav.getAttribute("data-tenant");'
        'var d=N[t];if(d){var hb=nav.querySelector(".gn-here b");if(hb)hb.textContent=d.name;'
        'var by={};(d.groups||[]).forEach(function(g){by[g[0]]=g[1];});'
        'nav.querySelectorAll(".gn-group[data-g]").forEach(function(grp){var gl=grp.getAttribute("data-g"),L=by[gl],p=grp.querySelector(".gn-panel");'
        'if(L&&p){p.innerHTML=L.map(function(x){return "<a href=\\""+x[1]+"\\">"+x[0]+"</a>";}).join("");grp.style.display="";}'
        'else{grp.style.display="none";}});}'
        'nav.querySelectorAll("a[href^=\\"tenant_\\"]").forEach(function(a){a.addEventListener("click",function(){'
        'var m=(this.getAttribute("href")||"").match(/tenant_(.+)\\.html/);if(m){try{localStorage.setItem("govos.tenant",m[1]);}catch(e){}}});});'
        '})();</script>') % _navmap_json()

def nav_bar(current):
    """Professional grouped top-bar, TENANT-AWARE: groups resolve to the active tenant's pages via the registry."""
    rev, byclass, treg, order = _switcher_maps()
    cf = (current or "").replace("/", "_")
    tid = _tenant_of(current)
    tname = (treg.get(tid, {}) or {}).get("name", "Maui County") if treg else "Maui County"
    groups = ""
    if treg:
        # Governments — the tenant picker (lands you on a tenant; nav then re-resolves to it).
        # The 12 Stones Charter LEADS as the apex tenant — the sovereign instrument the county tenants sit under.
        gv = '<a class="%s" href="tenant_12stonescharter.html">&#9878; 12 Stones Charter</a>' % ("cur" if cf == "tenant_12stonescharter.html" else "")
        gv += "".join('<a class="%s" href="tenant_%s.html">%s</a>' % ("cur" if cf == ("tenant_%s.html" % t) else "", t, _esc(treg[t]["name"])) for t in treg)
        gv += '<a href="jurisdictions.html">All governments &rarr;</a>'
        groups += '<div class="gn-group"><button class="gn-top">Governments<span class="ar">&#9662;</span></button><div class="gn-panel">%s</div></div>' % gv
        # tenant-aware groups, resolved from the registry for THIS tenant
        for glabel, classes in NAV_GROUP_CLASSES:
            seen = set(); links = ""
            for ck in classes:
                for (t, _name, f) in byclass.get(ck, []):
                    if t == tid and f and f not in seen:
                        seen.add(f)
                        links += '<a class="%s" href="%s">%s</a>' % ("cur" if f == cf else "", f, _esc(_CLABELS.get(ck, ck)))
            if links:
                groups += ('<div class="gn-group" data-g="%s"><button class="gn-top">%s<span class="ar">&#9662;</span></button>'
                           '<div class="gn-panel">%s</div></div>') % (glabel, glabel.replace("&", "&amp;"), links)
    else:
        # registry unavailable — fall back to the static groups so the nav still renders
        for glabel, files in NAV_GROUPS:
            links = "".join('<a class="%s" href="%s">%s</a>' % ("cur" if f == current else "", f, NAV_LABEL.get(f, f)) for f in files)
            groups += ('<div class="gn-group"><button class="gn-top">%s<span class="ar">&#9662;</span></button>'
                       '<div class="gn-panel">%s</div></div>') % (glabel.replace("&", "&amp;"), links)
    here = '<span class="gn-here">viewing: <b>%s</b></span>' % _esc(tname)
    jc = " cur" if current == "jurisdictions.html" else ""
    ac = " cur" if current == "agendas.html" else ""
    return (NAV_CSS +
            '<nav class="govos-nav" data-tenant="%s">' % tid +
            '<a class="gn-brand" href="reports.html"><span class="mk">&#10022;</span>'
            '<b>govOS</b><span class="sub">Kilo Aupuni</span></a>'
            '<button class="gn-burger" aria-label="Menu">&#9776;</button>'
            '<div class="gn-menu">'
            + here +
            # TENANT-BY-TENANT LOGIC (Jimmy 2026-06-20 — nav frustration): the top bar carries ONLY
            # platform-wide pages + universal actions, so nothing here is tenant-specific and it can't be
            # wrong about "viewing <tenant>". The CURRENT tenant's own reports (Agendas, Title 19, Officials,
            # Money, Minutes, Oversight…) are the Government/View pulldown (inject_switcher) — the single
            # tenant nav, which re-resolves to whichever tenant you're viewing. Title 19 here is the generic
            # cross-tenant SYSTEM page; each tenant's own calculators live on its govOS page via the pulldown.
            '<div class="gn-group"><button class="gn-top">Across govOS<span class="ar">&#9662;</span></button><div class="gn-panel">'
            + '<a class="%s" href="jurisdictions.html">Jurisdictions — all governments</a>' % jc
            + '<a class="%s" href="datasets.html">Open data</a>' % (" cur" if current == "datasets.html" else "")
            + '<a class="%s" href="agenda_explainer.html">Agenda explainer</a>' % (" cur" if current=="agenda_explainer.html" else "")
            + '<a class="%s" href="sage_bridge.html">Sage</a>' % (" cur" if current=="sage_bridge.html" else "")
            + '<a class="%s" href="olelo_glossary.html">&#699;&#332;lelo</a>' % (" cur" if current=="olelo_glossary.html" else "")
            + '<a href="king/civic/templates/title19-system/Title19%20System.html">Title 19 system</a>'
            + '</div></div>'
            + '<a class="gn-lead%s" href="testify.html">&#9878; Testify</a>' % (' cur' if current == 'testify.html' else '')
            + '<a class="gn-link%s" href="request_records.html">Request Records</a>' % (" cur" if current == "request_records.html" else "")
            + '<a class="gn-cta" href="take_action.html">Take part</a>'
            '</div></nav>' + NAV_JS + _nav_tenant_js())

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
_CLABELS = {}     # class_key -> human label (populated by _switcher_maps; used by the tenant-aware nav)
def _switcher_maps():
    """(rev {file->(class_key,class_label,tid)}, byclass {class_key->[(tid,name,file|None)]},
        treg {tid->{name, reports:[[label,file],...]}}, order [class_key,...]) — all from the ONE registry."""
    global _SWITCHER, _CLABELS
    if _SWITCHER is not None: return _SWITCHER
    rev, byclass, treg, order = {}, {}, {}, []
    try:
        reg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tenant_registry.json"), encoding="utf-8"))
        clabels = {c["key"]: c["label"] for c in reg.get("report_classes", [])}
        _CLABELS = clabels
        order = [c["key"] for c in reg.get("report_classes", [])]
        for c in reg.get("report_classes", []):
            k = c["key"]; byclass[k] = []
            for t in reg.get("civic_tenants", []):
                files = t["reports"].get(k) or []
                # build_site flattens published subdir paths ("lege/x.html" -> "lege_x.html"); match that
                # so the switcher chips never 404 (the seed-drift/flatten gotcha).
                f = files[0].replace("/", "_") if files else None
                byclass[k].append((t["id"], t["name"], f))
                if f: rev.setdefault(f, (k, clabels.get(k, k), t["id"]))
        for t in reg.get("civic_tenants", []):
            reports = []
            for k in order:
                files = t["reports"].get(k) or []
                if files:
                    reports.append([clabels.get(k, k), files[0].replace("/", "_")])
            treg[t["id"]] = {"name": t["name"], "reports": reports}
    except Exception:
        pass
    _SWITCHER = (rev, byclass, treg, order)
    return _SWITCHER

_SWITCH_CSS = ("<style id=tenant-switch-css>.tenant-nav{display:flex;align-items:center;gap:10px;flex-wrap:wrap;"
    "max-width:1100px;margin:10px auto 0;padding:9px 14px;background:#eef2f7;border:1px solid #bacde6;border-radius:11px;"
    "font-family:'Segoe UI',system-ui,sans-serif}.tn-grp{display:flex;align-items:center;gap:6px}"
    ".tn-lbl{font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#5b6e86;font-weight:600}"
    ".tenant-nav select{font-family:inherit;font-size:13px;color:#00356b;background:#fff;border:1px solid #bacde6;"
    "border-radius:8px;padding:5px 9px;cursor:pointer;max-width:230px}.tenant-nav select:hover{border-color:#00356b}"
    ".tn-here{font-size:11px;color:#41536b}.tn-here b{color:#00356b}</style>")

def inject_switcher(html, current_file):
    """Inject the TENANT-AWARE pulldown nav (Jimmy 2026-06-16 #1): a 'Government' select that switches tenant —
    staying on the SAME report class where that tenant has it — and a 'View' select that lists the CURRENT
    tenant's lenses (repopulated client-side per government). Native <select>s: mobile-first, no popups, works
    static (GitHub Pages) + king-local. Reusable component (the same skill ports to Studio)."""
    rev, byclass, treg, order = _switcher_maps()
    if not treg:
        return html
    cf = (current_file or "").replace("/", "_")
    info = rev.get(cf)
    cur_tid, cur_class = (info[2], info[0]) if info else (None, None)
    if cur_tid is None:
        m = re.match(r"tenant_(.+)\.html$", cf)
        if m and m.group(1) in treg:
            cur_tid = m.group(1)
    tclass = {k: {t: f for t, _n, f in v if f} for k, v in byclass.items()}
    data = json.dumps({"treg": treg, "tclass": tclass, "cur_tid": cur_tid,
                       "cur_class": cur_class, "cur_file": cf}, ensure_ascii=False)
    # The 12 Stones Charter leads the switcher as the apex tenant (resolves to tenant_12stonescharter.html;
    # not a registry tenant, so fill() falls to its overview option gracefully).
    gov_opts = '<option value="12stonescharter">⚖ 12 Stones Charter</option>' + \
        "".join('<option value="%s"%s>%s</option>' % (tid, " selected" if tid == cur_tid else "", treg[tid]["name"]) for tid in treg)
    here = (('<span class="tn-here">on <b>%s</b></span>' % treg[cur_tid]["name"]) if cur_tid else
            '<span class="tn-here">pick a government to begin</span>')
    widget = (
        '<div class="tenant-nav" role="navigation" aria-label="Government navigation">'
        '<div class="tn-grp"><span class="tn-lbl">Government</span>'
        '<select id="tnav-gov" aria-label="Choose a government">%s%s</select></div>'
        '<div class="tn-grp"><span class="tn-lbl">View</span>'
        '<select id="tnav-view" aria-label="Choose a report for this government"></select></div>%s</div>'
        '<script>(function(){var D=%s;var gov=document.getElementById("tnav-gov"),'
        'view=document.getElementById("tnav-view");'
        'function fill(t){view.innerHTML="";var rs=(D.treg[t]||{}).reports||[];'
        'if(!rs.length){var o=document.createElement("option");o.textContent="overview";o.value="tenant_"+t+".html";view.appendChild(o);return;}'
        'rs.forEach(function(r){var o=document.createElement("option");o.textContent=r[0];o.value=r[1];'
        'if(r[1]===D.cur_file)o.selected=true;view.appendChild(o);});}'
        'if(D.cur_tid)fill(D.cur_tid);'
        'gov.addEventListener("change",function(){var t=this.value,dest;'
        'try{localStorage.setItem("govos.tenant",t);}catch(e){}'
        'if(D.cur_class&&D.tclass[D.cur_class]&&D.tclass[D.cur_class][t])dest=D.tclass[D.cur_class][t];'
        'else dest="tenant_"+t+".html";location.href=dest;});'
        'view.addEventListener("change",function(){if(this.value)location.href=this.value;});})();</script>'
    ) % (("" if cur_tid else '<option value="" selected disabled>Choose a government…</option>'),
         gov_opts, here, data)
    sw = (_SWITCH_CSS if "tenant-switch-css" not in html else "") + widget
    m = re.search(r"</nav>", html, re.I)        # right under the top nav
    return (html[:m.end()] + "\n" + sw + html[m.end():]) if m else (sw + html)

# ── "Follow the money" for the ACTIVE tenant (Jimmy 2026-06-16: not Maui-centric). go.html's money
#    section is rebuilt client-side from this registry-driven map, per the government you pick. ──
_FTM_CLASSES = [("money", "Money behind them", "Who funds each decider — public campaign-finance record"),
                ("contracts", "Contracts &amp; spending", "Who this government pays — contract awards"),
                ("crossref", "Money &times; votes", "Where giving and deciding line up — framed as questions"),
                ("federal", "Federal dollars", "Federal money flowing into the jurisdiction"),
                ("audit", "Audit balance", "The money&times;votes equation scorecard")]
def _ftm_script(prefix=""):
    """<script>window.__FTM__=…</script> — per-tenant money trail from the ONE registry. prefix='../' for
    the /king/ copy so links resolve up a level there; '' for the root front door."""
    _rev, byclass, treg, _order = _switcher_maps()
    tenants, torder = {}, []
    for tid in treg:
        torder.append(tid); trail = []
        for ck, lbl, blurb in _FTM_CLASSES:
            for (t, _n, f) in byclass.get(ck, []):
                if t == tid and f:
                    trail.append([lbl, prefix + f, blurb]); break
        tenants[tid] = {"name": treg[tid]["name"], "trail": trail}
    return '<script id="ftm-data">window.__FTM__=%s;</script>' % json.dumps({"order": torder, "tenants": tenants}, ensure_ascii=False)

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
    # stray accents the scan caught on jurisdictions (green/orange) -> ok-green / gold
    ("#43d39e", "#1f8a5b"), ("#e0863a", "#b8860b"),
    # a11y: faint small-text was ~4.0:1 on white -> darken to clear WCAG AA 4.5:1 (runs LAST so it
    # also catches the #6d7f97 produced by the ink pairs above). UI/UX audit item 13.
    ("#6d7f97", "#5b6e86"),
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

# Typography unify (Jimmy 2026-06-19: "make the site like the home page"). The flat civic report pages were
# authored in Georgia serif; the canonical home page (index.html) is Segoe UI Variable SANS with JetBrains Mono
# for machine values. Swap ONLY the literal serif BODY stack -> the home-page sans stack. The explicit
# Consolas/JetBrains mono declarations (machine values) are untouched, so the brand's "mono for every machine
# value" rule holds. Applied ONLY in the flat-civic-page loops below — NOT in recolor_tree — so the King
# ceremonial register (--font-serif-display in styles.css) keeps its serif. Value-only, never markup/JS/data.
_FONT_SANS = "'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif"
_FONT_SWAPS = [
    ("Georgia,'Iowan Old Style',serif", _FONT_SANS),
    ("Georgia, 'Iowan Old Style', serif", _FONT_SANS),
    ("Georgia,serif", _FONT_SANS),
    ("Georgia, serif", _FONT_SANS),
]
def unify_font(html):
    for old, new in _FONT_SWAPS:
        html = html.replace(old, new)
    return html

_VIEWPORT = ('<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
             '<meta name="theme-color" content="#00356b">')
# the no-zoom heal: keep wide content (tables/images/pre) inside the viewport so the PAGE never overflows on a
# phone — wide tables scroll within themselves instead of pushing the page sideways.
_MOBILE_CSS = ('<style id="mobile-heal">img,video,svg{max-width:100%;height:auto}'
               'table,pre{max-width:100%}@media(max-width:680px){html{overflow-x:hidden}'
               'table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}'
               'td,th{word-break:break-word;overflow-wrap:anywhere}pre{white-space:pre-wrap}}</style>')
def ensure_mobile(html):
    """HEAL: every page readable on iPhone/iPad without zoom — inject the viewport meta AND the no-overflow CSS
    if missing. One place, every access point; no per-generator fixes, no double systems."""
    add = ("" if "width=device-width" in html else _VIEWPORT) + ("" if 'id="mobile-heal"' in html else _MOBILE_CSS)
    if not add:
        return html
    for pat in (r"<meta\s+charset[^>]*>", r"<head[^>]*>", r"<!doctype[^>]*>"):
        m = re.search(pat, html, re.I)
        if m:
            return html[:m.end()] + add + html[m.end():]
    return add + html

def ensure_civic_chrome(html):
    """Unify look to the home page (Jimmy 2026-06-20 'wire civic shell — unify look, KEEP the nav'):
    inject civic_shell's home-page design TOKENS + the shared FOOTER. Deliberately does NOT add the
    cs- header — the page's existing gn- govos-nav stays the only navbar (no double-nav). Idempotent
    (skips if already shelled); markup/color only, never touches data or scripts. Single source = civic_shell.py."""
    if not _civic_shell or "cs-foot" in html:
        return html
    sb = _civic_shell.style_block()                       # :root --cs-* tokens + namespaced cs- chrome CSS
    m = re.search(r"</head>", html, re.I)
    if m:
        html = html[:m.start()] + sb + html[m.start():]
    else:
        mb = re.search(r"<body[^>]*>", html, re.I)
        if mb:
            html = html[:mb.end()] + sb + html[mb.end():]
    foot = _civic_shell.footer_html()                     # the shared "govOS · 12 Stones Global" footer
    mb = re.search(r"</body>", html, re.I)
    if mb:
        html = html[:mb.start()] + foot + html[mb.start():]
    else:
        html = html + foot
    return html

def recolor_tree(root):
    """The ONE heal pass over a built tree: recolor to Yale-blue AND ensure mobile-viewport, in place, every
    .html (+ .css recolor). Skips .js/.json (no logic touched). Same pass for public site/ and (via king_recolor)
    the private King — one concept, all access points. The heal improves each page toward the standard each run."""
    n = 0
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            ext = fn.rsplit(".", 1)[-1].lower()
            if ext not in ("html", "css"):
                continue
            p = os.path.join(dp, fn)
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
                r = recolor(t)
                if ext == "html":
                    r = ensure_mobile(r)
                    if os.path.relpath(p, root).split(os.sep)[0] != "king":
                        r = unify_font(r)   # match the home page: flat civic pages -> Segoe sans (King ceremonial register keeps its serif)
                        r = ensure_civic_chrome(r)   # unify look to the home page: civic_shell tokens + shared footer (gn- nav stays)
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
    # extra per-tenant pages: copied + nav-injected, reached from the jurisdictions hub (not nav pills).
    # entity_*.html dossiers have dynamic names -> glob them in (+ the dossier index).
    import glob as _glob
    _dyn = ["entity_index.html"] + sorted(os.path.basename(p) for p in _glob.glob(os.path.join(MAUIOS, "entity_*.html")))
    for rel in EXTRA_PAGES + [d for d in _dyn if d not in EXTRA_PAGES]:
        src = os.path.join(MAUIOS, rel)
        if os.path.exists(src):
            with open(os.path.join(SITE, rel), "w", encoding="utf-8", newline="\n") as f:
                _h = inject_nav(open(src, encoding="utf-8", errors="replace").read(), rel)
                _h = inject_switcher(_h, rel)      # per-tenant report: choose a government switcher
                _h = add_narrative(_h, rel)
                _h = add_records_cta(_h, rel)
                _h = add_olelo_notice(_h)
                f.write(_h)
    _present_data = []
    for rel in DATA:
        src = os.path.join(MAUIOS, rel)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(SITE, "data", os.path.basename(rel)))
            _present_data.append((os.path.basename(rel), src))

    # [open-data] DCAT catalog (data.json) + a human Open Data front door (datasets.html). Indexes ONLY
    # the public DATA files above — the raw records behind every dashboard, downloadable. Defeats the
    # "you made it up" critique; matches Socrata/Project-Open-Data norms. Private back end is never listed.
    try:
        import time as _t
        _dcat = {"@context": "https://project-open-data.cio.gov/v1.1/schema/catalog.jsonld",
                 "@type": "dcat:Catalog",
                 "conformsTo": "https://project-open-data.cio.gov/v1.1/schema",
                 "describedBy": "https://project-open-data.cio.gov/v1.1/schema/catalog.json",
                 "dataset": []}
        _rows = []
        for _base, _src in _present_data:
            _meta = DATASET_META.get(_base, (_base.replace(".json", "").replace("_", " ").title(),
                                             "Public civic dataset behind the govOS dashboards.", ["civic"], "govOS"))
            _title, _desc, _kw, _source = _meta
            _mod = _t.strftime("%Y-%m-%d", _t.localtime(os.path.getmtime(_src)))
            _dcat["dataset"].append({
                "@type": "dcat:Dataset", "title": _title, "description": _desc,
                "identifier": "govos/" + _base, "modified": _mod, "accessLevel": "public",
                "keyword": _kw, "license": "https://creativecommons.org/licenses/by/4.0/",
                "publisher": {"@type": "org:Organization", "name": "12 Stones Global / govOS"},
                "distribution": [{"@type": "dcat:Distribution", "downloadURL": "data/" + _base,
                                  "mediaType": "application/json", "format": "JSON"}]})
            _rows.append('<div class="ds"><div class="dst">' + _esc(_title) +
                         ' <a class="dl" href="data/' + _base + '" download>↓ JSON</a></div>'
                         '<div class="dsd">' + _esc(_desc) + '</div>'
                         '<div class="dsm">source: ' + _esc(_source) + ' · updated ' + _mod +
                         ' · CC BY 4.0</div></div>')
        with open(os.path.join(SITE, "data.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(_dcat, f, ensure_ascii=False, indent=1)
        _ds_body = (
            '<div style="max-width:860px;margin:0 auto;padding:1.2rem 1rem">'
            '<h1 style="color:#0e4a84">Open Data</h1>'
            '<p class="lead">The raw public records behind every dashboard — downloadable, sourced, and machine-readable. '
            'We publish the data so you never have to take our word for it. Money and votes are offered as questions, '
            'never verdicts; every figure traces to a public filing.</p>'
            '<p class="lead">Machine catalog (DCAT / Project Open Data): '
            '<a class="dl" href="data.json" download>data.json</a> — point any open-data tool at it.</p>'
            '<style>.ds{border:1px solid #d6e2f0;border-radius:10px;padding:.7rem .9rem;margin:.6rem 0;background:#fff}'
            '.dst{font-weight:700;color:#0e4a84}.dsd{font-size:.92rem;margin:.25rem 0}'
            '.dsm{font-size:.78rem;color:#5a6b7b}.dl{font-size:.82rem;color:#0e4a84;text-decoration:none;'
            'border:1px solid #0e4a84;border-radius:6px;padding:.05rem .4rem;margin-left:.4rem}</style>'
            + "".join(_rows) +
            '<h2 style="color:#0e4a84;margin-top:1.4rem">Accessibility & sourcing</h2>'
            '<p class="lead">We build mobile-first, aim for WCAG 2.1 AA (high-contrast text, keyboard-navigable, '
            'labeled links), and source civic content only — we link to the record and never invent law or figures. '
            'Found a barrier or an error? Use Request Records to tell us and we will fix it.</p></div>')
        _ds_html = "<!doctype html><html lang=en><head><meta charset=utf-8>" \
                   "<meta name=viewport content=\"width=device-width,initial-scale=1\">" \
                   "<title>Open Data — govOS</title></head><body>" + _ds_body + "</body></html>"
        _ds_html = add_olelo_notice(inject_nav(_ds_html, "datasets.html"))
        with open(os.path.join(SITE, "datasets.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(_ds_html)
        print("  + datasets.html + data.json (DCAT): %d public datasets indexed" % len(_rows))
    except Exception as _e:
        print("  ! open-data catalog skipped: %s" % str(_e)[:120])

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
        _goraw = open(_go, encoding="utf-8").read()
        # inject the active-tenant "follow the money" map (root paths) before writing the root launcher
        _goroot = _goraw.replace("</head>", _ftm_script("") + "</head>", 1) if "ftm-data" not in _goraw else _goraw
        with open(os.path.join(SITE, "go.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(_goroot)
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
                if h.startswith(("http", "#", "../", "mailto:", "/")):
                    return 'href="%s"' % h
                if h == "king/":
                    return 'href="./"'
                if h in ("./", "."):
                    return 'href="../"'
                return 'href="../%s"' % h    # root-level govOS page -> up one from /king/
            _kgo = re.sub(r'href="([^"]*)"', _king_href, _goraw)
            # /king/ copy: money-trail links resolve up one level (the civic pages live at site root)
            _kgo = _kgo.replace("</head>", _ftm_script("../") + "</head>", 1) if "ftm-data" not in _kgo else _kgo
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
    # [orphan-heal 2026-06-17] Civic pages that are built + useful but weren't carded anywhere
    # (calendars, fire-recovery, agenda patterns) — wire them into the hub so nothing useful is orphaned.
    _MORE = [
        ("meetings_calendar.html",     "Meeting Calendars",        "Upcoming public meetings across every government."),
        ("meetings_maui.html",         "Meetings — Maui",          "Maui County meeting calendar."),
        ("meetings_honolulu.html",     "Meetings — Honolulu",      "City &amp; County of Honolulu meeting calendar."),
        ("meetings_hawaii.html",       "Meetings — Hawaiʻi",  "Hawaiʻi County meeting calendar."),
        ("meetings_kauai.html",        "Meetings — Kauaʻi",   "Kauaʻi County meeting calendar."),
        ("meetings_nyc.html",          "Meetings — New York",      "New York meeting calendar."),
        ("rebuild_first.html",         "Who Rebuilt First",        "Lahaina/Kula fire-recovery permit line — who got permits first."),
        ("agenda_patterns.html",       "Agenda Patterns",          "Recurring themes &amp; items across agendas over time."),
        ("bfed_agenda_today.html",     "Budget &amp; Finance — Today",  "Today’s Budget &amp; Finance Committee agenda."),
        ("bfed_eligibility_today.html","BFED Eligibility — Today", "Today’s budget eligibility view."),
        ("datasets.html",              "Open Data",                "The raw public records behind every dashboard — downloadable JSON + a DCAT catalog. Don’t take our word for it."),
        ("feature_board.html",         "Build the Software",       "Request how the county’s software should work and vote on others’ ideas — sorted by department &amp; agenda priority. Free signup; county-private tier too."),
    ]
    more_cards = "".join(
        f'<a class="card" href="{fn}"><div class="t">{name}</div><div class="b">{blurb}</div></a>'
        for fn, name, blurb in _MORE if os.path.exists(os.path.join(SITE, fn)))
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
 <a class="card" href="tenant_12stonescharter.html" style="grid-column:1/-1;border-left:5px solid #0f4d92"><div class="t">&#9878; The 12 Stones Sovereign Charter</div><div class="b">The apex tenant &middot; the sovereign instrument every government below sits under &middot; one blood, no gap in the law</div></a>
 <a class="card" href="tenant_hi-state.html"><div class="t">State of Hawai&#699;i</div><div class="b">Campaign money &middot; legislator votes &middot; state contracts &middot; federal dollars</div></a>
 <a class="card" href="tenant_hi-maui.html"><div class="t">Maui County</div><div class="b">Agendas &middot; votes &middot; donors &middot; contracts &middot; federal &middot; money&times;votes</div></a>
 <a class="card" href="tenant_hi-hawaii.html"><div class="t">Hawai&#699;i County</div><div class="b">Agendas &middot; campaign money (county slice)</div></a>
 <a class="card" href="tenant_hi-kauai.html"><div class="t">Kaua&#699;i County</div><div class="b">Agendas &middot; campaign money (county slice)</div></a>
 <a class="card" href="tenant_hi-honolulu.html"><div class="t">City &amp; County of Honolulu</div><div class="b">Agendas &middot; campaign money (county slice)</div></a>
 <a class="card" href="tenant_nyc.html"><div class="t">New York City</div><div class="b">Money &middot; contracts &middot; agendas &middot; money&times;votes</div></a>
 <a class="card" href="tenant_nys.html"><div class="t">New York State</div><div class="b">Money &middot; contracts &middot; agendas &middot; money&times;votes</div></a>
</div>
<div class="eyebrow" style="margin-top:26px">World centers — charter &amp; transparency</div>
<p class="lead">The same govOS lens applied to the world&rsquo;s financial-center cities — each under its own law, all under the shared 12 Stones apex. Charter crosswalks live; more records fill as the engine grows.</p>
<div class="grid">
 <a class="card" href="tenant_london.html"><div class="t">London</div><div class="b">City of London / GLA &middot; charter &#8644; UK law</div></a>
 <a class="card" href="tenant_tokyo.html"><div class="t">Tokyo</div><div class="b">Tokyo Metropolis &middot; charter &#8644; Japanese law</div></a>
 <a class="card" href="tenant_hongkong.html"><div class="t">Hong Kong SAR</div><div class="b">HKSAR &middot; charter &#8644; Basic Law</div></a>
 <a class="card" href="tenant_singapore.html"><div class="t">Singapore</div><div class="b">Republic of Singapore &middot; charter &#8644; law</div></a>
 <a class="card" href="tenant_zurich.html"><div class="t">Z&uuml;rich</div><div class="b">Z&uuml;rich &middot; charter &#8644; Swiss law</div></a>
 <a class="card" href="tenant_frankfurt.html"><div class="t">Frankfurt</div><div class="b">Frankfurt am Main (ECB seat) &middot; charter &#8644; German law</div></a>
 <a class="card" href="tenant_paris.html"><div class="t">Paris</div><div class="b">Paris &middot; charter &#8644; French law</div></a>
 <a class="card" href="tenant_dubai.html"><div class="t">Dubai</div><div class="b">Dubai + DIFC &middot; charter &#8644; UAE law</div></a>
 <a class="card" href="tenant_liverpool.html"><div class="t">Liverpool</div><div class="b">Village of Liverpool, NY &middot; charter &#8644; law</div></a>
</div>
<div class="eyebrow" style="margin-top:30px">All dashboards</div>
<div class="grid">{cards}</div>
<div class="eyebrow" style="margin-top:30px">Calendars, recovery &amp; patterns</div>
<div class="grid">{more_cards}</div>
<div class="eyebrow" style="margin-top:30px">Charter, law &amp; services</div>
<div class="grid">
 <a class="card" href="king/civic/templates/title19-system/Title19%20System.html"><div class="t">Title 19 System — through the Charter</div><div class="b">One front door to every Title 19 tool + the 12 Stones Charter lens.</div></a>
 <a class="card" href="king/civic/templates/mauios-gov/MauiOS%20Government%20OS.html"><div class="t">govOS — Charter Hub</div><div class="b">The charter ⇄ law reference layer: budget, county code, state law, crosswalks, services.</div></a>
 <a class="card" href="king/civic/templates/title19-service/Title19%20Service.html"><div class="t">Title 19 — Plain-Language Service (free)</div><div class="b">Live parcel lookup + zoning navigator. No account.</div></a>
 <a class="card" href="king/civic/templates/title19-substantial-change/Title19%20Substantial%20Change.html"><div class="t">Title 19 — Substantial Change Procedure</div><div class="b">When a change to an approved project needs a new public hearing — with a decision aid.</div></a>
 <a class="card" href="king/civic/templates/title16-service/Title16%20Service.html"><div class="t">Title 16 — Buildings &amp; Permits (free)</div><div class="b">Building/electrical/plumbing permits, codes, enforcement, disaster-recovery track.</div></a>
 <a class="card" href="king/civic/templates/title18-service/Title18%20Service.html"><div class="t">Title 18 — Subdivisions (free)</div><div class="b">Preliminary &amp; final plat process, fees, how it ties to zoning, enforcement.</div></a>
 <a class="card" href="king/civic/templates/title03-service/Title3%20Service.html"><div class="t">Title 3 — Real Property Tax (free)</div><div class="b">Assessment, classes, exemptions, appeals — plain language.</div></a>
 <a class="card" href="king/civic/templates/title05-service/Title5%20Service.html"><div class="t">Title 5 — Business Licenses (free)</div><div class="b">County business licensing &amp; permits, plain language.</div></a>
 <a class="card" href="king/civic/templates/title14-service/Title14%20Service.html"><div class="t">Title 14 — Water / Public Services (free)</div><div class="b">Water service, rates, meters, public utilities — plain language.</div></a>
 <a class="card" href="king/civic/templates/title10-service/Title10%20Service.html"><div class="t">Title 10 — Vehicles &amp; Traffic (free)</div><div class="b">Traffic code, parking, vehicles — plain language.</div></a>
 <a class="card" href="king/civic/templates/title12-service/Title12%20Service.html"><div class="t">Title 12 — Streets &amp; Sidewalks (free)</div><div class="b">Streets, sidewalks, public ways &amp; encroachments — plain language.</div></a>
 <a class="card" href="king/civic/templates/title20-service/Title20%20Service.html"><div class="t">Title 20 — Environmental Protection (free)</div><div class="b">Environmental protection, recycling, water quality — plain language.</div></a>
 <a class="card" href="king/civic/templates/title06-service/Title6%20Service.html"><div class="t">Title 6 — Animals (free)</div><div class="b">Animal control, licensing &amp; welfare — plain language.</div></a>
 <a class="card" href="king/civic/templates/title08-service/Title8%20Service.html"><div class="t">Title 8 — Health &amp; Safety (free)</div><div class="b">Public health &amp; safety code — plain language.</div></a>
 <a class="card" href="king/civic/templates/title09-service/Title9%20Service.html"><div class="t">Title 9 — Public Peace &amp; Welfare (free)</div><div class="b">Public peace, morals &amp; welfare — plain language.</div></a>
 <a class="card" href="king/civic/templates/title11-service/Title11%20Service.html"><div class="t">Title 11 — Public Transit (free)</div><div class="b">County public transit &amp; transportation — plain language.</div></a>
 <a class="card" href="king/civic/templates/title13-service/Title13%20Service.html"><div class="t">Title 13 — Parks &amp; Recreation (free)</div><div class="b">County parks, beaches &amp; recreation — plain language.</div></a>
 <a class="card" href="king/civic/templates/title22-service/Title22%20Service.html"><div class="t">Title 22 — Department of Agriculture (free)</div><div class="b">County Department of Agriculture — plain language.</div></a>
 <a class="card" href="king/civic/templates/title01-service/Title1%20Service.html"><div class="t">Title 1 — General Provisions (free)</div><div class="b">How the Code is organized &amp; applied — plain language.</div></a>
 <a class="card" href="king/civic/templates/title02-service/Title2%20Service.html"><div class="t">Title 2 — Administration &amp; Personnel (free)</div><div class="b">County administration, boards &amp; commissions — plain language.</div></a>
</div>
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
    # [front door = go.html] Jimmy 2026-06-16: the Quad-OS launcher (go.html) is the SAME consistent entry on
    # EVERY surface — public root AND the Tailscale King (king-local mirrors site/index.html below). The civic
    # hub lives on at reports.html (go.html's "govOS — home" card points there). One look, every front door.
    # 12sgi.com HOMEPAGE = the govOS CLIENT signup landing (Jimmy 2026-06-19: "the home page of 12sgi.com
    # = what a govOS client would see to sign up"). go.html stays the PRIVATE launcher at /go.html.
    _landing = os.path.join(SITE, "king", "govos_signup.html")
    _go_built = os.path.join(SITE, "go.html")   # the internal Quad-OS launcher (FTM map injected) — stays at /go.html
    _idx_src = _landing if os.path.exists(_landing) else _go_built
    if os.path.exists(_idx_src):
        _idx_html = open(_idx_src, encoding="utf-8", errors="ignore").read()
        # govos_signup.html is authored for king/ context (uses ../ for root-level paths).
        # When deployed to site/index.html (root), strip the leading ../ so links resolve correctly.
        def _root_href(m):
            h = m.group(1)
            if h.startswith('../'):
                return 'href="%s"' % h[3:]
            return 'href="%s"' % h
        _idx_html = re.sub(r'href="([^"]*)"', _root_href, _idx_html)
        with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
            f.write(_idx_html)
        print("  + index.html = %s (12sgi.com public front door = govOS client signup; go.html stays the private launcher)" % os.path.basename(_idx_src))
    # GitHub Pages custom domain: serve the civic engine (govOS) at 12sgi.com (Jimmy 2026-06-18).
    # The CNAME file in the deployed artifact tells GitHub Pages the custom domain. Written every build
    # (site/ is wiped each run). elementlotus.com = brand (WordPress); 12sgi.com = govOS (this site).
    open(os.path.join(SITE, "CNAME"), "w", encoding="utf-8").write("12sgi.com\n")
    print("  + CNAME = 12sgi.com (GitHub Pages custom domain for govOS)")
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
                            (os.path.join(PROJECT, "reports", "_status", "ram_loop.html"), "ram_loop.html"),
                            (os.path.join(PROJECT, "reports", "_status", "onboard_readiness.html"), "onboard_readiness.html"),
                            (os.path.join(PROJECT, "reports", "_status", "king_message.html"), "king_message.html"),
                            (os.path.join(PROJECT, "reports", "_status", "maui_re_report.html"), "maui_re_report.html")):
            if os.path.exists(_src):
                shutil.copy(_src, os.path.join(KLOCAL, _name))
                print(f"  + king-local OWNER-ONLY: {_name} (private — never public)")
        # [OWNER ONLY] recusal/conflict dollar evidence (the Po behind the public eligibility questions) -
        # king-local/Tailscale ONLY; deliberately NOT in PAGES/EXTRA_PAGES/seed so it never reaches Pages.
        _re = os.path.join(MAUIOS, "recusal_evidence.html")
        if os.path.exists(_re):
            shutil.copy(_re, os.path.join(KLOCAL, "recusal_evidence.html"))
            print("  + king-local OWNER-ONLY: recusal_evidence.html (donor-tie dollar evidence — never public)")
        # [OWNER ONLY] corporate-quad-os private packet (12SGI data room + cap table + deck PDFs) — king-local/Tailscale
        # ONLY; the WHOLE king_private_src/ tree, deliberately NOT in PAGES/EXTRA_PAGES/seed and NOT mirrored to SITE so
        # it never reaches public Pages. Add private pages/docs by dropping them in king_private_src/.
        _priv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "king_private_src")
        if os.path.isdir(_priv):
            shutil.copytree(_priv, KLOCAL, dirs_exist_ok=True)
            print("  + king-local OWNER-ONLY: king_private_src/* (12SGI corporate data room + cap table + docs — never public)")
        # [king-recolor] private pages + King-app .dc components bypass the site recolor above; re-flip any that
        # land in king-local dark (king-extract is volatile). Keeps the private server 100% Yale-blue every build.
        _kr = os.path.join(PROJECT, "tools", "kilo-aupuni", "king_recolor.py")
        if os.path.exists(_kr):
            import subprocess as _sp
            try:
                _sp.run([sys.executable, _kr], timeout=60, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                print("  + king_recolor: private/.dc pages kept Yale-blue (0 dark)")
            except Exception:
                pass

    # [build-aware API base] The generator bakes VBASE="/api" (same-origin = the PRIVATE King mirror on the
    # tailnet; king-local was mirrored ABOVE with /api intact). Here we rewrite ONLY the public site/ copies
    # to verify_api_base_public from config/beta.json (default "" = 'opening soon', clean + leak-safe). When
    # the Cloudflare Tunnel is up, setting that one field to https://api.12sgi.com wires public clients
    # both-ways - a single-line activation. Runs on CI too (KLOCAL absent there).
    try:
        _bp = json.load(open(os.path.join(PROJECT, "config", "beta.json"), encoding="utf-8")).get("verify_api_base_public", "")
    except Exception:
        _bp = ""
    _pub = ("" if (_bp or "").startswith("PASTE_") else (_bp or "")).rstrip("/")
    # [PUBLIC leak-sanitize] strip the PRIVATE tailnet host from PUBLIC site/ copies (king-local, mirrored
    # ABOVE, keeps the real ts.net for the owner). The :8443 funnel -> the public API base (or '#' until live);
    # the bare host -> 12sgi.com (the public King at /king exists there). Closes the go.html ts.net leak the
    # king/-only leak-gate didn't catch. NEVER touches king-local (private).
    _TSNET = "12sgianonymous.tail760750.ts.net"
    import glob as _glob
    _n = 0
    for _h in _glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True):
        try:
            _t = open(_h, encoding="utf-8").read()
            _o = _t
            _t = _t.replace('VBASE="/api"', 'VBASE="%s"' % _pub)
            _t = _t.replace("https://%s:8443" % _TSNET, (_pub or "#"))
            _t = _t.replace("https://%s" % _TSNET, "https://12sgi.com").replace(_TSNET, "12sgi.com")
            if _t != _o:
                open(_h, "w", encoding="utf-8").write(_t); _n += 1
        except Exception:
            pass
    if _n:
        print("  + public sanitize: VBASE=%r + stripped private ts.net host on %d public page(s); king-local untouched"
              % (_pub or "(opening-soon)", _n))
    # reconcile post-build scan: warn-only (dev UX); the hard-block runs in CI on seed_reports (publish.yml)
    try:
        import subprocess as _sp, sys as _sys
        _rp = os.path.join(os.path.dirname(__file__), "tools", "reconcile.py")
        if os.path.isfile(_rp):
            _r = _sp.run([_sys.executable, _rp, "--scan", SITE, "html", "--route-only"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
            if _r.stdout.strip() and "clean" not in _r.stdout:
                print("[reconcile] WARN (dev only — CI gate blocks on seed_reports):")
                for _ln in _r.stdout.strip().splitlines():
                    print("  " + _ln)
    except Exception:
        pass
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
