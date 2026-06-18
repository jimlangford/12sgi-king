# -*- coding: utf-8 -*-
"""
studio_parity.py - heal the STUDIO side UP to the CIVIC standard, and keep it there.

CIVIC is the reference. This reads config/parity_standard.json (the single declared standard)
and checks the studio surfaces on three dimensions - LOOK (Yale-blue tokens, no gold/purple),
TENANT LOGIC (the unified config/tenants.json model + per-tenant infra), and iPad-WORKABLE
(viewport + responsive, served over :8770/Tailscale). It SCORES each (0-100) and, with --heal,
auto-fixes the one thing that is safe to auto-fix: COLOR drift (color-only remap, byte-verified;
cosmology zone hexes are never touched). Structural gaps (tenant infra, per-feature iPad work)
are FLAGGED for the build plan - never auto-restructured.

Designed to be called by quadrant_selfheal.py (hourly, report+score) and the daily audit_cycle
(--heal). Stdlib only. Defensive: a missing source -> low score, never a crash.

Writes reports/_status/studio_parity.json (+ .html badge).  Run: python studio_parity.py [--heal]
"""
import os, re, json, sys, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CFG  = os.path.join(ROOT, "config")
STATUS = os.path.join(ROOT, "reports", "_status")

def load(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

STD = load(os.path.join(CFG, "parity_standard.json"), {}) or {}
TEN = load(os.path.join(CFG, "tenants.json"), {}) or {}
# intentional non-light registers (e.g. the dark-blue Studio shell) — LOOK parity is skipped + never healed
EXEMPT = {os.path.normpath(os.path.join(ROOT, r))
          for r in (STD.get("look", {}).get("register_exempt", {}) or {}) if r != "_note"}

def _surfaces():
    out = []
    for rel in (STD.get("surfaces_to_check", {}) or {}).get("studio", []):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p): out.append(p)
    # include any per-tenant studio pages once they exist
    sdir = os.path.join(ROOT, "app", "studio")
    if os.path.isdir(sdir):
        for fn in os.listdir(sdir):
            if fn.startswith("tenant_") and fn.endswith(".html"):
                out.append(os.path.join(sdir, fn))
    return sorted(set(out))

def check_look(text):
    look = STD.get("look", {})
    present = all(t.lower() in text.lower() for t in look.get("required_present", []))
    banned = look.get("banned_text_tokens", {})
    hits = []
    for grp in ("gold", "purple", "dark_bg"):
        for tok in banned.get(grp, []):
            if re.search(re.escape(tok), text, re.I):
                hits.append(tok)
    return present, sorted(set(hits))

def check_ipad(text):
    ip = STD.get("ipad_workable", {})
    has_vp = any(re.search(m, text, re.I) for m in ip.get("required_meta", []))
    has_resp = ("@media" in text) or ("max-width" in text) or ("min-width" in text) or ("touch-action" in text)
    return has_vp, has_resp

def heal_colors(text):
    hm = STD.get("look", {}).get("heal_map", {})
    n = 0
    for old, new in hm.items():
        new_text = re.sub(re.escape(old), new, text, flags=re.I)
        if new_text != text:
            n += text.lower().count(old.lower()); text = new_text
    return text, n

