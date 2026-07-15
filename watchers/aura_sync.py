# -*- coding: utf-8 -*-
"""aura_sync.py — nightly sync of public-safe civic data from local Neo4j → AuraDB Free.

AuraDB Free tier: 200k nodes, 400k relationships, 512MB storage. Ideal for read-heavy, cloud-accessible backups.
Your data (~6.5k nodes, ~18k relationships) fits 25x over with room.

This watcher runs nightly (cronjob or Docker scheduler):
  - Pulls all civic/public NODES from the local Neo4j (127.0.0.1:7474, no auth)
  - Pulls all FLOW relationships between civic nodes
  - Uperts them (idempotent MERGE) into AuraDB Free via bolt+s protocol (TLS required, no HTTP fallback)
  - Logs success/failure + row counts to the dispatch log for audit

Setup (one-time):
  1. Create a free Neo4j AuraDB instance: https://neo4j.com/cloud/aura-free/
  2. Save credentials to .env.v2 (gitignored):
       NEO4J_AURA_URI=neo4j+s://abcd1234-xxxx-xxxx.databases.neo4j.io:7687
       NEO4J_AURA_USER=neo4j
       NEO4J_AURA_PASSWORD=xxxxxxxxxxxxxxxxxx
  3. Leave NEO4J_AURA_URI empty to skip Aura syncs (no error — gracefully degrades)

Security:
  - DOES sync: Node labels (civic, asset, entity), properties (name, type, key), FLOW edges (amount, kind, source)
  - DOES NOT sync: auth tokens, internal service tokens, tenant secrets, raw workboard payloads
  - Aura credentials are injected at runtime from .env.v2, never committed
  - Can be further restricted by IP allowlisting in AuraDB console

Scheduled runs:
  - Docker Compose: add a `watchers` service with `cron` + this script
  - Kubernetes: CronJob resource running the same command
  - Local dev: `python watchers/aura_sync.py --once` from the repo root
"""
import json
import os
import sys
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# ── Repo-root imports ─────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from neo4j import GraphDatabase, Session
    _NEO4J_DRIVER_AVAILABLE = True
except ImportError:
    _NEO4J_DRIVER_AVAILABLE = False

# ── Config ────────────────────────────────────────────────────────────────────
LOCAL_NEO4J_HTTP = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
AURA_URI = os.environ.get("NEO4J_AURA_URI", "").strip()
AURA_USER = os.environ.get("NEO4J_AURA_USER", "neo4j")
AURA_PASSWORD = os.environ.get("NEO4J_AURA_PASSWORD", "").strip()
DISPATCH_LOG = os.environ.get("WORKBOARD_DISPATCH_LOG", "/data/dispatch/govos_v2_dispatch.jsonl")
TIMEOUT = 60


def say(msg: str):
    """Log to stdout + dispatch log."""
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}", flush=True)
    try:
        Path(DISPATCH_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(DISPATCH_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "kind": "watcher.aura_sync",
                        "iso": ts,
                        "message": msg,
                    }
                )
                + "\n"
            )
    except Exception as e:
        print(f"[dispatch log write failed: {e}]", flush=True)


def _local_cypher(statements: list[dict]) -> dict | None:
    """Send Cypher to local Neo4j via HTTP (no auth, no driver — fast + lightweight)."""
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(
        LOCAL_NEO4J_HTTP,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        say(f"local Neo4j unreachable at {LOCAL_NEO4J_HTTP}: {str(e)[:100]}")
        return None
    except Exception as e:
        say(f"local Neo4j error: {str(e)[:100]}")
        return None


def _rows(result_block: dict | None) -> list[list]:
    """Flatten Neo4j HTTP result block into row lists."""
    if not result_block or "results" not in result_block:
        return []
    results = result_block.get("results", [])
    if not results:
        return []
    return [row.get("row", []) for row in results[0].get("data", [])]


def _aura_session() -> Optional[Session]:
    """Open bolt+s connection to AuraDB. Returns None if credentials missing or driver unavailable."""
    if not _NEO4J_DRIVER_AVAILABLE:
        say("neo4j-driver not installed (pip install neo4j) — skipping Aura sync")
        return None
    if not AURA_URI or not AURA_PASSWORD:
        say("NEO4J_AURA_URI or NEO4J_AURA_PASSWORD not set in .env.v2 — Aura sync disabled (graceful)")
        return None
    try:
        driver = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASSWORD))
        session = driver.session()
        # Quick ping
        session.run("RETURN 1")
        return session
    except Exception as e:
        say(f"Aura connection failed: {str(e)[:150]}")
        return None


