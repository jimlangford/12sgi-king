# -*- coding: utf-8 -*-
"""graph_refresh.py — keep the LOCAL civic graph+vector store current, on the Hina cadence. FREE.

Runs on the sunset (hina/pō) edge — civic/record work rides Hina, not a wall clock (Jimmy 2026-07-08).
Reloads the Maui money-chain into Neo4j (chain_to_graph), refreshes the vector index from the host
Ollama embeddings (graph_vectors), then refreshes the additive PRIVATE skill/workboard spine
(private_spine) and the dedicated pulse geometry lattice (pulse_geometry). Zero Claude tokens.
Resilient: if Neo4j or Ollama is down it logs and skips — never crashes the maintenance tick.
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
            spine_note = "private spine skipped"
            try:
                import private_spine as P
                if P.refresh():
                    spine_note = "private spine current"
            except Exception as spine_exc:
                _say("graph_refresh spine skip: %s" % str(spine_exc)[:160])
            pulse_note = "pulse geometry skipped"
            try:
                import pulse_geometry as PG
                if PG.refresh():
                    pulse_note = "pulse geometry current"
            except Exception as pulse_exc:
                _say("graph_refresh pulse skip: %s" % str(pulse_exc)[:160])
            _say(f"graph_refresh: graph + vectors current ({spine_note}; {pulse_note}, Hina).")
        else:
            _say("graph_refresh: Neo4j unreachable — skipped (no crash).")
    except Exception as e:
        _say("graph_refresh error: %s" % str(e)[:160])


if __name__ == "__main__":
    main()
