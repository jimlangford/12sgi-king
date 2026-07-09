# -*- coding: utf-8 -*-
"""prosecutor_triage.py - king-AI triage pass for the JRCSL lead backlog.

ADR-001 #5 (Jimmy approved 2026-06-23).

The jrcsl_leads.jsonl backlog has 6816 entries, all gate_hint=NEEDS-RECORD.
These are Legistar meeting-action leads auto-pulled by the catchup watcher and
live meeting watcher. Without triage they pile up and the prosecutor lane is
blind to which ones matter most.

This tool:
  1. Reads jrcsl_leads.jsonl (the live backlog).
  2. RULE-BASED pre-score (fast, no AI): flags with verified civic keywords,
     entity patterns, confidence, body/committee type, money × vote correlation.
  3. KING-AI re-score (optional, free): sends top-N candidates to king-reason
     for a one-sentence "civic-risk note" and a 1–5 signal score.
  4. Writes a TRIAGE LEDGER (triage_ledger.json) so processed entries don't
     re-surface. Ledger key = the lead's 'key' hash (already present) or ts+matter.
  5. Outputs a TOP-SIGNAL summary (triage_summary.json) with the highest-signal leads.

INTEGRITY HARD RULES (JRCSL doctrine):
  * A lead is NEVER a finding.  Triage only RANKS leads for human review.
  * No assertion of wrongdoing is ever written.
  * king-reason (1.7B) is used ONLY for a risk-note + numeric score.
    The model's output is labelled [king-reason] and capped at 120 chars.
    It cannot verify primary records; it cannot promote a lead.
  * NEVER fabricate. NEVER publish. PRIVATE — lives in reports/_status/prosecutor/.
  * If king-reason is down -> rule-based score only.  No cloud fallback.

Usage:
  python tools/kilo-aupuni/prosecutor_triage.py              # triage all un-triaged
  python tools/kilo-aupuni/prosecutor_triage.py --top 20     # show top-N after triage
  python tools/kilo-aupuni/prosecutor_triage.py --dry-run    # score only, no ledger write
  python tools/kilo-aupuni/prosecutor_triage.py --reset      # clear ledger (re-triage all)
  python tools/kilo-aupuni/prosecutor_triage.py --ai-sample 10  # use king-AI on top 10

Outputs:
  reports/_status/prosecutor/triage_ledger.json   -- keys of triaged leads
  reports/_status/prosecutor/triage_summary.json  -- top-signal leads

ASCII-safe. Stdlib + local_ai (king-reason). No Claude/cloud.
"""
from __future__ import annotations
import os, sys, json, time, re, hashlib

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(os.path.dirname(HERE))
STORE_DIR = os.path.join(ROOT, "reports", "_status", "prosecutor")
LEADS_FILE  = os.path.join(STORE_DIR, "jrcsl_leads.jsonl")
LEDGER_FILE = os.path.join(STORE_DIR, "triage_ledger.json")
SUMMARY_FILE= os.path.join(STORE_DIR, "triage_summary.json")

sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))
try:
    import local_ai as _local_ai
    _AI_OK = True
except Exception:
    _AI_OK = False

# ---------------------------------------------------------------------------
# Rule-based scoring (no AI)
# ---------------------------------------------------------------------------

# High-signal body keywords: committees with budget/finance/land/planning authority
_BODY_HIGH = re.compile(
    r"(budget|finance|land.use|housing|planning|economic.dev|permitting|"
    r"water|disaster|relief|recovery|audit|oversight|ethics|public.safety|"
    r"labor|infrastructure|capital|grant|contract|procurement|revenue)",
    re.I,
)

# High-signal matter keywords: topics that correlate with civic-money risk
_MATTER_HIGH = re.compile(
    r"(grant|contract|lease|permit|bond|bid|award|fund|appropriat|"
    r"rezoning|variance|exemption|waiver|payment|settlement|loan|"
    r"amendment.*budget|budget.*amendment|emergency.*fund|allot)",
    re.I,
)

# Very-high: explicit money+decision signals
_MATTER_VERY_HIGH = re.compile(
    r"(\$[\d,]+|million|recovery.fund|cdbg|arpa|fema|homeland.security.grant|"
    r"lahaina|wildfire|disaster.declaration|public.land|crown.land|ceded.land)",
    re.I,
)

# Low-signal: purely procedural
_MATTER_LOW = re.compile(
    r"^(minutes|regular meeting|approve.*minutes|swearing.in|pledge|recess|"
    r"announcement|scheduling|agenda|communication|correspondence|recognition|"
    r"commend|congratulat|proclamat|adjournment|quorum)",
    re.I,
)

# Action patterns that reduce signal (outcome already decided)
_ACTION_CLOSED = re.compile(r"(approved|adopted|passed|enacted|denied|withdrawn|tabled)", re.I)