def main():
    heal = "--heal" in sys.argv
    surfaces = _surfaces()
    look_ok = ipad_ok = 0
    look_denom = 0
    look_hits_total = 0
    healed = []
    per = []
    for p in surfaces:
        try: t = open(p, encoding="utf-8").read()
        except Exception: continue
        is_exempt = os.path.normpath(p) in EXEMPT      # intentional dark register — skip LOOK + never heal it
        present, hits = check_look(t)
        if heal and hits and not is_exempt:            # NEVER recolor an exempt (dark-register) surface to light
            t2, n = heal_colors(t)
            if n and t2 != t:
                open(p, "w", encoding="utf-8", newline="\n").write(t2)
                disk = open(p, encoding="utf-8").read()
                if disk == t2:
                    healed.append({"file": os.path.basename(p), "tokens_recolored": n})
                    t = t2; present, hits = check_look(t)   # re-check post-heal
        vp, resp = check_ipad(t)
        if is_exempt:
            look_clean = None                          # LOOK is N/A for an exempt dark-register surface
        else:
            look_clean = present and not hits
            look_denom += 1
            if look_clean: look_ok += 1
            look_hits_total += len(hits)
        if vp and resp: ipad_ok += 1
        per.append({"file": os.path.basename(p), "look_clean": look_clean, "look_exempt": is_exempt,
                    "banned_found": (hits if not is_exempt else []), "ipad_viewport": vp, "ipad_responsive": resp})

    nsurf = max(1, len(surfaces))
    # tenant-logic parity: studio tenants registered with the full schema + (live infra присутствие)
    req = STD.get("tenant_logic", {}).get("required_tenant_fields", [])
    studio_q = set(STD.get("tenant_logic", {}).get("studio_quadrants", []))
    studio_tenants = [t for t in TEN.get("tenants", []) if t.get("quadrant") in studio_q]
    well_formed = sum(1 for t in studio_tenants if all(t.get(f) for f in req))
    # live infra check: does any per-tenant studio surface exist yet? (civic has tenant_<id>.html)
    served_tenant_pages = [s for s in surfaces if os.path.basename(s).startswith("tenant_")]
    def _has(rel, tok):
        try: return tok in open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore").read()
        except Exception: return False
    # dynamic per-tenant serving = the studio control layer: /api/tenants route + the switcher chrome
    served_dynamic = _has("app/studio/studio_server.py", "/api/tenants") and _has("app/studio/studio.html", "scl-bar")
    served = bool(served_tenant_pages) or served_dynamic
    tenant_score = round(100 * (
        0.5 * (well_formed / max(1, len(studio_tenants))) +            # registered with schema
        0.5 * (1 if served else 0)                                    # served per-tenant (static pages OR dynamic control layer)
    )) if studio_tenants else 0

    look_score = 100 if look_denom == 0 else round(100 * look_ok / look_denom)
    ipad_score = round(100 * ipad_ok / nsurf)
    overall = round((look_score + tenant_score + ipad_score) / 3)

    res = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "reference": STD.get("reference_side", "civic"),
        "healed_this_run": healed,
        "scores": {"look": look_score, "tenant_logic": tenant_score, "ipad_workable": ipad_score, "overall": overall},
        "look": {"surfaces": nsurf, "clean": look_ok, "banned_token_hits": look_hits_total},
        "tenant_logic": {"studio_tenants": len(studio_tenants), "well_formed": well_formed,
                         "served_per_tenant_pages": len(served_tenant_pages), "served_dynamic_control_layer": served_dynamic,
                         "gap": "studio tenants are registered but NOT yet served per-tenant on :8770 (civic has tenant_<id>.html + depth + switcher)" if not served_tenant_pages else "served"},
        "ipad_workable": {"surfaces": nsurf, "ok": ipad_ok},
        "per_surface": per,
        "flags_for_build_not_auto_healed": [
            "TENANT: build per-studio-tenant served surfaces on :8770 + a tenant switcher reading config/tenants.json (mirror civic tenant_<id>.html + depth)",
            "iPad: inventory + close per-feature desktop-only blockers (align ONE iPad layer with the SAGE/UE5 session)",
            "LOOK: converge studio onto the SHARED token CSS (tokens/colors.css) instead of a parallel :root",
        ],
    }
    os.makedirs(STATUS, exist_ok=True)
    with open(os.path.join(STATUS, "studio_parity.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("studio_parity: overall %d  (look %d / tenant %d / ipad %d)%s" % (
        overall, look_score, tenant_score, ipad_score, "  [HEALED %d file(s)]" % len(healed) if healed else ""))
    for row in per:
        print("  %-22s look_clean=%s banned=%s vp=%s resp=%s" % (
            row["file"], row["look_clean"], row["banned_found"] or "-", row["ipad_viewport"], row["ipad_responsive"]))
    return res

if __name__ == "__main__":
    main()
