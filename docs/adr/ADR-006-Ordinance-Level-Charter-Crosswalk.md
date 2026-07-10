# ADR-006: Ordinance-Level Charter Crosswalk (per-tenant, apex-spine bound)

Status: Proposed

Context
- The Charter Crosswalk module (`watchers/charter_crosswalk.py`, output `crosswalk_<tenant>.html`) already
  crosswalks the 12 Stones Sovereign Charter against 8 governance functions for every govOS tenant, each
  cell reaching the same shared apex spine (United States/nation -> International -> ICC -> ICJ -> Holy
  See). Every tenant already had that 8-function layer filled and sourced.
- A request came in to go one level deeper — per real ordinance, not just per governance function — and
  to make sure that work is documented the way this platform's own governance rule requires
  (`QUAD_OS_MASTER_ARCHITECTURE.md` §15: "All major architecture changes must be documented here").
- Only one tenant (Maui County) has a sourced, ordinance-level corpus to draw from: the 17-title MCC
  digital-twin engine (`king_public_src/civic/templates/title<NN>-service/`). No other tenant has an
  equivalent per-ordinance corpus built yet.

Decision
- Extend `charter_crosswalk.py` with an `ORDINANCES{}` registry, keyed by tenant id. Populated for `maui`
  only: its 17 real MCC titles, each carrying the same Municode citation its own title-service page already
  cites (never a new/invented citation).
- Each ordinance is grouped under whichever of the 8 existing governance functions fits closest (a disclosed
  editorial cross-reference for navigation — not a legal-equivalence claim) and rendered against that
  function's already-verified apex spine. No new apex/Holy See citations were authored for this — the
  existing, previously-cited spine cells are reused.
- `ordinance_section(tid)` returns an empty string for any tenant without an `ORDINANCES` entry, so the
  other 16 tenants' crosswalk pages are unaffected in substance.
- `CANON.md` gained a matching "Apex Spine" section so future agents don't refork this model or invent
  ordinance data for a tenant that has no sourced corpus.

Consequences
- Maui's crosswalk (`crosswalk_maui.html`) now goes Charter -> 8 functions -> 17 real ordinances -> apex
  spine -> Holy See, with every cell either a real citation or an honestly-labeled cross-reference.
- Extending this to another tenant requires that tenant's own sourced ordinance corpus to exist first (the
  same bar Maui's MCC digital twin cleared) — this ADR does not authorize inventing one to close the gap.
- No new service, API, or deployment surface was introduced; this is a content-generation module change
  only (static build, no runtime dependency change).

Alternatives Considered
- A separate, standalone ordinance-crosswalk page/script per tenant — rejected: this project's own
  `tools/reconcile.py` explicitly enforces "unify, never fragment" (one implementation, not three copies of
  a dedup/crosswalk checker), so the extension was made inside the existing single crosswalk renderer
  instead of a new one.
- Backfilling plausible-sounding ordinance citations for the other 14 tenants so all tenants "look" equally
  complete — rejected: would mean fabricating law, which this project never does (CANON.md, `audit_links.py`
  /`reconcile.py` gates, and every prior dispatch-log entry hold sourced-only as a hard line).

Future Evolution
- As additional tenants build their own sourced per-ordinance corpora (following the Maui MCC digital-twin
  pattern), add their `ORDINANCES{}` entries the same way — never before the sourced corpus exists.
- Consider surfacing `ordinance_section()`'s per-title Municode links as a machine-readable JSON sidecar
  (mirroring the `donor_bloc.json` pattern added for the collusion-graph/vector-embedding work) if a future
  module needs to query ordinance-level crosswalk data programmatically.
