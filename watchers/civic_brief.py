#!/usr/bin/env python3
"""
Civic Instant Brief engine — kilo-aupuni.

Given a natural-language query about a council agenda item, synthesizes:
  - Matching agenda items from the current cycle (all tenants)
  - Live testimony snapshot (filtered to the topic)
  - Cross-check flags: prosecutor leads, donor patterns, minutes anomalies
  - AI-synthesized plain-English brief (local king-reason, no cloud cost)

Called by:  king_serve.py  POST /api/civic/brief
CLI:        python civic_brief.py "homeless shelter parking lot pilot"
Output:     JSON to stdout (king_serve parses and returns to the browser)

Integrity: sourced only. Findings framed as QUESTIONS, not verdicts.
           Never fabricate Maui County Code sections.
"""
import os, json, sys, time, re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
STATUS  = PROJECT / "reports" / "_status"
MAUIOS  = PROJECT / "reports" / "mauios"
CONFIG  = PROJECT / "config"


# ── helpers ───────────────────────────────────────────────────────────────────

def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _load_jsonl(path, limit=200):
    out = []
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
            if len(out) >= limit:
                break
    except Exception:
        pass
    return out


_STOP = {"the","a","an","of","and","or","is","are","in","on","at","to","for",
         "with","about","what","how","this","that","it","its","be","was","were",
         "by","from","as","but","not","we","they","he","she","will","would","can"}

def _terms(query):
    words = re.findall(r"[a-zA-Z']{3,}", query.lower())
    return [w for w in words if w not in _STOP]


def _score(terms, *texts):
    """Fraction of query terms found in combined text (0–1)."""
    if not terms:
        return 0
    combined = " ".join(t.lower() for t in texts if t)
    hits = sum(1 for t in terms if t in combined)
    return hits / len(terms)


# ── section builders ──────────────────────────────────────────────────────────

def _agenda_matches(terms):
    items = []
    for fname in sorted(STATUS.glob("agenda_intel_*.json")):
        data = _load(fname, {})
        tenant = data.get("tenant", fname.stem.replace("agenda_intel_", ""))
        for mtg in data.get("meetings", []):
            for item in mtg.get("items", []):
                title = item.get("title", "")
                sc = _score(terms, title, item.get("file", ""))
                if sc > 0:
                    items.append({
                        "file":       item.get("file", ""),
                        "title":      title,
                        "date":       mtg.get("date", ""),
                        "committee":  mtg.get("body", ""),
                        "source_url": mtg.get("source", ""),
                        "tenant":     tenant,
                        "money_found":  item.get("money_found", []),
                        "fiscal_flags": item.get("money_lens", []),
                        "priority":     item.get("priority", False),
                        "score":        round(sc, 2),
                    })
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:6]


def _testimony_snap(terms, feed):
    testifiers = feed.get("testifiers", [])
    if not terms:
        return testifiers[:10]
    ranked = []
    for t in testifiers:
        sc = _score(terms, t.get("name",""), t.get("comment",""),
                    t.get("agenda_item",""), t.get("affiliation",""))
        ranked.append((sc, t))
    ranked.sort(key=lambda x: x[0], reverse=True)
    # Return query-relevant ones first, then fill with most recent
    relevant = [t for sc, t in ranked if sc > 0]
    rest     = [t for sc, t in ranked if sc == 0]
    return (relevant + rest)[:10]


