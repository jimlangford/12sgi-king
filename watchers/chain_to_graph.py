# -*- coding: utf-8 -*-
"""chain_to_graph.py — load the Maui money-chain into the LOCAL Neo4j graph. Runs on Jimmy's machine, FREE.

The one good idea borrowed from docker/genai-stack (a graph+vector store) — on our terms:
  - graph store = Neo4j Community, a LOCAL Docker container (127.0.0.1 only, no-auth prototype).
  - NO LangChain, NO second Ollama, NO pip driver: talks to Neo4j over its HTTP Cypher endpoint via urllib.
  - ZERO Claude tokens to run. Reuses reports/mauios/money_chain_maui.json (already built, sourced).

AuraDB Free dual-write (2026-07-13):
  - When NEO4J_AURA_URI is set in .env.v2, simultaneously writes civic data to AuraDB Free (backup+cloud mirror)
  - AuraDB is not required — gracefully skipped if missing credentials
  - Civic data is ~6.5k nodes / ~18k relationships, fits 25x over AuraDB Free limits (200k/400k/512MB)

Once loaded you can ask the graph what static JSON can't: multi-hop "up and down the chain" —
  which funder -> which prime -> which subrecipient -> is that sub ALSO a 990 nonprofit / a county vendor / a donor?

  python tools/kilo-aupuni/chain_to_graph.py            # (re)load the Maui chain into local + AuraDB
  python tools/kilo-aupuni/chain_to_graph.py --ask      # + print a few example up/down-the-chain queries
"""
import os, sys, json, argparse, urllib.request, urllib.error
from pathlib import Path


def _resolve_mauios_dir():
    override = os.environ.get("MAUIOS_REPORTS_DIR")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    default = here.parents[1] / "reports" / "mauios"
    candidates = []
    for ancestor in here.parents:
        candidates.append(ancestor / "reports" / "mauios")
    candidates.append(
        Path.home() / "Documents" / "Claude" / "Projects" / "Video System elementLOTUS" / "reports" / "mauios"
    )
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate
    return default


def _chain_path():
    return _resolve_mauios_dir() / "money_chain_maui.json"


NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
AURA_URI = os.environ.get("NEO4J_AURA_URI", "").strip()
AURA_USER = os.environ.get("NEO4J_AURA_USER", "neo4j")
AURA_PASSWORD = os.environ.get("NEO4J_AURA_PASSWORD", "").strip()
_AURA_DRIVER = None


def say(m):
    try:
        if sys.stdout:
            print(m, flush=True)
    except Exception:
        pass


def cypher(statements, endpoint=None, use_aura=False, timeout=90):
    """
    POST one or more Cypher statements to Neo4j's HTTP transactional endpoint (no auth = local prototype).
    If use_aura=True, attempts bolt driver connection. Falls back to local HTTP if not available.
    """
    target = endpoint or NEO
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(target, data=body,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        msg = "Neo4j not reachable"
        if use_aura:
            msg = "AuraDB not reachable"
        say("%s at %s (%s)." % (msg, target, str(e)[:120]))
        return None
    if out.get("errors"):
        say("Cypher errors: %s" % json.dumps(out["errors"])[:400])
    return out


def _aura_connect():
    """Open bolt+s connection to AuraDB if available. Returns session or None."""
    global _AURA_DRIVER
    if not AURA_URI or not AURA_PASSWORD:
        return None
    try:
        from neo4j import GraphDatabase
        _AURA_DRIVER = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASSWORD))
        session = _AURA_DRIVER.session()
        # Quick ping
        session.run("RETURN 1")
        return session
    except ImportError:
        say("neo4j-driver not installed — skipping AuraDB dual-write (pip install neo4j to enable)")
        return None
    except Exception as e:
        say("AuraDB connection failed: %s (continuing with local only)" % str(e)[:150])
        return None


def _aura_cypher(session, statements):
    """Execute Cypher batch on AuraDB via bolt driver session."""
    if not session:
        return None
    try:
        for stmt in statements:
            result = session.run(stmt["statement"], **(stmt.get("parameters") or {}))
            result.consume()  # Ensure it runs
        return {"ok": True}
    except Exception as e:
        say("AuraDB batch write failed: %s" % str(e)[:150])
        return None


