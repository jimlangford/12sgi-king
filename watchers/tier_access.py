#!/usr/bin/env python3
"""tier_access.py — the capability spine: tier -> capabilities, enforced in code (Jimmy 2026-06-18).

The govOS logic redesign (docs/GOVOS_LOGIC_REDESIGN.md) makes access TIER-SCOPED. This is the single
place that answers "what may this user do?" Every gated action calls can()/require() before running, so
access levels are enforced in code, not by convention. Reads config/civic_tiers.json (the capability map).

A user's TIER is resolved from the paid-orders ledger (the Stripe webhook records {verify_id|session ->
tier} on a completed checkout). No paid record => "free". Identity itself is the free-tier gate; payment
moves them up. Nothing here charges — it only reads who-paid-what to gate features.

BILLING MODEL (2026-06-25): no hard walls — every premium feature is reachable at every paying tier.
  "denied"   — tier cannot use this capability at all (free / ask_ai for premium features)
  "alacarte" — tier CAN use it, billed per-use on top of subscription (dashboards/$99)
  "included" — tier CAN use it, covered by the subscription (county/$999)
This means a $99 user is never locked out of a feature — they pay per use instead of being told "no."
New features: add capability to the right tiers' capabilities[] list; add to alacarte[] for $99,
leave it out of alacarte[] for $999 (included). billing_mode() reads civic_tiers.json at call time.

API:
  capabilities(tier)              -> [cap...]            (the tier's allowed actions)
  can(tier, capability)           -> bool
  require(tier, capability)       -> None | raises PermissionError
  billing_mode(tier, capability)  -> "included" | "alacarte" | "denied"
  tier_for(verify_id)             -> tier string         (from the paid-orders ledger)
  access(verify_id)               -> {tier, capabilities, billing_modes}
Stdlib only.
"""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
PLANS = os.path.join(PROJ, "config", "plans.json")          # CANONICAL (Jimmy 2026-06-18: keep studio names + live Stripe IDs)
TIERS = os.path.join(PROJ, "config", "civic_tiers.json")    # legacy capability map (fallback)
ORDERS = os.path.join(PROJ, "reports", "_status", "paid_orders.jsonl")     # webhook-recorded paid checkouts
# rank across the CANONICAL plans.json ids (+ legacy aliases so old orders still resolve)
_RANK = {"free": 0, "pro": 1, "studio_org": 2, "council_pro": 3, "commentary_seat": 2,
         "ask_ai": 1, "dashboards": 2, "county": 3, "member": 1, "builder": 3}
# capability map keyed to the canonical plans.json tier ids (civic enforcement; plans.json carries pricing/Stripe).
CAP_MAP = {
    "free":             ["read_public", "request", "vote"],
    "pro":              ["read_public", "request", "vote", "ai_advice", "civic_calc", "law_drafter",
                         "message_claude", "private_reports", "private_dashboards", "connect_post",
                         "analytics_read"],
    "studio_org":       ["read_public", "request", "vote", "ai_advice", "civic_calc", "law_drafter",
                         "message_claude", "private_reports", "private_dashboards", "connect_post",
                         "analytics_read", "analytics_api", "render_api",
                         "connect_crm", "connect_project", "connect_design", "connect_social",
                         "connect_music", "build_tenant", "county_data", "design_modules",
                         "animated_explainer"],
    "council_pro":      ["read_public", "request", "vote", "ai_advice", "civic_calc", "law_drafter",
                         "message_claude", "private_reports", "private_dashboards", "connect_post",
                         "analytics_read", "analytics_api", "render_api",
                         "connect_crm", "connect_project", "connect_design", "connect_social",
                         "connect_music", "build_tenant", "county_data", "design_modules",
                         "alacarte_studio", "animated_explainer",
                         "connect_civic_maps", "connect_marketing",
                         "connect_ifttt", "connect_pitch", "connect_blender", "connect_analytics"],
    # $99/seat govOS Commentary -- item-level meeting commentary, money proximity, non-compliance flags
    "commentary_seat":  ["read_public", "request", "vote", "ai_advice", "civic_calc",
                         "private_reports", "private_dashboards", "meeting_commentary",
                         "testimony_tracker", "compliance_flags"],
}
_ALIAS = {"ask_ai": "pro", "dashboards": "studio_org", "county": "council_pro", "member": "pro", "builder": "council_pro"}

# Fallback alacarte sets for legacy CAP_MAP tier ids (civic_tiers.json is the authoritative source;
# these kick in only when a tier isn't found there). Rule: studio_org/$99 = alacarte for all premium
# features; council_pro/$999 = everything included (empty set).
_ALACARTE_DEFAULTS = {
    "free":           set(),
    "pro":            set(),
    "studio_org":     {"animated_explainer", "burst_render", "cloud_render", "commentary_item",
                       "uipa_letter", "prosecutor_report", "agenda_animation", "render_api"},
    "council_pro":    set(),
    "commentary_seat": set(),
}


