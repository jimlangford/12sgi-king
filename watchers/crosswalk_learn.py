# -*- coding: utf-8 -*-
"""
crosswalk_learn.py - PER-TENANT, CONTINUOUS-LEARNING accountability crosswalk.

Each civic tenant has its OWN evolving crosswalk. On every run (ingest -> update -> reassess):
  - rebuild the tenant's current edges from its CURRENT public-record data,
  - diff against the tenant's PRIOR crosswalk state,
  - REASSESS past data against the new findings:
      * a new contribution / contract award -> the money x contract edge is updated/re-scored,
      * a new RECUSAL that answers an open "parity" pair -> that open question is CLOSED
        ("recusal found - the pair now answers"),
  - write the updated per-tenant crosswalk + append a learning-log entry (what changed + why).

Idempotent: same data in -> no change logged. New data in -> edges update + reassessments logged.
Designed to be called by the daily audit_cycle (and after each watcher ingest), so learning is automatic.

GUARDRAILS (unchanged): public records only; every edge SOURCED with a citation + a NEUTRAL
"what to ask" question; correlations are questions, not findings; no guilt; no private PII; aloha frame.

Outputs (reports/mauios/crosswalk/):  <tenant>.json (current graph + closed-history) ·
<tenant>.learnlog.jsonl (one diff entry per run) · _index.json (all tenants summary).
"""
import os, re, json, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MAU  = os.path.join(ROOT, "reports", "mauios")
OUT  = os.path.join(MAU, "crosswalk")
CFG  = os.path.join(ROOT, "config")