def _rows(result_block):
    """Flatten a Neo4j HTTP result block into a list of row-value lists."""
    if not result_block:
        return []
    r = result_block.get("results", [])
    if not r:
        return []
    return [row.get("row", []) for row in r[0].get("data", [])]


def load():
    chain_path = _chain_path()
    if not chain_path.exists():
        say("money-chain source missing: %s" % chain_path)
        return False
    with open(chain_path, encoding="utf-8") as f:
        d = json.load(f)
    nodes = d.get("nodes", [])
    edges = d.get("edges", [])
    xkeys = {c.get("key") for c in d.get("cross_links", [])}
    for n in nodes:
        nid = n.get("id", "")
        n["key"] = nid.split(":", 1)[1] if ":" in nid else nid
        n["crosslink"] = n["key"] in xkeys
    for i, e in enumerate(edges):
        # stable per-edge id (2026-07-09 heal-audit fix, see below) — src|dst|kind|index, deterministic
        # across reloads of the SAME source JSON, so a re-run MERGEs onto the same relationship instead
        # of creating a duplicate.
        e["eid"] = "%s|%s|%s|%d" % (e.get("src"), e.get("dst"), e.get("kind"), i)

    say("loading %d nodes + %d edges into Neo4j (%d cross-layer entities)..." % (len(nodes), len(edges), len(xkeys)))

    # VERIFIED DELETE (2026-07-09 heal-audit fix): the old code only checked cypher()->None, which catches a
    # NETWORK failure but not a Cypher-level error in a 200 response — so a failed/partial DETACH DELETE let
    # every scheduled civic_graph_refresh silently ADD a full second copy on top of the old one. Confirmed
    # live: 1528 FLOW edges = exactly 2x the correct 764. Now: check for a Cypher error AND verify the node
    # count is actually 0 before proceeding; abort rather than risk doubling again.
    del_out = cypher([{"statement": "MATCH (n) DETACH DELETE n"}])
    if del_out is None or del_out.get("errors"):
        say("ABORT: graph reset failed (%s) — refusing to load on top of a possibly-nonempty graph."
            % (json.dumps(del_out.get("errors")) if del_out else "Neo4j unreachable"))
        return False
    chk = cypher([{"statement": "MATCH (n) RETURN count(n)"}])
    remaining = _rows({"results": [chk["results"][0]]})[0][0] if chk and not chk.get("errors") else None
    if remaining != 0:
        say("ABORT: graph reset left %r node(s) behind — refusing to load (would double)." % (remaining,))
        return False

    # CONNECT TO AURA FOR DUAL-WRITE (2026-07-13)
    aura_session = _aura_connect()
    if aura_session:
        say("AuraDB connection OK — dual-write enabled")
    else:
        say("AuraDB dual-write disabled (credentials missing or connection failed)")

    # LOCAL NEO4J: create constraint and load nodes
    cypher([{"statement": "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (x:Node) REQUIRE x.id IS UNIQUE"}])
    cypher([{"statement":
             "UNWIND $rows AS n MERGE (x:Node {id:n.id}) "
             "SET x.name=n.label, x.type=n.type, x.key=n.key, x.crosslink=n.crosslink",
             "parameters": {"rows": nodes}}])
    
    # AURA: duplicate constraint + nodes
    if aura_session:
        try:
            aura_session.run("CREATE CONSTRAINT node_id IF NOT EXISTS FOR (x:Node) REQUIRE x.id IS UNIQUE")
            aura_session.run(
                "UNWIND $rows AS n MERGE (x:Node {id:n.id}) "
                "SET x.name=n.label, x.type=n.type, x.key=n.key, x.crosslink=n.crosslink",
                rows=nodes
            )
        except Exception as e:
            say("AuraDB node write failed: %s (continuing with local)" % str(e)[:150])

    # LOCAL NEO4J: load edges (id-keyed MERGE to prevent duplicates)
    cypher([{"statement":
             "UNWIND $rows AS e MATCH (a:Node {id:e.src}) MATCH (b:Node {id:e.dst}) "
             "MERGE (a)-[r:FLOW {eid:e.eid}]->(b) "
             "SET r.kind=e.kind, r.amount=e.amount, r.label=e.label, r.source=e.source, "
             "r.source_url=e.source_url, r.source_type=e.source_type, r.verify=e.verify",
             "parameters": {"rows": edges}}])
    
    # AURA: duplicate edges
    if aura_session:
        try:
            aura_session.run(
                "UNWIND $rows AS e MATCH (a:Node {id:e.src}) MATCH (b:Node {id:e.dst}) "
                "MERGE (a)-[r:FLOW {eid:e.eid}]->(b) "
                "SET r.kind=e.kind, r.amount=e.amount, r.label=e.label, r.source=e.source, "
                "r.source_url=e.source_url, r.source_type=e.source_type, r.verify=e.verify",
                rows=edges
            )
        except Exception as e:
            say("AuraDB edge write failed: %s (continuing with local)" % str(e)[:150])

    # LOCAL: verify load
    v = cypher([
        {"statement": "MATCH (n:Node) RETURN count(n)"},
        {"statement": "MATCH ()-[r:FLOW]->() RETURN count(r)"},
        {"statement": "MATCH (n:Node {crosslink:true}) RETURN count(n)"},
    ])
    if v and not v.get("errors"):
        nc = _rows({"results": [v["results"][0]]})[0][0]
        ec = _rows({"results": [v["results"][1]]})[0][0]
        xc = _rows({"results": [v["results"][2]]})[0][0]
        say("LOCAL: %s nodes, %s FLOW edges, %s cross-layer entities. Graph live at http://localhost:7474" % (nc, ec, xc))
        if ec != len(edges):
            say("WARNING: loaded edge count (%s) != source edge count (%d) — investigate before trusting the graph."
                % (ec, len(edges)))
    else:
        say("LOCAL verification failed")
        return False

    # AURA: verify load (if connected)
    if aura_session:
        try:
            nc_result = aura_session.run("MATCH (n:Node) RETURN count(n)").single()
            nc = nc_result[0] if nc_result else 0
            ec_result = aura_session.run("MATCH ()-[r:FLOW]->() RETURN count(r)").single()
            ec = ec_result[0] if ec_result else 0
            xc_result = aura_session.run("MATCH (n:Node {crosslink:true}) RETURN count(n)").single()
            xc = xc_result[0] if xc_result else 0
            say("AURA:  %s nodes, %s FLOW edges, %s cross-layer entities" % (nc, ec, xc))
        except Exception as e:
            say("AURA verification failed: %s" % str(e)[:150])
    
    # Clean up
    if aura_session:
        try:
            aura_session.close()
        except Exception:
            pass

    return True


