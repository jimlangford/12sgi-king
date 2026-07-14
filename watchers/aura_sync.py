"""
aura_sync.py — sync public-safe Neo4j data from local instance → AuraDB Free (always-free cloud mirror).

WHY: lotus-neo4j is local-only (127.0.0.1, Tailscale). AuraDB Free gives the same graph
a cloud endpoint reachable from any device without Tailscale — backup, read-only public
queries, and king-bridge fallback when the local container is offline.

WHAT SYNCS (public-safe only):
  - Node + FLOW graph (civic chain — sourced, public record)
  - TenantChainNode entities and funders
  - Doc nodes (sourced civic docs — federal_prime, subcontract, nonprofit_990, etc.)
  - Surface + Side nodes (civic UI structure)
  - BridgeJob nodes (AI inference results, anonymized)

WHAT NEVER SYNCS:
  - StudioClipNode / StudioAssetNode (production assets — PRIVATE while in production)
  - StudioLearning (training data — PRIVATE)
  - Owner-specific session data or private case data

USAGE:
  python watchers/aura_sync.py                  # full sync
  python watchers/aura_sync.py --dry-run        # print what would sync, no writes
  python watchers/aura_sync.py --label Doc      # sync one label only
  python watchers/aura_sync.py --status         # check connection to both instances

ENV VARS (set in .env.v2 or export before running):
  NEO4J_LOCAL_HTTP   — local Neo4j HTTP (default: http://127.0.0.1:7474/db/neo4j/tx/commit)
  NEO4J_AURA_URI     — AuraDB Free Bolt URI  (neo4j+s://xxxxxxxx.databases.neo4j.io)
  NEO4J_AURA_USER    — AuraDB user            (default: neo4j)
  NEO4J_AURA_PASSWORD — AuraDB password

To get AuraDB Free credentials:
  1. Go to https://neo4j.com/cloud/aura-free/
  2. Create a free instance (no credit card required)
  3. Download the connection credentials
  4. Set env vars above in .env.v2 (gitignored)

SCHEDULE: Add to Windows Task Scheduler or cron to run nightly:
  python C:\\Users\\12sgi\\Documents\\Claude\\12sgi-king\\watchers\\aura_sync.py >> logs\\aura_sync.log 2>&1
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import argparse
from typing import Optional

# ── Config ─────────────────────────────────────────────────────────────────────
LOCAL_HTTP   = os.environ.get("NEO4J_LOCAL_HTTP",
                               os.environ.get("NEO4J_HTTP",
                                              "http://127.0.0.1:7474/db/neo4j/tx/commit"))
AURA_URI     = os.environ.get("NEO4J_AURA_URI", "")
AURA_USER    = os.environ.get("NEO4J_AURA_USER", "neo4j")
AURA_PASS    = os.environ.get("NEO4J_AURA_PASSWORD", "")

# Labels safe to sync to cloud (public record only)
PUBLIC_LABELS = [
    "Node",           # civic entities, funders, officials
    "TenantChainNode", # Hawaii civic chains
    "Doc",            # sourced civic documents (exclude embedding to save space)
    "Surface",        # civic UI surfaces
    "Side",           # civic operational domains
    "Button",         # surface buttons
    "BridgeJob",      # AI inference results (anonymized)
]

# Labels NEVER synced to cloud
PRIVATE_LABELS = [
    "StudioClipNode",    # production video clips — PRIVATE
    "StudioAssetNode",   # production characters/assets — PRIVATE
    "StudioLearning",    # AI training data — PRIVATE
    "StudioResourceNode", # production resources — PRIVATE
]

BATCH_SIZE = 500  # nodes per Cypher batch


def say(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ── Local Neo4j (HTTP, no-auth) ────────────────────────────────────────────────
def local_cypher(statements: list[dict], timeout: int = 30) -> Optional[dict]:
    """Run Cypher against local Neo4j via HTTP API."""
    body = json.dumps({"statements": statements}).encode()
    req  = urllib.request.Request(
        LOCAL_HTTP, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read().decode())
            if result.get("errors"):
                say(f"  local cypher error: {result['errors'][:2]}")
            return result
    except urllib.error.URLError as e:
        say(f"  local Neo4j unreachable: {e}")
        return None


def local_ready() -> bool:
    result = local_cypher([{"statement": "RETURN 1"}])
    return result is not None and not result.get("errors")


def _rows(result: Optional[dict], result_index: int = 0) -> list:
    if not result or result.get("errors"):
        return []
    try:
        return [row["row"] for row in result["results"][result_index]["data"]]
    except (IndexError, KeyError):
        return []


# ── AuraDB Free (Bolt via neo4j driver) ────────────────────────────────────────
def _get_aura_driver():
    """Get neo4j Python driver for AuraDB. Lazy import — not required for local-only use."""
    try:
        from neo4j import GraphDatabase
        return GraphDatabase
    except ImportError:
        say("  neo4j Python driver not installed — run: pip install neo4j")
        return None


def aura_ready() -> bool:
    if not AURA_URI or not AURA_PASS:
        return False
    GraphDatabase = _get_aura_driver()
    if not GraphDatabase:
        return False
    try:
        with GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASS)) as drv:
            drv.verify_connectivity()
        return True
    except Exception as e:
        say(f"  AuraDB not reachable: {str(e)[:120]}")
        return False


def aura_write(cypher: str, params: dict = None, timeout: int = 30) -> bool:
    """Execute a write Cypher statement on AuraDB Free."""
    GraphDatabase = _get_aura_driver()
    if not GraphDatabase:
        return False
    try:
        with GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASS)) as drv:
            with drv.session() as session:
                session.run(cypher, **(params or {}), timeout=timeout)
        return True
    except Exception as e:
        say(f"  AuraDB write error: {str(e)[:200]}")
        return False


def aura_read(cypher: str, params: dict = None) -> list:
    """Execute a read Cypher statement on AuraDB Free. Returns list of records."""
    GraphDatabase = _get_aura_driver()
    if not GraphDatabase:
        return []
    try:
        with GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASS)) as drv:
            with drv.session() as session:
                result = session.run(cypher, **(params or {}))
                return [dict(r) for r in result]
    except Exception as e:
        say(f"  AuraDB read error: {str(e)[:200]}")
        return []


# ── Sync logic ─────────────────────────────────────────────────────────────────
def fetch_local_nodes(label: str, skip_properties: list = None) -> list[dict]:
    """Fetch all nodes of a given label from local Neo4j."""
    skip = set(skip_properties or [])
    result = local_cypher([{
        "statement": f"MATCH (n:{label}) RETURN properties(n) as props",
    }], timeout=60)
    rows = _rows(result)
    nodes = []
    for row in rows:
        props = row[0] if row else {}
        # Remove any private/large properties we don't want in cloud
        for key in skip:
            props.pop(key, None)
        nodes.append(props)
    return nodes


def fetch_local_rels(rel_type: str) -> list[dict]:
    """Fetch all relationships of a given type with source/target IDs."""
    result = local_cypher([{
        "statement": (
            f"MATCH (a)-[r:{rel_type}]->(b) "
            "RETURN a.id as src_id, labels(a)[0] as src_label, "
            "       b.id as dst_id, labels(b)[0] as dst_label, "
            "       properties(r) as props"
        ),
    }], timeout=60)
    rows = _rows(result)
    rels = []
    for row in rows:
        if row and len(row) >= 5:
            rels.append({
                "src_id":    row[0],
                "src_label": row[1],
                "dst_id":    row[2],
                "dst_label": row[3],
                "props":     row[4] or {},
            })
    return rels


def sync_nodes(label: str, dry_run: bool = False, skip_properties: list = None) -> int:
    """MERGE all nodes of a label from local → AuraDB."""
    nodes = fetch_local_nodes(label, skip_properties=skip_properties)
    if not nodes:
        say(f"  {label}: 0 nodes found locally — skipping")
        return 0

    say(f"  {label}: syncing {len(nodes)} nodes → AuraDB...")

    if dry_run:
        say(f"  {label}: [DRY RUN] would MERGE {len(nodes)} nodes")
        return len(nodes)

    synced = 0
    for i in range(0, len(nodes), BATCH_SIZE):
        batch = nodes[i:i + BATCH_SIZE]
        cypher = (
            f"UNWIND $nodes AS props "
            f"MERGE (n:{label} {{id: props.id}}) "
            f"SET n = props"
        )
        # For nodes without 'id', use a different merge key
        sample = batch[0] if batch else {}
        if "id" not in sample and "key" in sample:
            cypher = (
                f"UNWIND $nodes AS props "
                f"MERGE (n:{label} {{key: props.key}}) "
                f"SET n = props"
            )
        elif "id" not in sample:
            # No unique key — just create (less idempotent but better than nothing)
            cypher = (
                f"UNWIND $nodes AS props "
                f"CREATE (n:{label}) "
                f"SET n = props"
            )

        ok = aura_write(cypher, {"nodes": batch})
        if ok:
            synced += len(batch)
        else:
            say(f"  {label}: batch {i//BATCH_SIZE + 1} failed")

    say(f"  {label}: ✓ {synced}/{len(nodes)} nodes synced")
    return synced


def sync_relationships(rel_type: str, dry_run: bool = False) -> int:
    """MERGE all relationships of a type from local → AuraDB."""
    rels = fetch_local_rels(rel_type)
    if not rels:
        say(f"  {rel_type}: 0 relationships found — skipping")
        return 0

    say(f"  {rel_type}: syncing {len(rels)} relationships → AuraDB...")

    if dry_run:
        say(f"  {rel_type}: [DRY RUN] would MERGE {len(rels)} relationships")
        return len(rels)

    synced = 0
    for i in range(0, len(rels), BATCH_SIZE):
        batch = rels[i:i + BATCH_SIZE]
        # Group by src/dst label for efficient MATCH
        src_label = batch[0]["src_label"] if batch else "Node"
        dst_label = batch[0]["dst_label"] if batch else "Node"
        cypher = (
            f"UNWIND $rels AS r "
            f"MATCH (a:{src_label} {{id: r.src_id}}) "
            f"MATCH (b:{dst_label} {{id: r.dst_id}}) "
            f"MERGE (a)-[rel:{rel_type}]->(b) "
            f"SET rel = r.props"
        )
        ok = aura_write(cypher, {"rels": batch}, timeout=60)
        if ok:
            synced += len(batch)

    say(f"  {rel_type}: ✓ {synced}/{len(rels)} relationships synced")
    return synced


def sync_surface_hierarchy(dry_run: bool = False) -> int:
    """Sync Surface→Button and Side→Surface relationships."""
    synced = 0

    # Side → Surface (HAS_SURFACE)
    result = local_cypher([{
        "statement": (
            "MATCH (s:Side)-[:HAS_SURFACE]->(surf:Surface) "
            "RETURN s.key as side_key, surf.key as surf_key, properties(surf) as surf_props"
        )
    }])
    rows = _rows(result)
    if rows and not dry_run:
        for row in rows:
            side_key, surf_key, surf_props = row[0], row[1], row[2]
            aura_write(
                "MERGE (s:Side {key: $side_key}) "
                "MERGE (surf:Surface {key: $surf_key}) SET surf = $surf_props "
                "MERGE (s)-[:HAS_SURFACE]->(surf)",
                {"side_key": side_key, "surf_key": surf_key, "surf_props": surf_props or {}}
            )
            synced += 1

    # Surface → Button (HAS_BUTTON)
    result = local_cypher([{
        "statement": (
            "MATCH (surf:Surface)-[:HAS_BUTTON]->(b:Button) "
            "RETURN surf.key as surf_key, properties(b) as btn_props, id(b) as btn_neo_id"
        )
    }])
    rows = _rows(result)
    if rows and not dry_run:
        for row in rows:
            surf_key, btn_props, btn_id = row[0], row[1], row[2]
            btn_key = btn_props.get("key") or str(btn_id)
            aura_write(
                "MERGE (surf:Surface {key: $surf_key}) "
                "MERGE (b:Button {key: $btn_key}) SET b = $btn_props "
                "MERGE (surf)-[:HAS_BUTTON]->(b)",
                {"surf_key": surf_key, "btn_key": btn_key, "btn_props": btn_props or {}}
            )
            synced += 1

    if dry_run:
        say(f"  Surfaces/Buttons: [DRY RUN] would sync hierarchy")
    else:
        say(f"  Surfaces/Buttons: ✓ {synced} relationships synced")
    return synced


def get_aura_counts() -> dict:
    """Get node/rel counts from AuraDB Free."""
    if not AURA_URI:
        return {}
    counts = {}
    for label in PUBLIC_LABELS:
        rows = aura_read(f"MATCH (n:{label}) RETURN count(n) as cnt")
        counts[label] = rows[0]["cnt"] if rows else 0
    rel_rows = aura_read("MATCH ()-[r]->() RETURN count(r) as cnt")
    counts["_total_rels"] = rel_rows[0]["cnt"] if rel_rows else 0
    return counts


def status() -> None:
    """Print connection status for both local and AuraDB."""
    print("\n=== AURA SYNC STATUS ===\n")

    print("LOCAL Neo4j:")
    print(f"  Endpoint: {LOCAL_HTTP}")
    if local_ready():
        result = local_cypher([
            {"statement": "MATCH (n) RETURN count(n) as cnt"},
            {"statement": "MATCH ()-[r]->() RETURN count(r) as cnt"},
        ])
        nc = _rows(result, 0)[0][0] if _rows(result, 0) else "?"
        rc = _rows(result, 1)[0][0] if _rows(result, 1) else "?"
        print(f"  Status:   ✓ online — {nc} nodes, {rc} relationships")
        # Label breakdown
        for label in PUBLIC_LABELS + PRIVATE_LABELS:
            r = local_cypher([{"statement": f"MATCH (n:{label}) RETURN count(n)"}])
            cnt = _rows(r)[0][0] if _rows(r) else 0
            tag = "PUBLIC" if label in PUBLIC_LABELS else "PRIVATE (never synced)"
            print(f"    {label:25} {cnt:6d}  [{tag}]")
    else:
        print("  Status:   ✗ offline (start with: docker start lotus-neo4j)")

    print("\nAURADB FREE:")
    if not AURA_URI:
        print("  Status:   ✗ not configured")
        print("  Setup:    1. Go to https://neo4j.com/cloud/aura-free/")
        print("            2. Create free instance (no credit card)")
        print("            3. Set NEO4J_AURA_URI, NEO4J_AURA_USER, NEO4J_AURA_PASSWORD in .env.v2")
    elif not AURA_PASS:
        print(f"  URI:      {AURA_URI}")
        print("  Status:   ✗ NEO4J_AURA_PASSWORD not set")
    else:
        print(f"  URI:      {AURA_URI}")
        print(f"  User:     {AURA_USER}")
        if aura_ready():
            counts = get_aura_counts()
            total_nodes = sum(v for k, v in counts.items() if not k.startswith("_"))
            print(f"  Status:   ✓ online — {total_nodes} nodes, {counts.get('_total_rels', 0)} relationships")
            for label, cnt in counts.items():
                if not label.startswith("_"):
                    print(f"    {label:25} {cnt:6d}")
        else:
            print("  Status:   ✗ offline or wrong credentials")

    print("\nFREE TIER LIMITS (AuraDB Free):")
    print("  Nodes:         200,000  (your data: ~6,544 — 3.3% of limit)")
    print("  Relationships: 400,000  (your data: ~18,331 — 4.6% of limit)")
    print("  Storage:       512MB")
    print("  Cost:          $0 forever\n")


def full_sync(dry_run: bool = False, label_filter: str = None) -> dict:
    """Run a full sync from local Neo4j to AuraDB Free."""
    if not AURA_URI:
        say("AuraDB not configured — set NEO4J_AURA_URI, NEO4J_AURA_USER, NEO4J_AURA_PASSWORD")
        return {"error": "not_configured"}

    say(f"{'[DRY RUN] ' if dry_run else ''}Starting AuraDB sync — local → cloud...")

    if not local_ready():
        say("LOCAL Neo4j not reachable — cannot sync")
        return {"error": "local_offline"}

    if not dry_run and not aura_ready():
        say("AuraDB not reachable — cannot sync")
        return {"error": "aura_offline"}

    results = {}
    start   = time.time()

    # Sync nodes
    labels_to_sync = [label_filter] if label_filter else PUBLIC_LABELS
    for label in labels_to_sync:
        if label not in PUBLIC_LABELS:
            say(f"  {label}: SKIPPED — not in PUBLIC_LABELS (private data protection)")
            continue

        # Skip embedding vectors (too large for AuraDB Free 512MB limit)
        skip_props = ["embedding"] if label == "Doc" else None
        count = sync_nodes(label, dry_run=dry_run, skip_properties=skip_props)
        results[label] = count

    # Sync relationships (public only)
    if not label_filter:
        public_rels = ["FLOW", "TENANT_FLOW", "HAS_SURFACE", "HAS_BUTTON"]
        for rel_type in public_rels:
            count = sync_relationships(rel_type, dry_run=dry_run)
            results[f"rel:{rel_type}"] = count

        # Surface hierarchy (Side → Surface → Button)
        count = sync_surface_hierarchy(dry_run=dry_run)
        results["surface_hierarchy"] = count

    elapsed = round(time.time() - start, 1)
    total_nodes = sum(v for k, v in results.items() if not k.startswith("rel:") and k != "surface_hierarchy")
    total_rels  = sum(v for k, v in results.items() if k.startswith("rel:") or k == "surface_hierarchy")

    say(f"{'[DRY RUN] ' if dry_run else ''}Sync complete in {elapsed}s — {total_nodes} nodes, {total_rels} relationships")
    return {
        "synced_nodes": total_nodes,
        "synced_rels":  total_rels,
        "elapsed_s":    elapsed,
        "dry_run":      dry_run,
        "details":      results,
    }


# ── AuraDB read fallback (for king-bridge) ─────────────────────────────────────
def read_from_aura(cypher_stmt: str, params: dict = None) -> Optional[list]:
    """
    Fallback read from AuraDB when local Neo4j is offline.
    Called by king-bridge and chain_to_graph when LOCAL_HTTP is unreachable.
    Returns list of rows or None if AuraDB is also unavailable.
    """
    if not AURA_URI or not AURA_PASS:
        return None
    return aura_read(cypher_stmt, params)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run",  action="store_true", help="Print what would sync without writing")
    ap.add_argument("--status",   action="store_true", help="Check connection to both instances")
    ap.add_argument("--label",    default=None,        help="Sync a single label only (e.g. Doc)")
    a  = ap.parse_args()

    if a.status:
        status()
        return

    result = full_sync(dry_run=a.dry_run, label_filter=a.label)
    if result.get("error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
