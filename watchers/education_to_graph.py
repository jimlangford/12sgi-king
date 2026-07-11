#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""education_to_graph.py — load the civic-education grade-band <-> civic-data map into LOTUS
(the LOCAL Neo4j graph), and let a student/teacher ask "what should a K-2 / college / grad
student look at?" and get a grade-appropriate answer back — pulling from the SAME sourced
government data the govOS watchers already publish (Today's Civic Agenda, Meeting Calendars,
News vs Record, Open Data, the money-chain graph from chain_to_graph.py), never fabricated.

Same house rules as chain_to_graph.py / graph_vectors.py:
  - graph store = Neo4j Community, a LOCAL Docker container (127.0.0.1 only, no-auth prototype).
  - NO LangChain, NO pip driver: talks to Neo4j over its HTTP Cypher endpoint via urllib.
  - ZERO Claude/cloud tokens to run. This script only ever ADDS the education layer on top of
    whatever chain_to_graph.py already loaded — it never DETACH DELETEs the whole graph.
  - Runs on Jimmy's machine, not from a cloud agent session (Neo4j only answers on 127.0.0.1).

TWO layers, both requested together (2026-07-11, Jimmy):
  (1) GradeBand <-[:USES]-> CivicTool  — which tool/page each grade band is pointed at, and why.
      Sourced directly from education.html's own copy (nothing invented for the bands marked
      "in development" there — this script mirrors that honesty: those bands get the tools
      that are already usable as-is, no fabricated lesson content).
  (2) GradeBand <-[:CAN_QUERY]-> Node  — links each grade band to the EXISTING money-chain /
      civic Node graph (chain_to_graph.py), tagged with a grade_floor so a query can be filtered
      to "what's appropriate to show this grade band" without duplicating or rewriting that data.

  python watchers/education_to_graph.py                       # load both layers (idempotent MERGE)
  python watchers/education_to_graph.py --dry-run              # print the Cypher, POST nothing
  python watchers/education_to_graph.py --ask k2               # tools mapped to K-2
  python watchers/education_to_graph.py --ask college --query "county contracts"
                                                                 # grade-filtered pull from the
                                                                 # real graph (falls back to the
                                                                 # static map if Neo4j is down —
                                                                 # a student always gets an answer)
