/* SAGE Mahjong — pure game core (no DOM). TribeGameStudios · 12sgi.
   108 tiles = 54 SAGE nodes x 2 (the crosswalk equation: 54 = 108/2).
   Dual-environment: browser (window.MahjongCore) + node (module.exports) so the
   logic is unit-testable per the owner's test-each-function rule (Jimmy 2026-07-15). */
(function (root) {
  "use strict";

  // ── SAGE zones + the Mahjong graphic layer (canon: mahjong_crosswalk.html —
  // "We use the Mahjong graphics with ours", Jimmy 2026-07-15) ────────────────
  // Zones/winds: Mauka N01–14 (East) · Kula N15–27 (South) · Makai N28–41 (West)
  // · Universal N42–54 (North). Suits: Bamboo N01–18 · Circles N19–36 ·
  // Characters N37–54, rank = ((n-1) % 9) + 1 — two nodes share each suit-rank
  // face (the 54 = 108/2 equation); the SAGE card art tells them apart.
  function zoneOf(n) {
    if (n <= 14) return "mauka";
    if (n <= 27) return "kula";
    if (n <= 41) return "makai";
    return "universal";
  }

  function windOf(n) {
    return { mauka: "east", kula: "south", makai: "west", universal: "north" }[zoneOf(n)];
  }

  function suitOf(n) {
    if (n <= 18) return "bamboo";
    if (n <= 36) return "circles";
    return "chars";
  }

  function rankOf(n) { return ((n - 1) % 9) + 1; }

  // Unicode mahjong tiles: Chars 🀇=U+1F007, Bamboo 🀐=U+1F010, Circles 🀙=U+1F019
  function glyphOf(n) {
    var base = { chars: 0x1F007, bamboo: 0x1F010, circles: 0x1F019 }[suitOf(n)];
    return String.fromCodePoint(base + rankOf(n) - 1);
  }

  function phaseOf(n) { return n % 2 === 1 ? "ao" : "po"; }

  // ── Layout: 108 aligned-grid slots over 4 layers (60+32+12+4) ─────────────
  // Aligned grid keeps the free-tile rule exact: a slot is FREE when no occupied
  // slot sits directly above it (same col,row on layer+1) and at least one of its
  // same-layer horizontal neighbours (col±1,row) is empty.
  function buildLayout() {
    var slots = [], id = 0;
    function add(layer, col, row) { slots.push({ id: id++, layer: layer, col: col, row: row }); }
    // layer 0: 12 cols x 5 rows = 60
    for (var r = 0; r < 5; r++) for (var c = 0; c < 12; c++) add(0, c, r);
    // layer 1: 8 cols x 4 rows = 32 (centred: cols 2..9, rows 0.5..3.5 -> use rows 0..3 with offset stored)
    for (r = 0; r < 4; r++) for (c = 2; c < 10; c++) add(1, c, r + 0.5);
    // layer 2: 6 cols x 2 rows = 12 (cols 3..8, rows 1.5..2.5)
    for (r = 0; r < 2; r++) for (c = 3; c < 9; c++) add(2, c, r + 1.5);
    // layer 3: 4 cols x 1 row = 4 (cols 4..7, row 2)
    for (c = 4; c < 8; c++) add(3, c, 2);
    return slots; // 60+32+12+4 = 108
  }

  function keyOf(layer, col, row) { return layer + "|" + col + "|" + row; }

  function occupiedKeySet(slots, occupied) {
    var set = {};
    for (var i = 0; i < slots.length; i++)
      if (occupied[slots[i].id]) set[keyOf(slots[i].layer, slots[i].col, slots[i].row)] = true;
    return set;
  }

  // A slot's cover cells on the layer above (aligned grid + our half-row offsets):
  // any occupied slot on layer+1 whose (col,row) box overlaps this slot's box.
  function isCovered(slot, slots, occupied) {
    for (var i = 0; i < slots.length; i++) {
      var s = slots[i];
      if (!occupied[s.id] || s.layer !== slot.layer + 1) continue;
      if (Math.abs(s.col - slot.col) < 1 && Math.abs(s.row - slot.row) < 1) return true;
    }
    return false;
  }

  function isFree(slot, slots, occupied) {
    if (!occupied[slot.id]) return false;
    if (isCovered(slot, slots, occupied)) return false;
    var leftOcc = false, rightOcc = false;
    for (var i = 0; i < slots.length; i++) {
      var s = slots[i];
      if (!occupied[s.id] || s.layer !== slot.layer || s.row !== slot.row) continue;
      if (s.col === slot.col - 1) leftOcc = true;
      if (s.col === slot.col + 1) rightOcc = true;
    }
    return !(leftOcc && rightOcc);
  }

  function freeSlots(slots, occupied) {
    var out = [];
    for (var i = 0; i < slots.length; i++)
      if (isFree(slots[i], slots, occupied)) out.push(slots[i]);
    return out;
  }

  // ── Solvable deal ──────────────────────────────────────────────────────────
  // Simulate a full removal of the board: repeatedly pick two random FREE slots
  // and assign them the next node pair. The removal order we found IS a solution,
  // so the resulting deal is guaranteed solvable. Retries on the rare dead-end.
  function deal(rng) {
    rng = rng || Math.random;
    var slots = buildLayout();
    for (var attempt = 0; attempt < 60; attempt++) {
      var occupied = {}, i;
      for (i = 0; i < slots.length; i++) occupied[slots[i].id] = true;
      var nodes = [];
      for (i = 1; i <= 54; i++) nodes.push(i);
      // shuffle node order so every deal differs
      for (i = nodes.length - 1; i > 0; i--) {
        var j = Math.floor(rng() * (i + 1)), t = nodes[i]; nodes[i] = nodes[j]; nodes[j] = t;
      }
      var assign = {}, ok = true;
      for (var p = 0; p < 54; p++) {
        var free = freeSlots(slots, occupied);
        if (free.length < 2) { ok = false; break; }
        var a = Math.floor(rng() * free.length), b;
        do { b = Math.floor(rng() * free.length); } while (b === a);
        assign[free[a].id] = nodes[p];
        assign[free[b].id] = nodes[p];
        occupied[free[a].id] = false;
        occupied[free[b].id] = false;
      }
      if (!ok) continue;
      var tiles = slots.map(function (s) {
        var nn = assign[s.id];
        return { id: s.id, layer: s.layer, col: s.col, row: s.row,
                 node: nn, zone: zoneOf(nn), suit: suitOf(nn), rank: rankOf(nn),
                 glyph: glyphOf(nn), wind: windOf(nn), phase: phaseOf(nn), removed: false };
      });
      return { slots: slots, tiles: tiles };
    }
    throw new Error("deal: could not generate a solvable board");
  }

  // ── Game-state helpers (tiles carry removed flags) ────────────────────────
  function occFromTiles(tiles) {
    var occ = {};
    for (var i = 0; i < tiles.length; i++) occ[tiles[i].id] = !tiles[i].removed;
    return occ;
  }

  function tileFree(tile, game) {
    return isFree(tile, game.slots, occFromTiles(game.tiles));
  }

  function canMatch(a, b) {
    return a && b && a.id !== b.id && !a.removed && !b.removed && a.node === b.node;
  }

  function applyMatch(game, aId, bId) {
    var a = game.tiles[aId], b = game.tiles[bId];
    if (!canMatch(a, b)) return false;
    if (!tileFree(a, game) || !tileFree(b, game)) return false;
    a.removed = true; b.removed = true;
    return true;
  }

  function findHint(game) {
    var occ = occFromTiles(game.tiles), free = [];
    for (var i = 0; i < game.tiles.length; i++) {
      var t = game.tiles[i];
      if (!t.removed && isFree(t, game.slots, occ)) free.push(t);
    }
    for (i = 0; i < free.length; i++)
      for (var j = i + 1; j < free.length; j++)
        if (free[i].node === free[j].node) return [free[i].id, free[j].id];
    return null;
  }

  function remaining(game) {
    var n = 0;
    for (var i = 0; i < game.tiles.length; i++) if (!game.tiles[i].removed) n++;
    return n;
  }

  // Reshuffle the FACES of the remaining tiles in place (positions keep their
  // occupancy; only which node sits where changes). Tries to leave a move available.
  function shuffleRemaining(game, rng) {
    rng = rng || Math.random;
    var live = game.tiles.filter(function (t) { return !t.removed; });
    if (live.length < 4) return findHint(game) !== null;
    for (var attempt = 0; attempt < 40; attempt++) {
      var faces = live.map(function (t) { return t.node; });
      for (var i = faces.length - 1; i > 0; i--) {
        var j = Math.floor(rng() * (i + 1)), t = faces[i]; faces[i] = faces[j]; faces[j] = t;
      }
      for (i = 0; i < live.length; i++) {
        var f = faces[i];
        live[i].node = f; live[i].zone = zoneOf(f); live[i].suit = suitOf(f);
        live[i].rank = rankOf(f); live[i].glyph = glyphOf(f); live[i].wind = windOf(f);
        live[i].phase = phaseOf(f);
      }
      if (findHint(game)) return true;
    }
    return findHint(game) !== null;
  }

  // Full-solver used by tests: greedily play hints to completion.
  function solve(game) {
    var guard = 0;
    while (remaining(game) > 0 && guard++ < 200) {
      var h = findHint(game);
      if (!h) return false;
      applyMatch(game, h[0], h[1]);
    }
    return remaining(game) === 0;
  }

  var api = { zoneOf: zoneOf, suitOf: suitOf, rankOf: rankOf, glyphOf: glyphOf, windOf: windOf,
              phaseOf: phaseOf, buildLayout: buildLayout, deal: deal, tileFree: tileFree,
              canMatch: canMatch, applyMatch: applyMatch, findHint: findHint,
              remaining: remaining, shuffleRemaining: shuffleRemaining, solve: solve,
              isFree: isFree, freeSlots: freeSlots };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MahjongCore = api;
})(typeof self !== "undefined" ? self : this);
