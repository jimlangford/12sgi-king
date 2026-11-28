/* engine_sim_check.js — SAGE engine regression harness (node js/engine_sim_check.js).
 *
 * Dynamic twin of engine_check.py (which is static/text-only). Verifies the
 * 2026-07-02 review findings stay fixed:
 *   1. parity  — kpisAll() vs data/calc_vectors.json (the 3D harness math)
 *   2. gate    — the N54 synergy gate is SATISFIABLE against the canonical data
 *   3. winnable— a greedy bot actually wins (>=1 across the seed sweep)
 *   4. valve   — discardCard unfreezes a water-stuck full hand (no dead states)
 *   5. crisis  — empty-board Override resolution never logs "0 >= threshold"
 *   6. resume  — serialize/deserialize round-trip incl. discardsUsed + opts.spec
 * Exit 0 = pass. Zero DOM, zero network — pure engine + data files.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const SE = require("./sage_engine.js");

const DATA = path.join(__dirname, "..", "data");
const read = (f) => JSON.parse(fs.readFileSync(path.join(DATA, f), "utf8"));
const nodes = read("DT_SGI_Nodes.json");
const cards = read("DT_SGI_Cards.json");
const spec = read("calc_spec.json");
const vectors = read("calc_vectors.json");
SE.init(spec);

const failures = [];
function check(name, ok, detail) {
  console.log((ok ? "PASS" : "FAIL") + "  " + name + (detail ? " — " + detail : ""));
  if (!ok) failures.push(name + (detail ? " — " + detail : ""));
}

/* 1 — parity */
const st = SE.selftest(nodes, vectors);
check("parity vs sage_calc.py", st.pass && st.count === 54,
  st.count + " nodes, " + st.diffs.length + " diffs");

/* 2 — N54 gate satisfiable: force 4 pono per production zone, N54 in hand */
(function () {
  const g = SE.newGame(nodes, cards, { seed: 7 });
  g.hand = ["Card_N54"];
  g.playsUsed = 0;
  g.planted = {};
  const perZone = { Mauka: 0, Kula: 0, Makai: 0 };
  for (const n of nodes) {
    if (perZone[n.zone] !== undefined && perZone[n.zone] < 4) {
      g.planted[n.id] = { pono: true, plantedMoon: 1, card: "Card_N" + String(n.id).padStart(2, "0") };
      perZone[n.zone] += 1;
    }
  }
  const chk = SE.canPlay(g, "Card_N54");
  check("N54 gate opens at 4/4/4 pono", !!chk.ok, chk.reason || "ok");
  const res = SE.play(g, "Card_N54");
  check("N54 play wins", !!(res.ok && g.won),
    res.ok ? "won=" + g.won : res.reason);
})();

/* helpers for the greedy bot */
function moonDist(a, b) { const d = Math.abs(a - b) % 13; return Math.min(d, 13 - d); }
function ponoNow(card, moon) {
  return card.moon != null && moonDist(moon, card.moon) <= 1;
}

/* 3 — winnability sweep + 4 — no frozen states */
function playout(seed, maxMoons) {
  const g = SE.newGame(nodes, cards, { seed: seed });
  let frozenStreak = 0, maxFrozen = 0;
  for (let m = 0; m < maxMoons && !g.won; m++) {
    let acted = false;
    // plays
    for (let p = 0; p < 8; p++) {
      const playable = g.hand.filter(function (nm) { return SE.canPlay(g, nm).ok; });
      if (!playable.length) break;
      playable.sort(function (a, b) {
        const ca = cards.find(function (c) { return c.Name === a; });
        const cb = cards.find(function (c) { return c.Name === b; });
        const sa = (ca.node === 54 ? 1000 : 0) + (ponoNow(ca, g.moon) ? 10 : 0) + (ca.zone === "Mauka" ? 5 : 0);
        const sb = (cb.node === 54 ? 1000 : 0) + (ponoNow(cb, g.moon) ? 10 : 0) + (cb.zone === "Mauka" ? 5 : 0);
        return sb - sa;
      });
      const r = SE.play(g, playable[0]);
      if (!r.ok) break;
      acted = true;
      if (g.won) break;
    }
    // heals — spend off-moon same-zone cards on hewa nodes
    if (!g.won) {
      for (const id of Object.keys(g.planted)) {
        const pl = g.planted[id];
        if (pl.pono) continue;
        const zone = nodes.find(function (n) { return n.id === Number(id); }).zone;
        const healer = g.hand.find(function (nm) {
          const c = cards.find(function (x) { return x.Name === nm; });
          return c && !c.is_joker && c.zone === zone && !ponoNow(c, g.moon);
        });
        if (healer && SE.malama(g, Number(id), healer).ok) acted = true;
      }
    }
    // valve — when fully stuck, discard the least-useful card
    if (!g.won && !acted && g.hand.length) {
      const candidates = g.hand.filter(function (nm) {
        const c = cards.find(function (x) { return x.Name === nm; });
        return c && c.node !== 54;
      });
      if (candidates.length) {
        candidates.sort(function (a, b) {
          const ca = cards.find(function (c) { return c.Name === a; });
          const cb = cards.find(function (c) { return c.Name === b; });
          return (cb.moon != null ? moonDist(g.moon, cb.moon) : 99) -
                 (ca.moon != null ? moonDist(g.moon, ca.moon) : 99);
        });
        if (SE.discardCard(g, candidates[0]).ok) acted = true;
      }
    }
    frozenStreak = acted ? 0 : frozenStreak + 1;
    if (frozenStreak > maxFrozen) maxFrozen = frozenStreak;
    SE.endMoon(g);
  }
  return { won: g.won, maxFrozen: maxFrozen, moons: g.cycle * 13 + g.moon };
}

