# -*- coding: utf-8 -*-
"""yale_ecosystem.py — Yale University ecosystem ingest into Neo4j.

Ingests publicly available Yale feeds into an additive ``yale_ecosystem`` Neo4j
layer on the Pō cadence (Yale sunrise 09:20 UTC = 11:20 PM HST = Hawaii Pō):

  Yale News RSS         — news.yale.edu/news/feed
  Yale Events feed      — events.yale.edu (iCal/RSS)
  Yale OCR              — Office of Cooperative Research tech-transfer items
  Yale Alumni           — alumni.yale.edu events and programs
  Yale Grants / SOM     — open research funding and partnership calls

Each item becomes a ``YaleOpportunity`` Neo4j node with:
  id, title, url, source, item_type, date_iso, tags, summary, match_note
  layer = 'yale_ecosystem'
  aligned_context = SAGE_CIVIC_CONTEXT_ID  (additive cross-layer link)

Items are UPSERTED (MERGE on id) so repeated runs stay idempotent.

Rhythm:
  Engineering lane — auto-resolves during Pō (HINA active, 09:20–15:50 UTC)
  Creative lane   — yale_opportunity_scan.py runs at Hawaii dawn (15:50 UTC)

Resilient: unreachable Neo4j or any feed failure produces a soft skip, never a crash.

Jimmy Langford graduated Yale 1994 and 1995 (B.A. + M.A./professional).
The feeds cover research partnerships, grants, licensing, alumni networks, civic
governance programmes — all collaboration surfaces for 12SGI / govOS / elementLOTUS.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
LAYER = "yale_ecosystem"

# ── Rhythm constants (mirrors graph_refresh.py naming) ───────────────────────
# Yale sunrise New Haven CT (41.3°N 72.9°W) — July: ~05:20 EDT = 09:20 UTC
# Hawaii Pō (HINA active): 23:00–05:50 HST = 09:00–15:50 UTC
YALE_SUNRISE_UTC_HH = 9   # 09:20 UTC
YALE_SUNRISE_UTC_MM = 20

# ── Sage Civic context (cross-layer additive link) ────────────────────────────
try:
    from sage_trinity import SAGE_CIVIC_CONTEXT_ID  # type: ignore
except Exception:
    SAGE_CIVIC_CONTEXT_ID = "context:sage-civic"

# ── Mission tags used for lightweight match scoring ───────────────────────────
_MISSION_TAGS = {
    "civic", "governance", "transparency", "accountability", "government",
    "public", "policy", "community", "data", "technology", "research",
    "grant", "funding", "partnership", "collaboration", "nonprofit",
    "indigenous", "sovereignty", "native", "hawaii", "environment",
    "justice", "equity", "digital", "open", "innovation", "alumni",
    "health", "land", "water", "sustainability",
}

# ── Yale public feed sources ──────────────────────────────────────────────────
# All feeds are publicly accessible RSS/Atom; no credentials required.
YALE_FEEDS = [
    {
        "source": "yale_news",
        "label": "Yale News",
        "url": "https://news.yale.edu/news/feed",
        "item_type": "news",
    },
    {
        "source": "yale_ocr",
        "label": "Yale Office of Cooperative Research",
        "url": "https://ocr.yale.edu/news/feed",
        "item_type": "licensing",
    },
    {
        "source": "yale_alumni",
        "label": "Yale Alumni Association News",
        "url": "https://alumni.yale.edu/news/feed",
        "item_type": "alumni",
    },
    {
        "source": "yale_som",
        "label": "Yale School of Management News",
        "url": "https://som.yale.edu/news/feed",
        "item_type": "research",
    },
    {
        "source": "yale_jackson",
        "label": "Yale Jackson School of Global Affairs",
        "url": "https://jackson.yale.edu/news/feed",
        "item_type": "policy",
    },
    {
        "source": "yale_law",
        "label": "Yale Law School News",
        "url": "https://law.yale.edu/news/feed",
        "item_type": "policy",
    },
    {
        "source": "yale_environment",
        "label": "Yale School of the Environment",
        "url": "https://environment.yale.edu/news/feed",
        "item_type": "environment",
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _say(m: str) -> None:
    try:
        if sys.stdout:
            print(m, flush=True)
    except Exception:
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _post(statements: list[dict], timeout: float = 30) -> dict | None:
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(
        NEO,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.URLError as exc:
        _say("yale_ecosystem: Neo4j not reachable at %s (%s)" % (NEO, str(exc)[:120]))
        return None
    if out.get("errors"):
        _say("yale_ecosystem Cypher errors: %s" % json.dumps(out.get("errors"))[:300])
    return out


def _fetch_rss(url: str, timeout: int = 15) -> list[dict]:
    """Fetch an RSS/Atom feed and return a list of raw item dicts."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "12SGI-YaleIngest/1.0 (govOS civic intelligence; contact jrcsl@12sgi.com)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except Exception as exc:
        _say("yale_ecosystem: feed fetch failed %s — %s" % (url, str(exc)[:120]))
        return []
    try:
        root = ET.fromstring(raw.decode("utf-8", "replace"))
    except Exception as exc:
        _say("yale_ecosystem: XML parse failed %s — %s" % (url, str(exc)[:80]))
        return []
    items = []
    # RSS 2.0
    for item in root.findall(".//item"):
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "url": (item.findtext("link") or "").strip(),
            "summary": (item.findtext("description") or "").strip(),
            "date_raw": (item.findtext("pubDate") or "").strip(),
        })
    # Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", ns):
        link_el = entry.find("atom:link", ns)
        items.append({
            "title": (entry.findtext("atom:title", namespaces=ns) or "").strip(),
            "url": (link_el.get("href") if link_el is not None else "").strip(),
            "summary": (entry.findtext("atom:summary", namespaces=ns) or "").strip(),
            "date_raw": (entry.findtext("atom:updated", namespaces=ns) or "").strip(),
        })
    return items