def _reg():
    try:
        return json.load(open(TIERS, encoding="utf-8"))
    except Exception:
        return {"tiers": {}}


def capabilities(tier):
    """Capability list for a tier. SERVE==CHARGE (Jimmy 2026-06-18): the ADVERTISED ladder in
    civic_tiers.json is the source of truth for the civic tier ids (ask_ai/dashboards/county) so a
    customer gets exactly what they paid for — never the next tier up. CAP_MAP only backstops the
    legacy studio ids (pro/studio_org/council_pro) that aren't in the civic ladder."""
    civ = (_reg().get("tiers", {}) or {}).get(tier) or {}
    if civ.get("capabilities"):
        return list(civ["capabilities"])           # advertised == enforced
    if tier in CAP_MAP:
        return list(CAP_MAP[tier])
    if tier in _ALIAS:
        return list(CAP_MAP[_ALIAS[tier]])
    return list(CAP_MAP["free"])


def can(tier, capability):
    return capability in capabilities(tier)


def require(tier, capability):
    if not can(tier, capability):
        raise PermissionError("tier '%s' lacks capability '%s'" % (tier, capability))


def billing_mode(tier, capability):
    """Universal billing gate for every premium feature.

    Returns one of three values:
      "denied"   — tier cannot access this capability at all
      "alacarte" — tier can use it, billed per-use on top of subscription ($99 dashboards model)
      "included" — tier can use it, fully covered by the subscription ($999 county model)

    Adding a new billable feature:
      1. Add the capability name to the right tiers' capabilities[] in civic_tiers.json
      2. Add it to the alacarte[] list for the $99 tier (dashboards)
      3. Leave it OUT of alacarte[] for the $999 tier (county) — it becomes included automatically
      4. Call billing_mode(user_tier, capability) before any billable action

    Examples:
      billing_mode("free",      "animated_explainer") -> "denied"
      billing_mode("dashboards","animated_explainer") -> "alacarte"  (pay per render)
      billing_mode("county",    "animated_explainer") -> "included"  (in subscription)
    """
    canonical = _ALIAS.get(tier, tier)
    if not can(tier, capability):
        return "denied"
    # civic_tiers.json is authoritative; CAP_MAP/_ALACARTE_DEFAULTS are the fallback
    civ_tier = (_reg().get("tiers", {}) or {}).get(tier) or (_reg().get("tiers", {}) or {}).get(canonical) or {}
    alacarte_caps = set(civ_tier.get("alacarte", []))
    if not alacarte_caps:
        alacarte_caps = _ALACARTE_DEFAULTS.get(canonical, _ALACARTE_DEFAULTS.get(tier, set()))
    return "alacarte" if capability in alacarte_caps else "included"


def billing_modes(tier):
    """Full billing-mode map for a tier: {capability: "included"|"alacarte"} for every
    capability the tier can access. Drives frontend UI (show price vs show checkmark)."""
    return {cap: billing_mode(tier, cap) for cap in capabilities(tier)}


def tier_for(key):
    """Resolve a user's paid tier from the orders ledger (webhook-recorded). The `key` is a verify_id OR an
    email — payment-link buyers are keyed by email, /subscribe buyers by verify_id. No record -> 'free'.
    Takes the HIGHEST tier on record for that key (e.g. an upgrade)."""
    if not key:
        return "free"
    k = str(key).strip().lower()
    best = "free"
    try:
        for line in open(ORDERS, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            md = o.get("metadata") or {}
            vid = (o.get("verify_id") or md.get("verify_id") or "").strip().lower()
            email = (o.get("email") or md.get("email") or "").strip().lower()
            tier = o.get("tier") or md.get("tier") or ""
            paid = (o.get("payment_status") in (None, "paid")) or o.get("paid") or o.get("amount_total")
            if (k == vid or (email and k == email)) and tier in _RANK and paid and _RANK[tier] > _RANK[best]:
                best = tier
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return best


def access(key):
    """key = verify_id OR email. Returns tier + full capability list + billing mode per capability."""
    t = tier_for(key)
    return {"tier": t, "capabilities": capabilities(t), "billing_modes": billing_modes(t)}


def main():
    import sys, argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify-id", default="")
    ap.add_argument("--check", default="", help="capability to test for the resolved tier")
    a = ap.parse_args()
    acc = access(a.verify_id)
    print("tier:", acc["tier"])
    print("capabilities:", ", ".join(acc["capabilities"]) or "(none)")
    if a.check:
        print("can %r: %s" % (a.check, can(acc["tier"], a.check)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
