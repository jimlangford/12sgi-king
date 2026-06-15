# SAGE Realm Model — the crosswalk from civic logic to creative expression

> Canonical. Written 2026-06-15 (claude-home-thread) from Jimmy's articulation of the model.
> Read this when any work touches the link between the **govOS civic engine**, the **54 Sage nodes**,
> the **deck cards**, and the **Hawaiian moon / sun rhythm**. This is the "why" the data files encode.

---

## 1. The one sentence

**Each node is a spherical environment — energy, observed by an observer (the character card / player)
who carries a set of skills. The environment's *values* act on the character; the character must draw a
*balance from the existing source*. That act of balancing IS the crosswalk from logic to creative
expression (with logic). Sun↔moon (Ao↔Pō) is the overlapping rhythm both the civic lane and the
creative lane ride.**

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

- **Pō (moon / night)** → the *civic* lane: kaulana mahina pō-night → offering (testify / listen /
  rest / harvest-spirit). The 30 pō in 3 anahulu. (`moon_calendar.reading`)
- **Ao (sun / day)** → the *creative* lane: the card's `wa_phase` Ao archetypes → which sphere's
  energy is "in light" to express. The akua presiding (Pele=fire, Kāne=fresh-water/life,
  Lono=harvest/peace, Kanaloa=ocean) keys the creative palette.
- **The overlap** = both lanes read the **same date** through the **same source**. A date is at once a
  pō-night (civic offering) and an Ao/Pō key into a sphere's creative energy. `creative_offering(date)`
  returns the node/akua/wā/particles whose moon + phase best match the day — so the studio knows *which
  cut-scene / card energy* answers the same moment the civic agenda does.

This is the requested **inclusion of the creative lane in the overlapping sun-to-moon logic**: the
deckbuilder and (down the line) the farming engine pull their "what to grow / render now" from the
exact rhythm govOS uses to say "what to testify on now."

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
| This model | `docs/SAGE_REALM_MODEL.md` (you are here) |