def rule_score(lead: dict) -> int:
    """0–10 rule-based civic-signal score. Higher = more worth human review."""
    score = 3  # baseline (every Legistar entry is at least worth noting)
    matter = (lead.get("matter") or "")
    body   = (lead.get("body") or "")
    action = (lead.get("action") or "")
    flags  = lead.get("flags") or []
    conf   = lead.get("confidence", "med")

    # Confidence bonus
    if conf == "high":
        score += 2
    # Flag bonuses
    if "money" in flags:
        score += 2
    if "vote" in flags:
        score += 1
    # Body match
    if _BODY_HIGH.search(body):
        score += 2
    # Matter matches
    if _MATTER_VERY_HIGH.search(matter):
        score += 3
    elif _MATTER_HIGH.search(matter):
        score += 2
    # Procedural penalty
    if _MATTER_LOW.match(matter.strip()):
        score -= 3
    # Closed outcome: slightly lower (but still notable for record)
    if _ACTION_CLOSED.search(action):
        score -= 1
    # Source bonus: live beats catchup
    if lead.get("source") == "jrcsl-live":
        score += 1

    return max(0, min(10, score))


# ---------------------------------------------------------------------------
# King-AI risk note (optional)
# ---------------------------------------------------------------------------

def _king_risk_note(lead: dict) -> tuple:
    """Ask king-reason for a civic-risk note + 1–5 signal score.
    Returns (note_str, score_int).  Falls back on failure.
    """
    matter = (lead.get("matter") or "")[:250]
    body   = (lead.get("body") or "")[:100]
    flags  = ", ".join(lead.get("flags") or ["none"])
    prompt = (
        "You are reviewing a Maui County Legistar meeting item for civic-risk signals. "
        "Reply in ONE sentence under 100 chars: what public-interest risk (if any) this item "
        "poses, then a score 1-5 (5=highest risk). Format: '<risk note> | score:<N>'\n"
        "Committee: %s\nMatter: %s\nFlags: %s" % (body, matter, flags)
    )
    try:
        r = _local_ai.ask(prompt, prefer="local", timeout=50)
        if r.get("ok"):
            raw = r["text"].strip().split("\n")[0][:200]
            # parse score
            m = re.search(r"score:\s*([1-5])", raw, re.I)
            score = int(m.group(1)) if m else 3
            note  = re.sub(r"\s*\|\s*score:\s*[1-5]", "", raw).strip()[:120]
            return ("[%s] %s" % (r.get("via", "king"), note)), score
    except Exception:
        pass
    return "[rule-based]", 3


# ---------------------------------------------------------------------------
# Ledger helpers
# ---------------------------------------------------------------------------

def _load_ledger() -> dict:
    try:
        return json.load(open(LEDGER_FILE, encoding="utf-8"))
    except Exception:
        return {}


def _save_ledger(ledger: dict):
    os.makedirs(STORE_DIR, exist_ok=True)
    tmp = LEDGER_FILE + ".tmp"
    json.dump(ledger, open(tmp, "w", encoding="utf-8"), indent=2)
    os.replace(tmp, LEDGER_FILE)


def _lead_key(lead: dict) -> str:
    """Stable key for a lead entry.

    Uses the existing 'key' field if present (catchup entries have it).
    For keyless entries (live meeting transcripts) we generate a sha256 of
    matter+body — omitting ts because live entries sometimes have clock strings
    that vary across re-ingestions of the same event.
    """
    if lead.get("key"):
        return str(lead["key"])
    raw = "%s|%s" % (
        (lead.get("matter") or "").strip(),
        (lead.get("body") or "").strip(),
    )
    return "L-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:14]


# ---------------------------------------------------------------------------
# Main triage pass
# ---------------------------------------------------------------------------

