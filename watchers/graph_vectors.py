# -*- coding: utf-8 -*-
"""graph_vectors.py — semantic (vector) search over the Maui civic records, LOCAL + FREE.

The second layer borrowed from docker/genai-stack (a VECTOR store) — on our terms:
  - embeddings: Jimmy's OWN host Ollama (nomic-embed-text, CPU) — NO cloud, NO API key, zero Claude tokens.
  - store: the SAME local Neo4j (graph + vector in one place). Neo4j 5 native vector index, cosine, 768-dim.
  - NO LangChain, NO pip driver — stdlib urllib to both Ollama (:11434) and Neo4j HTTP (:7474).

Embeds the sourced civic records (chain flows + 990 nonprofits + the donor-bloc network) so you can ask
  in plain language — "Lahaina homeless housing grants", "engineering firms with county contracts",
  "who funds multiple Council members at once" — and get the right sourced records back, then hop into
  the graph from there.

  python tools/kilo-aupuni/graph_vectors.py --build            # embed + index (idempotent)
  python tools/kilo-aupuni/graph_vectors.py --query "..."      # semantic search
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


NEO = os.environ.get("NEO4J_HTTP") or "http://127.0.0.1:7474/db/neo4j/tx/commit"
# OLLAMA_HOST is often set bare on this machine (e.g. "127.0.0.1") — normalize to a full URL with port.
_oh = os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
if "://" not in _oh:
    _oh = "http://" + _oh
if _oh.count(":") < 2:            # scheme present but no explicit port
    _oh = _oh.rstrip("/") + ":11434"
OLLAMA = _oh
MODEL = "nomic-embed-text"
DIM = 768
INDEX = "civic_docs"
CAP = int(os.environ.get("VEC_CAP", "1500"))  # bound the first pass; no silent truncation (logged)


def say(m):
    try:
        if sys.stdout:
            print(m, flush=True)
    except Exception:
        pass


def _post(url, payload, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def cypher(statements, timeout=120):
    try:
        out = _post(NEO, {"statements": statements}, timeout)
    except urllib.error.URLError as e:
        say("Neo4j unreachable (%s) — is lotus-neo4j up?" % str(e)[:100]); return None
    if out.get("errors"):
        say("Cypher errors: %s" % json.dumps(out["errors"])[:300])
    return out


def embed(text):
    """One vector from the host Ollama. Handles both /api/embeddings (prompt) and /api/embed (input)."""
    for url, key, vkey in ((OLLAMA + "/api/embeddings", "prompt", "embedding"),
                           (OLLAMA + "/api/embed", "input", "embeddings")):
        try:
            d = _post(url, {"model": MODEL, key: text}, timeout=60)
            v = d.get(vkey)
            if vkey == "embeddings" and isinstance(v, list) and v and isinstance(v[0], list):
                v = v[0]
            if isinstance(v, list) and v:
                return v
        except Exception:
            continue
    return None


def gather_docs():
    """Sourced civic records to embed: chain flows + 990 nonprofits + the donor-bloc network. Each carries
    its provenance."""
    docs = []
    mauios = _resolve_mauios_dir()
    # chain flows (money_chain_maui.json)
    try:
        with open(mauios / "money_chain_maui.json", encoding="utf-8") as f:
            d = json.load(f)
        name = {n["id"]: n.get("label", n["id"]) for n in d.get("nodes", [])}
        for i, e in enumerate(d.get("edges", [])):
            amt = e.get("amount")
            amt_s = ("${:,.0f}".format(amt)) if isinstance(amt, (int, float)) else "n/a"
            txt = "%s %s: %s -> %s. %s" % (
                str(e.get("kind", "")).replace("_", " "), amt_s,
                name.get(e.get("src"), e.get("src")), name.get(e.get("dst"), e.get("dst")),
                e.get("verify", ""))
            docs.append({"id": "flow:%d" % i, "text": txt.strip(), "kind": e.get("kind", "flow"),
                         "source_url": e.get("source_url", ""), "source_type": e.get("source_type", "sourced")})
    except Exception as ex:
        say("chain docs skipped: %s" % str(ex)[:100])
    # 990 nonprofits (nonprofits_maui.json)
    try:
        with open(mauios / "nonprofits_maui.json", encoding="utf-8") as f:
            nd = json.load(f)
        rows = nd if isinstance(nd, list) else nd.get("organizations", nd.get("records", nd.get("nonprofits", [])))
        for r in rows:
            if not isinstance(r, dict):
                continue
            fin = r.get("financials", r)
            rev = fin.get("revenue") or fin.get("totrevenue")
            exp = fin.get("expenses") or fin.get("totfuncexpns")
            txt = "Nonprofit %s (%s), %s. EIN %s. Revenue %s expenses %s." % (
                r.get("name", ""), r.get("city", ""), r.get("category", r.get("ntee", "")),
                r.get("ein", ""), rev, exp)
            docs.append({"id": "np:%s" % r.get("ein", r.get("name", "")), "text": txt.strip(),
                         "kind": "nonprofit_990", "source_url": r.get("source_url", r.get("source", "")),
                         "source_type": r.get("source_type", "sourced")})
    except Exception as ex:
        say("nonprofit docs skipped: %s" % str(ex)[:100])
    # donor-bloc network (collusion_graph.py's write_bloc_json output, added 2026-07-10: "use the
    # graphing system to relearn our skills on the local AI" — the bloc was computed + loaded into Neo4j
    # and rendered to donor_bloc.html all along, but had no structured file for THIS embedding layer to
    # read, so the local semantic search never learned it. donor_bloc.json closes that gap.)
    try:
        with open(mauios / "donor_bloc.json", encoding="utf-8") as f:
            bd = json.load(f)
        for i, b in enumerate(bd.get("bloc", [])):
            reps_s = ", ".join(sorted((b.get("reps") or {}).keys()))
            total = b.get("total") or 0
            txt = "Donor bloc: %s (%s) funds %d Council member(s) at once (%s), total $%s.%s" % (
                b.get("donor", ""), str(b.get("kind", "")).replace("_", " "), b.get("n_reps", 0), reps_s,
                "{:,.0f}".format(total),
                (" Vendor tie: %s ($%s in county awards)." % (b.get("vendor"), "{:,.0f}".format(b.get("award_total") or 0)))
                if b.get("vendor") else "")
            docs.append({"id": "bloc:%d" % i, "text": txt.strip(), "kind": "donor_bloc",
                         "source_url": "", "source_type": "sourced"})
    except Exception as ex:
        say("donor-bloc docs skipped: %s" % str(ex)[:100])
    return docs


def build():
    docs = gather_docs()
    total = len(docs)
    if total > CAP:
        say("NOTE: %d docs found, embedding first %d (VEC_CAP); rest deferred (not silently dropped)." % (total, CAP))
        docs = docs[:CAP]
    say("embedding %d civic records via host Ollama (%s, CPU)..." % (len(docs), MODEL))
    rows, done = [], 0
    for dcmt in docs:
        v = embed(dcmt["text"])
        if not v:
            continue
        d2 = dict(dcmt); d2["embedding"] = v
        rows.append(d2); done += 1
        if done % 100 == 0:
            say("  embedded %d/%d" % (done, len(docs)))
    if not rows:
        say("no embeddings produced — is nomic-embed-text pulled and Ollama up?"); return False
    say("embedded %d/%d; writing to Neo4j + building vector index..." % (done, len(docs)))
    cypher([{"statement":
             "CREATE VECTOR INDEX %s IF NOT EXISTS FOR (d:Doc) ON (d.embedding) "
             "OPTIONS {indexConfig: {`vector.dimensions`: %d, `vector.similarity_function`: 'cosine'}}"
             % (INDEX, DIM)}])
    for i in range(0, len(rows), 200):
        batch = rows[i:i + 200]
        cypher([{"statement":
                 "UNWIND $rows AS r MERGE (d:Doc {id:r.id}) "
                 "SET d.text=r.text, d.kind=r.kind, d.source_url=r.source_url, d.source_type=r.source_type "
                 "WITH d, r CALL db.create.setNodeVectorProperty(d, 'embedding', r.embedding) RETURN count(*)",
                 "parameters": {"rows": batch}}])
    say("VECTOR LAYER LIVE: %d civic records embedded + indexed in Neo4j. Query with --query \"...\"" % done)
    return True


def query(q, k=6):
    qv = embed(q)
    if not qv:
        say("could not embed the query (Ollama/model?)"); return
    out = cypher([{"statement":
                   "CALL db.index.vector.queryNodes($idx, $k, $qv) YIELD node, score "
                   "RETURN node.text, node.kind, node.source_url, node.source_type, score",
                   "parameters": {"idx": INDEX, "k": k, "qv": qv}}])
    if not out or out.get("errors"):
        return
    say("\n— semantic matches for: %s —" % q)
    for row in out["results"][0].get("data", []):
        t, kind, src, st, score = row["row"]
        say("  [%.3f] (%s · %s) %s" % (score, kind, st, str(t)[:120]))
        if src:
            say("          source: %s" % src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--query", default="")
    a = ap.parse_args()
    if a.build:
        build()
    if a.query:
        query(a.query)
    if not a.build and not a.query:
        build()


if __name__ == "__main__":
    main()