def _flags(terms):
    flags = []

    # ── testimony crosscheck ──────────────────────────────────────────────────
    cc = _load(STATUS / "testimony_crosscheck.json", {})
    for industry, entries in cc.get("industries", {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            text = json.dumps(entry)
            if _score(terms, text) > 0.1:
                flags.append({
                    "type":     "crosscheck",
                    "industry": industry,
                    "label":    entry.get("name") or entry.get("label") or "",
                    "source":   "testimony_crosscheck",
                    "strength": entry.get("strength", 0),
                })

    # ── minutes anomalies ─────────────────────────────────────────────────────
    mr = _load(STATUS / "minutes_review.json", {})
    leads = mr.get("leads") or mr.get("summary", {}).get("awareness_leads") or []
    for lead in leads[:100]:
        if _score(terms, json.dumps(lead)) > 0.2:
            flags.append({
                "type":     "minutes_flag",
                "tenant":   lead.get("tenant", ""),
                "date":     lead.get("date", ""),
                "category": lead.get("category", ""),
                "snippet":  (lead.get("snippet") or "")[:250],
                "source":   "minutes_review",
            })

    # ── donor profile flags ───────────────────────────────────────────────────
    donors = _load(MAUIOS / "donor_profiles.json", [])
    if isinstance(donors, list):
        for profile in donors:
            if _score(terms, json.dumps(profile)) > 0.15:
                for d in profile.get("realestate", {}).get("donors", [])[:2]:
                    flags.append({
                        "type":     "donor",
                        "official": profile.get("label", ""),
                        "donor":    d.get("name", ""),
                        "total":    d.get("total", 0),
                        "industry": "real estate",
                        "source":   "donor_profiles",
                    })

    return flags[:18]


def _committee_history(terms):
    """Pull committee history hits from the minutes corpus summary."""
    mr = _load(STATUS / "minutes_review.json", {})
    summary = mr.get("summary", {})
    flag_counts = summary.get("flag_counts", {})
    # Return aggregate counts as context (can't do per-item without full corpus)
    if flag_counts:
        return [{"summary": flag_counts, "source": "minutes_review (2293 meetings indexed)"}]
    return []


_LEAK_TERMS = ("prosecutor", "case file", "owner_token", "sk_live", "sk_test", "rk_live", "pk_live",
               "whsec_", "akia", "ghp_", "xoxb", "aiza", "-----begin", "reports/_status/jrcsl",
               "reports/_status/prosecutor", "owner-only", "owner only", "dropbox", "bearer ", "api key")
# AUDIT H5 FOLLOWUP (2026-07-07): broadened keyword set — plural Sections, Ch., Resolution, Article, Rule,
# HRS / MCC / HAR, optional "No." — so common Hawaiʻi civic citation forms (HRS 205-2, MCC 19.30,
# Resolution 24-107) are caught, not just "Section N".
_CITE_RE = re.compile(
    r"(?:sections?|sec\.?|§|chapters?|ch\.?|ordinances?|bills?|resolutions?|titles?|articles?|rules?|hrs|mcc|har)"
    r"\s*\.?\s*(?:no\.?\s*)?[0-9][0-9A-Za-z.\-:]*", re.I)


def _guard_brief(text, source_ctx):
    """AUDIT H5 (2026-07-07): post-generation guard on the local model's free text. The model is TOLD not to
    fabricate code sections, but its output used to be returned with zero verification. (1) Leak-scan: if any
    owner/private/secret marker slipped in, DROP the brief — a public civic observer must never receive private
    data. (2) Citation check: any code/ordinance/bill number in the output whose id does NOT appear in the
    sourced context is unverified -> append a plain caveat so an invented citation is never read as fact."""
    if not text:
        return None
    low = text.lower()
    if any(t in low for t in _LEAK_TERMS):
        sys.stderr.write("civic_brief: leak-term in AI brief -> withheld\n")
        return None
    # AUDIT H5 FOLLOWUP: match the WHOLE citation PHRASE (keyword+number) against the normalized source,
    # NOT the bare number as a substring — a bare "15" appears in any date/amount, which let a fabricated
    # "Title 15 of the Maui County Code" pass. Phrase-matching requires the keyword+number to actually be sourced.
    src = " ".join((source_ctx or "").lower().split())
    unverified = []
    for c in _CITE_RE.findall(text):
        phrase = " ".join(c.lower().split()).rstrip(".,;:")
        if phrase and phrase not in src:
            unverified.append(" ".join(c.split()).rstrip(".,;:"))
    if unverified:
        text += ("\n\n⚠ Unverified against the sourced record: %s. Confirm before relying on these."
                 % ", ".join(sorted(set(unverified))[:6]))
    return text


def _ai_brief(query, agenda_items, testimony_snap, flags):
    """Synthesize a plain-English brief via local AI. Returns text or None."""
    try:
        sys.path.insert(0, str(PROJECT / "tools" / "ops"))
        from local_ai import ask as _ask

        ctx_parts = []

        if agenda_items:
            ctx_parts.append(
                "UPCOMING AGENDA ITEMS MATCHING THIS QUERY:\n" +
                "\n".join(
                    "• %s | %s | %s\n  %s" % (
                        it["file"], it["committee"], it["date"], it["title"]
                    )
                    for it in agenda_items[:3]
                )
            )

        if testimony_snap:
            ctx_parts.append(
                "LIVE TESTIMONY SNAPSHOT (%d testifiers):\n" % len(testimony_snap) +
                "\n".join(
                    "• %s [%s]%s" % (
                        t.get("name", "?"),
                        t.get("position") or t.get("stance") or "?",
                        (" — " + t["comment"][:180]) if t.get("comment") else ""
                    )
                    for t in testimony_snap[:5]
                )
            )

        if flags:
            ctx_parts.append(
                "PUBLIC RECORD FLAGS (question-framed):\n" +
                "\n".join(
                    "• [%s] %s" % (
                        f["type"].upper(),
                        (f.get("snippet") or f.get("label") or
                         f.get("donor", "") + " → " + f.get("official", ""))[:200]
                    )
                    for f in flags[:5]
                )
            )

        if not ctx_parts:
            ctx_parts.append("(No matching data found in the civic record for this query.)")

        prompt = (
            "You are a civic intelligence assistant for Maui County government transparency. "
            "Someone watching a council meeting just asked:\n\n\"%s\"\n\n"
            "SOURCED DATA FROM THE PUBLIC RECORD:\n%s\n\n"
            "Write a concise, factual 3–4 paragraph instant brief. Rules:\n"
            "1. Frame any concerns as QUESTIONS for pono accountability, not accusations.\n"
            "2. State only what the public record shows above — do NOT fabricate code sections or ordinance numbers.\n"
            "3. If data is thin, say so plainly.\n"
            "4. Be useful to a civic observer who has 60 seconds to read this.\n"
            "5. End with: 'Source: Maui County public record.'"
        ) % (query[:300], "\n\n".join(ctx_parts)[:2000])

        r = _ask(prompt, tier="fast", timeout=60)
        if not r.get("ok"):
            return None
        return _guard_brief(r["text"], "\n\n".join(ctx_parts))
    except Exception:
        return None


# ── main entry point ──────────────────────────────────────────────────────────

def generate_brief(query: str) -> dict:
    t0    = time.time()
    terms = _terms(query)

    # Live testimony feed (strip private tracking keys)
    feed = _load(STATUS / "testimony_live_feed.json", {})
    feed.pop("_seen_wavs", None)
    feed.pop("_seen_ecomment_names", None)

    agenda    = _agenda_matches(terms)
    testimony = _testimony_snap(terms, feed)
    flags_raw = _flags(terms)
    history   = _committee_history(terms)

    # Sources cited
    sources = []
    for item in agenda:
        if item.get("source_url"):
            sources.append({
                "label": "%s — %s" % (item["file"], item["committee"]),
                "url":   item["source_url"],
            })
    if feed.get("meeting_active"):
        sources.append({"label": "Live testimony feed", "url": "/watcher"})

    # AI brief (fast-path: king-reason, 60s cap)
    ai_text = _ai_brief(query, agenda, testimony, flags_raw)

    return {
        "ok":              True,
        "query":           query,
        "meeting_active":  feed.get("meeting_active", False),
        "meeting":         feed.get("meeting", {}),
        "agenda_items":    agenda,
        "testimony":       testimony,
        "flags":           flags_raw,
        "committee_history": history,
        "ai_brief":        ai_text,
        "sources":         sources,
        "elapsed_s":       round(time.time() - t0, 2),
        "generated_at":    time.strftime("%Y-%m-%d %H:%M HST", time.localtime()),
        "integrity":       (
            "This is an audit of the public record -- NOT legal advice and NOT a finding of wrongdoing. "
            "Sourced from Maui County public record. "
            "Findings framed as questions, not verdicts. "
            "Officials named for their official acts; private persons de-identified. "
            "No Title 15 in Maui County Code; Title 16 = Buildings & Construction."
        ),
    }


if __name__ == "__main__":
    import argparse, io
    # Force UTF-8 stdout so king_serve subprocess can receive non-ASCII JSON safely
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser(description="Civic Instant Brief")
    ap.add_argument("query", nargs="*", help="Natural-language civic query")
    args = ap.parse_args()
    q = " ".join(args.query) if args.query else "parking lot homeless shelter pilot"
    print(json.dumps(generate_brief(q), indent=2, ensure_ascii=False))
