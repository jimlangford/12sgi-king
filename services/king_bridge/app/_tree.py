"""
king-bridge Neo4j tree endpoint — appended to main.py as a module-level addition.
Provides /api/v2/bridge/tree — the full tenant→asset hierarchy for the landing page.
"""

# ── Tree query helpers (added to king_bridge) ─────────────────────────────────

def _neo_tree() -> dict:
    """
    Pull the full tenant→asset→sub-asset hierarchy from Neo4j in one pass.
    Returns a structured tree suitable for the landing page.
    Covers:
      - Studio tenants → assignments → characters/styles/assets/clips
      - Civic tenants  → report classes (from tenant_registry)
      - Money chain    → funders → primes → subs → officials (FLOW graph)
      - Surfaces       → civic/studio/social surfaces
      - Learning       → learning games + challenges
    """
    import os, json as _json
    from pathlib import Path as _Path

    # Studio tenants with their asset counts
    studio_q = (
        "MATCH (t:StudioAssetNode) WHERE t.type = 'tenant' "
        "OPTIONAL MATCH (t)-[r:STUDIO_REL]->(c:StudioAssetNode) "
        "RETURN t.entity_id AS id, t.name AS name, t.kind AS kind, "
        "t.status AS status, t.render_register AS render, "
        "t.film_key AS film_key, "
        "collect(DISTINCT {rel: r.kind, child_type: c.type}) AS children"
    )

    # Civic tenant chain per tenant
    civic_chain_q = (
        "MATCH (t:TenantChainNode) "
        "RETURN t.tenant AS tenant_id, t.type AS node_type, "
        "t.name AS name, t.id AS node_id "
        "ORDER BY t.tenant, t.type"
    )

    # Money FLOW: top funders + their prime counts
    flow_q = (
        "MATCH (f:Node)-[r:FLOW]->(e:Node) "
        "WHERE r.kind IN ['federal_prime', 'county_award', 'federal_award'] "
        "RETURN f.name AS funder, f.type AS funder_type, "
        "r.kind AS flow_kind, count(e) AS prime_count "
        "ORDER BY prime_count DESC LIMIT 20"
    )

    # Cross-link entities (appear in multiple chains)
    cross_q = (
        "MATCH (n:Node {crosslink: true}) "
        "RETURN n.name AS name, n.type AS type, n.id AS id LIMIT 30"
    )

    # Clips stats by semantic state
    clips_q = (
        "MATCH (c:StudioClipNode) "
        "RETURN c.semantic_state AS state, count(c) AS cnt ORDER BY cnt DESC"
    )

    # Characters (across all tenants)
    chars_q = (
        "MATCH (c:StudioAssetNode) WHERE c.type = 'character' "
        "RETURN c.id AS id, c.name AS name LIMIT 50"
    )

    # Surfaces
    surfaces_q = (
        "MATCH (s:Surface) RETURN s.side AS side, s.key AS key, "
        "s.title AS title, s.purpose AS purpose, s.ord AS ord "
        "ORDER BY s.side, s.ord"
    )

    # Learning
    learning_q = (
        "MATCH (l:StudioLearning) WHERE l.kind = 'learning_game' "
        "OPTIONAL MATCH (l)-[:LEARNING_EDGE]->(c:StudioLearning) "
        "RETURN l.id AS game_id, l.name AS game_name, "
        "count(c) AS challenge_count"
    )

    results = {}
    for key, q in [
        ("studio", studio_q),
        ("civic_chain", civic_chain_q),
        ("flow", flow_q),
        ("crosslinks", cross_q),
        ("clips", clips_q),
        ("characters", chars_q),
        ("surfaces", surfaces_q),
        ("learning", learning_q),
    ]:
        r = _neo_cypher([{"statement": q}])
        if r and not r.get("errors"):
            rows = []
            for row in r["results"][0]["data"]:
                cols = r["results"][0]["columns"]
                rows.append(dict(zip(cols, row["row"])))
            results[key] = rows
        else:
            results[key] = []

    # Load tenant_registry for civic report classes (static, always accurate)
    try:
        reg_path = _Path(__file__).resolve().parents[3] / "tenant_registry.json"
        with open(reg_path, encoding="utf-8") as f:
            reg = _json.load(f)
        results["civic_tenants"] = reg.get("civic_tenants", [])
        results["report_classes"] = reg.get("report_classes", [])
        results["creative_tenants_meta"] = reg.get("creative_tenants", [])
    except Exception:
        results["civic_tenants"] = []
        results["report_classes"] = []
        results["creative_tenants_meta"] = []

    # Summary counts
    results["summary"] = {
        "studio_tenants": len(results["studio"]),
        "civic_tenants":  len(results["civic_tenants"]),
        "characters":     len(results["characters"]),
        "clips":          sum(r.get("cnt", 0) for r in results["clips"]),
        "crosslinks":     len(results["crosslinks"]),
        "surfaces":       len(results["surfaces"]),
    }

    return results
