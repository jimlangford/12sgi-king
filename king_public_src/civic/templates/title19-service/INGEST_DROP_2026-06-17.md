# Title 19 Service — Ingestion Drop (AG-first pass)

**Date:** 2026-06-17 · **Author:** Cowork session (for James) · **Guardrails honored:** sourced/cited only; no fabrication; analysis vs. law labeled; no private data; env-ref secrets only (no keys in these files).

## What's in this drop
```
corpus/raw/title19_ch19.30A_agricultural_RAW.md     # AG chapter snapshot (law, cited)
corpus/structured/ag_table_of_uses.json             # AG Table of Uses: permitted / accessory / special-use / prohibited (cited)
corpus/structured/enforcement_civil_fines.md        # Title 19 enforcement, civil fines, penalties (law, verbatim cites)
corpus/ai_assistant/permit_assistant_corpus_ag.md   # Permit-assistant corpus seed (cited, with answer rules)
analysis/rules_to_code_candidates.md                # LABELED ANALYSIS: provisions that should be codified into Title 19
crosswalk/title19_crosswalk.json                    # Ingestion status + rules-vs-code map, designed to stay current
```

## Sourced vs. expanding
- **Sourced (law, ingested & cited):** AG district ch. 19.30A (through 2025 ords); Enforcement ch. 19.530 (criminal + administrative civil fines).
- **Expanding:** full verbatim text of the AG administrative rules (MC-12) and the Civil-Fines administrative rules (PDFs are not text-extractable via current tools — see "Open items"); all non-AG Title 19 districts; definitions/parking/conditional-permit chapters.

## Integration intent (NOT yet executed — needs repo access)
Target canonical path (per task): `12sgi-king/king_public_src/civic/templates/title19-service/`
- Map the files above into the service template's `corpus/`, `analysis/`, and `crosswalk/` dirs.
- Log this drop to the dispatch bus so King-server (local_358ac155) wires nav + publishes via the leak-gated jobrunner; orphan-check should then confirm reachability.

**Blocker:** This session has **no path to the `12sgi-king` repo** (the guessed paths did not resolve) and **no dispatch-bus tool** is available here. Nothing was written into the repo and no live publish occurred. To proceed, provide the repo's absolute path on this machine (so it can be mounted), or confirm how the dispatch bus should be written to.

## Open items / next passes
1. Get repo path → copy this drop into `title19-service/` and append a dispatch-log entry.
2. Ingest AG admin rules (MC-12) + Civil-Fines rules verbatim (need a text-extractable source; the DocumentCenter PDFs did not yield text via web fetch or browser extraction).
3. Expand Table of Uses to all districts (P2).
4. Refresh policy: re-pull each Municode node, compare ordinance trailers, mark stale, re-ingest.
