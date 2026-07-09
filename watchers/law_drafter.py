#!/usr/bin/env python3
"""law_drafter.py — paid-tier AI drafter for STATE law changes + MAUI CHARTER amendments (Jimmy 2026-06-18).

A premium private function: a member describes a goal, and this drafts a properly-formatted proposal —
a Hawaiʻi state bill / HRS amendment AND/OR a Maui County Charter amendment — aligned to the 12 STONES
SOVEREIGN CHARTER pillars (P1 Food Security · P2 Education · P3 Truth · P4 Sovereign Charter), and aimed at
HELPING the real Maui Charter. Local AI (Ollama :11434) writes the findings/purpose + suggested language;
a structured template is the fallback.

HONESTY (non-negotiable):
  • These are DRAFT SUGGESTIONS for the lawful amendment process — not law, not legal advice. State law
    changes go through the Legislature (legislator introduction → committees → three readings → both
    chambers → Governor). Maui Charter amendments go through the Charter's amendment process (Charter
    Commission and/or Council-proposed measures) and are RATIFIED BY THE VOTERS — *verify the current
    Charter amendment article/section*.
  • The 12 Stones Sovereign Charter is the AUTHOR'S framework (a values lens), clearly LABELED as such —
    it is not existing government law. The crosswalk (charter_crosswalk.py) ties the lens to real law.
  • Never fabricate an existing statute's text: the draft NAMES the provision to amend and flags
    "verify the current section" rather than inventing its words. Hawaiʻi drafting convention is shown:
    NEW material _underscored_, deleted material [bracketed].

PRIVATE / paid-tier — never published. Stdlib only (+ urllib for the local Ollama probe).

API:
  pillars()                                  -> [ {id,label,desc} ]
  draft(goal, scope, pillar, section=None)   -> {state_bill?, charter_amendment?, pillar, process, honest}
  stage(d)                                   -> path (private staging)
CLI: python law_drafter.py --goal "..." --scope both --pillar P1 [--section "HRS 205-..."]
"""
import os, sys, json, time, re, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
STAGE = os.path.join(PROJ, "reports", "_status", "law_drafts")          # PRIVATE; never published

PILLARS = [
    ("P1", "Food Security", "local food systems, ʻāina, agricultural self-reliance (12SGI bio mission)"),
    ("P2", "Education", "learn-by-doing, access to knowledge, civic literacy (SAGE)"),
    ("P3", "Truth", "truthful authorship, transparency, verifiable provenance (elementLOTUS)"),
    ("P4", "Sovereign Charter", "self-governance, accountable institutions, the people's trust (govOS)"),
]
_PILL = {p[0]: {"label": p[1], "desc": p[2]} for p in PILLARS}


def pillars():
    return [{"id": p[0], "label": p[1], "desc": p[2]} for p in PILLARS]


