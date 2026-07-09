# -*- coding: utf-8 -*-
"""graph_refresh.py — keep the LOCAL civic graph+vector store current, on the Hina cadence. FREE.

Runs on the sunset (hina/pō) edge — civic/record work rides Hina, not a wall clock (Jimmy 2026-07-08).
Reloads the Maui money-chain into Neo4j (chain_to_graph) then refreshes the vector index from the host
Ollama embeddings (graph_vectors). Zero Claude tokens. Resilient: if the Neo4j container or Ollama is
down it logs and skips — never crashes the maintenance tick.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def _say(m):
    try:
        if sys.stdout:
            print(m, flush=True)
    except Exception:
        pass


def main():
    try:
        import chain_to_graph as G
        if G.load():                       # graph reloaded (returns False + logs if Neo4j is down)
            import graph_vectors as V
            V.build()                      # vector index refreshed from host Ollama
            _say("graph_refresh: graph + vectors current (Hina).")
        else:
            _say("graph_refresh: Neo4j unreachable — skipped (no crash).")
    except Exception as e:
        _say("graph_refresh error: %s" % str(e)[:160])


if __name__ == "__main__":
    main()
