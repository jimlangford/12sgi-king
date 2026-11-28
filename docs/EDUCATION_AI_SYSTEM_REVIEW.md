# Education and Local AI System Review

**Reviewed:** 2026-11-27 HST  
**Boundary:** PRIVATE runtime review with PUBLIC-safe findings  
**Release effect:** none; no publishing, graph writes, film approvals, or student accounts

## Outcome

The education manifest is merged, available in the local runtime source, and passes its focused tests. The local coordination spine is operating: Docker services are healthy, Ollama can complete local inference, the authenticated read-only Claude bridge is reachable from AI Gateway, and Codex, Claude, GitHub Copilot, and GitHub Desktop are running on the owner machine.

The system is **operational with one degraded component**. A small local model completed inference, but the larger `king-civic` education persona did not finish loading within three minutes while other GPU workloads were active. Model presence and daemon liveness must not be reported as successful persona inference.

## Verified education state

- PR #405 merged to `main` as `83ee357a` after all GitHub checks passed.
- The live Actions-runner checkout was fast-forwarded from `5ed4713a` to `4142a4fd`, bringing in `watchers/education_pathways.py` and its tests.
- `python -m unittest tests.test_education_pathways -v` passed 2 tests.
- `python -m watchers.education_pathways --grade g68` returned the expected offline curriculum record.
- All six grade bands remain present.
- Film assets remain empty and `awaiting_approved_asset`.
- Publishing remains `not_staged` and scoped to `education`.
- SAGE is classified as `simulation_not_evidence`; no curriculum node assignments were invented.

## Local AI coordination spine

| Participant | Local coordination path | Verified state |
|---|---|---|
| Local AI / Ollama | Ollama on `127.0.0.1:11434` | Daemon ready; `qwen3:1.7b` returned `READY`; `king-civic` load timed out after 180 seconds |
| AI Gateway | Private Docker service on loopback | Healthy; canonical registry present; Claude review/status tools present |
| Claude Code | Authenticated host bridge on loopback | Ready in read-only mode; reachable from the AI Gateway container |
| Codex | Repository, handoff, and change-feed workflow | Desktop/runtime process active; this review records shared evidence |
| GitHub Copilot | GitHub branch/PR plus repository handoff and feed | Desktop/runtime processes active |
| GitHub | Reviewed branches, PR checks, and issue #403 | PR #405 merged; issue #403 remains the coordination contract |

The common system of record is the repository plus `docs/ACTIVE_AGENT_HANDOFF.md` and `docs/AI_CHANGE_FEED.jsonl`. These files coordinate agent work, but they are not a live multi-provider chat bus. Claude execution remains Owner-authenticated, read-only, and explicitly invoked through AI Gateway. Copilot collaboration remains repository/PR based.

## Runtime evidence

- Docker Engine responded with version 29.9.2.
- Auth, tenant, documents, AI, GPU Router, games, Studio Assets, AI Gateway, King Bridge, and database checks were healthy in the aggregate health service.
- Neo4j ports 7474 and 7687 were bound to `127.0.0.1`.
- The authenticated Claude bridge returned `ready` from the host and from inside the AI Gateway container.
- Ollama 0.40.18 exposed its version endpoint and local model catalog.
- The prior startup log still contains an older Compose recovery failure. Current health proves the stack is running, not that the startup procedure has passed a fresh reboot test.

## Boundaries preserved

- No live Neo4j curriculum writes.
- No film-to-grade or SAGE-node-to-grade approvals.
- No student data, education account connection, social publishing, or public deployment.
- No direct Claude job was submitted during this review; Owner authentication was not bypassed.
- The Claude bridge remains loopback-only and read-only.

## Required next gates

1. Diagnose the slow `king-civic` model load without interrupting active render jobs; rerun a bounded persona inference after GPU capacity is available.
2. Add a repeatable post-reboot check for Docker startup, aggregate health, Ollama inference, and the authenticated bridge path.
3. Create an explicit educator-reviewed SAGE assignment manifest before adding grade-to-node mappings.
4. Create a separate education film-approval manifest; public release status alone is not curriculum approval.
5. Keep provider-specific execution behind Owner claims and use the shared feed for safe cross-agent state.
