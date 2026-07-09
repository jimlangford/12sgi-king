#!/usr/bin/env python3
"""cross_tenant_entity.py — find a single private actor whose money/role spans MULTIPLE tenants
(jurisdictions), and frame the ONE honest oversight question per jurisdiction.

Answers the FINDING (2026-06-21, audit->prosecutor): "does one contractor's money touch decisions across
multiple jurisdictions?" — e.g. NAN INC / Nan Chul Shin appears as a ~$80M C&C-Honolulu contractor (with
donations to the mayor + most of that council) AND as the Maui Hoʻonani Village LANDOWNER.

DISCIPLINE (non-negotiable — this is where cross-tenant analysis goes wrong):
  * Each jurisdiction is judged ON ITS OWN RECORD. A donation in tenant A does NOT taint a decision in
    tenant B made by DIFFERENT officials with ZERO money tie. We REPORT the footprint; we never let A's
    money imply B's corruption.
  * Lawful contracts + lawful donations. Every output is a QUESTION for oversight, named to the exact
    public record that answers it — never an accusation, never a verdict.
  * Same-entity confidence is shown honestly (name-token match is weak; independent sourcing in another
    tenant that NAMES the principal raises it). We never assert "same actor" on a shared common word.
  * PRIVATE owner-side until publish-confirm (names officials over public records).

Scans every tenant's casework_<tenant>.json + vendor_donor_join_<tenant>.json for the entity token(s),
collects the money role per tenant, and writes a per-jurisdiction sourced picture. The LANDOWNER / non-money
roles (which don't live in the money join) are passed in via --note so they're recorded as sourced context,
explicitly separated from the money questions. Stdlib only.

Usage:
  python tools/kilo-aupuni/cross_tenant_entity.py --entity "nan" --principal "shin" \
     --note "hi-maui:LANDOWNER (Hoonani Village Bills 163/164/165, Pulehu Rd Kahului); ZERO donation tie to Maui deciders (sourced: hoonani_money_lens.md). Judge the land decision on its merits."
"""
import os, sys, json, re
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(PROJ, "reports", "mauios")
ST = os.path.join(PROJ, "reports", "_status")
OUTDIR = os.path.join(ST, "prosecutor")
HST = timezone(timedelta(hours=-10))

GENERIC = {"the", "inc", "llc", "ltd", "co", "company", "corp", "corporation", "of", "and", "hawaii",
           "county", "group", "trust", "lp", "llp", "dba", "associates"}


def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def tenants():
    out = []
    for f in os.listdir(ST):
        m = re.match(r"casework_(.+)\.json$", f)
        if m:
            out.append(m.group(1))
    return sorted(set(out))


def vdj_path(tenant):
    # tenant naming: casework files use hi-honolulu / maui / ny; vendor_donor_join uses the same suffix,
    # with the unsuffixed file = Maui canonical.
    cands = [os.path.join(M, "vendor_donor_join_%s.json" % tenant)]
    if tenant in ("maui", "hi-maui"):
        cands.append(os.path.join(M, "vendor_donor_join.json"))
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def name_tokens(name):
    return {w for w in re.split(r"[^a-z0-9]+", (name or "").lower()) if w}


def tok_match(name, *needles):
    """True only if a needle is a WHOLE token in name (no loose substring false positives like
    'nan' inside 'renaissance')."""
    toks = name_tokens(name)
    return any(nd and nd.lower() in toks for nd in needles)


def matches(name, ent, principal):
    # kept for the casework JSON-blob scan; token-boundary to avoid substring false positives
    return tok_match(name, ent, principal)