(function () {
  let wins = 0, worstFrozen = 0, firstWin = null;
  const SEEDS = 40, MOONS = 260;
  for (let s = 1; s <= SEEDS; s++) {
    const r = playout(s, MOONS);
    if (r.won) { wins++; if (firstWin === null) firstWin = s; }
    if (r.maxFrozen > worstFrozen) worstFrozen = r.maxFrozen;
  }
  check("winnable (greedy bot, " + SEEDS + " seeds x " + MOONS + " moons)", wins >= 1,
    wins + "/" + SEEDS + " wins, first at seed " + firstWin);
  check("no frozen states (discard valve)", worstFrozen <= 1,
    "longest zero-action streak " + worstFrozen + " moons");
})();

/* 4b — the valve API itself: stuck full hand can always discard, limit enforced */
(function () {
  const g = SE.newGame(nodes, cards, { seed: 11 });
  const name = g.hand[0];
  const r1 = SE.discardCard(g, name);
  check("discardCard moves hand -> discard", r1.ok && g.hand.indexOf(name) < 0 &&
    g.discard.indexOf(name) >= 0 && g.discardsUsed === 1);
  const r2 = SE.discardCard(g, g.hand[0]);
  check("discards_per_moon limit enforced", !r2.ok, r2.reason || "");
  SE.endMoon(g);
  check("discardsUsed resets + hand refills at end of moon",
    g.discardsUsed === 0 && g.hand.length === 7,
    "discardsUsed=" + g.discardsUsed + " hand=" + g.hand.length);
})();

/* 5 — crisis with empty board: honest log line */
(function () {
  const g = SE.newGame(nodes, cards, { seed: 13 });
  g.planted = {};
  g.crisisArmed = true;
  const r = SE.endMoon(g);
  const held = r.events.find(function (e) { return e.type === "override_held"; });
  const line = g.log.find(function (l) { return l.indexOf("OVERRIDE") >= 0; }) || "";
  check("empty-board Override resolves honestly",
    !!held && held.empty === true && line.indexOf(">=") < 0 &&
    line.indexOf("nothing planted") >= 0, line);
})();

/* 6 — serialize round-trip incl. discardsUsed + deserialize opts.spec */
(function () {
  const g = SE.newGame(nodes, cards, { seed: 17 });
  SE.play(g, g.hand.find(function (nm) { return SE.canPlay(g, nm).ok; }));
  SE.discardCard(g, g.hand[0]);
  const json = SE.serialize(g);
  const back = SE.deserialize(json, nodes, cards, { spec: spec });
  const same = JSON.stringify(JSON.parse(json)) === JSON.stringify(JSON.parse(SE.serialize(back)));
  check("serialize/deserialize round-trip (with opts.spec)",
    same && back.discardsUsed === g.discardsUsed,
    "discardsUsed=" + back.discardsUsed);
})();

/* verdict */
if (failures.length) {
  console.log("\nFAIL — " + failures.length + " check(s) down:");
  failures.forEach(function (f) { console.log("  - " + f); });
  process.exit(1);
}
console.log("\nPASS — all engine regression checks green");
process.exit(0);
