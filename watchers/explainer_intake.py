#!/usr/bin/env python3
"""explainer_intake.py — the AI intake for paid civic explainers (Jimmy 2026-06-18).

A buyer types what they want to understand about a government; we ask the question, an AI maps it to
a CHECKBOX list of explainable aspects (pre-ticking the relevant ones), they adjust, and the selection
drives the render spec + the quote. Every aspect maps to a REAL civic data surface we already produce
(sourced — no fabrication). Tenant-aware. Local-first: uses Ollama (:11434) if up, else a keyword matcher.

API:
  catalog(tenant)            -> [ {id,label,desc,weight,source,maui_only} ... ]   (the checkboxes)
  match(text, tenant)        -> {question, suggested:[id...], catalog:[...with 'checked'...], engine}
  spec(aspect_ids, tenant)   -> {aspects:[...], beats, seconds}   (selection -> render spec)
Stdlib only (urllib for the local Ollama probe). No fabrication: aspects are fixed, sourced surfaces.
"""
import os, sys, re, json, urllib.request

# The explainable ASPECTS of a county government — each maps to a civic surface we already build.
# weight = rough beats/seconds the aspect adds to the explainer (drives length → tokens → price).
ASPECTS = [
    # ── FEATURED: the Title-system software features we built (Jimmy's focus, 2026-06-18) ──
    {"id": "title19_system",   "label": "The Title 19 System (dual-charter)", "desc": "the zoning system hub — Maui County Code Title 19 read through the 12 Stones Charter, side by side", "weight": 5, "source": "title19-system", "maui_only": False, "featured": True},
    {"id": "title_navigator",  "label": "Plain-language Title navigator", "desc": "ANY Maui County Code Title (3·5·6·8·9·10·11·12·13·14·16·18·19·20·22) explained in plain words", "weight": 4, "source": "titleNN-service", "maui_only": False, "featured": True},
    {"id": "permit_assistant", "label": "Permit assistant", "desc": "the AI permit-assistant for a Title — what's allowed, what you need, where it hands off to MAPPS", "weight": 5, "source": "titleNN-service (Tier-3)", "maui_only": False, "featured": True},
    {"id": "parcel_lookup",    "label": "Parcel / TMK lookup", "desc": "a parcel's zoning + designation from the live Statewide GIS, with the rules that apply", "weight": 4, "source": "title19-service parcel-lookup", "maui_only": False, "featured": True},
    {"id": "substantial_change","label": "Substantial-change procedure", "desc": "the Title 19 substantial-change process — when a project change triggers a new review", "weight": 4, "source": "title19-substantial-change", "maui_only": False, "featured": True},
    {"id": "enforcement_fines","label": "Enforcement & civil fines", "desc": "violations, the correction schedule, and the civil-fine amounts (sourced MC-15 rule)", "weight": 4, "source": "title19-service enforcement", "maui_only": False, "featured": True},
    # ── the money/record aspects ──
    {"id": "whats_being_decided", "label": "What's being decided", "desc": "the live agenda — what's on the table this meeting", "weight": 4, "source": "agendas_<t>.html", "maui_only": False},
    {"id": "agenda_item",         "label": "A specific bill / item", "desc": "one bill, resolution, or communication explained plainly", "weight": 5, "source": "agenda feed", "maui_only": False},
    {"id": "how_to_testify",      "label": "How to testify",        "desc": "how to get your voice on the record before the vote", "weight": 3, "source": "testify.html", "maui_only": False},
    {"id": "money_behind",        "label": "Who funds the officials","desc": "campaign money behind each seat (money × votes)", "weight": 5, "source": "money_behind_officials.html", "maui_only": False},
    {"id": "testifiers",          "label": "Who testifies × money", "desc": "named public testifiers cross-referenced to donors", "weight": 5, "source": "testifiers_<t>.html", "maui_only": True},
    {"id": "council_votes",       "label": "How they vote (dissent)","desc": "split votes + the dissenter's own words (nay narratives)", "weight": 5, "source": "council_votes_<t>.html", "maui_only": True},
    {"id": "contracts",           "label": "Contracts × donors",    "desc": "who the county pays, matched to who funds the deciders", "weight": 5, "source": "contracts_x_donors.html", "maui_only": False},
    {"id": "federal_dollars",     "label": "Federal dollars",       "desc": "federal money landing here, by agency + recipient", "weight": 4, "source": "federal_money.html", "maui_only": False},
    {"id": "real_estate",         "label": "Real estate × money",   "desc": "giving × recorded property interests", "weight": 5, "source": "realestate_<t>.html", "maui_only": True},
    {"id": "the_law",             "label": "Which law governs this","desc": "the Maui County Code Title service for this subject", "weight": 4, "source": "titleNN-service", "maui_only": False},
    {"id": "charter_lens",        "label": "Through the Charter",   "desc": "the 12 Stones Charter ⇄ law lens (labeled analysis)", "weight": 3, "source": "crosswalk_<t>.html", "maui_only": False},
    {"id": "an_official",         "label": "A specific official",   "desc": "one official's record + the money behind them", "weight": 4, "source": "officials + money", "maui_only": False},
    {"id": "an_org",              "label": "A specific donor/org",  "desc": "one organization's giving + connections dossier", "weight": 4, "source": "entity_<org>.html", "maui_only": True},
    {"id": "moon_offering",       "label": "The moon offering",     "desc": "the kaulana mahina / Kumulipo offering for the date — keep it pono", "weight": 2, "source": "moon_calendar", "maui_only": False},
]
# free-text → aspect keyword hints (the offline matcher; Ollama refines when available)
_KW = {
    "title19_system": ["title 19", "zoning system", "land use", "dual charter", "title system"],
    "title_navigator": ["title", "code", "ordinance", "navigator", "plain language", "explain the code", "which title"],
    "permit_assistant": ["permit", "can i build", "am i allowed", "assistant", "what do i need", "build on", "shed", "adu"],
    "parcel_lookup": ["parcel", "tmk", "my property", "my land", "my lot", "designation", "zoned", "what zone"],
    "substantial_change": ["substantial change", "project change", "amend my permit", "modify the project", "new review"],
    "enforcement_fines": ["fine", "violation", "enforcement", "penalty", "cited", "notice of violation", "stop work"],
    "money_behind": ["money", "fund", "donor", "campaign", "finance", "backer", "who pays"],
    "council_votes": ["vote", "voted", "dissent", "nay", "split", "against", "yes or no"],
    "testifiers": ["testif", "who shows up", "spoke", "testimony"],
    "how_to_testify": ["how do i testify", "testify", "speak", "my voice", "comment"],
    "contracts": ["contract", "vendor", "awarded", "procure", "bid"],
    "federal_dollars": ["federal", "grant", "usaspending", "washington"],
    "real_estate": ["real estate", "property", "land", "development", "parcel", "rezone"],
    "the_law": ["law", "code", "title", "ordinance", "rule", "permit", "zoning"],
    "charter_lens": ["charter", "12 stones", "rights", "sovereign"],
    "agenda_item": ["bill", "resolution", "communication", "item"],
    "whats_being_decided": ["agenda", "meeting", "decided", "on the table", "coming up"],
    "an_official": ["councilmember", "mayor", "official", "representative"],
    "an_org": ["company", "organization", "llc", "developer", "corporation"],
    "moon_offering": ["moon", "kumulipo", "pono", "blessing", "offering", "mahina"],
}