def main():
    ent = arg("--entity", "")
    principal = arg("--principal", "")
    notes = [n for n in (arg("--note", "") or "").split(";;") if n.strip()]
    if not ent:
        print("ERROR: --entity required"); return 1

    per_tenant = []
    for t in tenants():
        rec = {"tenant": t, "money_role": None, "money_roles": [], "verdicts": []}
        # money side from vendor_donor_join — match the VENDOR by entity token (the donor hits live inside
        # that vendor's pair); collect ALL matching pairs (never overwrite).
        vdj = load(vdj_path(t), {}) or {}
        pairs = vdj.get("matched") or vdj.get("matches") or vdj.get("pairs") or []
        for p in pairs if isinstance(pairs, list) else []:
            if not isinstance(p, dict):
                continue
            v = p.get("vendor") or ""
            if tok_match(v, ent, principal):
                rec["money_roles"].append({
                    "vendor": v, "award_total": p.get("award_total"), "award_count": p.get("award_count"),
                    "contrib_total": p.get("contrib_total"), "officials": p.get("officials") or [],
                    "hits": [{"official": h.get("official_label") or h.get("official"),
                              "contributor": h.get("contributor"), "amount": h.get("amount"),
                              "basis": h.get("basis")} for h in (p.get("hits") or [])],
                })
        if rec["money_roles"]:
            rec["money_role"] = rec["money_roles"][0]  # back-compat single view
        # verdict side from casework
        cw = load(os.path.join(ST, "casework_%s.json" % t), {}) or {}
        cases = cw.get("cases") or cw.get("casework") or (cw if isinstance(cw, list) else [])
        for c in cases if isinstance(cases, list) else []:
            if matches(json.dumps(c), ent, principal):
                rec["verdicts"].append({"official": c.get("official"), "verdict": c.get("verdict"),
                                        "same_entity_confidence": c.get("same_entity_confidence"),
                                        "question": c.get("question"), "action": c.get("action")})
        if rec["money_role"] or rec["verdicts"]:
            per_tenant.append(rec)

    money_tenants = [r["tenant"] for r in per_tenant if r["money_role"]]
    rep = {
        "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        "entity": ent, "principal": principal,
        "DISCIPLINE": ("Each jurisdiction judged on its OWN record. A donation in one tenant does NOT taint "
                       "a decision in another made by different officials with zero money tie. Lawful "
                       "contracts + donations; every item is a QUESTION named to the record that answers it. "
                       "PRIVATE owner-side until publish-confirm."),
        "tenants_with_money_role": money_tenants,
        "cross_tenant_question": ("Is this the SAME private actor across jurisdictions (verify via DCCA "
                                  "principals), and where its money DOES touch deciders (only %s), did those "
                                  "deciders vote on/over its awards and disclose/recuse? Where it has a role "
                                  "but NO money tie, that jurisdiction's decision stands on its own merits."
                                  % (", ".join(money_tenants) or "none")),
        "per_tenant": per_tenant,
        "sourced_context_notes": notes,
        "verification_needed": [
            "DCCA BREG principals join: confirm the entity/principal is the SAME registered actor across the tenants named (raises/lowers same_entity_confidence; do not assert on a shared common word).",
        ] + ["Per money-tenant (%s): UIPA the procurement file + the recorded vote/approval on the awards, cross-referenced to each named official's campaign filings." % t for t in money_tenants],
    }
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, "cross_tenant_%s.json" % re.sub(r"[^a-z0-9]+", "_", ent.lower()))
    open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(rep, ensure_ascii=False, indent=2))
    print("cross_tenant_entity[%s]: money role in %d tenant(s): %s" % (ent, len(money_tenants), ", ".join(money_tenants) or "none"))
    for r in per_tenant:
        for mr in r.get("money_roles") or []:
            print("  $$ %-12s %-22s %s awards / %s contrib -> %d official(s)" % (
                r["tenant"], (mr.get("vendor") or "")[:22], "${:,.0f}".format(mr.get("award_total") or 0),
                "${:,.0f}".format(mr.get("contrib_total") or 0), len(mr.get("officials") or [])))
        for v in r["verdicts"]:
            print("     verdict[%s] %s (conf %s)" % (r["tenant"], v.get("verdict"), v.get("same_entity_confidence")))
    for n in notes:
        print("  ctx: %s" % n)
    print("  ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
