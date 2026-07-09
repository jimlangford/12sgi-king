#!/usr/bin/env python3
"""newsletter_catalog.py — the BACKLOG CATALOG that feeds the civic newsletter (Jimmy 2026-06-21:
"develop a really healthy newsletter and backlog catalog into what each department of a tenant would
be interested in ... light and dark ... hewa and Pono et al across entire parent and tenants").

LANE NOTE: authored by audit-quad-os (hub) as a cross-surface editorial FRAME. The CIVIC lane
(kilo-aupuni) owns + verifies + extends it and wires it into newsletter_digest.py; SERVER owns delivery
+ the WordPress publish. This module builds the catalog only; it never sends and never publishes.

THE 2x2 (Jimmy's keystone correction): light and dark are NOT good vs bad. Each holds a good and a bad.
Whoever balances threads -- a prosecutor, an orchestrator, a hub -- digital or human, organic chemistry
or silicon -- must hold all four quadrants at once. The doctrine already built IS this cosmology
operationalized (private-first = good dark; sourced + question-framed = good light without glare).

  PO (dark) . PONO  -> good dark : privacy, the gestating source, the private-first file that shields
                       the accused until it is sourced; rest; mercy that does not expose.
  PO (dark) . HEWA  -> bad dark  : concealment, corruption hidden from the record, the buried conflict.
  AO (light). PONO  -> good light: truth, the freed public record, the plain-words explainer, dignity seen.
  AO (light). HEWA  -> bad light : glare as cruelty, exposure-as-spectacle, surveillance overreach
                       ("instrument, not spectacle" names this failure).

PUBLIC-SAFE: every catalog item carries a quadrant + a gate. AO/PONO and PO/PONO items publish freely.
AO/HEWA (the audit question) publishes ONLY sourced + question-framed + strength>=3 (the aloha_oversight
gate). PO/HEWA -- the private prosecutorial theory -- is OWNER-ONLY and NEVER enters the newsletter; it is
named here so the editor knows what NOT to ship. A leak marker in any public item fails --verify.

Output: config/newsletter_catalog.json  (the machine backlog the issue-builder + WP stager read)
Stdlib only.
"""
import os, sys, json, re
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# The timing dimension we already employ: kaulana mahina (moon_calendar.py, same dir; USNO-grounded via
# tools/audio/kaulana_mahina.py). Ao = waxing/full (growing light), Pō = waning/dark -- the same axis as
# our quadrants. The newsletter rides the moon so the cadence feels natural, not forced. Graceful if absent.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import moon_calendar as _moon
except Exception:
    _moon = None

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
CONF = os.path.join(PROJ, "config")
HST = timezone(timedelta(hours=-10))
PUBLIC = "https://jimlangford.github.io/12sgi-king"

# Leak gate. newsletter_digest.FORBIDDEN uses the broad token 'prosecut', which correctly catches our
# private prosecutor LANE -- but here it would false-positive on the legitimate PUBLIC county
# "Department of the Prosecuting Attorney". So the public scan targets internal-artifact forms
# (underscore/path/adjective) that only our owner-only lane produces, never a public department name.
FORBIDDEN = re.compile(r"sk_live|rk_live|whsec_|case_file|/king|oversight_|password|api_token|"
                       r"webhook_secret|reports/_status|prosecutor_|prosecutorial|recusal", re.I)

# ---- the apex frame (verbatim spine from docs/CHARTER_ALIGNMENT.md + MAGNIFICA_HUMANITAS_REFERENCE.md) ----
CHARTER_FRAME = {
    "foundation": "Kamehameha III, 1839 Declaration of Rights -- ho'okahi koko, of one blood: "
                  "dignity is GIVEN by God, not earned (Charter Art. I).",
    "anchor": "Magnifica Humanitas -- His Holiness Pope Leo XIV, 15 May 2026 -- safeguarding the human "
              "person in the AI age. Art. XXVI: 'AI must serve the human person' is the apex law for how "
              "this AI-built system governs itself. Civilization of love over culture of power; "
              "instrument, not spectacle.",
    "telos": "The kingdom of heaven on earth: government as service, the people's record kept free.",
    "north_star": "Serve people first -- food security, education/SAGE, the civic record + transparency, "
                  "the sovereign charter. The way the work is done IS the charter, practiced.",
    "symbiosis": "The sovereign charter and the 1839 covenant answer, together, only to the kingdom of "
                 "heaven on earth, under Holy See guidance (Magnifica Humanitas, the Rerum Novarum line).",
}

