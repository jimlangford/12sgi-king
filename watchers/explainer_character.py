#!/usr/bin/env python3
"""explainer_character.py — CIVIC guardrail over studio's character-animation capability (Jimmy 2026-06-18).

Studio shipped batch/explainer_animate.animate_character(...) (still -> Wan2.2 i2v, GPU-gated). This is the
CIVIC pick-up: it wraps that primitive but ENFORCES the civic integrity rules so a civic explainer can never
animate a real person or the photoreal hero:

  • FICTIONAL/GENERIC NARRATORS ONLY — {LUNA, POLYNESIAN_STANDARD, NYC_STANDARD}. NEVER the real-Jimmy/James
    hero LoRA, a real official, Queen Liliʻuokalani, ORACELICA (Alicia Keys), or any actor-archetype likeness.
    (Standing rule: civic agenda visuals are env-only/no-likeness; + AI synthetic-media law: never deceptively
    synthesize a real person — docs/GOVOS_LOGIC_REDESIGN.md, docs/REFERENCES_CIVIC_PLATFORM.md §6.)
  • AI-DISCLOSURE REQUIRED — the result is tagged so the page/poster MUST show an "AI-generated" badge +
    embed C2PA before it can be shown/posted.
  • STAGE-ONLY — creative content; publish-allowlist = only moon + Sunshine-Law agenda posts publish. The clip
    is staged for preview / à-la-carte delivery to a paying client's OWN channels — never our public surfaces.
  • NEVER-INTERRUPT — defers to any active studio render (GPU co-tenant); only renders when the GPU is free.

CIVIC never imports the heavy studio render stack at module load — batch/explainer_animate is lazy-imported
only when an animation is actually requested. Stdlib only at import time.

API:
  narrators()                 -> [ {id, still, available} ]
  animate(narrator=DEFAULT, seed=1234) -> {ok|refused|deferred, media?, disclosure, stage_only, ...}
CLI: python explainer_character.py --list | --animate POLYNESIAN_STANDARD
"""
import os, sys, json, glob

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
REFS = os.path.join(PROJ, "exports", "character_refs")
STATUS = os.path.join(PROJ, "reports", "_status", "explainers")

# the ONLY characters a CIVIC explainer may animate — fictional / generic, never a real person or the hero.
CIVIC_NARRATORS = ("POLYNESIAN_STANDARD", "NYC_STANDARD", "LUNA")
DEFAULT = "POLYNESIAN_STANDARD"                 # most neutral: a generic archetype, no specific person
# explicit reasons real-person/hero characters are refused on civic (defensive denylist for clarity)
_BANNED_REASON = ("not allowed on CIVIC: this is a real person or the photoreal hero likeness. Civic explainers "
                  "use FICTIONAL/generic narrators only (env-only/no-likeness rule + AI synthetic-media law).")

DISCLOSURE = {"required": True, "badge": "⚙ AI-generated", "c2pa": True,
              "text": "AI-generated fictional narrator — not a real person.",
              "stage_only": True}


def narrators():
    out = []
    for n in CIVIC_NARRATORS:
        still = os.path.join(REFS, n + ".png")
        out.append({"id": n, "still": still, "available": os.path.exists(still)})
    return out


def _gpu_busy():
    """True if a studio render is using the GPU (so we DEFER — never interrupt). Best-effort."""
    try:
        sys.path.insert(0, HERE)
        import comfy_client as CC
        free = CC.vram_free_mib()
        return free >= 0 and free < 6000        # the co-tenant gate: <6 GB free => a render is active
    except Exception:
        return False                            # unknown -> let the studio gate_gpu() decide


def animate(narrator=DEFAULT, seed=1234, tier=None):
    """Animate an APPROVED fictional narrator for a civic explainer. Requires the 'animated_explainer'
    capability (county/$999 tier). Refuses real-person/hero characters, defers to active studio renders,
    and tags the result AI-disclosed + stage-only."""
    # tier gate — billing_mode() is the universal answer: "denied" | "alacarte" | "included"
    _mode = "included"   # default when no tier passed (internal/owner use)
    if tier is not None:
        sys.path.insert(0, HERE)
        import tier_access as _ta
        _mode = _ta.billing_mode(tier, "animated_explainer")
        if _mode == "denied":
            return {"ok": False, "refused": True, "tier_required": "dashboards",
                    "upgrade_url": "/king/upgrade?feature=animated_explainer",
                    "reason": "tier '%s' lacks animated_explainer" % tier,
                    "cta": "Upgrade to Private Dashboards ($99/mo) for à-la-carte animated explainers, or County ($999/mo) for included service."}
    narrator = (narrator or DEFAULT).upper() if narrator else DEFAULT
    if narrator not in CIVIC_NARRATORS:
        return {"ok": False, "refused": True, "narrator": narrator, "reason": _BANNED_REASON,
                "allowed": list(CIVIC_NARRATORS)}
    still = os.path.join(REFS, narrator + ".png")
    if not os.path.exists(still):
        return {"ok": False, "refused": True, "narrator": narrator,
                "reason": "no still for this narrator at exports/character_refs/%s.png" % narrator}
    if _gpu_busy():
        return {"ok": False, "deferred": True, "narrator": narrator,
                "reason": "GPU busy with a studio render — deferring (never interrupt). Retry when free."}
    # lazy-import the studio primitive ONLY now (heavy render stack)
    try:
        sys.path.insert(0, os.path.join(PROJ, "batch"))
        import explainer_animate as EA
        r = EA.animate_character(narrator, seed=seed)
    except Exception as e:
        return {"ok": False, "error": "studio animate unavailable: %s" % str(e)[:160], "narrator": narrator}
    if not r.get("ok"):
        return {"ok": False, "narrator": narrator, "error": r.get("error", "render failed")}
    return {"ok": True, "narrator": narrator, "media": r.get("media"), "clip": r.get("clip"),
            "disclosure": DISCLOSURE, "stage_only": True,
            "billing_mode": _mode,
            "billing": "per-render (civic_pricing.json premium_reel)" if _mode == "alacarte" else "included in subscription",
            "note": "Staged fictional narrator for civic explainer — AI-disclosed, never auto-published; "
                    "served privately at /explainer-media/ for preview / paid à-la-carte delivery."}


def latest_staged(narrator=None):
    """The most recent DONE narrator animation (for the page to embed in a preview/à-la-carte context)."""
    best = None
    for p in glob.glob(os.path.join(STATUS, "*.json")):
        try:
            j = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if j.get("state") == "done" and j.get("media") and (j.get("character") or "").upper() in CIVIC_NARRATORS:
            if narrator and (j.get("character") or "").upper() != narrator.upper():
                continue
            if best is None or j.get("updated", "") > best.get("updated", ""):
                best = j
    return best


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--animate", default=None, help="narrator id (POLYNESIAN_STANDARD|NYC_STANDARD|LUNA)")
    ap.add_argument("--seed", type=int, default=1234)
    a = ap.parse_args()
    if a.animate:
        print(json.dumps(animate(a.animate, a.seed), ensure_ascii=False, indent=1)); return 0
    print("Civic explainer narrators (fictional/generic only — never a real person/hero):")
    for n in narrators():
        print("  [%s] %-20s %s" % ("ok" if n["available"] else "--", n["id"], n["still"]))
    print("\nDefault:", DEFAULT, "| stage-only + AI-disclosure required | refuses hero/real-person characters")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