def read_leads() -> list:
    leads = []
    try:
        with open(LEADS_FILE, encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    leads.append(json.loads(ln))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return leads


def run(dry_run: bool = False, ai_sample: int = 0, top_n: int = 20) -> dict:
    leads = read_leads()
    ledger = _load_ledger()

    un_triaged = [l for l in leads if _lead_key(l) not in ledger]
    already_triaged = len(leads) - len(un_triaged)

    # Rule-based score all un-triaged
    scored = []
    for l in un_triaged:
        sc = rule_score(l)
        key = _lead_key(l)
        scored.append({"key": key, "lead": l, "rule_score": sc, "king_note": None, "king_score": None})

    # Sort by rule score descending
    scored.sort(key=lambda x: x["rule_score"], reverse=True)

    # Optionally ask king-AI on the top-N candidates (only if ai_sample > 0)
    if ai_sample > 0 and _AI_OK:
        for item in scored[:ai_sample]:
            note, kscore = _king_risk_note(item["lead"])
            item["king_note"]  = note
            item["king_score"] = kscore

    # Build top-signal list (for human review)
    top_leads = []
    for item in scored[:top_n]:
        l = item["lead"]
        top_leads.append({
            "key":          item["key"],
            "source":       l.get("source", "?"),
            "meeting_date": l.get("meeting_date", "?"),
            "body":         (l.get("body") or "")[:100],
            "matter":       (l.get("matter") or "")[:200],
            "flags":        l.get("flags", []),
            "confidence":   l.get("confidence", "med"),
            "gate_hint":    l.get("gate_hint", "NEEDS-RECORD"),
            "matter_url":   l.get("matter_url", ""),
            "rule_score":   item["rule_score"],
            "king_note":    item["king_note"],
            "king_score":   item["king_score"],
            "triage_note":  "RULE-TRIAGE: ranked for human review — NOT a finding. Pull primary record before any use.",
        })

    # Update ledger (mark all scored as triaged)
    new_ledger = dict(ledger)
    if not dry_run:
        for item in scored:
            new_ledger[item["key"]] = {
                "triaged_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "rule_score": item["rule_score"],
            }
        _save_ledger(new_ledger)

    # Write summary
    summary = {
        "_about": "PRIVATE prosecutor triage summary (king-reason + rule-based). NEVER publish.",
        "_generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "_dry_run": dry_run,
        "backlog": {
            "total_leads": len(leads),
            "already_triaged": already_triaged,
            "newly_triaged_this_run": len(scored),
            "high_confidence": sum(1 for l in leads if l.get("confidence") == "high"),
            "med_confidence":  sum(1 for l in leads if l.get("confidence") == "med"),
            "sources": {
                "jrcsl-catchup": sum(1 for l in leads if l.get("source") == "jrcsl-catchup"),
                "jrcsl-live":    sum(1 for l in leads if l.get("source") == "jrcsl-live"),
            },
        },
        "integrity": (
            "JRCSL doctrine: these are LEADS, not findings. "
            "king-reason (1.7B) provides a risk-note only. "
            "VERIFIED status requires a primary public record, pulled by a human session. "
            "No verdict, no fabrication, no publication."
        ),
        "top_signal_leads": top_leads,
    }

    if not dry_run:
        tmp = SUMMARY_FILE + ".tmp"
        json.dump(summary, open(tmp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        os.replace(tmp, SUMMARY_FILE)

    return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    args = sys.argv[1:]
    dry_run    = "--dry-run" in args
    top_n      = 20
    ai_sample  = 0

    if "--reset" in args and not dry_run:
        if os.path.exists(LEDGER_FILE):
            os.remove(LEDGER_FILE)
        print("Triage ledger cleared.")

    if "--top" in args:
        try: top_n = int(args[args.index("--top") + 1])
        except Exception: pass

    if "--ai-sample" in args:
        try: ai_sample = int(args[args.index("--ai-sample") + 1])
        except Exception: pass

    print("prosecutor_triage: reading leads from %s" % LEADS_FILE)
    print("  king-AI available : %s" % ("YES (local, free)" if _AI_OK else "NO (rule-based only)"))
    if ai_sample:
        print("  will call king-AI on top %d leads" % ai_sample)

    s = run(dry_run=dry_run, ai_sample=ai_sample, top_n=top_n)
    b = s["backlog"]

    print("\n=== PROSECUTOR TRIAGE RESULT ===")
    print("  Total leads in backlog      : %d" % b["total_leads"])
    print("  Already triaged (prior runs): %d" % b["already_triaged"])
    print("  Newly triaged this run      : %d" % b["newly_triaged_this_run"])
    print("  High-confidence leads       : %d" % b["high_confidence"])
    print("  Med-confidence leads        : %d" % b["med_confidence"])
    print("  Sources - catchup           : %d" % b["sources"]["jrcsl-catchup"])
    print("  Sources - live              : %d" % b["sources"]["jrcsl-live"])
    print("  Top-signal leads surfaced   : %d" % len(s["top_signal_leads"]))
    print("  Mutating actions taken      : 0")
    print("  Fabrication / verdicts      : 0")
    print("  Published                   : 0 (PRIVATE)")

    if s["top_signal_leads"]:
        print("\n  TOP %d SIGNAL LEADS (for human review — not findings):" % len(s["top_signal_leads"]))
        for i, t in enumerate(s["top_signal_leads"][:5], 1):
            print("  %d. [score=%s] [conf=%s] %s" % (
                i, t["rule_score"], t["confidence"],
                (t["matter"] or "?")[:90]))
            print("     body: %s" % (t["body"] or "?")[:80])
            if t.get("king_note"):
                print("     king: %s  (king_score=%s)" % (t["king_note"][:90], t["king_score"]))
            print("     url : %s" % (t.get("matter_url") or "—"))

    if not dry_run:
        print("\n  Ledger written  : %s" % LEDGER_FILE)
        print("  Summary written : %s" % SUMMARY_FILE)
    else:
        print("\n  DRY-RUN: no writes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
