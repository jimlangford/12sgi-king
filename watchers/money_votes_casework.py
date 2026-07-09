#!/usr/bin/env python3
"""money_votes_casework.py — work the flagged money×votes pairs into verdicts (Jimmy 2026-06-18:
"continue this week's work on Maui Council ... when complete use that skill on the other tenants").

THE SKILL: take the contractor↔donor↔official matches the engine flagged (vendor_donor_join) and work
each into an HONEST verdict — how strong is the same-entity money pattern, what is the one question it
raises, and the exact public record that would answer it. Lawful donations; every case is a QUESTION for
oversight, never an accusation. PRIVATE owner-side (names officials over public records) until publish-confirm.

TENANT-PARAMETERIZED so the same skill runs on every tenant once Maui is proven: pass --tenant; it reads
that tenant's vendor_donor_join data (falls back to the canonical Maui file). Output:
reports/_status/casework_<tenant>.json (+ .html). Stdlib only.
"""
import os, sys, json, re, html
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(PROJ, "reports", "mauios")
ST = os.path.join(PROJ, "reports", "_status")
HST = timezone(timedelta(hours=-10))
esc = lambda s: html.escape(str(s if s is not None else ""))

# roles with the most direct power over awards/budget — a donation to one of these is the tighter question
HIGH_ROLE = re.compile(r"BFED|budget|finance|chair|procure|award|appropriat", re.I)
GENERIC = {"the", "inc", "llc", "ltd", "co", "company", "corp", "corporation", "of", "and", "hawaii",
           "hawaiʻi", "maui", "county", "group", "trust", "lp", "llp", "dba", "associates", "engineers",
           "engineering", "architects", "consulting", "services"}


def toks(name):
    return {w for w in re.split(r"[^a-z0-9ʻ]+", (name or "").lower()) if w and w not in GENERIC and len(w) > 2}


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def vdj_for(tenant):
    # RESPECT EACH TENANT: use ONLY that tenant's own data. The unsuffixed vendor_donor_join.json is Maui's
    # canonical file, so it may serve maui; for any OTHER tenant, NO fallback — absent data => empty, never
    # Maui's contractors/officials mislabeled as another county. (Fabrication guard, Jimmy 2026-06-19.)
    cands = ["vendor_donor_join_%s.json" % tenant]
    if tenant == "maui":
        cands.append("vendor_donor_join.json")
    for cand in cands:
        p = os.path.join(M, cand)
        if os.path.exists(p):
            return load(p, {}), cand
    return {}, None


def same_entity_confidence(vendor, contributor, basis):
    """How sure are we the donor IS the vendor (not a generic-token coincidence)? token overlap + basis."""
    vt, ct = toks(vendor), toks(contributor)
    if not vt or not ct:
        return 0.0, "no distinctive tokens"
    overlap = vt & ct
    score = len(overlap) / max(1, len(vt | ct))
    note = ("shares %s" % ", ".join(sorted(overlap))) if overlap else "no shared distinctive token"
    if basis == "firm":
        score = min(1.0, score + 0.25)              # a firm-basis donation is the vendor entity itself
        note += "; firm-basis (vendor entity)"
    return round(score, 2), note


def work_case(m):
    hits = m.get("hits") or []
    h0 = hits[0] if hits else {}
    vendor = m.get("vendor") or ""
    contributor = h0.get("contributor") or ""
    official = h0.get("official_label") or h0.get("official") or ""
    basis = h0.get("basis", "?")
    award = m.get("award_total") or 0
    contrib = m.get("contrib_total") or 0
    conf, conf_note = same_entity_confidence(vendor, contributor, basis)
    high_role = bool(HIGH_ROLE.search(official))
    # AUDIT H2 (2026-07-07): attribute money HONESTLY. contrib_total sums the vendor's donors across ALL
    # matched officials (vendor_donor_join), but this case names ONE official (hits[0], the largest single
    # contribution). Printing the aggregate next to one name overstates that person's money — a
    # civic-integrity/libel line. Report the amount tied to THE NAMED OFFICIAL; note the cross-official
    # aggregate separately when the vendor's donors reached more than one official.
    officials_all = m.get("officials") or sorted(
        {(h.get("official_label") or h.get("official") or "") for h in hits})
    named_contrib = sum((h.get("amount") or 0) for h in hits
                        if (h.get("official_label") or h.get("official")) == official)
    n_officials = len([o for o in officials_all if o])
    also = ((" (the firm's donors gave $%s to %d officials in total)"
             % ("{:,.0f}".format(contrib), n_officials)) if n_officials > 1 else "")
    # honest verdict: strength = money at stake × same-entity confidence × role relevance
    strong = award >= 500000 and conf >= 0.34 and (high_role or basis == "firm")
    moderate = (award >= 100000 and conf >= 0.34) or (high_role and conf >= 0.5)
    verdict = "EXAMINE" if strong else ("NOTE" if moderate else "LIKELY-COINCIDENCE")
    question = ("%s holds $%s in county awards and %s gave $%s to %s%s. Did %s vote on or sit over the "
                "body that approved these awards, and was the donation disclosed at the time?" % (
                    vendor, "{:,.0f}".format(award), ("the firm" if basis == "firm" else "a person tied to it"),
                    "{:,.0f}".format(named_contrib), official.split(" - ")[0] or "the official", also,
                    official.split(" - ")[0] or "that member"))
    action = ("UIPA records request (HRS 92F) to the County Clerk: the procurement file + the recorded "
              "vote/approval on %s's awards, cross-referenced to %s's campaign filings." % (
                  vendor, official.split(" - ")[0] or "the member")) if verdict != "LIKELY-COINCIDENCE" else \
             "Low priority — likely a generic-name coincidence; hold unless the procurement file shows a tie."
    return {"vendor": vendor, "contributor": contributor, "official": official, "basis": basis,
            "award_total": award, "contrib_total": contrib, "official_contrib": round(named_contrib, 2),
            "officials_count": n_officials, "same_entity_confidence": conf,
            "confidence_note": conf_note, "high_power_role": high_role, "verdict": verdict,
            "question": question, "action": action}


