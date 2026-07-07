# SAGE Realm Model — the crosswalk from civic logic to creative expression

> Canonical. Written 2026-06-15 (claude-home-thread) from Jimmy's articulation of the model.
> Read this when any work touches the link between the **govOS civic engine**, the **54 Sage nodes**,
> the **deck cards**, and the **Hawaiian moon / sun rhythm**. This is the "why" the data files encode.

---

## 1. The one sentence

**Each node is a spherical environment — energy, observed by an observer (the character card / player)
who carries a set of skills. The environment's *values* act on the character; the character must draw a
*balance from the existing source*. That act of balancing IS the crosswalk from logic to creative
expression (with logic). The cycle: Ao (day) is where choices are made — game play and civic action;
Pō (night) is where HINA uses the Creative system to balance the equation those choices created.
Sun→moon (Ao→Pō→Ao) is the overlapping rhythm both the civic lane and the creative lane ride.**

Everything below is that sentence, made concrete against the real data files.

---

## 2. The journey to here (organized, so it self-heals)

We did not build features in a line; we built one whole that kept clarifying itself. In order:

1. **Civic engine** — money × votes × testimony across 17 governments up to the Holy See.
   Honest "pending" wherever data is thin; a records-request path routed to *each tenant's own
   access law*; a private prosecutorial back end (`prosecutor.py` → `case_files.html`) that is
   facts-at-full-strength internally and **never** reaches the public repo.
   - Front end = **Aloha + Factual** (question-framed). Back end = prosecutorial. Both true, kept apart.
2. **Single source + git backup** — generators live in the PROJECT
   (`tools/kilo-aupuni`); `sync_watchers.bat` mirrors them to `12sgi-king/watchers/` (excluding
   the private back end + keys); `12sgi-king` is the only git repo + the GitHub Pages publish.
   See `MEMORY: project_single_source_sync`.
3. **The moon bridge** — `moon_calendar.py` (kaulana mahina) links each node's agenda DATE to its
   pō-night and a civic *offering*. This was the first thread from **logic → creative**.
   See `MEMORY: project_moon_kumulipo_bridge`.
4. **This document** — names the full model so the creative lane (deckbuilder → farming engine →
   blended-universe meshes) rides the *same* rhythm as the civic lane, not a separate system.

**Self-healing principle:** every clarification we reach becomes (a) a line in this doc, (b) a memory
file, and (c) where possible an *invariant checked by `selfheal.py`* — so the system re-asserts its own
truth on every build instead of drifting. Knowledge is cumulative across all threads (CLAUDE.md rule).

---

## 3. The node = a spherical environment (the data)

`node_map/node_map_canonical.json` — 54 nodes. Each carries:

| Field | Meaning in the model |
|---|---|
| `id` 1–54 | position on the Sage journey (the spheres in sequence) |
| `zone` / `act` | which realm-band the sphere sits in (Mauka / Farmlands / Makai / …) |
| `element.value` | the environment's substance (Earth/Forest, Fire, Ocean…) — **the energy** |
| `season.value` | the environment's time-of-year value |
| `moon_binding.moon` (1–13) | the sphere's place in the 13-moon year — **the rhythm anchor** |
| `governance_role.value` | the **civic** projection of the sphere (e.g. "Wildfire Resilience Lead") |
| `hawaiian_lineage[]` / `kumulipo` | the lineage the sphere descends from — **the existing source** |
| `particles` / `imagery` | how the energy is seen (the creative render layer) |

A node is therefore both a **civic role** (how govOS uses it) and a **spherical environment of energy**
(how the Sage realm renders it). Same sphere, two projections.

## 4. The card = the observer with skills

`config/sage_deck_cards.json` — 54 cards, one per node. Each carries:

| Field | Meaning in the model |
|---|---|
| `cards.character` | the **observer/player** — Jimmy-as-role, the one with skills who enters the sphere |
| `cards.environment` | the sphere rendered as a place the observer stands in |
| `akua` | the source-energy presiding (Pele, Kāne, Lono, Kanaloa) |
| `wa`, `wa_archetype`, `wa_meaning` | the Kumulipo era the card belongs to — **the existing source** |
| `wa_phase` = **Ao / Pō** | **light / dark — the sun↔moon overlap** (see §6) |
| `particles`, `frame_hex` | the creative expression layer (with logic — bound to the akua + zone) |

