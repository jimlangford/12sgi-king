#!/usr/bin/env python3
"""tenant_builder.py — the BUILDER-tier engine: a member builds their OWN govOS tenant (Jimmy 2026-06-18).

The top tier ($999/mo · $11,000/yr, config/civic_tiers.json) lets a Stripe-verified builder stand up their
OWN Maui County TENANT in the govOS multi-tenant model and get functionality + system suggestions for it —
a private workspace where they design how their corner of the county software should work. This engine takes
a goal + desired functionality and produces a PRIVATE tenant SPEC: a tenant id, the 12 Stones pillar(s) it
serves, and a build plan of suggested MODULES (drawn from the civic surfaces we already build) + new systems.

It SUGGESTS + SPECS — it does not auto-provision a live tenant (that is a deliberate deploy step). Output is
PRIVATE (the builder's workspace) and never published (leak gate). Local AI (Ollama) proposes modules/systems
toward the goal; a catalog-keyword fallback keeps it working offline. Stdlib only.

API:
  catalog()                                   -> [ {module, what} ]   (the buildable govOS modules)
  build_spec(member, tenant_name, goal, ...)  -> dict (the private tenant spec + build plan)
  stage(spec)                                 -> path
CLI: python tenant_builder.py --member me --name "Upcountry Water Watch" --goal "track every water-meter decision + rate change"
"""
import os, sys, json, re, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
STAGE = os.path.join(PROJ, "reports", "_status", "tenant_builds")        # PRIVATE; never published

# The buildable govOS modules (the surfaces we already produce) a builder can instantiate for their tenant.
CATALOG = [
    ("dashboard", "a tenant overview dashboard (the carded hub)"),
    ("open_data", "an Open Data catalog (downloadable JSON + DCAT) for the tenant's records"),
    ("oversight_calculator", "executive-funds oversight calculator (awards, vendor concentration, contracts x donors)"),
    ("money_x_votes", "campaign money x votes joins for the tenant's deciders"),
    ("sunshine_compliance", "HRS 92 Sunshine deadline + ready-to-file notice + send-to-newspaper"),
    ("agenda_explainer", "plain-language agenda explainer + reels"),
    ("feature_board", "public request + vote board (free tier) for the tenant"),
    ("law_drafter", "state bill / charter amendment drafter (12 Stones pillar-aligned)"),
    ("title_navigator", "plain-language code/Title navigator + permit assistant + parcel lookup"),
    ("moon_offering", "the daily kaulana mahina / aloha civic offering"),
]
_CAT_LABEL = {m: w for m, w in CATALOG}
_CAT_KW = {
    "oversight_calculator": ["fund", "spend", "contract", "award", "budget", "audit", "money", "vendor"],
    "money_x_votes": ["donor", "campaign", "vote", "influence", "finance"],
    "sunshine_compliance": ["meeting", "notice", "agenda", "sunshine", "deadline", "testify", "hearing"],
    "agenda_explainer": ["agenda", "explain", "plain language", "what's on"],
    "feature_board": ["request", "vote", "suggest", "idea", "community"],
    "law_drafter": ["law", "bill", "charter", "amend", "ordinance", "rule"],
    "title_navigator": ["permit", "zoning", "parcel", "tmk", "code", "title", "build", "land"],
    "open_data": ["data", "download", "records", "transparency", "dataset"],
    "money_x_votes2": [],
    "moon_offering": ["moon", "aloha", "culture", "kumulipo"],
    "dashboard": [],
}
PILLARS = {"P1": "Food Security", "P2": "Education", "P3": "Truth", "P4": "Sovereign Charter"}


def catalog():
    return [{"module": m, "what": w} for m, w in CATALOG]


def _model():
    try:
        d = json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5).read())
        names = [m.get("name", "") for m in d.get("models", [])]
        return os.environ.get("OLLAMA_MODEL") or next((n for n in names if n.startswith(("llama", "qwen", "gemma"))), "llama3.1:8b")
    except Exception:
        return os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


def _ollama(prompt):
    try:
        body = json.dumps({"model": _model(), "prompt": prompt, "stream": False, "think": False, "options": {"temperature": 0.2, "num_gpu": 0}}).encode()
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            _d = json.loads(r.read().decode())
            return (_d.get("response") or _d.get("thinking") or "").strip()[:1500]
    except Exception:
        return ""


def _suggest_modules(goal):
    """Pick the modules that fit the goal. AI ranks; keyword fallback. Always include a dashboard."""
    ai = _ollama("From this list of module ids %s, return ONLY a comma-separated list of the 3-6 ids that best "
                 "fit this goal (no prose): %r" % (json.dumps([m for m, _ in CATALOG]), goal[:300]))
    picked = []
    if ai:
        picked = [m for m, _ in CATALOG if m in ai]
    if not picked:
        t = goal.lower()
        picked = [m for m in _CAT_KW if any(k in t for k in _CAT_KW.get(m, []))]
    picked = list(dict.fromkeys(["dashboard"] + picked))[:6]
    return picked


def build_spec(member, tenant_name, goal, pillars=None, modules=None):
    tid = "build_" + re.sub(r"[^a-z0-9]+", "_", (tenant_name or "tenant").lower()).strip("_")[:32]
    mods = modules or _suggest_modules(goal)
    plan = _ollama("In 3-4 plain sentences, outline how a small govOS tenant would deliver this goal using "
                   "these modules %s: %r. No markdown." % (json.dumps(mods), goal[:300])) \
        or ("Stand up a private tenant with a dashboard, wire the selected modules to the tenant's public "
            "records, and iterate from the request board.")
    return {
        "tenant_id": tid, "label": tenant_name, "owner": member, "goal": goal,
        "pillars": pillars or ["P4"], "pillar_labels": [PILLARS.get(p, p) for p in (pillars or ["P4"])],
        "modules": [{"module": m, "what": _CAT_LABEL.get(m, m)} for m in mods],
        "build_plan": plan, "private": True, "created": int(time.time()),
        "model": "govOS multi-tenant — every project is a tenant (config/tenants.json)",
        "honest": "A private SPEC + suggestions for the builder's own tenant — analyzes PUBLIC data + the "
                  "builder's own account; never auto-provisioned or published. Confirm any civic claim against the source.",
        "next": "Review the spec, then we instantiate the chosen modules in your private tenant workspace."}


def stage(spec):
    os.makedirs(STAGE, exist_ok=True)
    p = os.path.join(STAGE, "%s.json" % spec["tenant_id"])
    json.dump(spec, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--member", default="verified:member")
    ap.add_argument("--name", required=True)
    ap.add_argument("--goal", required=True)
    ap.add_argument("--pillars", default="P4", help="comma-separated P1..P4")
    a = ap.parse_args()
    spec = build_spec(a.member, a.name, a.goal, [p.strip() for p in a.pillars.split(",") if p.strip()])
    print("BUILDER TENANT SPEC — %s (%s)" % (spec["label"], spec["tenant_id"]))
    print("  owner:", spec["owner"], "| pillars:", ", ".join(spec["pillar_labels"]))
    print("  modules:")
    for m in spec["modules"]:
        print("    - %-22s %s" % (m["module"], m["what"]))
    print("  build plan:", spec["build_plan"])
    print("\nstaged ->", stage(spec))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
