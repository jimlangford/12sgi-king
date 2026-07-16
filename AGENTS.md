# Agent Operating Guide

This repository is not only a public website. It is a layered operating system with public civic pages, private owner controls, mirrors, deployment bridges, and local automation. Work here with care, humility, and aloha.

Before changing files, read `CANON.md` as the compact standing memory for JRCSL / 12SGI / Elemental Lotus work. Apply it quietly; do not spend response space restating it unless a boundary or handoff depends on it.

## Core Principle

Preserve intention before changing mechanism.

Do not treat unusual infrastructure as broken just because it does not match a generic web deployment pattern. Cloudflare, GitHub Pages, Tailscale, local `Documents/Claude/...` paths, `king-local`, private reports, public sanitizers, and mirror scripts may all be intentional parts of the system.

## Site Layout — Navigation Rules (CRITICAL)

The repo is served as a **subdirectory** of the public hostname. Every AI that writes or
reviews HTML/JS links **must** follow these path rules or links will 404 in production.

### File-serving map

| Disk location | Served at | Notes |
|---|---|---|
| `site/*.html` | public web root (e.g. `https://12sgi.com/reports.html`) | built output; DO NOT link to bare filenames from repo-root pages |
| `king_public_src/*.html` | `/king/` (private Tailscale + GitHub Pages) | relative links inside `king_public_src/` stay relative; links to `site/` pages use `../site/foo.html` |
| `element_lotus_public/*.html` | ElementLotus public site root | links to `site/` pages use `../site/foo.html`; `games/` and `sage/` live at `../site/games/` and `../site/sage/` |
| `go/*.html` | `/go/` (private Tailscale) | self-contained; internal links stay relative |
| `site/king/` | `/king/` on GitHub Pages | built copy of `king_public_src/`; do not edit directly |
| `site/go/` | `/go/` on GitHub Pages | built copy of `go/`; do not edit directly |

### Linking rules by source file location

**Root-level HTML files** (`404.html`, `education.html`, `grants.html`, `take_action.html`,
`testify.html`, etc.) — civic pages live in `site/`. Links must use the `site/` prefix:
```html
<!-- CORRECT -->
<a href="site/reports.html">Dashboard</a>
<a href="site/jurisdictions.html">Jurisdictions</a>

<!-- WRONG — file does not exist at repo root -->
<a href="reports.html">Dashboard</a>
```

**`govos-shell.js`** — injected nav and PAGE_INDEX hrefs follow the same rule. Civic pages
get the `site/` prefix; root-level action pages (`take_action.html`, `education.html`) do not:
```js
// CORRECT
'<a href="site/reports.html">...'
href: 'site/jurisdictions.html'

// WRONG
href: 'reports.html'
```

**`king_public_src/*.html`** — to reach civic pages in `site/`, go up one level then into `site/`:
```html
<!-- CORRECT -->
<a href="../site/reports.html">Dashboard</a>
<a href="../site/tenants_hub.html">Tenants Hub</a>
<!-- Links within king_public_src stay relative -->
<a href="commentary_seat.html">Commentary Seat</a>
<!-- NOT ../king/commentary_seat.html -->
```

**`element_lotus_public/*.html`** — same pattern; `games/` and `sage/` do NOT exist in
`element_lotus_public/`; they live in `site/`:
```html
<!-- CORRECT -->
<a href="../site/games/">Games</a>
<a href="../site/sage/">Sage</a>
<a href="../site/reports.html">Dashboard</a>

<!-- WRONG -->
<a href="games/">Games</a>
<a href="reports.html">Dashboard</a>
```

**`go/*.html`** — self-contained private pages; use relative paths within `go/`;
do not link to `site/` pages from here (they are private owner surfaces).

### Key civic pages location reference

All of the following exist under `site/`, NOT at repo root:
`reports.html`, `jurisdictions.html`, `datasets.html`, `agendas.html`, `testify.html`,
`news_record.html`, `civic_daily.html`, `meetings_calendar.html`, `studio.html`,
`money_behind_officials.html`, `ka_leo_voice.html`, `parity_check.html`,
`accountability_record.html`, `wildfire_recovery_watch.html`, `tenants_hub.html`,
`agenda_explainer.html`, `sage_bridge.html`, `olelo_glossary.html`, `request_records.html`,
`n53_engine.html`, `testimony_record.html`, `county_dashboard.html`.

`take_action.html`, `grants.html`, `education.html`, `king_landing.html`, `go.html`
exist at **repo root** (not in `site/`).