def ask():
    say("\n— example up/down-the-chain questions the GRAPH can answer (sourced; questions, not findings) —")
    # 1) cross-layer entities (a sub/prime that is ALSO a 990 nonprofit or county vendor or donor)
    r = cypher([{"statement":
                 "MATCH (n:Node {crosslink:true})-[r:FLOW]-() "
                 "RETURN n.name AS who, collect(DISTINCT r.kind) AS layers, count(r) AS edges "
                 "ORDER BY edges DESC LIMIT 8"}])
    for row in _rows(r):
        say("  cross-layer: %-42s layers=%s (%s edges)" % (str(row[0])[:42], row[1], row[2]))
    # 2) biggest single flows to verify
    r = cypher([{"statement":
                 "MATCH (a:Node)-[r:FLOW]->(b:Node) WHERE r.amount IS NOT NULL "
                 "RETURN a.name, r.kind, r.amount, b.name ORDER BY r.amount DESC LIMIT 6"}])
    say("  — largest flows —")
    for row in _rows(r):
        say("  $%15s  %-16s %s -> %s" % ("{:,.0f}".format(row[2]), row[1], str(row[0])[:24], str(row[3])[:28]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask", action="store_true")
    a = ap.parse_args()
    if load() and a.ask:
        ask()


if __name__ == "__main__":
    main()