QUADRANTS = {
    "po_pono":  {"axis": "dark", "moral": "pono", "name": "good dark",
                 "means": "privacy, the gestating source, the file that shields the accused until sourced; rest; mercy that does not expose",
                 "doctrine": "private-first; the owner-only prosecutor file; data held until it earns the light",
                 "publishable": True},
    "ao_pono":  {"axis": "light", "moral": "pono", "name": "good light",
                 "means": "truth, the freed public record, the plain-words explainer, dignity seen",
                 "doctrine": "the people's records stay free; explain-your-government; serve before audit",
                 "publishable": True},
    "ao_hewa":  {"axis": "light", "moral": "hewa", "name": "bad light",
                 "means": "glare as cruelty, exposure-as-spectacle, surveillance overreach",
                 "doctrine": "the failure to AVOID: 'instrument not spectacle'. The audit question is good light "
                             "ONLY when sourced + framed as a question; unsourced naming would be bad light",
                 "publishable": "gated"},
    "po_hewa":  {"axis": "dark", "moral": "hewa", "name": "bad dark",
                 "means": "concealment, corruption hidden from the record, the buried conflict",
                 "doctrine": "what the work EXPOSES. The private prosecutorial theory lives here -- OWNER-ONLY, "
                             "never in the newsletter; named so the editor knows what not to ship",
                 "publishable": False},
}


# ---- the cadence: each quadrant rides its natural moon, grounded in the pō offerings ----
# Nights of "reverence, not contention" (kapu/sacred or the dark-moon rest) -- never publish the audit
# question (ao_hewa) on these; only reverent good-light or rest.
NO_CONTENTION = {"Akua", "Kāne", "Lono", "Mauli", "Muku"}

CADENCE = {
    "ao_pono": {"phase": "waxing -> full (Hoʻonui + Poepoe)",
                "anchor_po": ["Kūkahi..Kūpau (stand & testify)", "Hoku", "Māhealani (full)"],
                "why": "good light grows toward the full moon -- the explainers, the services, and the "
                       "freed record ride the waxing; the Kū nights favor a call to show up."},
    "ao_hewa": {"phase": "full (Poepoe peak: Hoku, Māhealani)",
                "anchor_po": ["Hoku", "Māhealani (full)"],
                "why": "the sourced audit QUESTION belongs to full light -- 'testify in the open; nothing "
                       "hidden answers best now'. Suppressed on the sacred no-contention nights."},
    "po_pono": {"phase": "waning -> dark (Hoʻēmi)",
                "anchor_po": ["Lāʻau (healing)", "Kāloa (long horizon)", "Mauli (reflect)", "Muku (rest/renew)"],
                "why": "the good-dark wisdom track + reflection rest on the waning nights -- the teaching "
                       "essays and the close-the-loop questions, framed to restore, not to wound."},
    "po_hewa": {"phase": "none -- owner-only, no public cadence", "anchor_po": [], "why": "stays in the good dark."},
}

ISSUE_ANCHOR = "Māhealani (full moon) = the flagship weekly issue; the waxing builds toward it, the " \
               "waning reflects after. Daily agenda/Sunshine posts ride the sun separately (agenda_cadence)."