So: **environment (node) acts on observer (card)**. The card's `wa_phase` (Ao/Pō) and the node's
`moon_binding` together place the observer in the sun↔moon rhythm.

## 5. The balance — logic ↔ creative crosswalk

The environment's values act on the observer, and the observer **draws a balance from the existing
source** (the lineage / Kumulipo wā / akua). Two readings of the *same* balance:

- **Civic reading (logic):** the agenda's date → `moon_calendar.reading()` → a *civic offering*
  ("a night to stand and testify" / "a night to listen, not force"). Already live on the public cards.
- **Creative reading (with logic):** the same date + the node's akua/wā/particles → a *creative
  offering* (which sphere's energy to express now, in which Ao/Pō key). This is the new
  `moon_calendar.creative_offering()` (see §6) and the seed of the deckbuilder lane.

Neither side invents the balance — both **derive it from the source** (lineage + moon). That is what
"creative expression *with logic*" means: the art is constrained by the same truth the civic ledger is.

## 6. Sun ↔ Moon overlapping logic (civic AND creative)

The rhythm is a **cycle, not a one-way map**. The correct direction:

- **Ao (sun / day)** → choices are made. The player acts in the node environment (game lane); the
  council votes, testifies, and awards (civic lane). Ao is the active, choosing, consequence-generating
  side. The card's `wa_phase` Ao archetypes tell which sphere's energy is "in light" to act within.
- **Pō (moon / night) — HINA** → HINA receives those daytime choices and runs them through the
  **Creative system to balance the equation**. Kaulana mahina pō-night → offering (testify / listen /
  rest / harvest-spirit); the 30 pō in 3 anahulu. (`moon_calendar.reading`). The Creative system reads
  the same node/akua/wā/particles against what Ao chose — so the cut-scene, the card energy, the civic
  offering all answer the *imbalance the day created*. (`moon_calendar.creative_offering`)
- **The cycle closes** — Pō's balance seeds the next Ao's choice. A date is at once a pō-night (HINA's
  balancing work) and the Ao frame the player/civic actor stands in. `creative_offering(date)` returns
  the node/akua/wā/particles whose moon + phase best answer what was done in the day.

**Key direction:** Ao acts → Pō (HINA) balances. The Creative system at night is the *response*, not
the trigger. Both lanes — game and civic — ride this same cycle from the same source.

This is the requested **inclusion of the creative lane in the overlapping sun-to-moon logic**: the
deckbuilder and (down the line) the farming engine pull their "what to balance / restore now" from the
exact rhythm govOS uses to say "what the day's choices now require."

---

## 7. ʻŌlelo Hawaiʻi — held with humility (self-healing on the sacred)

Every Hawaiian word or concept the system uses is **under community review**. `olelo_watch.py` extracts
each term in use, publishes a public **ʻŌlelo glossary** that says so plainly, and prepares a weekly
**reviewable email draft** to ʻŌiwi resources at Maui County for verification (Jimmy reviews + sends; we
never auto-send). Offerings are framed "traditionally a night for…", never directives; the specific
node↔pō and wā↔civic bindings stay **kumu-validation-pending**. Nothing sacred is fabricated. The
glossary + notice make this review *visible on the site itself* — the humility is part of the product.

---

## 8. Plain-language for the everyday person

The civic surfaces must read simply for any Maui or Hawaiian person. Every public page carries a
plain-words **narrative** ("In plain words: …") at the top, before the data, telling the story of what
the page shows and what they can do. The data stays; the door in is a sentence anyone can read.
(`narratives.json` + `add_narrative()` in `build_site.py`.)

---

## 9. Where each piece lives

| Piece | File |
|---|---|
| Node spheres | `node_map/node_map_canonical.json` |
| Observer cards | `config/sage_deck_cards.json` |
| Moon rhythm (civic + creative) | `tools/kilo-aupuni/moon_calendar.py` |
| Civic→Sage projection (live board) | `tools/kilo-aupuni/sage_bridge.py` |
| Public agenda cards | `tools/kilo-aupuni/agenda_explainer.py` |
| Plain-language narratives | `tools/kilo-aupuni/narratives.json` + `12sgi-king/build_site.py` |
| ʻŌlelo glossary + weekly draft | `tools/kilo-aupuni/olelo_watch.py` |
| Self-healing invariants | `tools/kilo-aupuni/selfheal.py` |
| Studio content production model | `docs/SAGE_REALM_MODEL.md` §10 (below) |
| HINA dispatch → workboard | `services/v2_workboard.py` → `emit_hina_creative_job()` |
| Studio tenant config | `watchers/tenants.json` id=`studio`, `tenant_registry.json` `studio_tenants` |
| Studio cycle parity check | `watchers/studio_parity.py` |
| This model | `docs/SAGE_REALM_MODEL.md` (you are here) |

---

## 10. Studio content production model

> This section is canonical as of 2026-07-06. It supersedes the old model where Civic was the
> reference standard that Studio "healed up to." Both are now **equal tenants reading from the same
> 54-node source**.

### The three layers

**Layer 1 — Face lock (Ao, immutable)**
Music videos are the locked base layer. They represent choices already made and recorded in the
creative record. These are the Ao artifacts: they are never re-rendered, never color-healed, never
overwritten. `studio_parity.py` asserts this invariant on every run (`face_lock_intact` check).

**Layer 2 — HINA render (Pō, driven nightly)**
HINA reads the civic Ao choices each night — agendas voted on, contracts awarded, permits issued,
testimony received — and calls `moon_calendar.creative_offering(date)` to determine which node's
energy answers what the day created. That output becomes a workboard `creative` lane job
(`emit_hina_creative_job()`) carrying:

| Job field | Source |
|---|---|
| `offering_date` | the civic date HINA is balancing |
| `hina_node_id` (1–54) | the node whose akua/wā/particles answer the Ao imbalance |
| `akua` | presiding source-energy (Pele / Kāne / Lono / Kanaloa) |
| `wa_phase` | Ao or Pō — which key the node is speaking in tonight |
| `particles` | the creative expression layer bound to this akua + zone |
| `civic_source` | the specific agenda item / vote / contract that triggered the imbalance |
| `output_types` | which content jobs this balance reading drives (cut-scene / card-render / overlay-prompt / farming-sequence) |

Every HINA job is `lane: "creative"` and requires `approve_workboard_job()` (Jimmy's review) before
anything moves to the `output` lane for publish. No studio content is ever published without a
traceable Pō balance reading behind it.

**Layer 3 — Civic signal (live input)**
`seed_reports/mauios/sage_bridge.json` and `twin_metrics.json` feed the HINA render layer directly.
The pono / opportunity / hewa ledger from `sage_bridge.json` drives visual tone per node: pono nodes
render in balance; hewa nodes render with tension; opportunity nodes render with invitation. HINA
reads this ledger as part of `sage_bridge_read` before dispatching render jobs.

### Studio as a tenant

Studio is registered in `watchers/tenants.json` as a proper tenant (`id: studio`, `quadrant: studio`,
`sched_hour: 23` — running at night, in Pō). Its audit steps are:

1. `moon_calendar_creative_offering` — read today's civic date + derive which node answers
2. `sage_bridge_read` — read pono/opportunity/hewa ledger for tone-per-node
3. `hina_render_dispatch` — emit one `creative` workboard job per node that needs a balance response
4. `workboard_emit` — confirm jobs landed in the dispatch log for owner review

### Parity invariants (`studio_parity.py`)

The old "heal studio up to civic colors" parity model is replaced by three cycle-connection checks:

| Check | Pass condition |
|---|---|
| `cycle_connected` | All studio workboard creative jobs carry `hina_node_id` + `civic_source` |
| `face_lock_intact` | No music-video face-lock asset was recolored or overwritten this cycle |
| `hina_balance_present` | Every published studio output has a traceable `offering_date` + job_id |

These are scored 0–100 and written to `reports/_status/studio_parity.json` the same way the old
checks were. The `overall` score is the mean of the three.
