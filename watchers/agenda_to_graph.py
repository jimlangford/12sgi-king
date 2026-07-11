# -*- coding: utf-8 -*-
"""agenda_to_graph.py — load the civic agenda schedule into the LOCAL Neo4j graph.

Additive layer (label='agenda_civic') — never touches or deletes other layers.
Runs on the Hina cadence alongside the money-chain (chain_to_graph) via graph_refresh.

WHY: agenda_sources.json lists upcoming civic meetings as flat JSON. Once those meetings
are nodes in the graph, you can traverse them bi-directionally together with the money-
chain entities, the pulse geometry, and the Sage trinity — asking questions like:

    MATCH (m:CivicMeeting)-[:IN_PO]->(po:MoonNight {name:'Kūkahi'})
    RETURN m.date, m.body, m.tenant ORDER BY m.date

    MATCH (i:AgendaItem)-[:PREV_ACTION*1..4]->(orig:AgendaItem)
    RETURN orig.title, collect(i.date) AS timeline

    MATCH (m:CivicMeeting)-[:HAS_ITEM]->(i:AgendaItem)-[:NAMES]->(o:AgendaOrg)
    WHERE exists((o)-[:FUNDED_BY|:RECEIVES]-())
    RETURN o.name, i.title, m.date ORDER BY m.date

Nodes created / merged:
  MoonNight (30 permanent pō reference nodes)
  CivicMeeting (one per upcoming meeting per tenant)
  AgendaItem (when item detail is available)
  AgendaOrg (organisations named in items — MERGE by slug)
  AgendaDocument (attached packet files)

Edges:
  (CivicMeeting)-[:IN_PO]->(MoonNight)
  (CivicMeeting)-[:HAS_ITEM]->(AgendaItem)
  (AgendaItem)-[:PREV_ACTION]->(AgendaItem) — backward/forward continuity links
  (AgendaItem)-[:NAMES]->(AgendaOrg)
  (AgendaItem)-[:HAS_DOCUMENT]->(AgendaDocument)

Resilient: if Neo4j or moon_calendar is unavailable, logs and returns False (no crash).
Stdlib only — no third-party drivers; speaks the Neo4j HTTP transactional Cypher endpoint.
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
LAYER = "agenda_civic"
NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")

# ── sources ──────────────────────────────────────────────────────────────────
AGENDA_SOURCES = HERE / "agenda_sources.json"

# optional intel cache (reports/_status/agenda_intel_<tenant>.json)
_INTEL_DIR = REPO / "reports" / "_status"

# ── kaulana mahina pō names (mirrors moon_calendar.PO — imported if available) ──
_PO_NAMES = [
    ("Hilo","Hoʻonui","first thin crescent; new beginnings, planting",
     "a night of beginnings — plant the intention; learn the item before you speak","listen"),
    ("Hoaka","Hoʻonui","faint light; casting of shadows, caution",
     "go gently — gather the facts before the vote casts its shadow","listen"),
    ("Kūkahi","Hoʻonui","Kū — upright, standing; good for planting & work",
     "stand and be counted — a good night to testify","stand-testify"),
    ("Kūlua","Hoʻonui","Kū — upright, productive",
     "stand together — add your voice to the record","stand-testify"),
    ("Kūkolu","Hoʻonui","Kū — upright, productive",
     "keep standing — the upright nights favor those who show up","stand-testify"),
    ("Kūpau","Hoʻonui","Kū — the last of the upright nights",
     "finish what you stood for — submit the testimony","stand-testify"),
    ("ʻOlekūkahi","Hoʻonui","ʻOle — 'nothing'; low tides, rest, not for forcing",
     "a night to listen, not force — read the agenda, ready the question","listen-hold"),
    ("ʻOlekūlua","Hoʻonui","ʻOle — rest, weeding, clearing",
     "clear the noise — separate the money from the merit","listen-hold"),
    ("ʻOlekūkolu","Hoʻonui","ʻOle — rest, low productivity",
     "patience — let the record speak before you do","listen-hold"),
    ("ʻOlepau","Hoʻonui","ʻOle — the last quiet night",
     "rest closes; tomorrow the light grows — prepare to act","listen-hold"),
    ("Huna","Poepoe","hidden; root crops, the unseen made ready",
     "look for what's hidden in the item — the unanswered pair","flow"),
    ("Mōhalu","Poepoe","unfolding; flowers, fruit set",
     "let your testimony unfold — name the question plainly","flow"),
    ("Hua","Poepoe","fruit, seed, abundance begins",
     "the fruit forms — this is when showing up bears the most","stand-testify"),
    ("Akua","Poepoe","sacred to the akua; ceremony, reverence",
     "a sacred night — bring reverence, not contention, to the chamber","sacred"),
    ("Hoku","Poepoe","near-full; fullness, peak fishing & planting",
     "the people's voice is near its fullest — gather the neighbors","stand-testify"),
    ("Māhealani","Poepoe","FULL MOON; abundance, clarity, everything thrives",
     "full light — testify in the open; nothing hidden answers best now","full-light"),
    ("Kulu","Poepoe","the moon 'drips'/begins to wane; release",
     "release what's settled; carry forward what still needs answering","flow"),
    ("Lāʻaukūkahi","Poepoe","Lāʻau — medicine, healing herbs",
     "a healing night — frame the testimony to restore, not to wound","flow"),
    ("Lāʻaukūlua","Poepoe","Lāʻau — medicine, gathering of cures",
     "gather the remedy — the law that already answers the wrong","flow"),
    ("Lāʻaupau","Poepoe","Lāʻau — the last medicine night",
     "apply the cure — the records request, the testimony, the vote","stand-testify"),
    ("ʻOlekūkahi","Hoʻēmi","ʻOle — rest returns, low tides",
     "rest and watch — not every night is for forcing the hand","listen-hold"),
    ("ʻOlekūlua","Hoʻēmi","ʻOle — quiet, weeding",
     "weed the agenda — which items truly serve the people?","listen-hold"),
    ("ʻOlepau","Hoʻēmi","ʻOle — the last quiet of the waning",
     "stillness before the sacred nights — listen for the broken pair","listen-hold"),
    ("Kāloakūkahi","Hoʻēmi","Kāloa — sacred to Kanaloa (ocean); long crops, fishing",
     "the ocean's nights — think of the makai, the ʻāina, the long horizon","sacred"),
    ("Kāloakūlua","Hoʻēmi","Kāloa — Kanaloa; deep waters, endurance",
     "endure — the long crops and long fights both reward patience","flow"),
    ("Kāloapau","Hoʻēmi","Kāloa — the last of Kanaloa's nights",
     "close the deep work — what did the vote answer to?","flow"),
    ("Kāne","Hoʻēmi","KAPU to Kāne — fresh water, sun, life; ceremony, no contention",
     "sacred to Kāne — a night for collective good and clean water, not quarrel","sacred"),
    ("Lono","Hoʻēmi","KAPU to Lono — rain, harvest, peace; Makahiki spirit",
     "sacred to Lono — bring the harvest spirit: shared abundance, not capture","sacred"),
    ("Mauli","Hoʻēmi","last sliver, 'last breath' of the moon; reflection",
     "reflect — what pair still does not answer? mark it for the next light","listen"),
    ("Muku","Hoʻēmi","dark moon, 'cut off'; rest, the close before renewal",
     "the dark before renewal — rest, then begin the cycle in pono","listen"),
]

# ── moon math (mirrors moon_calendar — no import required) ───────────────────
_SYNODIC = 29.530588853
_REF_JD = 2451550.1  # 2000-01-06 ~18:14 UTC


def _jd(y: int, m: int, d: int) -> float:
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def _moon_age(date_str: str) -> float | None:
    """Days into current lunation (0..~29.53) from a YYYY-MM-DD string."""
    try:
        parts = date_str.split("-")
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        return (_jd(y, m, d) - _REF_JD) % _SYNODIC
    except Exception:
        return None


def _po_index(date_str: str) -> int | None:
    """Return 0-based pō index (0..29) for a date string, or None."""
    age = _moon_age(date_str)
    return None if age is None else min(29, int(age))


# ── Neo4j helper ─────────────────────────────────────────────────────────────

def _say(msg: str) -> None:
    try:
        print(msg, flush=True)
    except Exception:
        pass


def _post(statements: list[dict], timeout: int = 60):
    """POST Cypher statements to Neo4j. Returns None on network failure."""
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(
        NEO, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.URLError as exc:
        _say("agenda_to_graph: Neo4j not reachable (%s) — soft skip." % str(exc)[:100])
        return None
    if out.get("errors"):
        _say("agenda_to_graph: Cypher errors: %s" % json.dumps(out["errors"])[:300])
    return out


# ── data loading ─────────────────────────────────────────────────────────────

def _load_sources() -> list[dict]:
    try:
        with open(AGENDA_SOURCES, encoding="utf-8") as f:
            return json.load(f).get("sources", [])
    except Exception:
        return []


def _load_intel(tenant: str) -> dict:
    """Load agenda_intel cache for a tenant if available."""
    p = _INTEL_DIR / ("agenda_intel_%s.json" % tenant)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ── backward-link parsing ────────────────────────────────────────────────────

_BACKWARD_PAT = re.compile(
    r"(?:recessed|reconvened|continued|previously heard|deferred)\s+(?:from|to)?\s*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
    re.I,
)


def _extract_ref_date(text: str) -> str | None:
    """Extract a referenced prior meeting date from a title, return YYYY-MM-DD or None."""
    m = _BACKWARD_PAT.search(text or "")
    if not m:
        return None
    raw = m.group(1).replace("-", "/")
    parts = raw.split("/")
    if len(parts) == 3:
        mo, da, yr = parts[0], parts[1], parts[2]
        if len(yr) == 2:
            yr = "20" + yr
        try:
            return "%04d-%02d-%02d" % (int(yr), int(mo), int(da))
        except Exception:
            return None
    return None


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower())[:80].strip("-")


# ── node + edge builders ──────────────────────────────────────────────────────

def _moon_night_rows() -> list[dict]:
    rows = []
    for i, (name, anahulu, nature, offering, game_frame) in enumerate(_PO_NAMES):
        rows.append({
            "id": "moon:po:%d" % (i + 1),
            "po_index": i + 1,
            "name": name,
            "anahulu": anahulu,
            "nature": nature,
            "offering": offering,
            "game_frame": game_frame,
            "layer": LAYER,
        })
    return rows


def _meeting_rows(sources: list[dict]) -> list[dict]:
    rows = []
    for src in sources:
        tenant = src.get("tenant_id", "")
        for m in src.get("upcoming") or []:
            date_str = m.get("date", "")
            body = m.get("body", "")
            title = m.get("title", "")
            url = m.get("url", "")
            po_idx = _po_index(date_str)
            mid = "meeting:%s:%s:%s" % (tenant, date_str, _slugify(body)[:40])
            rows.append({
                "id": mid,
                "tenant": tenant,
                "date": date_str,
                "body": body,
                "title": title,
                "url": url,
                "po_index": (po_idx + 1) if po_idx is not None else None,
                "moon_night_id": ("moon:po:%d" % (po_idx + 1)) if po_idx is not None else None,
                "layer": LAYER,
            })
    return rows


def _item_rows_for_meeting(meeting_id: str, tenant: str, date_str: str,
                            intel: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (item_rows, org_rows, doc_rows) for a meeting from its intel cache."""
    item_rows: list[dict] = []
    org_rows: list[dict] = []
    doc_rows: list[dict] = []
    # intel keys vary; try to find a meetings list
    meetings = intel.get("meetings") or []
    for mtg in meetings:
        if mtg.get("date", "") != date_str:
            continue
        for idx, item in enumerate(mtg.get("items") or []):
            iid = "item:%s:%d" % (meeting_id, idx + 1)
            title = item.get("title") or item.get("name") or ""
            ref_date = _extract_ref_date(title)
            item_rows.append({
                "id": iid,
                "meeting_id": meeting_id,
                "item_num": idx + 1,
                "title": title,
                "item_type": item.get("type") or item.get("action_type") or "",
                "status": item.get("status") or "",
                "ref_date": ref_date or "",   # date of prior meeting this item came from
                "tenant": tenant,
                "layer": LAYER,
            })
            # named entities
            for ent in item.get("entities") or []:
                name = (ent if isinstance(ent, str) else ent.get("name", "")).strip()
                if name:
                    oid = "org:%s" % _slugify(name)
                    org_rows.append({"id": oid, "name": name,
                                     "item_id": iid, "layer": LAYER})
            # attached documents
            for att in item.get("attachments") or []:
                url = att.get("url") or att.get("file_url") or ""
                fname = att.get("name") or att.get("filename") or url.split("/")[-1][:80]
                if url:
                    did = "doc:%s:%d" % (_slugify(fname), abs(hash(url)) % 100000)
                    doc_rows.append({"id": did, "name": fname,
                                     "url": url, "item_id": iid, "layer": LAYER})
    return item_rows, org_rows, doc_rows