_MODEL = None
def _model():
    """Resolve an installed Ollama chat model once (the tag is llama3.1:8b here, not 'llama3')."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    _MODEL = os.environ.get("OLLAMA_MODEL", "")
    if not _MODEL:
        try:
            d = json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5).read())
            names = [m.get("name", "") for m in d.get("models", [])]
            _MODEL = next((n for n in names if n.startswith(("llama", "qwen", "gemma", "mistral"))), names[0] if names else "llama3.1:8b")
        except Exception:
            _MODEL = "llama3.1:8b"
    return _MODEL


def _ollama(prompt, n=380):
    try:
        body = json.dumps({"model": _model(), "prompt": prompt, "stream": False,
                           "think": False, "options": {"temperature": 0.2, "num_gpu": 0}}).encode()
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            _d = json.loads(r.read().decode())
            txt = (_d.get("response") or _d.get("thinking") or "").strip()
        # strip model chatter lead-ins ("Here is...:", "Sure, here's...:") so only the drafted text remains
        txt = re.sub(r"^(sure[,!]?\s*)?(here(\s+is|'s)|below is|the following is)[^\n:]*:\s*", "", txt, flags=re.I).strip()
        txt = txt.strip('"').strip()
        return txt[:2000]
    except Exception:
        return ""


def _findings(goal, pillar):
    p = _PILL.get(pillar, {"label": pillar, "desc": ""})
    ai = _ollama("Write 2-3 sentence legislative FINDINGS AND PURPOSE for a Hawaii bill addressing this "
                 "goal, in the dignified plain style of a real bill preamble (no markdown, no list): %r. "
                 "Frame it in service of %s — %s." % (goal[:300], p["label"], p["desc"]))
    if ai:
        return ai
    return ("The legislature finds that %s. The purpose of this Act is to advance that goal in service of "
            "the principle of %s (%s)." % (goal.rstrip(". ").lower(), p["label"], p["desc"]))


def _state_bill(goal, pillar, section):
    p = _PILL.get(pillar, {"label": pillar})
    sec = section or "[HRS chapter/section to amend — name it]"
    findings = _findings(goal, pillar)
    amend = _ollama("Draft ONE concise statutory duty/standard clause for a Hawaii bill toward this goal: %r. "
                    "Output ONLY the clause itself — no section number, no citation, no preamble, no quotes." % goal[:300]) \
        or "Each agency shall [the specific duty/standard that achieves the goal]."
    return {
        "title": "A BILL FOR AN ACT RELATING TO %s" % (p["label"].upper()),
        "preamble": "SECTION 1. " + findings,
        "amendment": ("SECTION 2. Section %s, Hawaii Revised Statutes, is amended to read (NEW material "
                      "_underscored_; deleted material [bracketed]):\n\n    _%s_" % (sec, amend)),
        "effective": "SECTION 3. This Act shall take effect upon its approval.",
        "process": "Lawful path: a legislator introduces this in the House or Senate → committee referral(s) "
                   "→ three readings → passage by both chambers → transmittal to the Governor. Confirm the "
                   "current text of %s before filing." % sec,
        "verify": "Verify the current text + section number of %s on capitol.hawaii.gov; this draft NAMES the "
                  "provision but does not reproduce its existing words." % sec}


def _charter_amendment(goal, pillar, section):
    p = _PILL.get(pillar, {"label": pillar, "desc": ""})
    sec = section or "[Maui Charter article/section to amend — name it]"
    rationale = _ollama("Write a 2-3 sentence rationale for a Maui County Charter amendment toward this goal: "
                        "%r, in service of %s (%s). Plain, dignified, no markdown." % (goal[:300], p["label"], p["desc"])) \
        or ("This amendment helps the County better serve %s by %s." % (p["label"].lower(), goal.rstrip(". ").lower()))
    language = _ollama("Draft ONE concise Maui County Charter amendment clause toward this goal: %r. Output only "
                       "the proposed charter language." % goal[:300]) \
        or "The County shall [the specific charter duty/structure that achieves the goal]."
    qgoal = goal.rstrip(". ")
    return {
        "section": sec,
        "proposed_language": "Amend %s to add (NEW material _underscored_):\n\n    _%s_" % (sec, language),
        "rationale": rationale,
        "ballot_question": "Shall the Revised Charter of the County of Maui be amended to %s?" % qgoal[:140].lower(),
        "process": "Lawful path: proposed by the Charter Commission and/or by Council resolution, then "
                   "RATIFIED BY THE VOTERS at a general election. Verify the current Charter amendment "
                   "article/section + the proposal deadline with the County Clerk / Corporation Counsel.",
        "verify": "Verify the current %s text on Municode + the Charter's amendment procedure before filing." % sec}


def draft(goal, scope="both", pillar="P4", section=None):
    """Draft a state bill and/or a Maui Charter amendment aligned to a 12 Stones pillar. scope: state|maui_charter|both."""
    p = _PILL.get(pillar, {"label": pillar, "desc": ""})
    out = {"goal": goal, "scope": scope, "pillar": pillar, "pillar_label": p["label"],
           "charter_lens": "Aligned to the 12 Stones Sovereign Charter pillar %s (%s) — the author's values "
                           "framework (a lens), NOT existing government law." % (pillar, p["label"]),
           "ai": bool(_ollama("ok", 2)),
           "honest": "DRAFT SUGGESTION for the lawful amendment process — not law, not legal advice. "
                     "Verify all section numbers; state law goes through the Legislature, charter changes are "
                     "ratified by the voters. Confirm with Corporation Counsel.",
           "generated": int(time.time())}
    # a single --section is an HRS-style ref for the state bill, or a Charter ref for a charter-only draft
    if scope in ("state", "both"):
        out["state_bill"] = _state_bill(goal, pillar, section)
    if scope in ("maui_charter", "both"):
        out["charter_amendment"] = _charter_amendment(goal, pillar, section if scope == "maui_charter" else None)
    return out


def render_text(d):
    L = ["DRAFT — %s (pillar %s · %s)" % (d["goal"], d["pillar"], d["pillar_label"]),
         d["charter_lens"], ""]
    if d.get("state_bill"):
        b = d["state_bill"]
        L += ["=" * 60, "STATE BILL", b["title"], "", b["preamble"], "", b["amendment"], "", b["effective"], "",
              "PROCESS: " + b["process"], "VERIFY: " + b["verify"], ""]
    if d.get("charter_amendment"):
        c = d["charter_amendment"]
        L += ["=" * 60, "MAUI CHARTER AMENDMENT", "Section: " + c["section"], "", c["proposed_language"], "",
              "RATIONALE: " + c["rationale"], "", "BALLOT QUESTION: " + c["ballot_question"], "",
              "PROCESS: " + c["process"], "VERIFY: " + c["verify"], ""]
    L += ["-" * 60, d["honest"]]
    return "\n".join(L)


def stage(d):
    os.makedirs(STAGE, exist_ok=True)
    slug = "%d_%s_%s" % (d["generated"], d["pillar"], re.sub(r"[^a-z0-9]+", "-", d["goal"].lower())[:40].strip("-"))
    json.dump(d, open(os.path.join(STAGE, "draft_%s.json" % slug), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(STAGE, "draft_%s.txt" % slug), "w", encoding="utf-8", newline="\n").write(render_text(d))
    return os.path.join(STAGE, "draft_%s.txt" % slug)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goal", required=True)
    ap.add_argument("--scope", default="both", choices=["state", "maui_charter", "both"])
    ap.add_argument("--pillar", default="P4", choices=[p[0] for p in PILLARS])
    ap.add_argument("--section", default=None)
    a = ap.parse_args()
    d = draft(a.goal, a.scope, a.pillar, a.section)
    print(render_text(d))
    print("\nstaged ->", stage(d))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