def tonight(date_str=None):
    """Given a date (default today HST), what content is 'in season' per the kaulana mahina."""
    if _moon is None:
        return {"available": False, "note": "moon_calendar not importable; cadence advisory only."}
    if not date_str:
        date_str = datetime.now(timezone(timedelta(hours=-10))).date().isoformat()
    r = _moon.reading(date_str)
    ao = r["phase"] in ("waxing", "full")
    sacred = r["po"] in NO_CONTENTION
    if r["phase"] == "full":
        feature = ["ao_pono", "ao_hewa"]
    elif ao:
        feature = ["ao_pono"]
    else:
        feature = ["po_pono"]
    if sacred and "ao_hewa" in feature:
        feature.remove("ao_hewa")  # reverence, not contention
    say = {
        "ao_pono": "Publish a good-light piece: an explainer, a service, the open record.",
        "ao_hewa": "Full light -- a sourced, question-framed audit item may go out (never an accusation).",
        "po_pono": "A good-dark night: the reflective wisdom essay, or a close-the-loop question.",
    }
    return {"available": True, "date": r["date"], "night": r["night"], "po": r["po"],
            "anahulu": r["anahulu"], "phase": r["phase"], "ao_po": "Ao" if ao else "Pō",
            "sacred_no_contention": sacred, "civic_offering": r["offering"],
            "feature_quadrants": feature, "guidance": [say[q] for q in feature]}


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def dept_items(dep, tenant):
    """Map one department's people-first fields onto the catalog quadrants."""
    items = []
    nm = dep.get("name", dep.get("id"))
    fp = dep.get("for_people")
    if fp:
        items.append({"quadrant": "ao_pono", "kind": "explainer",
                      "headline": "What the %s does for you" % nm,
                      "angle": fp, "source_href": dep.get("source"), "gate": "public"})
    serve = dep.get("serve") or {}
    if serve.get("href"):
        items.append({"quadrant": "ao_pono", "kind": "service",
                      "headline": serve.get("label") or ("Use the %s service" % nm),
                      "angle": "A working service this department offers you -- free.",
                      "source_href": serve["href"], "gate": "public"})
    rec = dep.get("record") or {}
    if rec.get("href"):
        items.append({"quadrant": "ao_pono", "kind": "record",
                      "headline": rec.get("label") or "The public record",
                      "angle": "The decisions, kept in the open so you can see them.",
                      "source_href": rec["href"], "gate": "public"})
    aud = dep.get("audit") or {}
    if aud.get("href"):
        items.append({"quadrant": "ao_hewa", "kind": "audit_question",
                      "headline": aud.get("label") or "Who funds the deciders here?",
                      "angle": "Framed as a question, never an accusation: who funds the people who "
                               "decide here, and does that money touch the decisions? Publish ONLY when "
                               "sourced (public records) + strength>=3.",
                      "source_href": aud["href"], "gate": "gated_sourced_question"})
    # PO/HEWA placeholder -- the private theory. Named, never rendered public.
    items.append({"quadrant": "po_hewa", "kind": "private_marker",
                  "headline": "(owner-only) what the audit on %s may be exposing" % nm,
                  "angle": "Held in the good-dark until sourced. Stays in the prosecutor lane. "
                           "NEVER ship to the newsletter.",
                  "source_href": None, "gate": "owner_only"})
    return [dict(it, department=dep.get("id"), department_name=nm, tenant=tenant) for it in items]


WISDOM_SEEDS = [
    {
        "slug": "healthy-member-named-the-problem",
        "title": "When the healthiest person is called the problem",
        "source": "Family-systems therapy (Minuchin, Satir, Bowen, Friedman) -- shared by Jimmy, 2026-06-21.",
        "light_dark": "A worked example of the 2x2. The reformer who stops obeying an unhealthy rule "
                      "is named 'the problem' (bad light: the system's glare turned on the truth-teller). "
                      "Differentiation -- staying present AND honest -- is good light. The unwritten rule "
                      "kept in the dark is bad dark; mercy and privacy are good dark.",
        "charter_tie": "The whistleblower / civic-reformer dynamic at scale. A transparency system that "
                       "'stops participating in unhealthy rules' should expect to be named the problem by "
                       "what it audits. Defense = sourced (good light), in relationship not cutoff (aloha), "
                       "integrity un-abandoned. One-blood dignity: the scapegoat is still ohana.",
        "gate": "public",
    },
]