def load(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
def slug(s): return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
def nv(s):
    s = (s or "").lower()
    s = re.sub(r"\b(inc|llc|ltd|corp|co|incorporated|company|consulting|group|associates|architects|engineers|engineering)\b", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)
def usd(x): return "${:,.0f}".format(x or 0)
def now(): return datetime.datetime.now().isoformat(timespec="seconds")

CIVIC = (load(os.path.join(CFG, "tenants.json"), {}) or {}).get("_civic_tenants_ref", {}).get("ids", [])

# ---- per-tenant data sources (defensive: only Maui has the rich joins today; others thin) ----
def tenant_data(tid):
    """Return (vendor_donor_join, parity, officials) for the tenant from its current public-record files."""
    if tid == "hi-maui":
        return (load(os.path.join(MAU, "vendor_donor_join.json"), {}) or {},
                load(os.path.join(MAU, "parity_check.json"), {}) or {},
                load(os.path.join(MAU, "officials.json"), {}) or {})
    # other tenants: per-tenant files where present (money_<x>, parity_<x>) - thin for now
    suff = {"hi-state": "state", "hi-honolulu": "honolulu", "hi-hawaii": "hawaii", "hi-kauai": "kauai",
            "ny": "nyc", "nys": "nys", "liverpool": "liverpool"}.get(tid, tid)
    return ({}, load(os.path.join(MAU, "parity_%s.json" % suff), {}) or {}, {})

def ekey(e):  # stable identity of an edge for diffing across runs
    return "|".join([e.get("kind", ""), e.get("src", ""), e.get("dst", ""), str(e.get("contributor") or "")])

def build_edges(tid):
    vdj, parity, officials = tenant_data(tid)
    edges = []
    # money x contract (sourced, neutral) - from the vendor<->donor<->official join
    for m in vdj.get("matched", []):
        vid = "ven:" + nv(m.get("vendor"))
        for h in m.get("hits", []):
            off = h.get("official");
            if not off: continue
            person = (h.get("official_label", off) or off).split(" - ")[0]
            edges.append({
                "kind": "money_x_contract", "src": vid, "dst": "off:" + slug(off),
                "vendor": m.get("vendor"), "official": off, "contributor": h.get("contributor"),
                "amount": h.get("amount", 0), "award": m.get("award_total", 0),
                "detail": "%s in contributions from %s set beside %s in county awards to the firm" % (
                    usd(h.get("amount", 0)), h.get("contributor", "?"), usd(m.get("award_total", 0))),
                "source": "HI Campaign Spending Commission x HANDS (name match - a question to verify)",
                "ask": "Did %s disclose this relationship and recuse where required when %s's matters came before the body?" % (person, m.get("vendor")),
                "status": "open",
            })
    # parity "pair that does not answer" (open recusal question) - reassessable
    for pr in parity.get("hewa", {}).get("pairs", []):
        vid = "ven:" + nv(pr.get("vendor"))
        for off in pr.get("officials", []):
            edges.append({
                "kind": "parity_question", "src": "off:" + slug(off), "dst": vid,
                "vendor": pr.get("vendor"), "official": off,
                "award": pr.get("award_total", 0), "contrib": pr.get("contrib_total", 0),
                "detail": "%s in awards alongside %s in contributions" % (usd(pr.get("award_total", 0)), usd(pr.get("contrib_total", 0))),
                "source": "reports/mauios/vendor_donor_join.json (CSC x HANDS public records)",
                "ask": "Is there a recusal or disclosure in the minutes for this pair? If not, why not? (a question, not a finding)",
                "status": "open",
            })
    return edges

def recusal_index(tid):
    """official_slug -> set of vendor-name tokens the official has a RECUSAL on (public minutes)."""
    _, _, officials = tenant_data(tid)
    idx = {}
    for name, rec in (officials or {}).items():
        toks = set()
        for r in rec.get("recusals", []) or []:
            blob = (json.dumps(r) if not isinstance(r, str) else r).lower()
            for w in re.split(r"[^a-z0-9]+", blob):
                if len(w) > 3: toks.add(w)
        idx[slug(name)] = toks
    return idx

def learn(tid):
    prev = load(os.path.join(OUT, "%s.json" % tid), {}) or {}
    prev_edges = {ekey(e): e for e in prev.get("edges", [])}
    cur = build_edges(tid)
    cur_map = {ekey(e): e for e in cur}
    rec_idx = recusal_index(tid)

    new_e, changed_e, closed_e = [], [], []
    # REASSESS each current edge against prior + against recusals
    for k, e in cur_map.items():
        old = prev_edges.get(k)
        # close an open parity question if a recusal now answers it
        if e["kind"] == "parity_question":
            toks = rec_idx.get(slug(e.get("official", "")), set())
            vt = [w for w in re.split(r"[^a-z0-9]+", (e.get("vendor", "") or "").lower()) if len(w) > 3]
            if any(t in toks for t in vt):
                e["status"] = "closed_by_recusal"
                e["closed_note"] = "A recusal/disclosure now appears in the minutes for this pair - the pair answers. (still a documented fact, not a finding.)"
                if not old or old.get("status") != "closed_by_recusal": closed_e.append(e)
        if not old:
            new_e.append(e)
        elif (old.get("amount") != e.get("amount")) or (old.get("award") != e.get("award")) or (old.get("contrib") != e.get("contrib")):
            e["reassessed"] = {"prev_amount": old.get("amount"), "prev_award": old.get("award"), "prev_contrib": old.get("contrib"), "at": now()}
            changed_e.append(e)
    # carry forward closed-history for pairs that dropped out of current data (don't lose the record)
    for k, old in prev_edges.items():
        if k not in cur_map and old.get("status", "").startswith("closed"):
            cur.append(old)

    graph = {
        "tenant": tid, "generated": now(),
        "frame": "Public records only. Every edge is sourced + carries a neutral question. Documents and asks; does not convict. No private PII. Aloha.",
        "counts": {"edges": len(cur),
                   "open_money_x_contract": sum(1 for e in cur if e["kind"] == "money_x_contract" and e.get("status") == "open"),
                   "open_parity_questions": sum(1 for e in cur if e["kind"] == "parity_question" and e.get("status") == "open"),
                   "closed_by_recusal": sum(1 for e in cur if e.get("status") == "closed_by_recusal")},
        "edges": cur,
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "%s.json" % tid), "w", encoding="utf-8", newline="\n") as f:
        json.dump(graph, f, ensure_ascii=False, indent=1)
    learned = {"at": now(), "tenant": tid, "new_edges": len(new_e), "changed_edges": len(changed_e),
               "parity_questions_closed_by_recusal": len(closed_e),
               "note": ("ingest->update->reassess: %d new, %d re-scored, %d open question(s) closed by a recusal"
                        % (len(new_e), len(changed_e), len(closed_e))) if (new_e or changed_e or closed_e)
                       else "no change since last run (idempotent)"}
    if new_e or changed_e or closed_e:  # only log real movement
        with open(os.path.join(OUT, "%s.learnlog.jsonl" % tid), "a", encoding="utf-8") as f:
            f.write(json.dumps(learned, ensure_ascii=False) + "\n")
    return graph, learned

def main():
    os.makedirs(OUT, exist_ok=True)
    summary = {"generated": now(), "tenants": {}}
    for tid in (CIVIC or ["hi-maui"]):
        try:
            g, l = learn(tid)
            summary["tenants"][tid] = {**g["counts"], "last_learn": l["note"]}
            print("  %-12s edges=%d open_q=%d closed=%d  | %s" % (
                tid, g["counts"]["edges"], g["counts"]["open_parity_questions"], g["counts"]["closed_by_recusal"], l["note"]))
        except Exception as e:
            summary["tenants"][tid] = {"error": str(e)}
            print("  %-12s ERROR %s" % (tid, e))
    with open(os.path.join(OUT, "_index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("crosswalk_learn: %d tenants -> %s" % (len(summary["tenants"]), OUT))
    return summary

if __name__ == "__main__":
    main()