def _aura_write_nodes(session: Session, nodes: list[dict]) -> int:
    """Batch MERGE nodes into Aura. Returns count written."""
    if not nodes:
        return 0
    try:
        result = session.run(
            """
            UNWIND $rows AS n
            MERGE (x:Node {id: n.id})
            SET x.name = n.name,
                x.type = n.type,
                x.key = n.key,
                x.crosslink = n.crosslink
            RETURN count(*)
            """,
            rows=nodes,
        )
        return result.single()[0]
    except Exception as e:
        say(f"Aura node write failed: {str(e)[:150]}")
        return 0


def _aura_write_edges(session: Session, edges: list[dict]) -> int:
    """Batch MERGE edges into Aura. Returns count written."""
    if not edges:
        return 0
    try:
        result = session.run(
            """
            UNWIND $rows AS e
            MATCH (a:Node {id: e.src})
            MATCH (b:Node {id: e.dst})
            MERGE (a)-[r:FLOW {eid: e.eid}]->(b)
            SET r.kind = e.kind,
                r.amount = e.amount,
                r.label = e.label,
                r.source = e.source,
                r.source_url = e.source_url,
                r.source_type = e.source_type,
                r.verify = e.verify
            RETURN count(*)
            """,
            rows=edges,
        )
        return result.single()[0]
    except Exception as e:
        say(f"Aura edge write failed: {str(e)[:150]}")
        return 0


def sync_once() -> bool:
    """
    One-shot sync: pull nodes + edges from local Neo4j, push to AuraDB.
    Returns True if successful (or if Aura is disabled), False on error.
    """
    say("=== aura_sync START ===")

    # Pull from local Neo4j
    say("pulling civic data from local Neo4j...")
    local_result = _local_cypher(
        [
            {
                "statement": "MATCH (n:Node) RETURN n.id, n.name, n.type, n.key, coalesce(n.crosslink, false) AS crosslink"
            }
        ]
    )
    if local_result is None or local_result.get("errors"):
        say(f"local Neo4j pull failed: {local_result}")
        return False

    nodes = []
    for row in _rows(local_result):
        nodes.append(
            {
                "id": row[0],
                "name": row[1],
                "type": row[2],
                "key": row[3],
                "crosslink": row[4],
            }
        )
    say(f"pulled {len(nodes)} nodes from local")

    # Pull edges
    local_edges_result = _local_cypher(
        [
            {
                "statement": """
                MATCH ()-[r:FLOW]->()
                RETURN r.eid, r.src, r.dst, r.kind, r.amount, r.label, r.source, r.source_url, r.source_type, r.verify
            """
            }
        ]
    )
    if local_edges_result is None or local_edges_result.get("errors"):
        say(f"local Neo4j edge pull failed: {local_edges_result}")
        return False

    # Reconstruct edges (eid comes from chain_to_graph.py load, or we rebuild it)
    edges = []
    for row in _rows(local_edges_result):
        edges.append(
            {
                "eid": row[0],
                "src": row[1],
                "dst": row[2],
                "kind": row[3],
                "amount": row[4],
                "label": row[5],
                "source": row[6],
                "source_url": row[7],
                "source_type": row[8],
                "verify": row[9],
            }
        )
    say(f"pulled {len(edges)} edges from local")

    # Connect to Aura
    aura_session = _aura_session()
    if aura_session is None:
        say("Aura sync disabled or unavailable — local sync complete, skipping cloud")
        say("=== aura_sync END (Aura disabled) ===")
        return True

    # Write to Aura
    try:
        say("writing nodes to Aura...")
        nodes_written = _aura_write_nodes(aura_session, nodes)
        say(f"wrote {nodes_written} nodes to Aura")

        say("writing edges to Aura...")
        edges_written = _aura_write_edges(aura_session, edges)
        say(f"wrote {edges_written} edges to Aura")

        say(f"=== aura_sync COMPLETE: {nodes_written} nodes, {edges_written} edges ===")
        return True
    except Exception as e:
        say(f"Aura write batch failed: {str(e)[:150]}")
        return False
    finally:
        try:
            aura_session.close()
        except Exception:
            pass


def main():
    """Entry point. Always exits 0 to prevent container restart loops."""
    try:
        if sync_once():
            sys.exit(0)
        else:
            say("sync failed, but exiting 0 anyway (no restart loop)")
            sys.exit(0)
    except Exception as e:
        say(f"FATAL: {str(e)}")
        traceback.print_exc()
        sys.exit(0)


if __name__ == "__main__":
    main()