def build():
    maui = load(os.path.join(CONF, "maui_departments.json"), {})
    deps = maui.get("departments", [])
    reg = load(os.path.join(CONF, "tenant_registry.json"), {})
    civ = reg.get("civic_tenants", [])
    tenants = [{"id": t.get("id"), "name": t.get("name")} for t in civ] if isinstance(civ, list) else []

    items = []
    for dep in deps:
        items.extend(dept_items(dep, maui.get("tenant", "hi-maui")))

    catalog = {
        "generated": datetime.now(HST).isoformat(),
        "built_by": "audit-quad-os (hub frame) -> kilo-aupuni owns/verifies/extends",
        "charter_frame": CHARTER_FRAME,
        "quadrants": QUADRANTS,
        "lens_note": "Light and dark are not good vs bad. Each holds a good and a bad. Whoever balances "
                     "threads -- digital or human, organic chemistry or silicon -- holds all four.",
        "cadence": CADENCE,
        "issue_anchor": ISSUE_ANCHOR,
        "tonight": tonight(),
        "current_tenant": maui.get("tenant", "hi-maui"),
        "parent_tenant": "hi-state",
        "tenants": tenants,
        "scaling": "Same department x quadrant pattern applies to every civic tenant once its "
                   "departments file exists. Thin tenants stay honestly empty -- never fabricate content.",
        "department_items": items,
        "wisdom_track": WISDOM_SEEDS,
        "counts": {
            "departments": len(deps),
            "department_items": len(items),
            "public_items": sum(1 for i in items if i["gate"] == "public"),
            "gated_items": sum(1 for i in items if i["gate"] == "gated_sourced_question"),
            "owner_only_items": sum(1 for i in items if i["gate"] == "owner_only"),
            "wisdom_items": len(WISDOM_SEEDS),
            "tenants": len(tenants),
        },
    }
    return catalog


def verify(cat):
    """Public items carry no leak markers; every gated audit item has a source; owner-only never public."""
    problems = []
    for it in cat["department_items"] + cat["wisdom_track"]:
        blob = json.dumps(it, ensure_ascii=False)
        if it.get("gate") in ("public", "gated_sourced_question") and FORBIDDEN.search(blob):
            problems.append("LEAK marker in public item: %s" % it.get("headline"))
        if it.get("gate") == "gated_sourced_question" and not it.get("source_href"):
            problems.append("gated audit item with no source: %s" % it.get("headline"))
    # the po_hewa marker must never be marked public
    for it in cat["department_items"]:
        if it["quadrant"] == "po_hewa" and it["gate"] != "owner_only":
            problems.append("po_hewa item not owner_only: %s" % it.get("headline"))
    return problems


def main():
    if "--when" in sys.argv:
        i = sys.argv.index("--when")
        ds = sys.argv[i + 1] if len(sys.argv) > i + 1 and not sys.argv[i + 1].startswith("-") else None
        t = tonight(ds)
        if not t.get("available"):
            print("cadence: %s" % t.get("note"))
            return
        print("kaulana mahina -- %s : pō %d %s (%s, %s, %s)%s" % (
            t["date"], t["night"], t["po"], t["anahulu"], t["phase"], t["ao_po"],
            "  [sacred: reverence, not contention]" if t["sacred_no_contention"] else ""))
        print("  civic offering : %s" % t["civic_offering"])
        print("  in season tonight : %s" % ", ".join(t["feature_quadrants"]))
        for g in t["guidance"]:
            print("    -> %s" % g)
        return
    cat = build()
    out = os.path.join(CONF, "newsletter_catalog.json")
    if "--verify" in sys.argv:
        probs = verify(cat)
        if probs:
            print("newsletter_catalog VERIFY: FAIL")
            for p in probs:
                print("  -", p)
            sys.exit(1)
        print("newsletter_catalog VERIFY: PASS -- %d dept items (%d public / %d gated / %d owner-only), "
              "%d wisdom, %d tenants. No leak markers; every audit item sourced." % (
              cat["counts"]["department_items"], cat["counts"]["public_items"],
              cat["counts"]["gated_items"], cat["counts"]["owner_only_items"],
              cat["counts"]["wisdom_items"], cat["counts"]["tenants"]))
        return
    json.dump(cat, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    c = cat["counts"]
    print("newsletter_catalog: wrote %s" % out)
    print("  %d departments -> %d items (%d public / %d gated-audit / %d owner-only) + %d wisdom across %d tenants" % (
          c["departments"], c["department_items"], c["public_items"], c["gated_items"],
          c["owner_only_items"], c["wisdom_items"], c["tenants"]))


if __name__ == "__main__":
    main()
