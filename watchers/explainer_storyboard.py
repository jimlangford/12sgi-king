#!/usr/bin/env python3
"""explainer_storyboard.py — compose a paid explainer's STORYBOARD from selected aspects (Jimmy 2026-06-18).

explainer_intake.spec() picks the aspects + the beat count; THIS turns that selection into the actual
ordered, narratable beats the reel renderer consumes. Each beat carries a title, a warm-voice narration
line (the line olelo_voice/agenda_reel speak), and an ENV-ONLY visual cue (landscape / moon / text — never
a person's likeness, per the civic public policy). The arc is fixed and pono:

    1) MOON open    — the kaulana mahina / Kumulipo offering for the date (sets the tone, breaks nothing)
    N) one beat per chosen aspect, in catalog order — plain-language, SOURCED, money/votes framed as a
       question never a verdict (the curse-breaker stance: aloha + facts, not accusation)
    Z) ALOHA close  — "the curse is broken with aloha" — the same three verse lines the explainer page animates

No fabrication: narration is built from the fixed ASPECTS catalog copy + the optional moon offering. CPU/stdlib.

API:
  storyboard(aspect_ids, tenant, date=None)  -> {tenant, date, beats:[{n,kind,id,title,narration,visual,seconds}], seconds, narration}
  narration_lines(aspect_ids, tenant, date)  -> [str]   (just the spoken lines, for agenda_reel)
CLI: python explainer_storyboard.py --aspects title19_system,enforcement_fines --tenant hi-maui --date 2026-06-20
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explainer_intake as EI

# Jimmy's voice profile for civic explainers (Jimmy 2026-06-25: "make sure explainers are done in my voice").
# These principles govern every narration line written here or in new beats:
VOICE_PROFILE = {
    "tone":        "christ-aloha: civic duty IS aloha in action — knowing your government is how you protect your community",
    "register":    "plain over jargon; present-tense; life happening now — not institutional, not corporate, never robotic",
    "money_votes": "question-framed, never a verdict: 'who funds the people who decide?' — offer the record, let the listener sit with it",
    "sourcing":    "every fact names its source; if we don't have the source, we say so plainly and don't fill the gap",
    "aloha_close": "E ala e — the curse is broken with aloha; end every explainer on the pono, the rising, the light",
    "moon_open":   "begin with the sky, the kaulana mahina — ground the civic in the sacred before looking at the work of government",
    "never":       ["accusatory verdict", "corporate-speak", "passive voice hiding the actor", "jargon without plain translation", "fabricated data"],
    "examples": {
        "good": ["Who funds the people who decide? The records, not a verdict.",
                 "Your voice belongs on the record. Here is how to get it there.",
                 "The rule, plainly — so the conversation starts from the real text."],
        "bad":  ["Transparency is essential for democracy.", "Follow for plain-language civic updates.",
                 "This important issue affects many stakeholders."]
    }
}

# Per-aspect narration: a warm, plain, SOURCED line + an env-only visual cue. Falls back to the catalog
# label/desc for any aspect not specially scripted. Money/votes lines are framed as questions, never verdicts.
_BEAT = {
    "title19_system":    ("The Title 19 System", "Here is how the land-use law actually reads — Maui County Code Title 19, set side by side with the 12 Stones Charter, so you can see the rule and the principle at once.", "slow pan over a Maui ridgeline at dawn, the title text rising over the land"),
    "title_navigator":   ("The plain-language Title navigator", "Any Title of the County Code, explained in plain words — you ask, it answers, and it always links back to the real text.", "an open book of the code dissolving into clear plain sentences over the coastline"),
    "permit_assistant":  ("The permit assistant", "Thinking of building? The assistant walks you through what's allowed and what you'll need, then hands you off to the county's own system — no guesswork.", "a quiet upcountry lot, a gentle checklist of steps appearing one by one"),
    "parcel_lookup":     ("Your parcel, your rules", "Type a TMK and see a parcel's zoning and designation from the live Statewide GIS — the actual rules that apply to that piece of land.", "a map zooming to a single parcel, its designation glowing softly"),
    "substantial_change":("The substantial-change procedure", "When a project changes enough to need a fresh look, here is exactly what triggers that review — clearly, before it surprises anyone.", "two versions of a site plan fading between each other over the land"),
    "enforcement_fines": ("Enforcement and civil fines", "If a rule is broken, here is the correction schedule and the civil-fine amounts — sourced from the county's own administrative rule, not invented.", "a notice of violation laid on a table, the correction timeline drawn out plainly"),
    "whats_being_decided":("What's being decided", "This is what is actually on the table this meeting — the live agenda, in plain language.", "the agenda unfurling like a scroll over the council chamber doors"),
    "agenda_item":       ("The item, explained", "One bill, one resolution — what it does and who it touches — explained so you don't need a lawyer to follow it.", "a single agenda line lifting off the page into clear words"),
    "how_to_testify":    ("How to testify", "Your voice belongs on the record. Here is how to get it there before the vote — the deadline, the form, the room.", "an empty podium in a sunlit chamber, a path of light leading to it"),
    "money_behind":      ("Who funds the seats", "Here is the campaign money behind each seat — a question worth asking out loud: who funds the people who decide? The records, not a verdict.", "donation figures rising quietly beside each council seat, sourced and dated"),
    "testifiers":        ("Who testifies, and the money near them", "The people who spoke on the record, set beside the donations in the same arena — offered as a question to sit with, not an accusation.", "names on the testimony list, soft lines drawn to the public donor records"),
    "council_votes":     ("How they vote — and who dissents", "The split votes, and the dissenter's own words. When someone votes no, you deserve to hear why, in their voice.", "a vote tally resolving, the lone nay highlighted with its quoted reason"),
    "contracts":         ("Contracts beside donors", "Who the county pays, set beside who funds the deciders — public records on both sides, offered so you can ask the question yourself.", "contract awards and donor records flowing toward each other over the harbor"),
    "federal_dollars":   ("Federal dollars, landing here", "The federal money arriving in this place, by agency and recipient — so you can see where Washington's dollars actually go.", "a wide aerial of the island, funding streams arriving from across the sea"),
    "real_estate":       ("Real estate and money", "Campaign giving set beside recorded property interests — a pattern to notice and question, drawn only from public records.", "parcels lighting up across a valley, soft links to the giving record"),
    "the_law":           ("Which law governs this", "The exact Title of the County Code that governs this subject — so the conversation starts from the real rule.", "the relevant code title rising clearly over the subject it governs"),
    "charter_lens":      ("Through the Charter", "The same facts seen through the 12 Stones Charter — labeled clearly as our analysis, set beside the law, never replacing it.", "the law text and the charter principle meeting gently, two columns of light"),
    "an_official":       ("One official's record", "One official — their record and the money behind them, side by side, from the public file.", "a single seat in the chamber, its record and giving drawn out beside it"),
    "an_org":            ("One organization's giving", "One organization — its giving and its connections, gathered from public records into one clear dossier.", "an org name at the center, its public connections branching softly outward"),
    "moon_offering":     ("The moon offering", "The kaulana mahina for this date, and an offering from the Kumulipo — kept pono, kept gentle.", "the moon in its phase over still water, the offering text beneath it"),
}

# the three verse lines the explainer page animates on its moon→sun curse-breaker — spoken on the close
_CLOSE_VERSE = ["E ala e — rise with the light.",
                "The moon wanes, the sun breaks.",
                "The curse is broken with aloha."]


def _moon_open(tenant, date):
    """The opening moon beat. Uses moon_calendar's reading/offering when available; else a gentle generic line."""
    title = "The moon tonight"
    narration = "We begin with the sky. "
    visual = "the moon in its phase rising over a calm Hawaiian sea, the date written in light"
    try:
        import moon_calendar as MC
        rd = None
        for fn in ("reading_for", "reading", "for_date", "offering_for"):
            if hasattr(MC, fn):
                rd = getattr(MC, fn)(date) if date else getattr(MC, fn)()
                break
        if isinstance(rd, dict):
            po = rd.get("po") or rd.get("phase") or rd.get("name") or ""
            off = rd.get("offering") or rd.get("creative_offering") or rd.get("aloha") or ""
            if po: title = "The moon — %s" % po
            if off: narration = "We begin with the sky. %s" % off
    except Exception:
        pass
    if narration.strip() == "We begin with the sky.":
        narration = "We begin with the sky — the kaulana mahina, the Hawaiian moon for this date, offered with aloha before we look at the work of government."
    return {"kind": "moon", "id": "moon_open", "title": title, "narration": narration,
            "visual": visual, "seconds": 6}