# ── main refresh ──────────────────────────────────────────────────────────────

def refresh() -> bool:
    """Write the civic agenda schedule into Neo4j as an additive agenda_civic layer.

    Returns True on success, False on Neo4j unavailable or hard error.
    """
    # 1. Ensure uniqueness constraints for this layer
    result = _post([
        {"statement": (
            "CREATE CONSTRAINT agenda_civic_moon_id IF NOT EXISTS "
            "FOR (n:MoonNight) REQUIRE n.id IS UNIQUE"
        )},
        {"statement": (
            "CREATE CONSTRAINT agenda_civic_meeting_id IF NOT EXISTS "
            "FOR (n:CivicMeeting) REQUIRE n.id IS UNIQUE"
        )},
        {"statement": (
            "CREATE CONSTRAINT agenda_civic_item_id IF NOT EXISTS "
            "FOR (n:AgendaItem) REQUIRE n.id IS UNIQUE"
        )},
        {"statement": (
            "CREATE CONSTRAINT agenda_civic_org_id IF NOT EXISTS "
            "FOR (n:AgendaOrg) REQUIRE n.id IS UNIQUE"
        )},
        {"statement": (
            "CREATE CONSTRAINT agenda_civic_doc_id IF NOT EXISTS "
            "FOR (n:AgendaDocument) REQUIRE n.id IS UNIQUE"
        )},
    ])
    if result is None:
        return False

    # 2. MoonNight reference nodes (30 permanent pō nights)
    moon_rows = _moon_night_rows()
    r = _post([{
        "statement": (
            "UNWIND $rows AS r "
            "MERGE (n:AgendaCivic:MoonNight {id:r.id}) "
            "SET n += r"
        ),
        "parameters": {"rows": moon_rows},
    }])
    if r is None:
        return False
    _say("agenda_to_graph: %d MoonNight nodes merged." % len(moon_rows))

    # 3. CivicMeeting nodes
    sources = _load_sources()
    meeting_rows = _meeting_rows(sources)
    if meeting_rows:
        r = _post([{
            "statement": (
                "UNWIND $rows AS r "
                "MERGE (n:AgendaCivic:CivicMeeting {id:r.id}) "
                "SET n += r"
            ),
            "parameters": {"rows": meeting_rows},
        }])
        if r is None:
            return False

    # 4. IN_PO edges: CivicMeeting → MoonNight
    meeting_po_pairs = [
        {"mid": m["id"], "poid": m["moon_night_id"]}
        for m in meeting_rows if m.get("moon_night_id")
    ]
    if meeting_po_pairs:
        _post([{
            "statement": (
                "UNWIND $pairs AS p "
                "MATCH (m:CivicMeeting {id:p.mid}) "
                "MATCH (po:MoonNight {id:p.poid}) "
                "MERGE (m)-[e:IN_PO {layer:$layer}]->(po)"
            ),
            "parameters": {"pairs": meeting_po_pairs, "layer": LAYER},
        }])

    # 5. AgendaItem nodes (from intel cache) + HAS_ITEM edges
    all_items: list[dict] = []
    all_orgs: list[dict] = []
    all_docs: list[dict] = []
    for src in sources:
        tenant = src.get("tenant_id", "")
        intel = _load_intel(tenant)
        for m in src.get("upcoming") or []:
            date_str = m.get("date", "")
            body = m.get("body", "")
            mid = "meeting:%s:%s:%s" % (tenant, date_str, _slugify(body)[:40])
            items, orgs, docs = _item_rows_for_meeting(mid, tenant, date_str, intel)
            all_items.extend(items)
            all_orgs.extend(orgs)
            all_docs.extend(docs)

    if all_items:
        _post([{
            "statement": (
                "UNWIND $rows AS r "
                "MERGE (n:AgendaCivic:AgendaItem {id:r.id}) "
                "SET n += r"
            ),
            "parameters": {"rows": all_items},
        }])
        _post([{
            "statement": (
                "UNWIND $rows AS r "
                "MATCH (m:CivicMeeting {id:r.meeting_id}) "
                "MATCH (i:AgendaItem {id:r.id}) "
                "MERGE (m)-[e:HAS_ITEM {layer:$layer}]->(i)"
            ),
            "parameters": {"rows": all_items, "layer": LAYER},
        }])

    # 6. PREV_ACTION edges (backward/forward continuity)
    #    When an item's title says "Reconvened from MM/DD/YYYY", link it to an
    #    earlier meeting node (if it exists in the graph) with a PREV_ACTION edge.
    for item in all_items:
        ref_date = item.get("ref_date")
        if not ref_date:
            continue
        tenant = item.get("tenant", "")
        # find any meeting on that tenant+date
        _post([{
            "statement": (
                "MATCH (cur:AgendaItem {id:$iid}) "
                "MATCH (prev:CivicMeeting {tenant:$tenant, date:$date}) "
                "MERGE (cur)-[e:PREV_ACTION {layer:$layer, ref_date:$date}]->(prev)"
            ),
            "parameters": {
                "iid": item["id"],
                "tenant": tenant,
                "date": ref_date,
                "layer": LAYER,
            },
        }])

    # 7. AgendaOrg nodes + NAMES edges
    if all_orgs:
        # deduplicate by org id
        seen_orgs: dict[str, dict] = {}
        for o in all_orgs:
            seen_orgs.setdefault(o["id"], o)
        org_nodes = [{"id": v["id"], "name": v["name"], "layer": LAYER}
                     for v in seen_orgs.values()]
        _post([{
            "statement": (
                "UNWIND $rows AS r "
                "MERGE (n:AgendaCivic:AgendaOrg {id:r.id}) "
                "SET n += r"
            ),
            "parameters": {"rows": org_nodes},
        }])
        _post([{
            "statement": (
                "UNWIND $rows AS r "
                "MATCH (i:AgendaItem {id:r.item_id}) "
                "MATCH (o:AgendaOrg {id:r.id}) "
                "MERGE (i)-[e:NAMES {layer:$layer}]->(o)"
            ),
            "parameters": {"rows": all_orgs, "layer": LAYER},
        }])

    # 8. AgendaDocument nodes + HAS_DOCUMENT edges
    if all_docs:
        seen_docs: dict[str, dict] = {}
        for d in all_docs:
            seen_docs.setdefault(d["id"], d)
        doc_nodes = [{"id": v["id"], "name": v["name"], "url": v["url"], "layer": LAYER}
                     for v in seen_docs.values()]
        _post([{
            "statement": (
                "UNWIND $rows AS r "
                "MERGE (n:AgendaCivic:AgendaDocument {id:r.id}) "
                "SET n += r"
            ),
            "parameters": {"rows": doc_nodes},
        }])
        _post([{
            "statement": (
                "UNWIND $rows AS r "
                "MATCH (i:AgendaItem {id:r.item_id}) "
                "MATCH (d:AgendaDocument {id:r.id}) "
                "MERGE (i)-[e:HAS_DOCUMENT {layer:$layer}]->(d)"
            ),
            "parameters": {"rows": all_docs, "layer": LAYER},
        }])

    # 9. Cross-layer edge: CivicMeeting → Entity (money-chain) for orgs already in graph
    #    Opportunistic — only succeeds when chain_to_graph has already loaded the chain.
    if all_orgs:
        _post([{
            "statement": (
                "UNWIND $orgs AS o "
                "MATCH (org:AgendaOrg {id:o.id}) "
                "MATCH (ent) WHERE ent.name =~ ('(?i).*' + o.name + '.*') "
                "  AND (ent:Entity OR ent:Organization) "
                "MERGE (org)-[e:SAME_AS {layer:$layer, note:'name-match cross-layer'}]->(ent)"
            ),
            "parameters": {
                "orgs": [{"id": v["id"], "name": v["name"]} for v in seen_orgs.values()],
                "layer": LAYER,
            },
        }])

    _say("agenda_to_graph: %d meetings · %d items · %d orgs · %d docs · layer=%s"
         % (len(meeting_rows), len(all_items), len(all_orgs), len(all_docs), LAYER))
    return True


def main() -> None:
    ok = refresh()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
