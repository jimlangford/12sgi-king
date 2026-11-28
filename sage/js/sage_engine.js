/* sage_engine.js — SAGE · the ahupuaʻa game — PURE logic engine.
 *
 * Zero DOM, zero fetch. The UI passes in the fetched data (nodes, cards, calc_spec,
 * calc_vectors); the engine never touches the network or the document.
 *
 * PARITY: nodeKpis / kpisAll are a bit-faithful JS twin of tools/grants/sage_calc.py.
 * All KPI math flows through nodeKpis (parity-exact vs Python). Game-layer modifiers
 * (hewa ×0.5) are applied OUTSIDE nodeKpis so the KPI export stays pure sage_calc.
 *
 * Attach: window.SageEngine (browser) + module.exports (node/tests).
 * Deterministic: same seed = same game (mulberry32; rng counter lives in state.rngState).
 */
(function () {
"use strict";

/* ------------------------------------------------------------------ spec -- */

/** Stored calc spec (data/calc_spec.json). Set via SageEngine.init(spec). */
let SPEC = null;

/** Game-rule fallbacks — used only if spec.game_rules omits a key. */
const DEFAULT_RULES = {
  hand_size: 7,
  plays_per_moon: 3,
  moons_per_cycle: 13,
  water_base_capacity: 500,
  mauka_watershed_bonus: 400,
  hewa_production_factor: 0.5,
  pono_moon_tolerance: 1,
  hina_bridge_enabled: true,     // Kaulana Mahina seam grace (Jimmy 2026-07-03): the 28->30 bridge night
  hina_bridge_base_chance: 0.5,  // ONE KNOB — Hina's max grace at the full moon; moon-weighted in hinaBridgeChance()
  discards_per_moon: 1,   // pressure valve — a stuck hand can never freeze the deck
  n54_gate: { per_zone_pono_min: 4 },   // production zones only — the 2 Universal cards ARE the jokers
  crisis_threshold: "60 + 25*cycles_completed + 5*planted_count",
};

const DEFAULT_LABEL = "PROJECTED (modeled, assumptions stated) — not actuals";
const ZONE_LIST = ["Mauka", "Kula", "Makai"]; // the three bands the N54 gate counts
const KPI_NODE_FIELDS = ["yield_lbs_day", "water_gal_day", "resilience",
                         "fishing_lbs_day", "revenue_day", "gwt_day", "jobs"];
const KPI_ZONE_FIELDS = ["nodes", "yield_lbs_day", "water_gal_day",
                         "fishing_lbs_day", "revenue_day", "gwt_day", "jobs"];
const KPI_TOTAL_FIELDS = KPI_ZONE_FIELDS.concat(["annual_revenue", "annual_gwt"])
                         .filter(function (f) { return f !== "resilience"; });

/**
 * Store the calculator spec (zone_coef, price_per_lb, gwt_rate, assumptions,
 * game_rules). Must be called (directly, via newGame opts.spec, or via
 * deserialize opts.spec) before any KPI math. Keeps the engine pure: the UI
 * fetches, the engine computes.
 * @param {object} spec parsed data/calc_spec.json
 * @returns {object} the stored spec
 */
function init(spec) {
  if (!spec || !spec.zone_coef || !spec.price_per_lb || typeof spec.gwt_rate !== "number") {
    throw new Error("SageEngine.init: spec must carry zone_coef, price_per_lb, gwt_rate");
  }
  SPEC = spec;
  return SPEC;
}

function getSpec() {
  if (!SPEC) throw new Error("SageEngine: call init(spec) first (data/calc_spec.json)");
  return SPEC;
}

function gameRules() {
  const gr = getSpec().game_rules || {};
  const out = {};
  for (const k in DEFAULT_RULES) out[k] = (gr[k] !== undefined ? gr[k] : DEFAULT_RULES[k]);
  return out;
}

/** Parse the crisis-threshold formula string from spec.game_rules into coefficients. */
function crisisCoefs() {
  const s = String(gameRules().crisis_threshold || "");
  const m = s.match(/(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*\*\s*cycles_completed\s*\+\s*(\d+(?:\.\d+)?)\s*\*\s*planted_count/);
  if (m) return { base: +m[1], perCycle: +m[2], perPlanted: +m[3] };
  return { base: 60, perCycle: 25, perPlanted: 5 }; // documented fallback = spec default
}

/* ------------------------------------------------------- rounding parity -- */

/**
 * Half-even ("banker's") rounding matching Python round(x, digits) bit-for-bit.
 *
 * Floating-error strategy (documented per spec): the naive "add a 1e-9 nudge then
 * Math.round" approach mis-rounds values like 2.675 whose IEEE754 double is BELOW
 * the decimal tie (Python: round(2.675, 2) == 2.67, nudge gives 2.68). Instead we
 * do what CPython itself does: round the EXACT decimal expansion of the double.
 * Every double is a dyadic rational, so toFixed(50) (spec-exact in all modern
 * engines) exposes the true value; any real deviation from a decimal tie at
 * digit<=3 is >= 1/(2^52*10^4) and therefore visible well inside 50 digits —
 * the same discrimination the 1e-9 nudge was meant to approximate, made exact.
 * Ties (a true trailing "5000…0") break to the even kept digit.
 * @param {number} x value
 * @param {number} [digits=0] decimal places (>= 0)
 * @returns {number} x rounded half-even to `digits` places
 */
function roundPy(x, digits) {
  digits = digits | 0;
  if (!Number.isFinite(x)) return x;
  if (digits < 0) throw new Error("roundPy: digits must be >= 0");
  const neg = x < 0;
  const ax = Math.abs(x);
  // Exact decimal expansion (see doc above). 50 fractional digits is exact for
  // every magnitude this engine produces (all values >= ~0.01 or exactly 0).
  const s = ax.toFixed(50);
  const dot = s.indexOf(".");
  let intPart = s.slice(0, dot);
  const frac = s.slice(dot + 1);
  let keep = frac.slice(0, digits);
  const rest = frac.slice(digits);
  let roundUp = false;
  if (rest.length) {
    const first = rest.charCodeAt(0) - 48;
    const tailNonZero = /[1-9]/.test(rest.slice(1));
    if (first > 5 || (first === 5 && tailNonZero)) roundUp = true;
    else if (first === 5 && !tailNonZero) {
      // exact tie -> half-even on the last kept digit
      const last = digits > 0
        ? (keep.length ? keep.charCodeAt(keep.length - 1) - 48 : 0)
        : (intPart.charCodeAt(intPart.length - 1) - 48);
      roundUp = (last % 2) === 1;
    }
  }
  if (roundUp) {
    // increment the decimal string intPart+keep with carry
    let d = (intPart + keep).split("");
    let i = d.length - 1;
    while (i >= 0) {
      if (d[i] === "9") { d[i] = "0"; i--; }
      else { d[i] = String.fromCharCode(d[i].charCodeAt(0) + 1); break; }
    }
    if (i < 0) d.unshift("1");
    const joined = d.join("");
    intPart = joined.slice(0, joined.length - keep.length) || "0";
    keep = joined.slice(joined.length - keep.length);
  }
  const out = parseFloat(intPart + (keep ? "." + keep : "")) || 0;
  return neg ? -out : out;
}

/* --------------------------------------------------------------- the RNG -- */

/**
 * mulberry32 seeded PRNG. Returns a () => float in [0,1). Every random decision
 * in the engine flows from this generator (via the counter held in state.rngState
 * so determinism survives serialize/deserialize).
 * @param {number} seed uint32 seed
 * @returns {function(): number}
 */
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) | 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** One mulberry32 step advancing state.rngState (stored as int32, serializable). */
function rand(state) {
  state.rngState = ((state.rngState | 0) + 0x6D2B79F5) | 0;
  let t = state.rngState;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

/** In-place Fisher–Yates shuffle driven by state.rngState. */
function shuffleInPlace(state, arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rand(state) * (i + 1));
    const tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
  }
  return arr;
}

/* ------------------------------------------------------ calculator (heart) */

/**
 * kaulana mahina timing multiplier — exact twin of sage_calc.moon_window().
 * Falsy moon (null, 0) => 1.0; else 1.0 + 0.10*(1 - |moon-7|/7) rounded half-even to 3.
 * @param {?number} moon 1..13 or null
 * @returns {number}
 */
function moonWindow(moon) {
  if (!moon) return 1.0;
  return roundPy(1.0 + 0.10 * (1 - Math.abs((moon - 7) / 7.0)), 3);
}

/** Zone with the sage_calc Universal fallback. */
function zoneOf(row) {
  const z = row && row.zone;
  return (getSpec().zone_coef && getSpec().zone_coef[z]) ? z : "Universal";
}

/**
 * Exact sage_calc.py KPI row for one node — the parity heart. NEVER apply
 * game modifiers here; hewa ×0.5 etc. live in endMoon/score only.
 * @param {object} node a DT_SGI_Nodes row ({id, zone, moon, grant_programs, ...})
 * @returns {object} {node, zone, moon, yield_lbs_day, water_gal_day, resilience,
 *                    fishing_lbs_day, revenue_day, gwt_day, jobs, grant_programs}
 */
function nodeKpis(node) {
  const spec = getSpec();
  const zone = zoneOf(node);
  const c = spec.zone_coef[zone];
  const mw = moonWindow(node.moon);
  const y = roundPy(c.yield * mw, 1);
  const water = roundPy(c.water, 1);
  const fish = roundPy(c.fish * mw, 1);
  const price = spec.price_per_lb[zone];
  const rev = roundPy((y + fish) * price, 2);
  const gwt = roundPy(rev * spec.gwt_rate, 2);
  return {
    node: node.id, zone: zone, moon: (node.moon === undefined ? null : node.moon),
    yield_lbs_day: y, water_gal_day: water, resilience: c.resil,
    fishing_lbs_day: fish, revenue_day: rev, gwt_day: gwt, jobs: c.jobs,
    grant_programs: node.grant_programs || [],
  };
}

/** Build the sage_kpis payload from KPI rows — mirrors sage_calc roll-up math exactly. */
function buildPayload(rows, generated) {
  function s(k) {
    let acc = 0;
    for (const r of rows) acc += r[k];
    return roundPy(acc, 1);
  }
  const byzone = {};
  for (const r of rows) {
    if (!byzone[r.zone]) {
      byzone[r.zone] = { nodes: 0, yield_lbs_day: 0, water_gal_day: 0,
                         fishing_lbs_day: 0, revenue_day: 0, gwt_day: 0, jobs: 0 };
    }
    const z = byzone[r.zone];
    z.nodes += 1;
    // cumulative per-add rounding — exactly like the Python loop
    for (const k of ["yield_lbs_day", "water_gal_day", "fishing_lbs_day",
                     "revenue_day", "gwt_day", "jobs"]) {
      z[k] = roundPy(z[k] + r[k], 1);
    }
  }
  const spec = getSpec();
  return {
    generated: generated || new Date().toISOString(),
    label: spec.label || DEFAULT_LABEL,
    assumptions: spec.assumptions || {},
    ahupuaa_totals: {
      nodes: rows.length,
      yield_lbs_day: s("yield_lbs_day"), water_gal_day: s("water_gal_day"),
      fishing_lbs_day: s("fishing_lbs_day"), revenue_day: s("revenue_day"),
      gwt_day: s("gwt_day"), jobs: s("jobs"),
      annual_revenue: roundPy(s("revenue_day") * 365, 2),
      annual_gwt: roundPy(s("gwt_day") * 365, 2),
    },
    by_zone: byzone,
    nodes: rows,
  };
}

/**
 * Full 54-node sage_kpis payload (selftest / "export all" view).
 * @param {object[]} nodes all DT_SGI_Nodes rows
 * @param {string} [generated] ISO timestamp; defaults to now
 * @returns {object} sage_kpis-shaped payload
 */
function kpisAll(nodes, generated) {
  return buildPayload(nodes.map(nodeKpis), generated);
}

/**
 * sage_kpis payload for PLANTED nodes only. Hewa nodes still export their FULL
 * sage_calc row — the export is a steady-state projection, labeled PROJECTED.
 * @param {object} state game state
 * @param {string} [generated] ISO timestamp; defaults to now
 * @returns {object} sage_kpis-shaped payload
 */
function kpisPlanted(state, generated) {
  const ids = Object.keys(state.planted).map(Number).sort(function (a, b) { return a - b; });
  const rows = ids.map(function (id) { return nodeKpis(state._nodeById[id]); });
  return buildPayload(rows, generated);
}

/* --------------------------------------------------------------- selftest -- */

/**
 * 3D-parity harness: compare kpisAll(nodes) against data/calc_vectors.json
 * (truth = python sage_calc.py). Checks every numeric per-node field plus the
 * by_zone and ahupuaa_totals roll-ups, tolerance 0.011.
 * @param {object[]} nodes all DT_SGI_Nodes rows
 * @param {object} vectors parsed calc_vectors.json {nodes:[...], by_zone, ahupuaa_totals}
 * @param {number} [tolerance=0.011]
 * @returns {{pass: boolean, count: number, diffs: {node, field, ours, truth}[]}}
 */
function selftest(nodes, vectors, tolerance) {
  const tol = (typeof tolerance === "number") ? tolerance : 0.011;
  const ours = kpisAll(nodes, "selftest");
  const diffs = [];
  function cmp(where, field, a, b) {
    const bad = (typeof a !== "number" || typeof b !== "number")
      ? a !== b : Math.abs(a - b) > tol;
    if (bad) diffs.push({ node: where, field: field, ours: a === undefined ? null : a,
                          truth: b === undefined ? null : b });
  }
  const truthByNode = {};
  for (const t of (vectors.nodes || [])) truthByNode[t.node] = t;
  let count = 0;
  for (const r of ours.nodes) {
    const t = truthByNode[r.node];
    count++;
    if (!t) { diffs.push({ node: r.node, field: "(row)", ours: "present", truth: null }); continue; }
    for (const f of KPI_NODE_FIELDS) cmp(r.node, f, r[f], t[f]);
  }
  const vz = vectors.by_zone || {};
  for (const z of Object.keys(vz)) {
    const oz = ours.by_zone[z] || {};
    for (const f of KPI_ZONE_FIELDS) cmp("by_zone." + z, f, oz[f], vz[z][f]);
  }
  const vt = vectors.ahupuaa_totals || {};
  for (const f of KPI_TOTAL_FIELDS) cmp("ahupuaa_totals", f, ours.ahupuaa_totals[f], vt[f]);
  return { pass: diffs.length === 0, count: count, diffs: diffs };
}

/* ------------------------------------------------------------- game state -- */

/** Attach non-serialized data lookups to a state (hidden from JSON.stringify). */
function attachData(state, nodes, cards) {
  const nodeById = {}, cardByName = {}, cardByNode = {};
  for (const n of nodes) nodeById[n.id] = n;
  for (const c of cards) { cardByName[c.Name] = c; cardByNode[c.node] = c; }
  for (const pair of [["_nodes", nodes], ["_cards", cards], ["_nodeById", nodeById],
                      ["_cardByName", cardByName], ["_cardByNode", cardByNode]]) {
    Object.defineProperty(state, pair[0], { value: pair[1], enumerable: false,
                                            writable: true, configurable: true });
  }
  return state;
}

function logLine(state, msg) { state.log.push(msg); return { type: "log", msg: msg }; }

/** Wrapping moon distance on the 13-moon wheel. */
function moonDist(a, b, moons) {
  const d = Math.abs(a - b) % moons;
  return Math.min(d, moons - d);
}

/**
 * Hina Bridge — Kaulana Mahina seam grace (Jimmy 2026-07-03).
 * A card planted exactly ONE moon BEYOND the pono window — the "day before and
 * after", the 28->30 calendar-bridge night where the lunar count and the solar
 * count don't line up — may still be granted pono IF HINA ALLOWS. Hina, akua of
 * the moon, is strongest at the full moon (moon 7) and weakest at the dark edges
 * (moons 1 & 13), so the grace chance is moon-weighted. Pure + deterministic:
 * returns the probability in [0,1]; the caller rolls it with the seeded rand().
 * Returns 0 when the play is NOT on the seam, or when the bridge is disabled —
 * so pono (dist<=tolerance) and deep-hewa (dist>=tolerance+2) are untouched.
 * @param {number} currentMoon 1..13
 * @param {?number} cardMoon 1..13 or null
 * @param {object} rules game rules
 * @returns {number} bridge probability in [0,1]
 */
function hinaBridgeChance(currentMoon, cardMoon, rules) {
  if (!rules.hina_bridge_enabled) return 0;
  if (cardMoon === null || cardMoon === undefined) return 0;
  const seam = (rules.pono_moon_tolerance || 0) + 1;                 // exactly one ring beyond pono
  if (moonDist(currentMoon, cardMoon, rules.moons_per_cycle) !== seam) return 0;
  let favor = 1 - Math.abs(currentMoon - 7) / 6;                     // 1.0 at full moon (7) -> 0 at dark edges (1,13)
  if (favor < 0) favor = 0;
  return roundPy((rules.hina_bridge_base_chance || 0) * (0.4 + 0.6 * favor), 3);
}

/**
 * Start a new deterministic game: shuffle all 54 cards with mulberry32(seed),
 * deal to hand_size. Drawing the Override (node 53) arms the crisis.
 * @param {object[]} nodes DT_SGI_Nodes rows (54)
 * @param {object[]} cards DT_SGI_Cards rows (54)
 * @param {object} [opts] {seed?: uint32, spec?: calc_spec} — spec calls init() for you
 * @returns {object} state
 */
function newGame(nodes, cards, opts) {
  opts = opts || {};
  if (opts.spec) init(opts.spec);
  const rules = gameRules();
  const seed = (opts.seed === undefined || opts.seed === null)
    ? (Math.floor(Math.random() * 4294967296) >>> 0) : (opts.seed >>> 0);
  const state = {
    seed: seed,
    rngState: seed | 0,
    moon: 1,
    cycle: 0,
    playsUsed: 0,
    discardsUsed: 0,
    deck: [],
    hand: [],
    discard: [],
    planted: {},               // id -> {pono, plantedMoon, card}
    waterCapacity: rules.water_base_capacity,
    waterUsed: 0,
    season: { revenue: 0, gwt: 0, jobs: 0, yield: 0, fishing: 0 },
    crisisArmed: false,
    won: false,
    log: [],
  };
  attachData(state, nodes, cards);
  state.deck = shuffleInPlace(state, cards.map(function (c) { return c.Name; }));
  logLine(state, "moon 1 · new game · seed " + seed);
  draw(state);
  return state;
}

/**
 * Refill the hand to hand_size (deck top = end of array). When the deck runs dry
 * the discard is reshuffled back in (deterministic — same rng stream). Drawing
 * the Override joker (node 53) sets crisisArmed and logs the crisis banner line.
 * @param {object} state
 * @returns {{drawn: string[], events: object[]}}
 */
function draw(state) {
  const rules = gameRules();
  const drawn = [], events = [];
  while (state.hand.length < rules.hand_size) {
    if (!state.deck.length) {
      if (!state.discard.length) break;
      state.deck = shuffleInPlace(state, state.discard.splice(0));
      events.push(logLine(state, "moon " + state.moon + " · deck reshuffled from discard"));
    }
    const name = state.deck.pop();
    state.hand.push(name);
    drawn.push(name);
    const card = state._cardByName[name];
    if (card && card.node === 53) {
      state.crisisArmed = true;
      events.push(logLine(state, "moon " + state.moon +
        " · CRISIS · Override drawn — the system remembers. Resilience holds or the weakest falls."));
      events.push({ type: "crisis", card: name });
    }
  }
  return { drawn: drawn, events: events };
}

/** Count planted-pono nodes per zone (for the N54 synergy gate). */
function ponoZoneCounts(state) {
  const counts = { Mauka: 0, Kula: 0, Makai: 0, Universal: 0 };
  for (const id of Object.keys(state.planted)) {
    if (!state.planted[id].pono) continue;
    const z = zoneOf(state._nodeById[Number(id)]);
    if (counts[z] !== undefined) counts[z] += 1;
  }
  return counts;
}

/**
 * Rulebook check for playing a card: in hand, plays left, N53 never plantable,
 * N54 synergy gate, node not already planted, water fits remaining capacity.
 * @param {object} state
 * @param {string} cardName e.g. "Card_N12"
 * @returns {{ok: boolean, reason?: string}}
 */
function canPlay(state, cardName) {
  const rules = gameRules();
  if (state.hand.indexOf(cardName) < 0) return { ok: false, reason: "card not in hand" };
  const card = state._cardByName[cardName];
  if (!card) return { ok: false, reason: "unknown card " + cardName };
  if (state.playsUsed >= rules.plays_per_moon) {
    return { ok: false, reason: "no plays left this moon — end moon to continue" };
  }
  if (card.node === 53) {
    return { ok: false, reason: "Override is never planted — it resolves at end of moon" };
  }
  if (card.node === 54) {
    // Gate = 4 pono in each PRODUCTION zone. The only Universal cards are the two
    // jokers (N53 never plantable, N54 is this card) — a Universal-pono requirement
    // would be unsatisfiable, N54 can't be its own precondition. Found by the
    // 2026-07-02 winnability smoke; deck lock is 18 Mauka / 18 Kula / 16 Makai + 2.
    const c = ponoZoneCounts(state);
    const g = rules.n54_gate;
    const gateOk = ZONE_LIST.every(function (z) { return c[z] >= g.per_zone_pono_min; });
    if (!gateOk) {
      return { ok: false, reason: "synergy gate not met — need " + g.per_zone_pono_min +
        " pono per zone (Mauka " +
        c.Mauka + "/" + g.per_zone_pono_min + " · Kula " + c.Kula + "/" + g.per_zone_pono_min +
        " · Makai " + c.Makai + "/" + g.per_zone_pono_min + ")" };
    }
    return { ok: true };
  }
  if (state.planted[card.node]) return { ok: false, reason: "node already planted" };
  const node = state._nodeById[card.node];
  if (!node) return { ok: false, reason: "no node " + card.node };
  // Mauka plants are EXEMPT from the water budget: upland forest isn't irrigated
  // from the stream — it catches rain and GROWS the watershed. Without this, the
  // game soft-locks (need Mauka to grow water, can't afford to plant Mauka —
  // found by the 2026-07-02 winnability smoke). KPI export keeps water_gal_day
  // untouched: that's the pure calc layer, this is the game layer.
  if (zoneOf(node) !== "Mauka") {
    const water = nodeKpis(node).water_gal_day;
    const free = state.waterCapacity - state.waterUsed;
    if (water > free) {
      return { ok: false, reason: "water short — needs " + water + " gal/day, " +
        free + " free (plant mauka to grow the watershed)" };
    }
  }
  return { ok: true };
}

/**
 * Play a card from the hand. Plants its node (pono if within pono_moon_tolerance
 * of the current moon on the wrapping 13-moon wheel, else hewa at 50% production),
 * grows the watershed +mauka_watershed_bonus for Mauka plants, or — for N54 with
 * the gate open — WINS the game ("aloha as completion"). Mutates state.
 * @param {object} state
 * @param {string} cardName
 * @returns {{ok: boolean, reason?: string, events: object[]}}
 */
function play(state, cardName) {
  const check = canPlay(state, cardName);
  if (!check.ok) return { ok: false, reason: check.reason, events: [{ type: "reject", msg: check.reason }] };
  const rules = gameRules();
  const card = state._cardByName[cardName];
  const events = [];
  state.hand.splice(state.hand.indexOf(cardName), 1);
  state.playsUsed += 1;

  if (card.node === 54) {
    state.won = true;
    state.discard.push(cardName);
    events.push(logLine(state, "moon " + state.moon +
      " · N54 played · ALOHA AS COMPLETION — the ahupuaʻa is whole"));
    events.push({ type: "win", card: cardName });
    return { ok: true, events: events };
  }

  const node = state._nodeById[card.node];
  const k = nodeKpis(node);
  let pono = (card.moon !== null && card.moon !== undefined)
    && moonDist(state.moon, card.moon, rules.moons_per_cycle) <= rules.pono_moon_tolerance;
  let hinaBridged = false;
  if (!pono) {   // Hina Bridge: a seam play (day before/after) may be granted pono if Hina allows
    const chance = hinaBridgeChance(state.moon, card.moon, rules);
    if (chance > 0 && rand(state) < chance) { pono = true; hinaBridged = true; }
  }
  state.planted[card.node] = { pono: pono, plantedMoon: state.moon, card: cardName, hinaBridged: hinaBridged };
  if (zoneOf(node) === "Mauka") {
    state.waterCapacity += rules.mauka_watershed_bonus;   // water-exempt: catches rain, grows the shed
  } else {
    state.waterUsed = roundPy(state.waterUsed + k.water_gal_day, 1);
  }
  const nn = "N" + String(card.node).padStart(2, "0");
  if (pono) {
    if (hinaBridged) {
      events.push(logLine(state, "moon " + state.moon + " · planted " + nn +
        " pono · HINA BRIDGED the seam (day before/after granted) · +" + k.yield_lbs_day + " lbs/day"));
      events.push({ type: "planted", node: card.node, pono: true, bridged: true,
                    msg: "Hina bridged the seam — the day before/after was granted" });
    } else {
      events.push(logLine(state, "moon " + state.moon + " · planted " + nn +
        " pono · +" + k.yield_lbs_day + " lbs/day"));
      events.push({ type: "planted", node: card.node, pono: true, msg: "planted pono — on its moon" });
    }
  } else {
    events.push(logLine(state, "moon " + state.moon + " · planted " + nn +
      " HEWA (reversed, 50%) · " + (card.hewa_reversed || "")));
    events.push({ type: "planted", node: card.node, pono: false,
                  msg: card.hewa_reversed || "hewa — reversed" });
  }
  return { ok: true, events: events };
}

/**
 * Mālama (heal) a hewa node: discard any hand card of the SAME zone onto it.
 * Flips the node pono. Does not consume a play. Mutates state.
 * @param {object} state
 * @param {number} nodeId planted hewa node id
 * @param {string} discardCardName hand card of the same zone to give up
 * @returns {{ok: boolean, reason?: string, events: object[]}}
 */
function malama(state, nodeId, discardCardName) {
  const p = state.planted[nodeId];
  if (!p) return { ok: false, reason: "node not planted", events: [] };
  if (p.pono) return { ok: false, reason: "node is already pono", events: [] };
  if (state.hand.indexOf(discardCardName) < 0) {
    return { ok: false, reason: "card not in hand", events: [] };
  }
  const card = state._cardByName[discardCardName];
  const node = state._nodeById[nodeId];
  if (!card || !node) return { ok: false, reason: "unknown card or node", events: [] };
  if (zoneOf(card) !== zoneOf(node)) {
    return { ok: false, reason: "mālama needs a " + zoneOf(node) + " card — " +
      discardCardName + " is " + zoneOf(card), events: [] };
  }
  state.hand.splice(state.hand.indexOf(discardCardName), 1);
  state.discard.push(discardCardName);
  p.pono = true;
  const nn = "N" + String(nodeId).padStart(2, "0");
  const ev = logLine(state, "moon " + state.moon + " · mālama · " + nn +
    " healed pono (gave " + discardCardName + ")");
  return { ok: true, events: [ev, { type: "malama", node: nodeId }] };
}

/**
 * Discard a hand card to the discard pile as a FREE action (discards_per_moon
 * per moon, default 1). The pressure valve found by the 2026-07-02 review:
 * draw() only fires when the hand is under hand_size, so a hand full of
 * water-blocked cards would otherwise freeze the deck forever (no crisis, no
 * N54 path, nothing). Discarding cycles the current — the card returns via the
 * deck reshuffle. Deterministic; discardsUsed is serialized and resets each moon.
 * @param {object} state
 * @param {string} cardName hand card to give to the pile
 * @returns {{ok: boolean, reason?: string, events: object[]}}
 */
function discardCard(state, cardName) {
  const rules = gameRules();
  if (state.hand.indexOf(cardName) < 0) {
    return { ok: false, reason: "card not in hand", events: [] };
  }
  const used = state.discardsUsed | 0;
  if (used >= rules.discards_per_moon) {
    return { ok: false, reason: "no free discards left this moon — end moon to continue",
             events: [] };
  }
  state.hand.splice(state.hand.indexOf(cardName), 1);
  state.discard.push(cardName);
  state.discardsUsed = used + 1;
  const ev = logLine(state, "moon " + state.moon + " · discarded " + cardName +
    " (free, " + state.discardsUsed + "/" + rules.discards_per_moon +
    " this moon) — the hand refills at end of moon");
  return { ok: true, events: [ev, { type: "discard", card: cardName }] };
}

/**
 * End the moon: (1) every planted node produces one moon of KPIs — hewa nodes at
 * hewa_production_factor on yield/fishing/revenue/gwt ONLY (jobs is a headcount
 * snapshot, not scaled); (2) if the crisis is armed, resolve it — if the total
 * resilience of planted PONO nodes < threshold (spec formula: base + perCycle*
 * cycles_completed + perPlanted*planted_count) the LOWEST-resilience planted node
 * (tie-break: lowest id) reverts to unplanted and its card goes to discard; the
 * Override card then leaves the hand for the discard; (3) moon advances, wrapping
 * 13 -> 1 with cycle++; (4) plays reset and the hand refills to hand_size.
 * @param {object} state
 * @returns {{events: object[]}}
 */
function endMoon(state) {
  const rules = gameRules();
  const events = [];
  // 1 — production
  const ids = Object.keys(state.planted).map(Number).sort(function (a, b) { return a - b; });
  let dy = 0, df = 0, dr = 0, dg = 0, jobsNow = 0;
  for (const id of ids) {
    const k = nodeKpis(state._nodeById[id]);
    const f = state.planted[id].pono ? 1 : rules.hewa_production_factor;
    dy += k.yield_lbs_day * f;
    df += k.fishing_lbs_day * f;
    dr += k.revenue_day * f;
    dg += k.gwt_day * f;
    jobsNow += k.jobs; // jobs are people employed, not scaled by hewa
  }
  state.season.yield = roundPy(state.season.yield + dy, 1);
  state.season.fishing = roundPy(state.season.fishing + df, 1);
  state.season.revenue = roundPy(state.season.revenue + dr, 2);
  state.season.gwt = roundPy(state.season.gwt + dg, 2);
  state.season.jobs = roundPy(jobsNow, 1);
  if (ids.length) {
    events.push(logLine(state, "moon " + state.moon + " · harvest · +" +
      roundPy(dy, 1) + " lbs · +$" + roundPy(dr, 2) + " · GWT $" + roundPy(dg, 2)));
  }
  // 2 — crisis resolution
  if (state.crisisArmed) {
    const cc = crisisCoefs();
    const threshold = cc.base + cc.perCycle * state.cycle + cc.perPlanted * ids.length;
    let resil = 0;
    for (const id of ids) if (state.planted[id].pono) resil += nodeKpis(state._nodeById[id]).resilience;
    if (!ids.length) {
      // empty board: nothing to revert — do NOT claim "resil >= threshold" held
      events.push(logLine(state, "moon " + state.moon +
        " · OVERRIDE · nothing planted — nothing for the reset to take"));
      events.push({ type: "override_held", resilience: 0, threshold: threshold, empty: true });
    } else if (resil < threshold) {
      let weakest = ids[0], weakestR = Infinity;
      for (const id of ids) {
        const r = nodeKpis(state._nodeById[id]).resilience;
        if (r < weakestR) { weakestR = r; weakest = id; }
      }
      const victim = state.planted[weakest];
      const k = nodeKpis(state._nodeById[weakest]);
      delete state.planted[weakest];
      if (zoneOf(state._nodeById[weakest]) === "Mauka") {
        state.waterCapacity -= rules.mauka_watershed_bonus;  // mirror of the exempt plant: no water refund
      } else {
        state.waterUsed = roundPy(state.waterUsed - k.water_gal_day, 1);
      }
      if (victim.card) state.discard.push(victim.card);
      const nn = "N" + String(weakest).padStart(2, "0");
      events.push(logLine(state, "moon " + state.moon + " · OVERRIDE · resilience " +
        resil + " < " + threshold + " — " + nn + " falls (the weakest reverts)"));
      events.push({ type: "override", node: weakest, resilience: resil, threshold: threshold });
    } else {
      events.push(logLine(state, "moon " + state.moon + " · OVERRIDE · resilience " +
        resil + " >= " + threshold + " — the system holds"));
      events.push({ type: "override_held", resilience: resil, threshold: threshold });
    }
    state.crisisArmed = false;
    // the Override card leaves the hand for the discard — it is never planted
    for (const name of state.hand.slice()) {
      const c = state._cardByName[name];
      if (c && c.node === 53) {
        state.hand.splice(state.hand.indexOf(name), 1);
        state.discard.push(name);
      }
    }
  }
  // 3 — advance the moon (wrap 13 -> 1, cycle++)
  state.moon += 1;
  if (state.moon > rules.moons_per_cycle) {
    state.moon = 1;
    state.cycle += 1;
    events.push(logLine(state, "cycle " + state.cycle + " complete · moon 1 begins anew"));
  } else {
    events.push(logLine(state, "moon " + state.moon + " rises"));
  }
  // 4 — reset plays + free discards, refill hand
  state.playsUsed = 0;
  state.discardsUsed = 0;
  const d = draw(state);
  for (const ev of d.events) events.push(ev);
  return { events: events };
}

/**
 * "Ahupuaʻa health" — annual_revenue + jobs*10000 + resilience_sum, over planted
 * nodes. Game layer: hewa nodes count revenue at hewa_production_factor (applied
 * OUTSIDE nodeKpis); jobs + resilience count in full for any planted node.
 * @param {object} state
 * @returns {number}
 */
function score(state) {
  const rules = gameRules();
  let revDay = 0, jobs = 0, resil = 0;
  for (const id of Object.keys(state.planted)) {
    const k = nodeKpis(state._nodeById[Number(id)]);
    revDay += k.revenue_day * (state.planted[id].pono ? 1 : rules.hewa_production_factor);
    jobs += k.jobs;
    resil += k.resilience;
  }
  const annual = roundPy(roundPy(revDay, 1) * 365, 2);
  return roundPy(annual + jobs * 10000 + resil, 2);
}

/* ---------------------------------------------------------- serialization -- */

/**
 * Serialize state to a JSON string (deck/hand/discard by card Name; the data
 * lookups are non-enumerable and excluded). Round-trips via deserialize().
 * @param {object} state
 * @returns {string}
 */
function serialize(state) {
  return JSON.stringify({
    v: 1,
    seed: state.seed, rngState: state.rngState,
    moon: state.moon, cycle: state.cycle, playsUsed: state.playsUsed,
    discardsUsed: state.discardsUsed || 0,
    deck: state.deck, hand: state.hand, discard: state.discard,
    planted: state.planted,
    waterCapacity: state.waterCapacity, waterUsed: state.waterUsed,
    season: state.season, crisisArmed: state.crisisArmed, won: state.won,
    log: state.log,
  });
}

/**
 * Rebuild a live state from serialize() output, re-attaching the node/card data.
 * @param {string|object} json serialized state (string or already-parsed object)
 * @param {object[]} nodes DT_SGI_Nodes rows
 * @param {object[]} cards DT_SGI_Cards rows
 * @param {object} [opts] {spec?: calc_spec} — spec calls init() for you (resume path)
 * @returns {object} state
 */
function deserialize(json, nodes, cards, opts) {
  if (opts && opts.spec) init(opts.spec);
  const s = (typeof json === "string") ? JSON.parse(json) : json;
  const state = {
    seed: s.seed >>> 0, rngState: s.rngState | 0,
    moon: s.moon, cycle: s.cycle, playsUsed: s.playsUsed || 0,
    discardsUsed: s.discardsUsed || 0,
    deck: s.deck.slice(), hand: s.hand.slice(), discard: s.discard.slice(),
    planted: JSON.parse(JSON.stringify(s.planted || {})),
    waterCapacity: s.waterCapacity, waterUsed: s.waterUsed,
    season: Object.assign({ revenue: 0, gwt: 0, jobs: 0, yield: 0, fishing: 0 }, s.season),
    crisisArmed: !!s.crisisArmed, won: !!s.won,
    log: (s.log || []).slice(),
  };
  return attachData(state, nodes, cards);
}

/* ------------------------------------------------------------------ export -- */

const api = {
  init: init,
  roundPy: roundPy,
  moonWindow: moonWindow,
  hinaBridgeChance: hinaBridgeChance,
  nodeKpis: nodeKpis,
  kpisAll: kpisAll,
  kpisPlanted: kpisPlanted,
  selftest: selftest,
  newGame: newGame,
  draw: draw,
  canPlay: canPlay,
  play: play,
  malama: malama,
  discardCard: discardCard,
  endMoon: endMoon,
  score: score,
  serialize: serialize,
  deserialize: deserialize,
  mulberry32: mulberry32,
};

if (typeof window !== "undefined") window.SageEngine = api;
else if (typeof globalThis !== "undefined") globalThis.SageEngine = api;
if (typeof module !== "undefined" && module.exports) module.exports = api;

})();
