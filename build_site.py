#!/usr/bin/env python3
# build_site.py - assemble the public static site for GitHub Pages.
# Collects the Kilo Aupuni report HTML + JSON from reports/mauios (+ council) and writes
# a flat ./site/ with an index.html linking everything. Runs locally OR on a CI runner.
#
#   python build_site.py            # -> ./site
#   KA_SITE=/path python build_site.py
import os, re, shutil, json, sys, time, subprocess
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
COUNCIL = os.path.join(PROJECT, "reports", "council")
SEED_MAUIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_reports", "mauios")

# civic_shell = the unified home-page chrome (single source = tools/kilo-aupuni/civic_shell.py). CI-safe:
# falls back to None if the project tree isn't present, so the build never breaks on a runner.
sys.path.insert(0, os.path.join(PROJECT, "tools", "kilo-aupuni"))
try:
    import civic_shell as _civic_shell   # vendored at repo root for CI (build-mirror; source = project tools/kilo-aupuni)
except Exception:
    _civic_shell = None
sys.path.insert(0, os.path.join(PROJECT, "tools", "ops"))
try:
    import blog_engine as _blog_engine
except Exception:
    _blog_engine = None
# build rev: 2026-07-01 blog pages wired into public site/ output
SITE    = os.environ.get("KA_SITE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "site"))
HST     = timezone(timedelta(hours=-10))

def mauios_src(rel):
    """Prefer the live local reports tree, but fall back to repo seed artifacts."""
    src = os.path.join(MAUIOS, rel)
    if os.path.exists(src):
        return src
    seed = os.path.join(SEED_MAUIOS, rel)
    return seed if os.path.exists(seed) else src

# headline dashboards (filename in mauios -> public name + blurb)
PAGES = [
    ("aloha_aina.html",                  "Aloha ʻĀina",                  "The land is chief. How the open record becomes the land's legal shield - food security as land vitality, sourced from 57 certified operations across six islands, widened back into the living ecosystem. He aliʻi ka ʻāina, he kauā ke kanaka."),
    ("rep_audit.html",                   "Audit by Representative",      "For each Maui County Council member - how their recorded behavior (votes, the money behind them, recusals) lines up against the will of the voters they represent. The overlapping money-and-votes logic as a graph. Sourced questions for the Board of Ethics, never verdicts."),
    ("donor_bloc.html",                  "The Donor Bloc",                "Which donor and vendor entities fund multiple Council members at once - a graph (Neo4j) of the shared-money network, mapped to real parcels those entities hold. Council votes are near-unanimous almost always; the money network is the sourced pattern here, not vote coordination."),
    ("civic_daily.html",                 "Today's Civic Agenda",         "Today's Maui meetings before they happen - HST times, agenda items, what to ask, how to testify - bracketed by the night's moon prayers. Refreshed each sunrise. Public records (Legistar)."),
    ("county_dashboard.html",            "Maui County Dashboard",        "Coverage map + lens activity + money trail across every watcher."),
    ("accountability_record.html",       "Accountability Record",        "Public record: corruption rankings, federal convictions (Stant/Choy/English/Cullen), reforms recommended vs enacted."),
    ("sole_source_watch.html",           "Sole-Source Watch",            "Sole-source/exemption awards (the Stant mechanism) + the executive-branch gap + the lawful records path."),
    ("patterns_money_x_votes.html",      "Patterns: Money x Votes",      "RE/developer money received vs. lens-bill dissents; cross-jurisdiction donor web."),
    ("contracts_x_donors.html",          "Contracts x Donors",           "Maui county contract awardees (HANDS) name-matched to campaign donors of tracked officials. Public records, framed as questions."),
    ("testimony_effect_map.html",        "Testimony Effect Map",         "Where real-estate-industry donor-entities hold recorded Maui parcels, alongside the fact that industry testified on Bill 9. In-house SVG map, real parcel geometry (Hawai'i statewide GIS)."),
    ("great_mahele_overlay.html",        "The Great Mahele on the Map",  "The 1848 land division overlaid on the modern ahupua'a map: real Land Commission Award entries from the 1929 territorial index for four Maui districts, alongside real ahupua'a geometry."),
    ("maui_contract_awards.html",        "Maui Contract Awards",         "Every public Notice of Award to a Maui County jurisdiction (HANDS) - the vendor side of the money."),
    ("statewide_money_patterns.html",    "Statewide Money (2008+)",      "Campaign money across all 4 counties + State; the donor network."),
    ("money_behind_officials.html",      "Money Behind Officials",       "Campaign finance per tracked official, real-estate donors flagged."),
    ("officials_scorecard.html",         "Maui Officials Scorecard",     "Council votes + recusals from the minutes."),
    ("council_votes_maui.html",          "Council Votes - Nay Narratives","Every Maui Council split vote + the dissenter's own recorded words, beside the campaign money behind each seat. Public records, framed as questions."),
    ("bill9_money_vs_will.html",          "Bill 9 - the Vote, the Money","The Council's 5-3 final vote to phase out transient vacation rentals in apartment districts, set beside the real-estate money behind the three NO votes. Public records (roll-call + campaign finance), framed as questions, never accusations. Neo4j-backed."),
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
EXTRA_PAGES = [# interactive parcel/TMK map (live Hawaii Statewide GIS) — embedded on the Maui tenant landing
               "maui_parcel_map.html",
               "contracts_state.html", "contracts_honolulu.html", "contracts_kauai.html", "contracts_hawaii.html",
               "contracts_nyc.html", "contracts_nys.html", "contracts_liverpool.html",
               # item 2: money / lobby / parity dimensions per tenant (built + verified by the workflow)
               "money_nyc.html", "lobby_nyc.html", "parity_nyc.html",
               "money_nys.html", "parity_nys.html",
               "money_state.html", "parity_state.html",
               "money_honolulu.html", "parity_honolulu.html",
               # item-2 gaps (workflow 2): lobby crosses for HI State / Honolulu / NY State
               "lobby_state.html", "lobby_honolulu.html", "lobby_nys.html",
               # workflow 3: matrix close + subcontractor chains + Ka Leo fan-out (ka_leo_nyc withheld - failed verify)
               "money_liverpool.html", "parity_liverpool.html",
               "money_dubai.html", "money_frankfurt.html", "money_hongkong.html", "money_london.html",
               "money_paris.html", "money_singapore.html", "money_tokyo.html", "money_zurich.html",
               "subcontractors_nyc.html",
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
               "meetings_calendar.html", "meetings_maui.html", "meetings_honolulu.html", "meetings_hawaii.html", "meetings_kauai.html", "meetings_nyc.html", "bfed_agenda_today.html", "bfed_eligibility_today.html", "minutes_hi-maui.html", "minutes_hi-hawaii.html",
               # news vs record — pairs each news story with the underlying primary source (civic_daily_briefing's
               # sibling watcher); linked from the education front door but was never wired into the build before.
               "news_record.html",
               "minutes_hi-kauai.html", "minutes_hi-honolulu.html", "minutes_ny.html",
               # N53 integrity engine — past minutes / supplemental materials / roll-call corpus
               "n53_engine.html", "archive.html", "testimony_money.html", "testimony_record.html",
               "archive_state.html", "archive_hi-state.html", "archive_maui.html", "archive_honolulu.html", "archive_hawaii.html", "archive_kauai.html",
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
               "prosecutor_public_feed.html",
               # govOS Audit — the per-tenant combined view (funders -> votes/recusals -> contracts -> the questions),
               # one page (govos_audit.py). Maui sourced; others honest-empty until their officials are sourced.
               "govos_audit_hi-state.html", "govos_audit_hi-maui.html", "govos_audit_hi-hawaii.html",
               "govos_audit_hi-kauai.html", "govos_audit_hi-honolulu.html", "govos_audit_ny.html",
               "title19.html",  # Maui submission-calculator hub (onboarding estimate, all departments)
               # govOS DEPARTMENT-AS-FUNCTION layer (dept_pages.py) — each of Maui's 18 departments as a page
               # with its people-first function + serve/record/audit + its subject-matched county contracts.
               # Reached from tenant_hi-maui.html's department cards ("full department view") + the index.
               "departments_maui.html",
               "dept_council_maui.html", "dept_mayor_maui.html", "dept_management_maui.html",
               "dept_finance_maui.html", "dept_public_works_maui.html", "dept_water_maui.html",
               "dept_planning_maui.html", "dept_environmental_maui.html", "dept_fire_maui.html",
               "dept_police_maui.html", "dept_prosecutor_maui.html", "dept_parks_maui.html",
               "dept_housing_maui.html", "dept_agriculture_maui.html", "dept_transportation_maui.html",
               "dept_liquor_maui.html", "dept_personnel_maui.html", "dept_corp_counsel_maui.html",
               # federal_money.html (the Maui+State front page) is now a carded dashboard in PAGES; county sub-pages stay here
               "federal_money_hawaii.html", "federal_money_honolulu.html",
               "federal_money_kauai.html", "federal_money_nyc.html", "federal_officials.html", "audit_balance.html",
               "audit_balance_dubai.html", "audit_balance_frankfurt.html", "audit_balance_hongkong.html",
               "audit_balance_liverpool.html", "audit_balance_london.html",
               "audit_balance_paris.html", "audit_balance_singapore.html", "audit_balance_tokyo.html", "audit_balance_zurich.html",
               # county 'Who governs' rosters — sourced from each council's official site (2026-06-16)
               "officials_honolulu.html", "officials_hawaii.html", "officials_kauai.html", "officials_nyc.html",
               "officials_maui.html", "officials_nys.html",
               # per-representative silencing audit (rep_audit.py) — one console per Maui council member, reached from rep_audit.html
               "rep_batangan.html", "rep_cook.html", "rep_johnson.html", "rep_lee.html", "rep_paltin.html",
               "rep_rawlins-fernandez.html", "rep_sinenci.html", "rep_sugimura.html", "rep_uu-hodgins.html",
               "rep_kama_former.html",   # former member (deceased Oct 2025) — her own record, kept separate
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
               # nonprofits + subcontractor chain + the unified money-chain graph (Jimmy 2026-07-08/09) — built,
               # verified, but never added to PAGES/EXTRA_PAGES, so they never reached SITE at all (the actual
               # root cause of "I don't see all the pages for that tenant" — not a missing nav link, a missing copy).
               "nonprofits_maui.html", "subcontracts_maui.html", "money_chain_maui.html",
               # subcontractors_maui.html = the ALIAS subcontract_chain.py writes alongside subcontracts_maui.html
               # (county_awards.dim_links + the Maui tenant tiles link the "subcontractors_" spelling). The primary
               # ships above; the alias was never in a copy list -> broken link from maui.html/tenant_hi-maui.html/
               # money_chain_maui.html. Real federal USASpending subaward data (Maui FIPS 15009), already staged.
               # Added 2026-07-14 (audit-quad-os, Maui ingest repatch).
               "subcontractors_maui.html",
               # ── OTHER-TENANT civic pages (hi-hawaii/honolulu/kauai/state + NY). Data was STAGED but never
               # copied — same gap as the Maui pages above. The generators were fixed 2026-07-14 (audit-quad-os)
               # so each page carries its OWN tenant name/facts, not Maui's: contracts_x_donors + money_behind
               # titles were mislabeled "Maui", and money_behind's Lahaina/$1.639B disaster-lens is now gated to
               # Maui only (it's a Maui fact, false under another county). Stale hi-*_contract_awards.html orphans
               # were deleted instead — the correct contracts_<slug>.html already ship above.
               "contracts_x_donors_hi-hawaii.html", "contracts_x_donors_hi-honolulu.html",
               "contracts_x_donors_hi-kauai.html", "contracts_x_donors_hi-state.html",
               "money_behind_officials_hi-hawaii.html", "money_behind_officials_hi-honolulu.html",
               "money_behind_officials_hi-kauai.html", "money_behind_officials_hi-state.html",
               "money_kauai_shell.html", "minutes_hi-state.html",
               "audit_balance_nys.html", "federal_money_nys.html",
               # maui_services.html — the "one front door" hub (2026-07-15): mirrors mauicounty.gov's
               # service structure by LINKING OUT to the county's authoritative transactions (pay/permits/
               # DMV/UIPA/jobs/alerts — we index, never clone) alongside our public-record + accountability
               # pages. Closes the feature-parity gap the mauicounty.gov comparison surfaced.
               "maui_services.html",
               # who_paid_the_vote.html — AURORA·GOLD educational surface (2026-07-15): "who paid for the vote"
               # taught at every reading level (keiki->analyst) over a ghosted celestial star map aligned to
               # Wailuku (county seat) + Lahaina (Royal Capital 1820-1845). standalone-aurora = opts out of the
               # govOS Georgia stamp; real money-graph data from Neo4j, sourced + question-framed.
               "who_paid_the_vote.html",
               # the ethics+education lens rolled UP to the State (parent) and BACK DOWN to every county
               # (Jimmy 2026-07-15 "all the way up and back") — who_paid_gen.py, each with its own celestial
               # anchors (present seat ↔ historic royal seat) + that tenant's VERIFIED donor data.
               "who_paid_the_vote_hi-state.html", "who_paid_the_vote_hi-hawaii.html",
               "who_paid_the_vote_hi-honolulu.html", "who_paid_the_vote_hi-kauai.html",
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
        "hands_maui_awards.json", "vendor_donor_join.json", "sage_bridge.json",
        "prosecutor_public_feed.json"]

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
    "testimony_effect_map.html": "Testimony Effect Map",
    "great_mahele_overlay.html": "The Great Mahele on the Map",
    "maui_contract_awards.html": "Contract Awards",
    "lobby_money_watch.html": "Lobby + Money",
    "officials_scorecard.html": "Officials Scorecard",
    "lege_legislator_scorecard.html": "Legislator Scorecard",
    "civic_daily.html": "Today's Civic Agenda",
    "news_record.html": "News vs Record",
    "education.html": "Civic Education",
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
    "crosswalk_liverpool.html": "Charter ⇄ Law (Village of Liverpool, NY)",
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
    "king/civic/templates/blessings/Night%20Tends%20the%20Day.html": "Blessing — The Night Tends the Day",
    "king/civic/templates/blessings/Every%20Hand%20Knows%20Its%20Work.html": "Blessing — Every Hand Knows Its Work",
    "king/civic/templates/blessings/Each%20Voice%20True%20None%20in%20Discord.html": "Blessing — Each Voice True, None in Discord",
    "king/civic/templates/title19-substantial-change/Title19%20Substantial%20Change.html": "Title 19 — Substantial Change Procedure",
    "king/civic/templates/budget-transparency/Budget%20Transparency.html": "Budget — Every Dollar",
    "king/civic/templates/county-code/Maui%20County%20Code%20%26%20Rules.html": "Maui County Code",
    "king/civic/templates/state-law/State%20of%20Hawai%CA%BBi%20Law%20Index.html": "Hawaiʻi Law Index",
    "king/civic/templates/hawaii-crosswalk/Hawai%CA%BBi%20County%20Crosswalk.html": "Hawaiʻi County Crosswalk",
    "king/civic/templates/agenda-explainer/Agenda%20Explainer.html": "Agenda Explainer",
    # nonprofits + subcontractor chain (Jimmy 2026-07-09) — the money-chain graph work
    "money_chain_maui.html": "Money Chain — Maui (graph)",
    "nonprofits_maui.html": "990 Nonprofits — Maui",
    "subcontracts_maui.html": "Subcontractor Chain — Maui",
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
                          "testimony_effect_map.html",
                          "lobby_money_watch.html", "maui_contract_awards.html", "statewide_money_patterns.html",
                          "wildfire_recovery_watch.html", "rebuild_first.html", "money_holysee.html",
                          # nonprofits + subcontractor chain (Jimmy 2026-07-09, "the new audit profiles") —
                          # were built, verified, but never surfaced anywhere navigable. Now they are.
                          "money_chain_maui.html", "nonprofits_maui.html", "subcontracts_maui.html"]),
    ("The Record", ["civic_daily.html", "n53_engine.html", "archive.html", "testimony_record.html", "testimony_money.html", "parity_check.html", "accountability_record.html",
                    "sole_source_watch.html", "commission_antitrust.html", "bill9_bill9_testimony_scan.html",
                    "great_mahele_overlay.html",
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
    "html{background:#081420}body{background:#081420;color:#eaf2fc}"
    ".govos-nav{position:sticky;top:0;z-index:9999;display:flex;align-items:center;gap:2px;height:56px;"
    "padding:0 18px;background:rgba(11,28,46,0.72);border-bottom:1px solid rgba(90,151,230,.24);"
    "-webkit-backdrop-filter:blur(14px) saturate(1.15);backdrop-filter:blur(14px) saturate(1.15);"
    "font-family:-apple-system,'SF Pro Text','Segoe UI Variable Text','Segoe UI',system-ui,Roboto,sans-serif;font-size:13px}"
    ".govos-nav *{box-sizing:border-box}"
    ".gn-brand{display:flex;align-items:center;gap:9px;text-decoration:none;margin-right:16px;white-space:nowrap}"
    ".gn-brand .mk{color:#5a97e6;font-size:17px;line-height:1}"
    ".gn-brand b{color:#eaf2fc;font-weight:700;font-size:15px;letter-spacing:.2px}"
    ".gn-brand .sub{color:#e3ad33;font-size:9.5px;letter-spacing:1.5px;text-transform:uppercase;border-left:1px solid #1f3d5f;padding-left:9px}"
    ".gn-here{font-size:11px;color:#6d89ab;margin-right:12px;white-space:nowrap;align-self:center}.gn-here b{color:#5a97e6}"
    ".gn-menu{display:flex;align-items:center;gap:1px;flex:1}"
    ".gn-group{position:relative}"
    ".gn-top{display:flex;align-items:center;gap:6px;background:none;border:0;color:#a7c0dd;font:inherit;font-size:13px;padding:8px 12px;border-radius:9px;cursor:pointer;transition:.16s}"
    ".gn-top .ar{font-size:9px;color:#6d89ab}"
    ".gn-top:hover,.gn-group:hover .gn-top{color:#eaf2fc;background:rgba(47,116,208,.14)}"
    ".gn-top.active{color:#5a97e6}"
    ".gn-panel{position:absolute;top:calc(100% + 6px);left:0;min-width:244px;background:rgba(15,37,64,.94);border:1px solid rgba(90,151,230,.24);"
    "border-radius:13px;padding:6px;box-shadow:0 16px 40px -10px rgba(0,0,0,.7);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);display:none;flex-direction:column;gap:1px;z-index:50}"
    ".gn-group:hover .gn-panel,.gn-group.open .gn-panel{display:flex}"
    ".gn-panel a{display:block;color:#a7c0dd;text-decoration:none;padding:8px 11px;border-radius:8px;font-size:13px;white-space:nowrap;transition:.14s}"
    ".gn-panel a:hover{background:rgba(47,116,208,.18);color:#fff}"
    ".gn-panel a.cur{color:#5a97e6;background:rgba(47,116,208,.15)}"
    ".gn-link{color:#a7c0dd;text-decoration:none;padding:8px 12px;border-radius:9px}"
    ".gn-link:hover{color:#eaf2fc;background:rgba(47,116,208,.14)}"
    ".gn-link.cur{color:#5a97e6}"
    ".gn-lead{color:#e3ad33;font-weight:600;text-decoration:none;padding:8px 12px;border-radius:9px;margin-right:4px}"
    ".gn-lead:hover{background:rgba(227,173,51,.14)}.gn-lead.cur{color:#e3ad33}"
    ".gn-cta{margin-left:auto;background:linear-gradient(180deg,#2f74d0,#00356b);color:#fff;font-weight:600;text-decoration:none;padding:9px 16px;border-radius:10px;font-size:13px;white-space:nowrap;border:1px solid #2f74d0}"
    ".gn-cta:hover{background:linear-gradient(180deg,#5a97e6,#2f74d0)}"
    ".gn-burger{display:none;margin-left:auto;background:none;border:0;color:#eaf2fc;font-size:21px;cursor:pointer;padding:4px 8px;line-height:1}"
    "@media(max-width:880px){"
    ".gn-burger{display:block}"
    ".gn-menu{display:none;position:absolute;top:56px;left:0;right:0;flex-direction:column;align-items:stretch;"
    "background:rgba(11,28,46,0.97);border-bottom:1px solid rgba(90,151,230,.24);padding:8px;gap:2px;max-height:82vh;overflow:auto}"
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
def _tenant_from_filename(cf, treg):
    """Resolve a tenant from a filename TOKEN (Jimmy 2026-07-03 'fix the pick-a-government render gate so the
    real vote data displays'): e.g. council_votes_maui / dept_council_maui / agendas_nys -> the matching
    registry tenant. SOURCED-not-fabricated: matches the registry tenant's own id-suffix (hi-maui->maui,
    ny->ny) or the first word of its name, on whole '_/-/.' token boundaries so 'ny' can't match 'any'.
    Returns a tid or None (None only when no registry tenant token is in the filename)."""
    if not treg:
        return None
    toks = set(t for t in re.split(r"[_\-.]", (cf or "").lower()) if t)
    for tid in treg:
        idtok = tid.split("-")[-1].lower()
        nametok = re.split(r"[\s,]", (treg[tid].get("name") or "").lower())[0]
        for t in toks:
            # exact token match, OR a short-id prefix (idtok 'ny' matches 'nys'/'nyc' but not 'nylon' —
            # bounded to +2 chars so it stays a deliberate tenant token, never a coincidental substring)
            if t == idtok or t == nametok or (len(idtok) >= 2 and t.startswith(idtok) and len(t) - len(idtok) <= 2):
                return tid
    return None


def _tenant_of(current):
    """Which tenant a flat filename belongs to (registry rev map, tenant_<id>.html, or filename token);
    home tenant otherwise."""
    rev, byclass, treg, order = _switcher_maps()
    cf = (current or "").replace("/", "_")
    if cf in rev: return rev[cf][2]
    m = re.match(r"tenant_(.+)\.html$", cf)
    if m and treg and m.group(1) in treg: return m.group(1)
    ft = _tenant_from_filename(cf, treg)
    if ft: return ft
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


# ── maui.html = tenant_hi-maui.html, byte-for-byte (2026-07-09, Jimmy: "I don't want Maui's cards
#    different looking from other tenants, that is a system error based on the old MauiOS"). Maui used to
#    get its OWN hand-rolled directory (MAUI_NAV_GROUPS, a second, Maui-only rendering path) — exactly the
#    Maui-centric special-casing that was a leftover from the era when this whole system WAS "MauiOS".
#    govOS treats every tenant identically: tenant_pages.py's directory_sections() (project tools/kilo-aupuni,
#    the SAME function for all 6 tenants) is now the ONLY generator of a tenant's page directory. This
#    function no longer renders anything of its own — it just mirrors site/tenant_hi-maui.html (already
#    built by the normal "dashboards" pass above, from the SAME unified tenant_pages.py output) under the
#    legacy "maui.html" URL so old bookmarks/links keep working.
def build_maui_nav_page():
    src = os.path.join(SITE, "tenant_hi-maui.html")
    if not os.path.exists(src):
        print("  ! maui.html SKIPPED: site/tenant_hi-maui.html not built yet (dashboards pass didn't run first)")
        return
    body = open(src, encoding="utf-8", errors="replace").read()
    with open(os.path.join(SITE, "maui.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("  + maui.html: mirrors tenant_hi-maui.html verbatim (%d bytes) — no separate Maui rendering path" % len(body))


def _ensure_civic_document(pth, rel):
    """Headless civic fragments (many generators emit a bare `<nav>…<footer>` with no <head>/<body>)
    can't receive the govos.css/govos-shell.js stamp — rebuild_page injects the <link> at </head> and the
    <script> at </body>, and if neither tag exists the shared shell silently never lands, leaving an
    UNSTYLED nav (audit found 93 such pages). Wrap those into a proper document so the stamp reaches them,
    matching the 357 pages that already pair `govos-nav` + govos.css/js. Skip real documents (already have
    </head>), king-app DataComponents (*.dc.html, imported headless by app.html), and non-civic subtrees
    (king/ sage/ games/ go/ + template partials carry their own structure). Added 2026-07-15 (audit-quad-os,
    from-scratch civic rebuild — the ASSET dimension: one shared nav shell on every civic page)."""
    low = rel.lower()
    if low.endswith(".dc.html") or low.split("/")[0] in ("king", "sage", "games", "go") or "civic/templates" in low:
        return False
    txt = pth.read_text(encoding="utf-8", errors="replace")
    if "</head>" in txt.lower():
        return False   # already a full document
    wrapped = ('<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
               '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
               '</head><body>\n' + txt + '\n</body></html>')
    pth.write_text(wrapped, encoding="utf-8", newline="\n")
    return True


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

# DARK-REGISTER FIX (2026-07-09 heal-audit): was a light gray panel (#eef2f7 bg + white <select>s) that
# reads as a stray bright box on every civic page now that NAV_CSS sets a global dark body — none of its
# hex values overlapped build_site._RECOLOR's remap table, so the color-fix pass never touched it. Recolored
# to the same fresh-navy glass register as NAV_CSS/tenant_directory.py.
_SWITCH_CSS = ("<style id=tenant-switch-css>.tenant-nav{display:flex;align-items:center;gap:10px;flex-wrap:wrap;"
    "max-width:1100px;margin:10px auto 0;padding:9px 14px;background:rgba(15,37,64,.7);border:1px solid #1f3d5f;border-radius:11px;"
    "-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);font-family:'Segoe UI',system-ui,sans-serif}"
    ".tn-grp{display:flex;align-items:center;gap:6px}"
    ".tn-lbl{font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:#a7c0dd;font-weight:600}"
    ".tenant-nav select{font-family:inherit;font-size:13px;color:#eaf2fc;background:#0f2540;border:1px solid #1f3d5f;"
    "border-radius:8px;padding:5px 9px;cursor:pointer;max-width:230px}.tenant-nav select:hover{border-color:#5a97e6}"
    ".tn-here{font-size:11px;color:#a7c0dd}.tn-here b{color:#5a97e6}</style>")

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
    if cur_tid is None:
        # FILENAME-TOKEN fallback (Jimmy 2026-07-03 'fix the pick-a-government render gate'): council_votes_maui
        # / dept_council_maui / agendas_nys carry the tenant in the name -> resolve it so the bar shows "on
        # Maui County" (with the real vote data) instead of "pick a government to begin". Deliberately does NOT
        # home-default here: a page whose filename names a NON-registry place (agendas_london/paris) must NOT
        # be mislabeled "Maui" — that would be fabrication. No token -> stays the honest picker.
        cur_tid = _tenant_from_filename(cf, treg)
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
        'gov.addEventListener("change",function(){var t=this.value;'
        'try{localStorage.setItem("govos.tenant",t);}catch(e){}'
        'if(D.cur_class&&D.tclass[D.cur_class]&&D.tclass[D.cur_class][t]){'
        'location.href=D.tclass[D.cur_class][t];}else{'
        'view.innerHTML="";var ph=document.createElement("option");ph.value="";ph.disabled=true;ph.selected=true;'
        'ph.textContent="— pick a view —";view.appendChild(ph);'
        'var rs=(D.treg[t]||{}).reports||[];'
        'if(!rs.length){var ov=document.createElement("option");ov.textContent="overview";'
        'ov.value="tenant_"+t+".html";view.appendChild(ov);}'
        'else rs.forEach(function(r){var o=document.createElement("option");o.textContent=r[0];o.value=r[1];view.appendChild(o);});'
        'var h=document.querySelector(".tn-here");'
        'if(h){var n=(D.treg[t]||{}).name||t;h.innerHTML="on <b>"+n+"</b>";}}'
        '});'
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
    ("#16130d", "#0f2540"), ("#1c1810", "#16324e"), ("#2a241a", "#1f3d5f"), ("#2a2419", "#1f3d5f"),
    ("#e0872f", "#e3ad33"), ("#3a2e20", "#0f2540"), ("#c3b79c", "#a7c0dd"), ("#e9dcc0", "#eaf2fc"),
    ("#efe4c8", "#eaf2fc"), ("#d9c9a8", "#a7c0dd"), ("#c9b98f", "#a7c0dd"), ("#b8a67e", "#6d89ab"),
    # FRESH YALE BLUE (dark navy register, Jimmy 2026-07-08). Same source hexes; keep pages DARK.
    # backgrounds: warm-dark -> deep navy
    ("#0c100e", "#081420"), ("#0c0b09", "#081420"), ("#080c12", "#081420"), ("#0a0e14", "#081420"),
    ("#0b0f0d", "#0b1c2e"), ("#0b0e14", "#0b1c2e"),
    # panels: dark -> navy panel
    ("#121714", "#0f2540"), ("#151d19", "#0f2540"), ("#16140f", "#0f2540"), ("#15110d", "#0f2540"),
    ("#1e1b14", "#16324e"), ("#1a1610", "#16324e"), ("#2a261c", "#1f3d5f"),
    # lines/borders: dark -> navy line
    ("#2a2f29", "#1f3d5f"), ("#34301f", "#1f3d5f"), ("#243029", "#1f3d5f"),
    # ink: cream/light stays LIGHT (light-on-dark) -> soft blue-white
    ("#efe9da", "#eaf2fc"), ("#e8e4d8", "#eaf2fc"), ("#eef3ef", "#eaf2fc"), ("#f0ead8", "#eaf2fc"),
    ("#cfc9b6", "#a7c0dd"), ("#bdb8a4", "#a7c0dd"), ("#b3a98f", "#a7c0dd"),
    ("#9a957f", "#6d89ab"), ("#8a8674", "#6d89ab"), ("#756b56", "#6d89ab"), ("#9fb1a6", "#6d89ab"),
    # accents: gold stays gold; bright gold -> bright Yale blue
    ("#d9b24c", "#e3ad33"), ("#e3ad33", "#e3ad33"), ("#f4c95d", "#5a97e6"), ("#f3d589", "#5a97e6"),
    ("#e7c361", "#5a97e6"), ("#f0cf7a", "#5a97e6"),
    # aloha teal / sea -> ok-green / Yale blue
    ("#9fd9bf", "#4bbf7b"), ("#c8efd9", "#4bbf7b"), ("#e3ecdf", "#a7c0dd"), ("#5fc0d8", "#5a97e6"), ("#3a8fb7", "#2f74d0"),
    # moon/Po purple: keep readable ON DARK -> light indigo
    ("#ecdfff", "#c9b8ff"), ("#efe4ff", "#c9b8ff"), ("#cdb4f0", "#b9a6ef"),
    ("rgba(205,180,240", "rgba(201,184,255"),
    # stray cream/ivory -> light ink
    ("#f4eeda", "#eaf2fc"), ("#f6f0dc", "#eaf2fc"),
    # status: keep semantics, readable on dark
    ("#6abf86", "#4bbf7b"), ("#56c08a", "#4bbf7b"), ("#d29922", "#e3ad33"),
    ("#e06a4a", "#f0663f"), ("#e5736b", "#f0663f"),
    ("#43d39e", "#4bbf7b"), ("#e0863a", "#e3ad33"),
    # faint small text on dark
    ("#6d7f97", "#6d89ab"),
    # rgba tints (keep alpha): gold stays gold; teal -> green
    ("rgba(217,178,76", "rgba(227,173,51"),
    ("rgba(159,217,191", "rgba(75,191,123"), ("rgba(67,211,158", "rgba(75,191,123"),
    # light-on-dark hairlines: KEEP light-on-dark (Yale-blue tint) so they read on navy
    ("rgba(255,255,255,.1)", "rgba(90,151,230,.16)"), ("rgba(255,255,255,.08)", "rgba(90,151,230,.13)"),
    ("rgba(255,255,255,.06)", "rgba(90,151,230,.1)"), ("rgba(255,255,255,.045)", "rgba(90,151,230,.08)"),
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
                # AURORA-KEEP (Jimmy 2026-07-16 "go.html -> aurora-gold"): a page that declares its own
                # AURORA·GOLD palette opts OUT of the Yale-blue recolor + civic-chrome footer, but — unlike
                # standalone-aurora — STILL receives the shared govos shell (nav/js) it depends on. Mobile-heal
                # still applies. Marker in the first 600 chars.
                _aurora_keep = ext == "html" and "aurora-keep" in t[:600]
                r = t if _aurora_keep else recolor(t)
                if ext == "html":
                    r = ensure_mobile(r)
                    if not _aurora_keep and os.path.relpath(p, root).split(os.sep)[0] != "king":
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

# ── Lane harness (Jimmy 2026-07-05: 'break the build into ~30 lanes to reduce build
# errors with the heal system') ────────────────────────────────────────────────────
# Each build step below is registered as an independent, named "lane" instead of running
# inline. A broken lane can NEVER take down the whole build (mirrors the same philosophy
# already proven in .github/workflows/publish.yml's `run() { timeout 240 ... || true }`
# watcher wrapper) -- it's caught, timed, logged with a consistent "[lane] name: ..." line,
# and recorded into buildinfo.json's "lanes" array so the heal system (selfheal.py / any
# future CI check) can see EXACTLY which lane failed on a given build, instead of scanning
# raw scrollback for a stray "skipped: ..." line buried in 500+ lines of output.
import contextlib

_LANE_REPORT = []

@contextlib.contextmanager
def _lane(name):
    t0 = time.time()
    try:
        yield
        dt = time.time() - t0
        _LANE_REPORT.append({"lane": name, "ok": True, "seconds": round(dt, 2)})
        print("  [lane] %s: ok (%.2fs)" % (name, dt))
    except Exception as e:
        dt = time.time() - t0
        _LANE_REPORT.append({"lane": name, "ok": False, "seconds": round(dt, 2), "error": str(e)[:200]})
        print("  [lane] %s: FAILED (%.2fs) -- %s" % (name, dt, str(e)[:200]))

def main():
    _LANE_REPORT.clear()
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE, exist_ok=True)
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
    with _lane("civic_money_maps"):
        # DURABLE re-injection (Jimmy 2026-07-16 "put maps on every civic page ... where the money goes"):
        # the money pages are regenerated by their own generators (donor_watch etc.), which WIPES the
        # injected animated "where the money goes / comes from" map. Re-inject over reports/mauios HERE,
        # BEFORE the copy lanes below carry the pages into SITE -> king-local, so every deploy ships them.
        # civic_money_maps --all is idempotent + self-healing (strips a map from any page that no longer has
        # money content). Isolated in a subprocess so a failure NEVER breaks the build (money maps are additive).
        try:
            _cmm = os.path.join(PROJECT, "tools", "kilo-aupuni", "civic_money_maps.py")
            if os.path.exists(_cmm):
                _r = subprocess.run([sys.executable, "-X", "utf8", _cmm, "--all"], capture_output=True,
                                    text=True, timeout=180, cwd=PROJECT, env=dict(os.environ, PYTHONUTF8="1"))
                _tail = (_r.stdout or "").rstrip().splitlines()
                print("  + civic money maps: " + (_tail[-1] if _tail else "ran") + ("" if _r.returncode == 0 else " (rc=%d)" % _r.returncode))
        except Exception as _cmme:
            print("  ! civic money maps skipped (build continues): %s" % str(_cmme)[:120])
    with _lane("dashboards"):
        present = []
        for rel, name, blurb in PAGES:
            src = mauios_src(rel)
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
    with _lane("extra_pages"):
        # extra per-tenant pages: copied + nav-injected, reached from the jurisdictions hub (not nav pills).
        # entity_*.html dossiers have dynamic names -> glob them in (+ the dossier index).
        import glob as _glob
        _dyn = ["entity_index.html"] + sorted(os.path.basename(p) for p in _glob.glob(os.path.join(MAUIOS, "entity_*.html")))
        for rel in EXTRA_PAGES + [d for d in _dyn if d not in EXTRA_PAGES]:
            src = mauios_src(rel)
            if os.path.exists(src):
                _raw = open(src, encoding="utf-8", errors="replace").read()
                # A page marked `standalone-aurora` carries its OWN complete design (AURORA·GOLD) and must
                # NOT receive the govOS civic nav / switcher / narrative / ʻōlelo injections, nor the
                # govos.css stamp below — it is a self-contained surface with its own back-link.
                if "standalone-aurora" in _raw[:400]:
                    _h = _raw
                else:
                    _h = inject_nav(_raw, rel)
                    _h = inject_switcher(_h, rel)      # per-tenant report: choose a government switcher
                    _h = add_narrative(_h, rel)
                    _h = add_records_cta(_h, rel)
                    _h = add_olelo_notice(_h)
                with open(os.path.join(SITE, rel), "w", encoding="utf-8", newline="\n") as f:
                    f.write(_h)
    with _lane("data_files"):
        _present_data = []
        for rel in DATA:
            src = mauios_src(rel)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(SITE, "data", os.path.basename(rel)))
                _present_data.append((os.path.basename(rel), src))
        # prosecutor_public_feed.html fetches ./prosecutor_public_feed.json at the SITE ROOT (relative,
        # same-dir), but the DATA loop above only lands it in site/data/ -> the page's fetch 404s. Copy it
        # to root too so the feed resolves. Added 2026-07-14 (audit-quad-os, other-tenant repatch).
        _pf = mauios_src("prosecutor_public_feed.json")
        if os.path.exists(_pf):
            shutil.copy(_pf, os.path.join(SITE, "prosecutor_public_feed.json"))
        # tenant_hi-state links lege/legislator_scorecard.html at the SUBDIR path, but the build otherwise
        # ships only the flattened lege_legislator_scorecard.html -> the subdir link 404s (the flatten
        # gotcha). Ship the subdir copy too so the link resolves; the govos_shell_stamp lane (recursive
        # glob) stamps it with the correct ../ asset prefix. Added 2026-07-14 (audit-quad-os, repatch).
        _lege = mauios_src(os.path.join("lege", "legislator_scorecard.html"))
        if os.path.exists(_lege):
            os.makedirs(os.path.join(SITE, "lege"), exist_ok=True)
            shutil.copy(_lege, os.path.join(SITE, "lege", "legislator_scorecard.html"))

    with _lane("open_data_catalog"):
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

    with _lane("tenant_coverage"):
        # [tenant-coverage] HIDDEN-DATA DASHBOARD (Jimmy 2026-07-01): renders the tenant_registry.json
        # coverage matrix (already public, already embedded in every tenant switcher) as an actual heatmap.
        try:
            import subprocess as _sp
            _tch = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchers", "tenant_coverage_heatmap.py")
            if os.path.exists(_tch):
                _r = _sp.run([sys.executable, _tch], capture_output=True, text=True, timeout=30)
                print("  " + (_r.stdout.strip() or "! tenant_coverage_heatmap produced no output"))
        except Exception as _e:
            print("  ! tenant coverage heatmap skipped: %s" % str(_e)[:120])

    with _lane("blog"):
        # [blog] public Aloha blog — studio notes, creative methodology, production dispatches.
        # blog_engine.py writes to king-local; here we also render to site/ for GitHub Pages.
        if _blog_engine is not None:
            try:
                _blog_posts = _blog_engine.load_posts()
                _blog_pub = sorted([p for p in _blog_posts if p.get("status") == "published"],
                                   key=lambda p: p.get("date", ""), reverse=True)
                # static=True (Jimmy 2026-07-01 heal-forward): the public site has no server to resolve
                # /king/blog?post=X, so every mirrored post orphaned itself the moment it published --
                # render real blog_post_<slug>.html / blog.html relative links here instead.
                with open(os.path.join(SITE, "blog.html"), "w", encoding="utf-8", newline="\n") as f:
                    f.write(_blog_engine.render_list_page(_blog_pub, static=True))
                for _bp in _blog_pub:
                    _slug = _bp.get("slug", _bp.get("id", ""))
                    with open(os.path.join(SITE, "blog_post_%s.html" % _slug), "w", encoding="utf-8", newline="\n") as f:
                        f.write(_blog_engine.render_post_page(_bp, static=True))
                print("  + blog.html + %d post pages (Aloha blog -> public site/)" % len(_blog_pub))
            except Exception as _be:
                print("  ! blog skipped: %s" % str(_be)[:120])

    with _lane("links_copy"):
        # [links] copy linked supporting folders so per-official "full profile" pages resolve.
        # "donors" is Maui's; each other tenant's money_behind_officials_<t>.html links its own
        # donors_<t>/ dir (donor_watch.py derives the href from basename(OUT_DIR)). Copy them all.
        # Extended 2026-07-14 (audit-quad-os, other-tenant repatch — closed 32 broken donor-profile links).
        import glob as _glob
        _donor_dirs = ["donors"] + sorted(os.path.basename(p) for p in _glob.glob(os.path.join(MAUIOS, "donors_*")) if os.path.isdir(p))
        for sub in _donor_dirs:
            s = os.path.join(MAUIOS, sub)
            if os.path.isdir(s):
                shutil.copytree(s, os.path.join(SITE, sub), dirs_exist_ok=True)
                print(f"  + {sub}/: {len(os.listdir(s))} profile pages")

    with _lane("bids_copy"):
        # [bids] Maui County bid/RFP detail pages (bids_watch.py -> reports/mauios/bids/, sourced from
        # mauicounty.gov CivicEngage). Pages like news_record.html link specific bids by their exact
        # "bids/bid <id> <title>.html" path. The full archive is ~3,830 files -> dumping it ALL into
        # site/ (which the build rmtree-wipes every run) is slow + Windows-race-prone AND leaves 3,829
        # orphan pages reachable only by guessing the URL (not "findable" in any real sense). Instead
        # ship EXACTLY the bids a built page actually references: the link resolves, nothing is orphaned,
        # the build stays fast and robust. Self-maintaining — whatever pages link, those bids ship. The
        # full archive stays in reports/mauios/bids (owner source). Added 2026-07-14 (audit-quad-os,
        # Maui ingest repatch; runs after EXTRA_PAGES so the referencing pages already exist in site/).
        _bids_src = os.path.join(MAUIOS, "bids")
        if os.path.isdir(_bids_src):
            import glob as _glob
            import urllib.parse as _uq
            _bref = re.compile(r'''(?:href|src)=["']([^"']*bids/[^"']+\.html)["']''', re.I)
            _wanted = set()
            for _hp in _glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True):
                try:
                    _t = open(_hp, encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                for _href in _bref.findall(_t):
                    _rel = _uq.unquote(_href.split("bids/", 1)[1]).split("#")[0].split("?")[0]
                    if _rel:
                        _wanted.add(_rel)
            _copied, _missing = 0, []
            if _wanted:
                _bids_dst = os.path.join(SITE, "bids")
                os.makedirs(_bids_dst, exist_ok=True)
                for _bn in sorted(_wanted):
                    _bs = os.path.join(_bids_src, _bn)
                    if os.path.isfile(_bs):
                        _bd = os.path.join(_bids_dst, _bn)
                        os.makedirs(os.path.dirname(_bd), exist_ok=True)
                        shutil.copy(_bs, _bd)
                        _copied += 1
                    else:
                        _missing.append(_bn)
            _arch = len([f for f in os.listdir(_bids_src) if f.lower().endswith(".html")])
            print(f"  + bids/: {_copied} referenced bid page(s) shipped (archive has {_arch})"
                  + (f" — MISSING from archive: {_missing[:3]}" if _missing else ""))

    with _lane("sage_game"):
        # [sage] publish the self-contained 2D SAGE education game at /sage/ (Jimmy 2026-07-03:
        # the CF tunnel that served the game was flaky/down, breaking every public link -> host it
        # on always-up GitHub Pages instead. Pure static (HTML/CSS/JS/JSON/images), no server.
        _gsrc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_sage")
        if os.path.isdir(_gsrc):
            _gdst = os.path.join(SITE, "sage")
            if os.path.isdir(_gdst):
                shutil.rmtree(_gdst, ignore_errors=True)
            # dirs_exist_ok: rmtree(ignore_errors=True) can leave a half-deleted dir behind a transient
            # Windows file lock, and plain copytree then dies on it — the intermittent sage_game lane
            # failure (fixed 2026-07-15; same robust pattern the bids_copy lane already uses).
            shutil.copytree(_gsrc, _gdst, dirs_exist_ok=True)
            print("  + sage/: 2D SAGE game (%d card assets, static, always-up)"
                  % len([f for f in os.listdir(os.path.join(_gsrc, "assets", "cards"))
                         if f.endswith(".jpg")] if os.path.isdir(os.path.join(_gsrc, "assets", "cards")) else []))

    with _lane("games_hub"):
        # [games] TribeGameStudios hub at /games/ — all cultural games in one always-up catalog.
        # Extends the sage_game lane pattern: pure static HTML, zero external deps, leak-clean.
        # Sources: game_studio/ (hub + 4 new games) + /sage/ (existing SAGE game, stays at /sage/).
        _ghsrc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_studio")
        if os.path.isdir(_ghsrc):
            _ghdst = os.path.join(SITE, "games")
            if os.path.isdir(_ghdst):
                shutil.rmtree(_ghdst, ignore_errors=True)
            # dirs_exist_ok: same transient-lock hardening as the sage_game lane above (2026-07-15)
            shutil.copytree(_ghsrc, _ghdst, dirs_exist_ok=True)
            _gh_files = [f for f in os.listdir(_ghsrc) if f.endswith(".html")]
            print("  + games/: TribeGameStudios hub (%d HTML games, static, always-up)" % len(_gh_files))

    with _lane("king_public_system"):
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
    with _lane("platform_packages"):
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
            # go/ subpages — private Owner Console panels (docker, ollama, llm-watch, comfyui,
            # github, system, logs). Each page fails closed on the public mirror: content only
            # renders when /board/api/* is reachable (Tailscale + king server). Safe to publish
            # because they contain no secrets and present only an "unreachable" error card on
            # the public mirror. go/X.html must live next to go.html so relative links resolve.
            _go_src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "go")
            if os.path.isdir(_go_src_dir):
                _go_dest_dir = os.path.join(SITE, "go")
                os.makedirs(_go_dest_dir, exist_ok=True)
                _go_sub_copied = []
                for _gsub in sorted(os.listdir(_go_src_dir)):
                    if _gsub.endswith(".html"):
                        shutil.copy(os.path.join(_go_src_dir, _gsub), os.path.join(_go_dest_dir, _gsub))
                        _go_sub_copied.append(_gsub)
                if _go_sub_copied:
                    print("  + go/ subpages: %d Owner Console panels (fail-closed on mirror)" % len(_go_sub_copied))
            print("  + go.html: live/mirror failover launcher (root + king/)")
        _go_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "go")
        if os.path.isdir(_go_dir):
            shutil.copytree(_go_dir, os.path.join(SITE, "go"), dirs_exist_ok=True)
            print("  + go/: owner-console route pages (/go/*)")
    with _lane("element_lotus_public_shell"):
        # [studio-shell] Public studio-first shell for Element Lotus / 12 Stones Global. Keeps the
        # interactive games on static Pages while WordPress can remain the narrative/brand shell.
        _elsrc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "element_lotus_public")
        if os.path.isdir(_elsrc):
            _copied = []
            for _name in sorted(os.listdir(_elsrc)):
                _src = os.path.join(_elsrc, _name)
                if os.path.isfile(_src):
                    shutil.copy(_src, os.path.join(SITE, _name))
                    _copied.append(_name)
            if _copied:
                print("  + Element Lotus shell: %d public studio file(s) (games/films/music first)" % len(_copied))
    with _lane("static_pages"):
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
        # Maui tenant CUSTOM navigation — must run AFTER all Maui pages are in SITE so the exists() gate
        # links only real pages. govOS bar = outer tenant switcher; maui.html = the Maui tenant's own directory.
        build_maui_nav_page()
    with _lane("grants"):
        # [grants] community grants library — public preview page (paywall for full access)
        _gr = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grants.html")
        if os.path.exists(_gr):
            shutil.copy(_gr, os.path.join(SITE, "grants.html"))
            print("  + grants.html: community grants library preview (97 grants, paywall gated)")
        # request_records.html is now GENERATED (request_records.py, tenant-aware) + flows through EXTRA_PAGES.
    with _lane("production_status"):
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
                # [slate-data] Generate site/slate-data.js from production_status.json +
                # data/media_catalog.json so the browser payload always reflects the live
                # JSON sources.  Overwrites the static copy copied from element_lotus_public/.
                _mc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "media_catalog.json")
                _mc = {}
                if os.path.exists(_mc_path):
                    try:
                        _mc = json.load(open(_mc_path, encoding="utf-8"))
                        shutil.copy(_mc_path, os.path.join(SITE, "data", "media_catalog.json"))
                    except Exception:
                        pass
                _catalog_entries = _mc.get("entries") or []
                _cat_films = [e for e in _catalog_entries if e.get("type") == "film" and e.get("public_visibility")]
                _cat_music = [e for e in _catalog_entries if e.get("type") == "music" and e.get("public_visibility")]
                _PUBLIC_ENTRY_KEYS = ("id", "title", "type", "status", "public_visibility",
                                      "youtube_url", "youtube_video_id", "thumbnail",
                                      "release_date", "duration", "description",
                                      "related_project", "album", "credits",
                                      "copyright_status", "tags")
                def _safe_entry(e):
                    return {k: e.get(k) for k in _PUBLIC_ENTRY_KEYS}
                _slate_js = (
                    "/* slate-data.js — generated by build_site.py from production_status.json"
                    " + data/media_catalog.json\n"
                    " * Do not edit site/slate-data.js directly — edit the source files and rebuild.\n"
                    " * PUBLIC: only public-safe fields. PRIVATE production controls remain protected. */\n"
                    "(function () {\n"
                    "  window.SLATE = " + json.dumps({
                        "films_produced":  _p.get("films_produced"),
                        "quadcast_songs":  _p.get("quadcast_songs"),
                        "youtube_uploaded": _p.get("youtube_uploaded"),
                        "updated":         _p.get("updated"),
                        "latest_films":    _p.get("latest_films") or [],
                        "catalog": {
                            "films": [_safe_entry(e) for e in _cat_films],
                            "music": [_safe_entry(e) for e in _cat_music],
                        },
                    }, indent=2, ensure_ascii=False) + ";\n"
                    "}());\n"
                )
                with open(os.path.join(SITE, "slate-data.js"), "w", encoding="utf-8", newline="\n") as _sjf:
                    _sjf.write(_slate_js)
                print("  + slate-data.js (generated from production_status.json + media_catalog.json)")
            except Exception:
                pass
    with _lane("build_index_html"):
        g = now_hst().strftime("%Y-%m-%d %H:%M HST")
        cards = "".join(
            f'<a class="card" href="{fn}"><div class="t">{name}</div><div class="b">{blurb}</div></a>'
            for fn, name, blurb in present)
        # [orphan-heal 2026-06-17] Civic pages that are built + useful but weren't carded anywhere
        # (calendars, fire-recovery, agenda patterns) — wire them into the hub so nothing useful is orphaned.
        _MORE = [
            ("maui.html",                  "Maui County — every page", "The full Maui tenant directory: officials, all 18 departments, the money, the votes, agendas, records, entities — every Maui page grouped in one place."),
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
<div class="eyebrow" style="margin-top:30px">Blessings as we go</div>
<div class="grid">
 <a class="card" href="king/civic/templates/blessings/Night%20Tends%20the%20Day.html"><div class="t">The Night Tends the Day</div><div class="b">The Kumulipo rhythm — Pō tends the day's work and dreams the next day forward.</div></a>
 <a class="card" href="king/civic/templates/blessings/Every%20Hand%20Knows%20Its%20Work.html"><div class="t">Every Hand Knows Its Work</div><div class="b">Kuleana — each lane of the house knowing and tending its own work.</div></a>
 <a class="card" href="king/civic/templates/blessings/Each%20Voice%20True%20None%20in%20Discord.html"><div class="t">Each Voice True, None in Discord</div><div class="b">Harmony — the house grew to many lanes, and every voice was checked and rang true.</div></a>
</div>
{prod}
<div class="eyebrow" style="margin-top:30px">Raw data</div>
<p>{" · ".join(f'<a class="data" href="data/{os.path.basename(d)}">{os.path.basename(d)}</a>' for d in DATA if os.path.exists(mauios_src(d)))}</p>
<footer>generated {g} · Kilo Aupuni · sources: CivicClerk · Hawaii Campaign Spending Commission · LegiScan · capitol.hawaii.gov · public record<br>&copy; 2026 James RCS Langford · 12 Stones Global · all rights reserved</footer>
</div></body></html>"""
        index = inject_nav(index, "")     # nav on the hub too (home pill highlights nothing)
        with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
            f.write(index)
        # the nav's "🌺 govOS" home points at reports.html — make it the named hub in BOTH
        # contexts (public site root + king-local, where index.html is the King shell).
        with open(os.path.join(SITE, "reports.html"), "w", encoding="utf-8") as f:
            f.write(index)
    with _lane("public_front_door"):
        # [front door] 2026-07: the education page (Lux et Veritas PONO) is now the public front door
        # per owner request — it fronts the whole government watcher (daily briefing + yearly meeting
        # calendars) through a civic-education lens. The former studio-first shell is preserved at
        # /studio.html (not lost, just no longer the root), and /games/, /sage/, reports.html (civic
        # hub), and the private launcher at /go.html are all still untouched.
        _edu_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "education.html")
        _studio_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "element_lotus_public", "index.html")
        _govos_fallback = os.path.join(SITE, "king", "govos_signup.html")
        _go_built = os.path.join(SITE, "go.html")
        if os.path.exists(_studio_root):
            shutil.copy(_studio_root, os.path.join(SITE, "studio.html"))
            print("  + studio.html: former front-door shell, preserved at a stable URL")
        _idx_src = _edu_root if os.path.exists(_edu_root) else (
            _studio_root if os.path.exists(_studio_root) else (
                _govos_fallback if os.path.exists(_govos_fallback) else _go_built))
        if os.path.exists(_idx_src):
            _front = open(_idx_src, encoding="utf-8", errors="replace").read()
            if _idx_src == _edu_root:
                # LINK FIX (2026-07-16): education.html is authored at the REPO ROOT (links prefixed
                # `site/…` so they resolve there), but it is deployed FROM site/ AS the root index — so
                # every `site/…` nav link 404s on 12sgi.com. Strip the prefix on href/src only; the
                # target pages are siblings in the deployed root. Source stays untouched.
                for _a in ('href="site/', "href='site/", 'src="site/', "src='site/"):
                    _front = _front.replace(_a, _a[:-5])   # drop the trailing "site/"
            with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8", newline="\n") as _f:
                _f.write(_front)
            if _idx_src == _edu_root:
                with open(os.path.join(SITE, "education.html"), "w", encoding="utf-8", newline="\n") as _f:
                    _f.write(_front)
            print("  + index.html = %s (public front door: civic education leads; go.html stays the private launcher)" % os.path.basename(_idx_src))
    with _lane("cname"):
        # GitHub Pages custom domain for the public mirror / interactive artifacts at 12sgi.com.
        # The CNAME file in the deployed artifact tells GitHub Pages the custom domain. Written every build
        # (site/ is wiped each run). elementlotus.com = WordPress brand shell; 12sgi.com = static mirror + games + civic artifacts.
        open(os.path.join(SITE, "CNAME"), "w", encoding="utf-8").write("12sgi.com\n")
        print("  + CNAME = 12sgi.com (GitHub Pages custom domain for the public mirror)")
    with _lane("buildinfo_json"):
        # BUILD MARKER for git-awareness (Jimmy 2026-07-03): stamp the deployed commit into the
        # artifact so the state-based sense-organ can read the LIVE sha directly (one curl of
        # /buildinfo.json) and reconcile live-vs-committed -- instead of ASSUMING the push worked.
        try:
            import subprocess as _sp
            _sha = os.environ.get("GITHUB_SHA") or _sp.run(
                ["git", "rev-parse", "HEAD"], cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True, text=True).stdout.strip()
            json.dump({"sha": _sha, "sha_short": (_sha or "")[:7],
                       "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                      open(os.path.join(SITE, "buildinfo.json"), "w", encoding="utf-8"))
            print("  + buildinfo.json = %s (git-awareness live-deploy marker)" % (_sha or "")[:7])
        except Exception as _e:
            print("  ! buildinfo.json skipped: %s" % _e)
    print(f"built site -> {SITE}: {len(present)} dashboards + {len([d for d in DATA if os.path.exists(mauios_src(d))])} data files")

    with _lane("quadrant_progress"):
        # [self-heal] go.html links to quadrant_progress.html (the Quad-OS progress page, generated to
        # reports/_status by quadrant_selfheal). Publish it so those links resolve (was 2 broken of 7721);
        # it's leak-clean and gets recolored by the pass below.
        for _qpn in ("quadrant_progress.html", "quadrant_progress_log.html"):
            _qp = os.path.join(PROJECT, "reports", "_status", _qpn)
            if os.path.exists(_qp):
                shutil.copy(_qp, os.path.join(SITE, _qpn))
                print(f"  + {_qpn}: published (resolves go.html / progress links)")

    with _lane("recolor_site"):
        # [recolor] Yale-blue civic skin across EVERY emitted page + tenant (color-only; logic untouched).
        # Runs before the king-local mirror so the private superset inherits the same new palette.
        _rc = recolor_tree(SITE)
        print(f"  + recolor: Yale-blue civic palette applied to {_rc} html/css files (all tenants; data/JS untouched)")

    with _lane("govos_shell_stamp"):
        # [unify 2026-07-14] ONE builder ships the stamp. rebuild_site.py used to stamp site/ locally
        # (shared govos.css + govos-shell.js injected, the repeated inline nav/CSS/JS blobs stripped)
        # AFTER a build — but this builder rmtree-wipes site/ at the top of main(), so every CI deploy
        # rebuilt UNSTAMPED pages and the stamping never reached 12sgi.com (review finding 2026-07-14).
        # Fix: the stamp is now a build lane. The canonical shared assets live at the REPO ROOT
        # (govos.css / govos-shell.js — site/ copies are wiped every run) and are copied in first;
        # if either is missing we raise BEFORE stamping, so a failed lane leaves the self-contained
        # inline pages intact (never links to a css that isn't there). Runs before the king-local
        # mirror so the private superset inherits the stamped pages too (private-first).
        _here = os.path.dirname(os.path.abspath(__file__))
        for _an in ("govos.css", "govos-shell.js", "legibility_fix.css"):
            _asrc = os.path.join(_here, _an)
            if not os.path.exists(_asrc):
                raise RuntimeError("canonical %s missing at repo root - stamp skipped, pages keep inline blobs" % _an)
            shutil.copy(_asrc, os.path.join(SITE, _an))
        import pathlib as _pl
        # rebuild_site.py sits next to this file. If build_site is ever IMPORTED (e.g. publish_audit.py) or
        # run from a foreign cwd, this dir may not be on sys.path -> `No module named 'rebuild_site'` silently
        # fails the stamp lane (pages then link a govos.css that never lands). Pin _here on sys.path so the
        # import is invocation-independent -- the stamp can never silently no-op. (audit-quad-os 2026-07-16)
        if _here not in sys.path:
            sys.path.insert(0, _here)
        import rebuild_site as _rs
        _rs.SITE_DIR = _pl.Path(SITE)   # honor KA_SITE overrides; asset ../ depth computed from the real SITE
        _sfiles = [p for p in sorted(_rs.SITE_DIR.glob("**/*.html"))
                   if ".git" not in p.parts and "__pycache__" not in p.parts]
        # ASSET dimension: give headless civic fragments a real <head>/<body> FIRST, so the stamp below
        # can inject the shared govos.css/govos-shell.js into them (else 93 pages ship an unstyled nav).
        # standalone-aurora pages carry their own complete design and opt OUT of the shared shell entirely.
        _standalone = set()
        for _p in _sfiles:
            try:
                if "standalone-aurora" in _p.read_text(encoding="utf-8", errors="replace")[:400]:
                    _standalone.add(_p)
            except Exception:
                pass
        _wrapped = 0
        for _p in _sfiles:
            if _p in _standalone:
                continue
            _rel = str(_p.relative_to(_rs.SITE_DIR)).replace("\\", "/")
            if _ensure_civic_document(_p, _rel):
                _wrapped += 1
        _changed = sum(1 for _p in _sfiles if _p not in _standalone and _rs.rebuild_page(_p, verbose=False))
        if _wrapped:
            print("  + wrapped %d headless civic fragment(s) into full documents (shared shell now reaches them)" % _wrapped)
        # maui.html mirrors tenant_hi-maui.html byte-for-byte (one-writer rule, 2026-07-09) — re-mirror
        # AFTER the stamp so identity is guaranteed by construction, not by stamp determinism.
        build_maui_nav_page()
        # Honest counter (fixed 2026-07-15): rebuild_page returns CHANGED-this-run, which reads as 0 on an
        # already-stamped tree and looked like a silent failure. Count pages actually CARRYING the stamp.
        _carrying = sum(1 for _p in _sfiles if "govos.css" in _p.read_text(encoding="utf-8", errors="replace"))
        print("  + govos shell stamp: %d/%d pages carry shared govos.css + govos-shell.js (%d changed this run)"
              % (_carrying, len(_sfiles), _changed))

    with _lane("king_local_mirror"):
        # [private-mirror] Unification: the LOCAL/owner King (king-local) must be a SUPERSET
        # of the public build — same civic dashboards + data, plus the owner-only surfaces it
        # already has. We mirror the public artifacts into it so PRIVATE serves the same
        # information, and (running locally) it updates BEFORE the git push reaches GitHub
        # Pages — "private first, public mirror." On CI this dir is absent, so it no-ops.
        KLOCAL = os.path.expanduser(os.path.join("~", "AppData", "Local", "king-extract", "deploy", "king-local"))
        if os.path.isdir(KLOCAL):
            import glob
            # PRIVATE = SUPERSET OF PUBLIC (fix 2026-07-16, audit-quad-os): mirror EVERY top-level artifact,
            # not just *.html. The shared civic assets (govos.css / govos-shell.js / legibility_fix.css /
            # studio.css / data.json / slate-data.js) are linked RELATIVE by every civic page
            # (href="govos.css" -> /king/govos.css). An html-only mirror left private king-local serving
            # those assets 404, so EVERY civic page rendered UNSTYLED on the private King (Jimmy's Tailscale
            # view) while public GitHub Pages -- which uploads all of site/ -- was fine. Copy all top-level
            # files so private carries the pages AND their stylesheet/scripts. (The parallel schtask deploy,
            # deploy_king_local_civic.ps1, carries the same fix so both king-local writers stay in sync.)
            for h in glob.glob(os.path.join(SITE, "*")):
                if not os.path.isfile(h):
                    continue
                b = os.path.basename(h)
                # SINGLE SOURCE: local root == public root (the civic landing front door).
                # The King System app lives at /king/ on BOTH (one tap from the landing).
                shutil.copy(h, os.path.join(KLOCAL, b))
            # HEAL-FORWARD (2026-07-01, server-quad-os): the loop above just copied the STATIC public
            # blog.html/blog_post_*.html (relative links, trimmed nav) over whatever king_serve.py's own
            # generation had in king-local -- king_serve.py serves /king/blog as a raw static file (no
            # blog_engine import, confirmed by trace), so those relative links resolve WRONG under the
            # private /king/blog (no .html) URL shape (e.g. href="king/" -> /king/king/, a 404). Re-render
            # the PRIVATE (static=False, absolute /king/... nav + dynamic ?post= links) version directly
            # into KLOCAL right here so this build pass is self-consistent and never depends on some other
            # process re-running blog_engine.generate() afterward to undo the clobber.
            if _blog_engine is not None and "_blog_pub" in dir():
                try:
                    with open(os.path.join(KLOCAL, "blog.html"), "w", encoding="utf-8", newline="\n") as f:
                        f.write(_blog_engine.render_list_page(_blog_pub))
                    for _bp in _blog_pub:
                        _slug = _bp.get("slug", _bp.get("id", ""))
                        with open(os.path.join(KLOCAL, "blog_post_%s.html" % _slug), "w", encoding="utf-8", newline="\n") as f:
                            f.write(_blog_engine.render_post_page(_bp))
                    print("  + king-local blog: re-rendered PRIVATE nav (static=False) over the public mirror copy")
                except Exception as _kbe:
                    print("  ! king-local blog re-render skipped: %s" % str(_kbe)[:120])
            for sub in ("data", "donors", "king"):   # +king: civic/templates tree so go.html resolves on the private server (true superset)
                s = os.path.join(SITE, sub)
                if os.path.isdir(s):
                    shutil.copytree(s, os.path.join(KLOCAL, sub), dirs_exist_ok=True)
            # king_serve strips the /king/ prefix and serves the civic templates from KLOCAL/civic (NOT KLOCAL/king/civic),
            # so mirror the civic tree to the ROOT civic dir too — else nav links like king/civic/templates/title16-service/...
            # 404 on the private server even though the page exists under king/ (Jimmy 2026-06-25, "broken links NEVER AGAIN").
            _civ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "king_public_src", "civic")
            if os.path.isdir(_civ):
                shutil.copytree(_civ, os.path.join(KLOCAL, "civic"), dirs_exist_ok=True)
            print(f"  + king-local (PRIVATE superset): mirrored {len(present)} dashboards + data + king/ + civic/ -> served first via Tailscale")
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
                    # HONEST LOG (2026-07-09 heal-audit fix): this used to discard real stdout and print a
                    # hardcoded "(0 dark)" regardless of what actually happened. Show the script's real count.
                    _kro = _sp.run([sys.executable, _kr], timeout=60, capture_output=True, text=True)
                    _kline = (_kro.stdout or "").strip().splitlines()
                    print("  + " + (_kline[-1] if _kline else "king_recolor: ran, no output"))
                except Exception as _kre:
                    print("  ! king_recolor FAILED: %s" % str(_kre)[:120])

    with _lane("public_api_sanitize"):
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
        _TSNET = "king.tail760750.ts.net"
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
    with _lane("link_prefix_fix"):
        # DEPLOY-TIME LINK NORMALIZER (James 2026-07-17 "go thru every link no errors"): repo-root /
        # king_public_src / element_lotus_public pages are authored with location-relative prefixes
        # (site/…, ../…) that break once flattened into site/; and the public sanitize above turns
        # owner-only backend routes into 12sgi.com/board etc. (404). This runs LAST over site/ and
        # fixes both classes so no internal link 404s on the public mirror. Idempotent, href/src only.
        try:
            import sys as _sys
            _tp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
            if _tp not in _sys.path: _sys.path.insert(0, _tp)
            import fix_link_prefixes as _flp
            _lt, _lf = _flp.fix_site(SITE)
            print("  + link normalize: %d href/src fixed across %d page(s) (no broken internal links)" % (_lt, _lf))
        except Exception as _e:
            print("  ! link normalize skipped:", str(_e)[:120])
    with _lane("reconcile"):
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
    with _lane("lane_report"):
        # Fold the per-lane pass/fail/timing summary into buildinfo.json so the heal system
        # (selfheal.py or any future CI check) can see exactly which lane failed on a given
        # build, instead of scanning raw scrollback for a stray "skipped: ..." line.
        _bi_path = os.path.join(SITE, "buildinfo.json")
        _bi = json.load(open(_bi_path, encoding="utf-8")) if os.path.exists(_bi_path) else {}
        _bi["lanes"] = _LANE_REPORT
        _failed = [l["lane"] for l in _LANE_REPORT if not l["ok"]]
        _bi["lanes_failed"] = _failed
        json.dump(_bi, open(_bi_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  + lane report: {len(_LANE_REPORT)} lanes, {len(_failed)} failed"
              + (f" ({', '.join(_failed)})" if _failed else ""))
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