def catalog(tenant="hi-maui"):
    maui = tenant in ("hi-maui", "maui")
    return [a for a in ASPECTS if (maui or not a["maui_only"])]

def _ollama_match(text, ids):
    """Ask the LOCAL Ollama (:11434) to pick the relevant aspect ids. Returns a subset or None if Ollama is down."""
    try:
        prompt = ("A resident asks: %r. From this list of explainable government aspects, return ONLY a JSON "
                  "array of the ids that match their request (no prose): %s" % (text[:300], json.dumps(ids)))
        body = json.dumps({"model": "llama3", "prompt": prompt, "stream": False, "options": {"temperature": 0}}).encode()
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read().decode()).get("response", "")
        m = re.search(r"\[.*?\]", resp, re.S)
        picked = json.loads(m.group(0)) if m else []
        return [i for i in picked if i in ids] or None
    except Exception:
        return None

def _keyword_match(text, ids):
    t = (text or "").lower()
    hit = [aid for aid in ids if any(k in t for k in _KW.get(aid, []))]
    return hit

def match(text, tenant="hi-maui"):
    cat = catalog(tenant); ids = [a["id"] for a in cat]
    suggested = (_ollama_match(text, ids) if text.strip() else None)
    engine = "ollama"
    if suggested is None:
        suggested = _keyword_match(text, ids); engine = "keyword"
    if not suggested:                                  # nothing matched → default to the Title-system focus
        suggested = [i for i in ("title19_system", "title_navigator") if i in ids]; engine = "default"
    out = []
    for a in cat:
        out.append({**a, "checked": a["id"] in suggested})
    return {"question": "What would you like explained about this government?", "tenant": tenant,
            "suggested": suggested, "catalog": out, "engine": engine}

def spec(aspect_ids, tenant="hi-maui"):
    """Selection → render spec: the chosen aspects + total beats + target seconds (drives the quote)."""
    cat = {a["id"]: a for a in catalog(tenant)}
    chosen = [cat[i] for i in (aspect_ids or []) if i in cat]
    if not chosen:
        chosen = [cat["whats_being_decided"]] if "whats_being_decided" in cat else []
    beats = 2 + len(chosen)                            # intro/aloha + one beat per aspect
    seconds = int(round(sum(a["weight"] for a in chosen) * 1.2)) + 6   # ~weighted length + chant/aloha tail
    return {"tenant": tenant, "aspects": [a["id"] for a in chosen],
            "labels": [a["label"] for a in chosen], "beats": beats, "seconds": seconds}

def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", default="", help="free-text request to match to checkboxes")
    ap.add_argument("--tenant", default="hi-maui")
    a = ap.parse_args()
    m = match(a.text, a.tenant)
    print("Q: %s  [%s engine]" % (m["question"], m["engine"]))
    for c in m["catalog"]:
        print("  [%s] %-22s — %s" % ("x" if c["checked"] else " ", c["label"], c["desc"]))
    print("\nspec:", json.dumps(spec(m["suggested"], a.tenant), ensure_ascii=False))
    return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