"""
import os, sys, json, argparse, urllib.request, urllib.error

NEO = os.environ.get("NEO4J_HTTP") or "http://127.0.0.1:7474/db/neo4j/tx/commit"

# ---------------------------------------------------------------------------
# Layer 1: grade band -> civic tool/page, sourced from education.html's own copy.
# ---------------------------------------------------------------------------
GRADE_BANDS = [
    {"id": "k2",      "label": "K \u2013 2",                     "ages": "5\u20138"},
    {"id": "g35",     "label": "Grades 3 \u2013 5",               "ages": "8\u201311"},
    {"id": "g68",     "label": "Grades 6 \u2013 8",               "ages": "11\u201314"},
    {"id": "g912",    "label": "Grades 9 \u2013 12",              "ages": "14\u201318"},
    {"id": "college", "label": "College & University",     "ages": None},
    {"id": "grad",    "label": "Graduate & Professional",  "ages": None},
]

CIVIC_TOOLS = [
    {"id": "civic_dashboard",   "label": "Civic Dashboard",                       "url": "reports.html",         "kind": "tool", "grade_floor": 0},
    {"id": "agenda_viewer",     "label": "Agenda Viewer / Agenda Intel",          "url": "agendas.html",         "kind": "tool", "grade_floor": 0},
    {"id": "civic_records",     "label": "Civic Records",                        "url": "reports.html",         "kind": "tool", "grade_floor": 0},
    {"id": "news_vs_record",    "label": "News vs Record",                       "url": "news_record.html",     "kind": "data", "grade_floor": 2},
    {"id": "civic_daily",       "label": "Today's Civic Agenda (daily state)",    "url": "civic_daily.html",     "kind": "data", "grade_floor": 1},
    {"id": "meetings_calendar", "label": "Meeting Calendars (yearly calendar)",   "url": "meetings_calendar.html","kind": "data", "grade_floor": 1},
    {"id": "open_data",         "label": "Open Data catalog",                    "url": "datasets.html",        "kind": "data", "grade_floor": 4},
    {"id": "money_chain",       "label": "Money-chain graph (LOTUS)",            "url": None,                   "kind": "data", "grade_floor": 4},
]
# grade_floor is an index into GRADE_BANDS (0=k2 ... 5=grad) — the youngest band a tool is
# considered appropriate to hand to unguided. Below its floor, a tool can still be shown but
# framed as a class-led activity (see USES.activity), never as a self-serve research source.

USES = [  # (grade_id, tool_id, activity) — mirrors education.html's own text, nothing added
    ("k2", "civic_dashboard",   "Name a local official and their job (Map Our Community Leaders activity)"),
    ("k2", "agenda_viewer",     "Show a real upcoming agenda; ask what the county is deciding this week"),
    ("k2", "civic_records",     "Coastal/permit records for the land-and-water lesson"),
    ("g35", "news_vs_record",    "Compare a news headline to the underlying primary source, at a 3-5 reading level"),
    ("g35", "meetings_calendar", "Find how often the local council actually meets"),
    ("g68", "news_vs_record",    "Check a news story's frame against the filed record"),
    ("g68", "civic_daily",       "Read today's real agenda before a class discussion"),
    ("g912", "agenda_viewer",    "Track money-to-votes patterns tied to a real upcoming agenda item"),
    ("g912", "civic_dashboard",  "Civic-action unit: testimony + public-comment workflow"),
    ("college", "open_data",     "Research methods / data-journalism coursework on the raw sourced JSON"),
    ("college", "meetings_calendar", "Longitudinal study of meeting cadence, 2015-present"),
    ("grad", "open_data",        "Policy / public-administration research on the full sourced record"),
    ("grad", "money_chain",      "Multi-hop funder -> prime -> subrecipient case study via the LOTUS graph"),
    ("grad", "civic_daily",      "Same-day government-activity case material"),
]

_GRADE_ORDER = {g["id"]: i for i, g in enumerate(GRADE_BANDS)}


def say(m):
    try:
        if sys.stdout:
            print(m, flush=True)
    except Exception:
        pass


def cypher(statements, timeout=90):
    """POST Cypher statements to Neo4j's HTTP transactional endpoint (no auth = local prototype)."""
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(NEO, data=body,
                                  headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        say("Neo4j not reachable at %s (%s). Is the lotus-neo4j container up?" % (NEO, str(e)[:120]))
        return None
    if out.get("errors"):
        say("Cypher errors: %s" % json.dumps(out["errors"])[:400])
    return out


def _rows(result_block, i=0):
    if not result_block or result_block.get("errors"):
        return []
    r = result_block.get("results", [])
    if not r or i >= len(r):
        return []
    return [row.get("row", []) for row in r[i].get("data", [])]


def build_statements():
    """Additive load: MERGE only. Never touches the existing :Node money-chain graph beyond
    linking to it by id — safe to run alongside / after chain_to_graph.py, any order, repeatedly."""
    stmts = [
        {"statement": "CREATE CONSTRAINT gradeband_id IF NOT EXISTS FOR (x:GradeBand) REQUIRE x.id IS UNIQUE"},
        {"statement": "CREATE CONSTRAINT civictool_id IF NOT EXISTS FOR (x:CivicTool) REQUIRE x.id IS UNIQUE"},
        {"statement": "UNWIND $rows AS g MERGE (x:GradeBand {id:g.id}) SET x.label=g.label, x.ages=g.ages, x.order=g.order",
         "parameters": {"rows": [dict(g, order=i) for i, g in enumerate(GRADE_BANDS)]}},
        {"statement": "UNWIND $rows AS t MERGE (x:CivicTool {id:t.id}) SET x.label=t.label, x.url=t.url, x.kind=t.kind, x.grade_floor=t.grade_floor",
         "parameters": {"rows": CIVIC_TOOLS}},
        {"statement": ("UNWIND $rows AS u MATCH (g:GradeBand {id:u.grade}) MATCH (t:CivicTool {id:u.tool}) "
                        "MERGE (g)-[r:USES]->(t) SET r.activity=u.activity"),
         "parameters": {"rows": [{"grade": g, "tool": t, "activity": a} for g, t, a in USES]}},
        # Layer 2: link each GradeBand to the existing money-chain Node graph (chain_to_graph.py),
        # gated by grade_floor so grad/college reach it and younger bands don't get an unguided
        # self-serve link into raw financial-flow data. No-op (empty MATCH) if that graph hasn't
        # been loaded yet — never an error, just fewer edges.
        {"statement": ("MATCH (g:GradeBand) WHERE g.order >= 4 "
                        "MATCH (n:Node) "
                        "MERGE (g)-[r:CAN_QUERY]->(n) SET r.via='money_chain'")},
    ]
    return stmts


def load(dry_run=False):
    stmts = build_statements()
    if dry_run:
        for s in stmts:
            say(s["statement"])
        say("(--dry-run: nothing posted to Neo4j)")
        return True
    out = cypher(stmts)
    if out is None or out.get("errors"):
        say("ABORT: education graph load failed.")
        return False
    v = cypher([
        {"statement": "MATCH (n:GradeBand) RETURN count(n)"},
        {"statement": "MATCH (n:CivicTool) RETURN count(n)"},
        {"statement": "MATCH ()-[r:USES]->() RETURN count(r)"},
        {"statement": "MATCH ()-[r:CAN_QUERY]->() RETURN count(r)"},
    ])
    if v:
        gb = _rows(v, 0)[0][0] if _rows(v, 0) else 0
        ct = _rows(v, 1)[0][0] if _rows(v, 1) else 0
        us = _rows(v, 2)[0][0] if _rows(v, 2) else 0
        cq = _rows(v, 3)[0][0] if _rows(v, 3) else 0
        say("loaded: %d grade bands, %d civic tools, %d USES edges, %d CAN_QUERY edges (money-chain link)"
            % (gb, ct, us, cq))
    return True


def _static_ask(grade_id):
    """Fallback answer when Neo4j is unreachable — a student/teacher never gets nothing."""
    band = next((g for g in GRADE_BANDS if g["id"] == grade_id), None)
    if not band:
        return "unknown grade band %r — choose one of: %s" % (grade_id, ", ".join(g["id"] for g in GRADE_BANDS))
    rows = [(t, a) for g, t, a in USES if g == grade_id]
    tool_by_id = {t["id"]: t for t in CIVIC_TOOLS}
    lines = ["%s (%s):" % (band["label"], band["ages"] or "college/grad")]
    for tid, activity in rows:
        t = tool_by_id.get(tid, {})
        lines.append("  - %s (%s): %s" % (t.get("label", tid), t.get("url", "-"), activity))
    return "\n".join(lines)


def ask(grade_id, query=None):
    """Grade-appropriate pull: try the live graph first (LOTUS), fall back to the static map."""
    out = cypher([
        {"statement": ("MATCH (g:GradeBand {id:$id})-[u:USES]->(t:CivicTool) "
                        "RETURN t.label, t.url, u.activity, t.kind ORDER BY t.grade_floor"),
         "parameters": {"id": grade_id}},
    ])
    rows = _rows(out, 0) if out else []
    if not rows:
        say(_static_ask(grade_id))
        return
    band = next((g for g in GRADE_BANDS if g["id"] == grade_id), {"label": grade_id})
    say("%s (from LOTUS graph):" % band["label"])
    for label, url, activity, kind in rows:
        say("  - [%s] %s (%s): %s" % (kind, label, url, activity))
    if query:
        # Grade-gated pull from the money-chain / civic Node graph the CAN_QUERY edge licenses.
        out2 = cypher([
            {"statement": ("MATCH (g:GradeBand {id:$id})-[:CAN_QUERY]->(n:Node) "
                            "WHERE toLower(n.name) CONTAINS toLower($q) "
                            "RETURN n.name, n.type LIMIT 10"),
             "parameters": {"id": grade_id, "q": query}},
        ])
        rows2 = _rows(out2, 0) if out2 else []
        if rows2:
            say("  matching sourced records for %r:" % query)
            for name, typ in rows2:
                say("    - %s (%s)" % (name, typ))
        else:
            say("  no matching records for %r at this grade level (either none exist, this grade "
                "band isn't licensed for the money-chain graph, or Neo4j/chain_to_graph.py hasn't "
                "been loaded yet)." % query)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print the Cypher, POST nothing")
    ap.add_argument("--ask", metavar="GRADE_ID", help="print the tools mapped to a grade band (k2, g35, g68, g912, college, grad)")
    ap.add_argument("--query", metavar="TEXT", help="with --ask: grade-gated pull from the money-chain graph")
    args = ap.parse_args()
    if args.ask:
        ask(args.ask, args.query)
        return
    load(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
