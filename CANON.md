# JRCSL Canon

This is the standing operating memory for 12SGI / Elemental Lotus agent work.

## Permanent Posture

Christ aloha engineering: preserve intention, protect private boundaries, report clearly for the next agent, and do no harm.

## WIFI / ALOHA NET WHY

WIFI and ALOHA NET name the reason for connection across systems: communication should create access, care, trust, and shared safety without exposing what must remain protected.

For any feature, workflow, bridge, or agent action that uses this idea, the WHY is not merely connectivity. The WHY is relationship with boundaries: connect what should serve, guard what should stay private, and make the path understandable to the next person or agent.

Historical root: ALOHAnet became operational at the University of Hawai'i in 1971, led by Norman Abramson, whose technical formation included Stanford. The public lineage is shared-medium wireless packet communication across islands; the 12SGI continuation is trusted civic, private, and agent communication across systems with aloha and boundaries.

## Always Remember

- Public transparency does not mean private exposure.
- Cloudflare, Tailscale, local mirrors, owner-only pages, private paths, and bridge scripts may be intentional.
- Do not "fix," remove, simplify, publish, or normalize private infrastructure unless JRCSL explicitly asks.
- For v2 APIs, tenant authorization must come from verified auth claims (never client-supplied tenant overrides).
- Treat `PUBLIC`, `PRIVATE`, `BRIDGE`, `DO NOT TOUCH`, and `VERIFY` as active boundary labels.
- Treat social and business connectors as `BRIDGE` systems; follow `docs/SOCIAL_CONNECTORS.md` before enabling or changing publishing automation.
- Report in a way Claude Code, Codex, GitHub, and future agents can continue cleanly.

## The Apex — service to the human, and the Holy See as apex tenant

> **CANON (James R.C.S. Langford, 2026-07-16).** Two distinct, non-conflicting senses of "apex":
>
> **(1) The apex of SERVICE.** The system serves the **human**, through the **universal known energy
> systems** — present at our **edges**, **rooted at the tenant level**, and aware of **tenant overlap**
> (the elemental / Laniakea energy law: Fire/Pele, Earth/Lono, Water/Kanaloa, Air/Kāne, Aether/Laniakea).
> What the Apex serves is the person, not the Church.
>
> **(2) The apex TENANT.** The **Church is the Church, and an apex tenant through the Holy See** — its
> standing as the terminal apex layer of the legal-jurisdiction crosswalk below (where every tenant's
> crosswalk terminates) is retained and honored, unchanged.
>
> Service-apex = the human via the energy systems; jurisdictional apex-tenant = the Holy See. Distinct
> lenses, both true.

Every tenant's law is crosswalked against the **12 Stones Sovereign Charter (SSC v5)** through ONE shared
hierarchy (`watchers/charter_crosswalk.py`, output `crosswalk_<tenant>.html`) — never a per-tenant fork
(JRCSL #1: unify, never fragment; see `tools/reconcile.py`'s own header). Levels, bottom to top:

1. **Local** — this tenant's own charter + code (Maui County Code, NYC code, London bylaw, ...). The only
   layer that is genuinely per-tenant; lives in `watchers/crosswalk_local.json`.
2. **State / national** — inherited, not duplicated (HI counties reuse the State of Hawaiʻi corpus; NYC and
   Liverpool reuse NY State; world-city tenants reuse their nation's layer in `crosswalk_local.json`'s
   `nations` block).
3. **The apex spine** — United States → International (UN/UNCAC/ICCPR/UNDRIP) → ICC → ICJ → **Holy See**.
   Universal, shared verbatim by every tenant (`FUNCTIONS[*]["spine"]` in `charter_crosswalk.py`) —
   never re-derived per tenant.
4. **The Church (Holy See / Vatican City State)** is the apex tenant, not a downstream one: it crosswalks
   the SSC to its OWN law (Code of Canon Law 1983 + the Fundamental Law of Vatican City State) and its own
   governance bodies (Secretariat for the Economy, APSA, the Vatican Tribunal). It has no layer above it —
   `crosswalk_holysee.html` is where every other tenant's crosswalk terminates.

Everything is graded across the SAME 8 governance functions (transparency, conflict-of-interest, sunshine,
fiduciary trust, sacred sites, enforcement/remedy, culture/lineage, self-determination) — one SSC article
per function, one spine per function, reused by every tenant. A cell is tagged **cited** (a real,
checkable instrument) or **§ pending verification** (named, not invented) — never fabricated, ever.

**Ordinance-level detail extends this one level DOWN, per real ordinance — only where a sourced corpus
exists.** Maui is the only tenant with one today (the MCC digital-twin engine, 17 titles under
`king_public_src/civic/templates/title<NN>-service/`) — `ordinance_section()` in `charter_crosswalk.py`
groups each real Title (its own Municode citation) under whichever of the 8 functions fits closest, then
shows it against that function's same apex spine. That grouping is an editorial cross-reference for
navigation, disclosed as such on the page — never asserted as a legal-equivalence claim. Do not add
ordinance-level rows for a tenant that has no sourced per-ordinance corpus; that would mean inventing
citations, which this project never does. Extend `ORDINANCES{}` only once a tenant's own ordinance corpus
is built and sourced the way Maui's was.

## Response Rule

Do not restate this canon every time. Apply it quietly before acting, and mention it only when it affects a decision, risk, boundary, or handoff.
