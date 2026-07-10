# -*- coding: utf-8 -*-
"""yale_opportunity_scan.py — query Yale graph for top opportunities and queue outreach drafts.

Runs AFTER yale_ecosystem.py on the creative lane cadence (Hawaii dawn, 15:50 UTC = 05:50 HST = Ao).
HINA has already balanced during Pō; the ingest is complete; now the system surfaces what matters.

Flow (mirrors outbox.py approval gate):
  1. Query Neo4j for YaleOpportunity nodes with match_score >= threshold.
  2. For each new opportunity (not yet in scan state file), draft a short outreach
     email or meeting request using the local Ollama endpoint (zero Claude tokens).
  3. Enqueue each draft to outbox.py with status=pending — nothing sends until owner approves.
  4. Persist scan state so the same item is never re-drafted (idempotent).

Lane alignment:
  Engineering lane  — yale_ecosystem.py ingests at 09:20 UTC (Yale sunrise, Pō)
  Creative lane     — this scanner runs at 15:50 UTC (Hawaii dawn, Ao begins)
  Output lane       — owner reviews/approves in outbox; send fires at 17:00 UTC
                      (Hawaii 7 AM, Yale 1 PM — same-day response window)

Resilient: Ollama down → falls back to a template draft. Neo4j down → skips cleanly.
PRIVATE: state file and draft queue live in the owner-only reports path.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# ── Paths ─────────────────────────────────────────────────────────────────────
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
STATE_PATH = Path(
    os.environ.get(
        "YALE_SCAN_STATE_PATH",
        os.path.join(PROJ, "reports", "_status", "yale_scan_state.json"),
    )
)

# ── Service endpoints ─────────────────────────────────────────────────────────
NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_DRAFT_MODEL", "llama3")

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_MATCH_SCORE = 16   # opportunities with score >= this get a draft
MAX_NEW_PER_RUN = 10   # cap new drafts per run to avoid outbox flooding

# ── 12SGI mission context for Ollama prompts ──────────────────────────────────
_MISSION_BRIEF = (
    "12SGI (12 Stone Group Inc) builds civic intelligence software — govOS, elementLOTUS, "
    "and the Naga civic console. We serve local government transparency, indigenous governance, "
    "public records access, and community accountability in Hawaii and New York. "
    "Our owner Jimmy Langford graduated Yale in 1994 and 1995."
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _say(m: str) -> None:
    try:
        if sys.stdout:
            print(m, flush=True)
    except Exception:
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── State (which IDs have already been scanned/drafted) ──────────────────────

def _read_state() -> dict:
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"drafted_ids": [], "last_scan_at": None}


def _write_state(state: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(STATE_PATH)
    except Exception as exc:
        _say("yale_scan: state write skip — %s" % str(exc)[:100])


# ── Neo4j query ───────────────────────────────────────────────────────────────

def _post(statements: list[dict], timeout: float = 30) -> dict | None:
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(
        NEO,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.URLError as exc:
        _say("yale_scan: Neo4j not reachable — %s" % str(exc)[:120])
        return None


def _query_top_opportunities(min_score: int, limit: int) -> list[dict]:
    result = _post([{
        "statement": (
            "MATCH (opp:YaleOpportunity) "
            "WHERE opp.match_score >= $min "
            "RETURN opp.id AS id, opp.title AS title, opp.url AS url, "
            "opp.source AS source, opp.item_type AS item_type, "
            "opp.date_iso AS date_iso, opp.summary AS summary, "
            "opp.match_score AS match_score "
            "ORDER BY opp.match_score DESC, opp.date_iso DESC "
            "LIMIT $lim"
        ),
        "parameters": {"min": min_score, "lim": limit * 3},  # over-fetch then filter by state
    }])
    if not result:
        return []
    cols = (result.get("results") or [{}])[0].get("columns", [])
    rows = []
    for r in (result.get("results") or [{}])[0].get("data", []):
        row = dict(zip(cols, r.get("row", [])))
        if row.get("id"):
            rows.append(row)
    return rows


# ── Ollama draft generation ───────────────────────────────────────────────────

def _ollama_draft(opportunity: dict) -> str | None:
    """Ask local Ollama to draft a short outreach message. Returns None on failure."""
    title = opportunity.get("title") or ""
    summary = opportunity.get("summary") or ""
    item_type = opportunity.get("item_type") or "opportunity"
    url = opportunity.get("url") or ""
    prompt = (
        "You are drafting a short, professional outreach email on behalf of 12SGI.\n\n"
        "ABOUT US:\n%s\n\n"
        "YALE %s:\nTitle: %s\nSummary: %s\nURL: %s\n\n"
        "Write a 3-5 sentence outreach email or meeting request to Yale. "
        "Be specific about how 12SGI's civic intelligence software could collaborate. "
        "Tone: professional, collegial, Yale-alumni warmth. "
        "Do NOT use placeholder text like [Name] — address it to the relevant Yale office. "
        "Sign as: Jimmy Langford, Yale '94/'95, 12SGI / elementLOTUS."
    ) % (_MISSION_BRIEF, item_type.upper(), title, summary[:300], url)
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.6, "num_predict": 300},
    }).encode("utf-8")
    req = urllib.request.Request(
        "%s/api/generate" % OLLAMA_BASE.rstrip("/"),
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
            text = (data.get("response") or "").strip()
            return text if len(text) > 30 else None
    except Exception as exc:
        _say("yale_scan: Ollama draft failed (%s) — using template" % str(exc)[:80])
        return None


def _template_draft(opportunity: dict) -> str:
    """Fallback template draft when Ollama is unavailable."""
    title = opportunity.get("title") or "this opportunity"
    item_type = opportunity.get("item_type") or "opportunity"
    url = opportunity.get("url") or ""
    return (
        "Dear Yale colleagues,\n\n"
        "I came across your recent %s — \"%s\" — and believe there is a meaningful "
        "collaboration opportunity with 12SGI (12 Stone Group Inc).\n\n"
        "12SGI builds civic intelligence software (govOS, elementLOTUS) serving local "
        "government transparency and community accountability in Hawaii and New York. "
        "As a Yale alumnus ('94/'95), I am particularly interested in exploring how "
        "our work aligns with Yale's mission in this area.\n\n"
        "I would welcome a brief call or email exchange to explore next steps.\n\n"
        "Reference: %s\n\n"
        "With warmth,\nJimmy Langford\nYale '94 / '95\n12SGI / elementLOTUS\njrcsl@12sgi.com"
    ) % (item_type, title, url)


# ── Outbox enqueue ────────────────────────────────────────────────────────────

def _enqueue_draft(opportunity: dict, body_text: str) -> bool:
    """Enqueue the outreach draft to outbox.py for owner approval."""
    try:
        sys.path.insert(0, str(HERE))
        import outbox  # type: ignore
    except ImportError:
        _say("yale_scan: outbox.py not importable — draft not queued (log only)")
        _say("DRAFT [%s]: %s" % (opportunity.get("id"), body_text[:200]))
        return False

    title = opportunity.get("title") or "Yale opportunity"
    item_type = (opportunity.get("item_type") or "opportunity").title()
    subject = "[YALE/%s] Outreach draft: %s" % (item_type, title[:80])
    source_note = (
        "Yale source: %s\nURL: %s\nMatch score: %s\nDate: %s\n\n---\n\n"
    ) % (
        opportunity.get("source_label") or opportunity.get("source") or "",
        opportunity.get("url") or "",
        opportunity.get("match_score") or 0,
        opportunity.get("date_iso") or "",
    )
    preview_text = source_note + body_text
    item_id = "yale-draft-" + re.sub(r"[^a-z0-9]", "-", (opportunity.get("id") or "")[-30:])
    outbox.enqueue(
        to="jrcsl@12sgi.com",
        subject=subject,
        body_text=preview_text,
        source="yale_opportunity_scan",
        item_id=item_id,
    )
    _say("yale_scan: draft enqueued — %s" % subject[:100])
    return True


# ── Main scan ─────────────────────────────────────────────────────────────────

def scan(min_score: int = MIN_MATCH_SCORE, max_new: int = MAX_NEW_PER_RUN) -> bool:
    """Query Neo4j, draft outreach for new opportunities, enqueue to outbox.

    Returns True if the scan completed (even if zero new items were found).
    Returns False only if Neo4j is unreachable.
    """
    state = _read_state()
    drafted_ids: list = state.get("drafted_ids") or []

    opportunities = _query_top_opportunities(min_score=min_score, limit=max_new + len(drafted_ids))
    if opportunities is None:
        return False  # Neo4j down
    if not opportunities:
        _say("yale_scan: no opportunities above score %d in graph" % min_score)
        state["last_scan_at"] = _now_iso()
        _write_state(state)
        return True

    new_count = 0
    for opp in opportunities:
        opp_id = opp.get("id") or ""
        if not opp_id or opp_id in drafted_ids:
            continue
        if new_count >= max_new:
            break

        # Attempt Ollama draft; fall back to template
        draft_text = _ollama_draft(opp) or _template_draft(opp)
        _enqueue_draft(opp, draft_text)

        drafted_ids.append(opp_id)
        new_count += 1

    state["drafted_ids"] = drafted_ids[-500:]  # keep last 500 to bound file size
    state["last_scan_at"] = _now_iso()
    _write_state(state)
    _say("yale_scan: %d new drafts queued (total seen: %d)" % (new_count, len(drafted_ids)))
    return True


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ok = scan()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