def storyboard(aspect_ids, tenant="hi-maui", date=None):
    """Compose the ordered, narratable beats for a paid explainer from the selected aspects."""
    sp = EI.spec(aspect_ids, tenant)
    cat = {a["id"]: a for a in EI.catalog(tenant)}
    chosen = sp["aspects"]
    beats = []
    n = 1
    # 1) moon open
    m = _moon_open(tenant, date); m["n"] = n; beats.append(m); n += 1
    # 2..N) one beat per chosen aspect, in catalog order
    order = [a["id"] for a in EI.ASPECTS if a["id"] in chosen]
    for aid in order:
        a = cat.get(aid, {})
        if aid in _BEAT:
            title, narr, vis = _BEAT[aid]
        else:
            title = a.get("label", aid); narr = a.get("desc", ""); vis = "the subject shown plainly over the land, with its source named"
        beats.append({"n": n, "kind": "aspect", "id": aid, "title": title,
                      "narration": narr, "visual": vis, "seconds": max(4, int(a.get("weight", 4)))})
        n += 1
    # Z) aloha curse-breaker close (matches the explainer page's animated verse)
    beats.append({"n": n, "kind": "close", "id": "aloha_close",
                  "title": "The curse is broken with aloha",
                  "narration": " ".join(_CLOSE_VERSE),
                  "visual": "the moon dissolving into sunrise over the islands, the three verse lines rising in light",
                  "seconds": 6})
    seconds = sum(b["seconds"] for b in beats)
    # OPTIONAL animated narrator (studio capability, civic-guardrailed): a FICTIONAL/disclosed narrator only,
    # à-la-carte + stage-only. Attach the approved default + any already-staged clip — never auto-rendered here.
    narrator = {"available": False}
    try:
        import explainer_character as EC          # same dir; already on sys.path (line 22)
        staged = EC.latest_staged()
        narrator = {"available": True, "default": EC.DEFAULT, "allowed": list(EC.CIVIC_NARRATORS),
                    "disclosure": EC.DISCLOSURE, "stage_only": True,
                    "staged_media": (staged or {}).get("media"),
                    "note": "Fictional AI-disclosed narrator only (never a real person/hero); à-la-carte; "
                            "stage-only — not on the public explainer."}
    except Exception:
        pass
    return {"tenant": tenant, "date": date, "aspects": chosen, "beats": beats,
            "seconds": seconds, "narration": [b["narration"] for b in beats], "narrator": narrator,
            "honest": "Sourced civic content; money and votes are offered as questions, not verdicts. No likeness, no fabrication."}


def narration_lines(aspect_ids, tenant="hi-maui", date=None):
    return storyboard(aspect_ids, tenant, date)["narration"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aspects", default="title19_system", help="comma-separated aspect ids")
    ap.add_argument("--tenant", default="hi-maui")
    ap.add_argument("--date", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sb = storyboard([x.strip() for x in a.aspects.split(",") if x.strip()], a.tenant, a.date)
    if a.json:
        print(json.dumps(sb, ensure_ascii=False, indent=1)); return 0
    print("STORYBOARD — %s — %d beats — ~%ds" % (a.tenant, len(sb["beats"]), sb["seconds"]))
    for b in sb["beats"]:
        print("  %2d. [%-6s] %-32s (%ds)" % (b["n"], b["kind"], b["title"], b["seconds"]))
        print("        voice: %s" % b["narration"])
        print("        visual: %s" % b["visual"])
    print("\n  %s" % sb["honest"])
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