### Build pipeline note

`build_site.py` copies source files into `site/` at build time. The checked-in files under
`king_public_src/`, `go/`, and `element_lotus_public/` are the source of truth. Never edit
`site/` files directly — they are overwritten on every build.

### `.claude/launch.json` preview note

The Claude preview server (`king-preview`) serves `king_public_src/` on port 4321. When
testing locally via this preview, paths inside `king_public_src/` resolve correctly
but `../site/` paths will 404 unless you also run a server at the parent level. Use
`python -m http.server 8888 --directory ./` from repo root for full path testing.

---

## Boundary Labels

Use these labels in reports and handoffs:

- `PUBLIC`: safe published website output.
- `PRIVATE`: owner-only control plane, local mirror, Tailscale, private data room, or non-public report.
- `BRIDGE`: connection layer between local tools, GitHub Actions, Cloudflare, GitHub Pages, Tailscale, or mirrors.
- `DO NOT TOUCH`: intentional infrastructure unless the owner explicitly asks for changes.
- `VERIFY`: commands run and results observed.

## Do No Harm Rules

- Do not remove or "simplify" private connection paths, Cloudflare notes, Tailscale hosts, local mirror logic, owner-only reports, or deployment bridges without explicit instruction.
- Do not publish private files or owner-only pages into the public `site/` output.
- Do not rewrite setup docs just because the visible workflow appears to use a different deployment path.
- Do not flatten the system into a standard static-site template.
- Keep changes narrow, reversible, and aligned with existing comments and scripts.
- **Do not add bare filenames as href targets** (e.g. `href="reports.html"`) in root-level or `element_lotus_public/` HTML. Civic pages live in `site/`. See Navigation Rules above.

## Lane Discipline & Cross-System Diplomacy

This repo coordinates across more than one AI system, so any agent (Claude Code, Codex, GitHub
Copilot, or a future agent) should work by these house rules rather than assuming another
system's job:

- **Workboard lanes** (`services/v2_workboard.py`) are the shared contract between agents:
  - `engineering` — internal plumbing. Self-heals; no human gate required.
  - `creative` — content a human must review before it leaves the system (this is where
    **Element LOTUS** lives per `docs/SERVICE_REGISTRY.md` — "creative/AI experiences for
    content generation and publishing"). Never auto-heal a creative job; it waits for
    `approve_workboard_job()` / `reject_workboard_job()` (CLI: `--approve` / `--reject`).
  - `output` — approved and staged for public/social publish. Same rule: owner approval only.
- **Neo4j ("Neo")** (`watchers/chain_to_graph.py`, `graph_vectors.py`) is a LOCAL, zero-cloud-token
  graph + vector store on the owner's machine. Do not reroute its job through a cloud AI call, and
  do not assume a cloud agent can reach it directly — it only answers to `NEO4J_HTTP` on
  `127.0.0.1`. If a task looks like it needs graph provenance (e.g. linking a published post back
  to a sourced civic record), that is a deliberate, owner-approved wiring decision, not something
  to bolt on unasked.
- **Diplomatic asks, not assumptions:** when a task touches a lane, system, or owner-only surface
  you don't have full visibility into (Neo4j, Element LOTUS, king-server routes outside this repo,
  the owner's local automation), don't silently guess at the integration. Either ask the owner
  directly, or append a plain, factual entry to `DISPATCH_LOG.md` naming the open question so the
  next agent or the owner can resolve it. This keeps the system pono (in balance) instead of one
  agent overriding another's lane.

## Reporting Format

When reporting work, use language another agent can continue from:

1. `INSPECTED`: files, workflows, tools, or GitHub surfaces checked.
2. `CHANGED`: exact files and purpose.
3. `PRESERVED`: private/public boundaries intentionally left intact.
4. `VERIFY`: commands run and whether they passed.
5. `NEXT`: safest next action, if any.

## Local Validation

Known lightweight checks:

```powershell
python -m compileall -q .
python tools\reconcile.py --gate seed_reports html --route-only
$env:KA_SITE='C:\tmp\12sgi-king-site-check'; python build_site.py
```

The default `site/` tree can be touched by local tools or file watchers. If a direct `python build_site.py` hits a Windows file lock, prefer a redirected `KA_SITE` build before assuming the build is broken.

## Spirit Of The Work

Move with Christ aloha: truthful, careful, protective, and useful. Strengthen the system without harming the people, private pathways, or trust boundaries it serves.