def build(tenant):
    vdj, src = vdj_for(tenant)
    matches = vdj.get("matched") or vdj.get("matches") or []
    cases = sorted((work_case(m) for m in matches), key=lambda c: c["award_total"], reverse=True)
    summary = {"examine": sum(1 for c in cases if c["verdict"] == "EXAMINE"),
               "note": sum(1 for c in cases if c["verdict"] == "NOTE"),
               "likely_coincidence": sum(1 for c in cases if c["verdict"] == "LIKELY-COINCIDENCE"),
               "total_award_examined": round(sum(c["award_total"] for c in cases if c["verdict"] == "EXAMINE"), 2)}
    out = {"tenant": tenant, "source": src,
           "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST"),
           "integrity": ("Lawful donations + public awards. Each case is a QUESTION for oversight with the exact "
                         "record that answers it — never an accusation. PRIVATE owner-side until publish-confirm."),
           "summary": summary, "cases": cases}
    os.makedirs(ST, exist_ok=True)
    json.dump(out, open(os.path.join(ST, "casework_%s.json" % tenant), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    _html(out)
    return out


def _html(out):
    def row(c):
        cls = {"EXAMINE": "#b3261e", "NOTE": "#8a6d00", "LIKELY-COINCIDENCE": "#5a6b7b"}.get(c["verdict"], "#333")
        return ("<tr><td><b>%s</b></td><td>$%s</td><td>%s</td><td>$%s</td><td>%.2f</td>"
                "<td style='color:%s;font-weight:700'>%s</td></tr>"
                "<tr class=q><td colspan=6><div class= q>%s</div><div class=a>&rarr; %s</div></td></tr>" % (
                    esc(c["vendor"]), "{:,.0f}".format(c["award_total"]), esc(c["official"].split(" - ")[0]),
                    # AUDIT H2 FOLLOWUP (2026-07-07): render the NAMED official's contribution, not the vendor's
                    # cross-official aggregate — the published page was overstating the named person by up to ~5x.
                    "{:,.0f}".format(c.get("official_contrib", c["contrib_total"])), c["same_entity_confidence"], cls, esc(c["verdict"]),
                    esc(c["question"]), esc(c["action"])))
    rows = "".join(row(c) for c in out["cases"])
    s = out["summary"]
    doc = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           "<title>Money×Votes Casework — %s (PRIVATE)</title>"
           "<style>body{font-family:system-ui,Segoe UI,sans-serif;max-width:920px;margin:1.4rem auto;padding:0 1rem;color:#1f2d3a}"
           "h1{color:#0e4a84;font-size:1.3rem}.integrity{background:#eef5ff;border-left:3px solid #0e4a84;padding:.6rem .9rem;"
           "border-radius:8px;font-size:.9rem}table{border-collapse:collapse;width:100%%;margin-top:1rem;font-size:.9rem}"
           "th,td{border-bottom:1px solid #e3edf8;padding:.4rem .5rem;text-align:left}th{background:#f3f8ff;color:#0e4a84}"
           ".q td{background:#fbfdff;border-bottom:2px solid #e3edf8}.q .q{color:#33414f}.a{color:#1f6f54;font-size:.86rem;margin-top:.2rem}"
           ".pill{display:inline-block;background:#f3f8ff;border-radius:20px;padding:.1rem .6rem;margin-right:.4rem;font-size:.85rem}</style>"
           "<h1>Money &times; Votes Casework — %s <span style='font-size:.8rem;color:#b3261e'>PRIVATE</span></h1>"
           "<div class=integrity>%s</div>"
           "<p><span class=pill>%d to examine</span><span class=pill>%d to note</span>"
           "<span class=pill>%d likely coincidence</span><span class=pill>$%s in awards flagged to examine</span></p>"
           "<table><tr><th>Vendor</th><th>Awards</th><th>Funded official</th><th>Donation</th>"
           "<th>Same-entity</th><th>Verdict</th></tr>%s</table>"
           "<p style='color:#5a6b7b;font-size:.82rem;margin-top:1rem'>Generated %s · source %s · a question to the "
           "record, never a claim.</p>" % (
               esc(out["tenant"]), esc(out["tenant"]), esc(out["integrity"]), s["examine"], s["note"],
               s["likely_coincidence"], "{:,.0f}".format(s["total_award_examined"]), rows,
               esc(out["generated"]), esc(out["source"])))
    open(os.path.join(ST, "casework_%s.html" % out["tenant"]), "w", encoding="utf-8", newline="\n").write(doc)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="maui")
    a, _ = ap.parse_known_args()    # tolerant: safe when imported + main() called by audit_cycle.step()
    out = build(a.tenant)
    s = out["summary"]
    print("money_votes_casework[%s]: %d cases -> EXAMINE %d / NOTE %d / coincidence %d ($%s awards to examine)" % (
        a.tenant, len(out["cases"]), s["examine"], s["note"], s["likely_coincidence"],
        "{:,.0f}".format(s["total_award_examined"])))
    for c in out["cases"]:
        if c["verdict"] == "EXAMINE":
            print("  EXAMINE: %s ($%s) -> %s" % (c["vendor"], "{:,.0f}".format(c["award_total"]), c["official"].split(" - ")[0]))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
