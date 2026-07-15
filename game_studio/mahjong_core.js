/* SAGE Mahjong — pure game core (no DOM). TribeGameStudios · 12sgi.
   108 tiles = 54 SAGE nodes x 2 (the crosswalk equation: 54 = 108/2).
   Dual-environment: browser (window.MahjongCore) + node (module.exports) so the
   logic is unit-testable per the owner's test-each-function rule (Jimmy 2026-07-15). */
(function (root) {
  "use strict";

  // ── SAGE zones (canon: CLAUDE.md 54-song arc) ─────────────────────────────
  function zoneOf(n) {
    if (n <= 9)  return "fire";     // N01–09 Universal Opening + Fire (Pele/Kāne)
    if (n <= 19) return "mauka";    // N10–19 Mauka (Lono)
    if (n <= 38) return "kula";     // N20–38 Farmlands/Kula (Kāne/Lono)
    if (n <= 52) return "makai";    // N39–52 Makai (Kanaloa)
    if (n === 53) return "override"; // N53 Override Joker
    return "synergy";                // N54 Universal Synergy
  }

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
        return { id: s.id, layer: s.layer, col: s.col, row: s.row,
                 node: assign[s.id], zone: zoneOf(assign[s.id]), removed: false };
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
      for (i = 0; i < live.length; i++) { live[i].node = faces[i]; live[i].zone = zoneOf(faces[i]); }
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

  var api = { zoneOf: zoneOf, buildLayout: buildLayout, deal: deal, tileFree: tileFree,
              canMatch: canMatch, applyMatch: applyMatch, findHint: findHint,
              remaining: remaining, shuffleRemaining: shuffleRemaining, solve: solve,
              isFree: isFree, freeSlots: freeSlots };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MahjongCore = api;
})(typeof self !== "undefined" ? self : this);