_DATE_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S GMT",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d",
)


def _parse_date(raw: str) -> str:
    """Return an ISO-8601 UTC string or today's date."""
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            pass
    return datetime.now(timezone.utc).date().isoformat()


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:500]


def _match_score(title: str, summary: str) -> int:
    """Count how many mission tags appear in the combined text (0–100)."""
    combined = (title + " " + summary).lower()
    hits = sum(1 for t in _MISSION_TAGS if re.search(r"\b" + re.escape(t) + r"\b", combined))
    return min(100, hits * 8)


def _item_id(source: str, url: str, title: str) -> str:
    """Stable deterministic ID for MERGE deduplication."""
    slug = re.sub(r"[^a-z0-9]+", "-", (url or title).lower())[-60:]
    return "yale:%s:%s" % (source, slug)


# ── Build nodes ───────────────────────────────────────────────────────────────

def build_opportunity_rows(feed_meta: dict, raw_items: list[dict]) -> list[dict]:
    rows = []
    source = feed_meta["source"]
    item_type = feed_meta["item_type"]
    for it in raw_items[:40]:  # cap per feed to keep Neo4j lean
        title = it.get("title") or ""
        url = it.get("url") or ""
        summary = _strip_html(it.get("summary") or "")
        if not title or not url:
            continue
        date_iso = _parse_date(it.get("date_raw") or "")
        score = _match_score(title, summary)
        rows.append({
            "id": _item_id(source, url, title),
            "title": title[:200],
            "url": url[:400],
            "source": source,
            "source_label": feed_meta["label"],
            "item_type": item_type,
            "date_iso": date_iso,
            "summary": summary,
            "match_score": score,
            "match_note": "mission-tag overlap score (0-100); higher = stronger 12SGI alignment",
            "layer": LAYER,
            "ingested_at": _now_iso(),
        })
    return rows


# ── Neo4j write ───────────────────────────────────────────────────────────────

def refresh() -> bool:
    """Ingest all Yale feeds into Neo4j as YaleOpportunity nodes.

    Additive layer (``yale_ecosystem``); never touches other layers.
    Soft-skips if Neo4j is unreachable or any feed fails.
    Runs on the Yale sunrise Pō cadence (09:20 UTC daily).
    """
    # 1. Ensure uniqueness constraint
    if _post([{
        "statement": (
            "CREATE CONSTRAINT yale_ecosystem_id IF NOT EXISTS "
            "FOR (x:YaleOpportunity) REQUIRE x.id IS UNIQUE"
        ),
    }]) is None:
        return False

    total = 0
    for feed in YALE_FEEDS:
        raw = _fetch_rss(feed["url"])
        if not raw:
            _say("yale_ecosystem: no items from %s" % feed["label"])
            continue
        rows = build_opportunity_rows(feed, raw)
        if not rows:
            continue
        _post([{
            "statement": (
                "UNWIND $rows AS r "
                "MERGE (n:YaleOpportunity {id:r.id}) "
                "SET n += r"
            ),
            "parameters": {"rows": rows},
        }])
        total += len(rows)
        _say("yale_ecosystem: %d items from %s" % (len(rows), feed["label"]))

    # 2. Cross-layer additive link: top-scoring opportunities → SAGE_CIVIC context
    _post([{
        "statement": (
            "MATCH (opp:YaleOpportunity) WHERE opp.match_score >= 16 "
            "MATCH (civic {id:$cid}) "
            "MERGE (opp)-[e:ALIGNED_WITH {key:opp.id + ':sage-civic'}]->(civic) "
            "SET e.layer = $layer, e.note = 'Yale opportunity aligned to 12SGI civic mission'"
        ),
        "parameters": {"cid": SAGE_CIVIC_CONTEXT_ID, "layer": LAYER},
    }])

    # 3. Stamp the layer refresh timestamp
    _post([{
        "statement": (
            "MERGE (meta:YaleEcosystemMeta {id:'yale_ecosystem:meta'}) "
            "SET meta.last_refreshed_at = $ts, meta.layer = $layer, meta.total_items = $total"
        ),
        "parameters": {"ts": _now_iso(), "layer": LAYER, "total": total},
    }])

    _say("yale_ecosystem: refresh complete — %d total items across %d feeds." % (total, len(YALE_FEEDS)))
    return True


# ── Query helpers (used by yale_opportunity_scan.py) ─────────────────────────

def top_opportunities(min_score: int = 16, limit: int = 20) -> list[dict]:
    """Return top YaleOpportunity nodes by match_score + recency."""
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
        "parameters": {"min": min_score, "lim": limit},
    }])
    if not result:
        return []
    rows = []
    for r in (result.get("results") or [{}])[0].get("data", []):
        cols = (result.get("results") or [{}])[0].get("columns", [])
        row = dict(zip(cols, r.get("row", [])))
        if row:
            rows.append(row)
    return rows


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ok = refresh()
    if ok:
        opps = top_opportunities(limit=5)
        _say("Top opportunities:")
        for o in opps:
            _say("  [%d] %s — %s" % (o.get("match_score", 0), o.get("title", "")[:80], o.get("url", "")[:60]))


if __name__ == "__main__":
    main()
