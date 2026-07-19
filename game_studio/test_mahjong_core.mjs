// SAGE Mahjong core — function tests (node). Run: node game_studio/test_mahjong_core.mjs
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const M = require("./mahjong_core.js");

let pass = 0, fail = 0;
function t(name, fn) {
  try { fn(); console.log("  PASS", name); pass++; }
  catch (e) { console.log("  FAIL", name, "->", e.message); fail++; }
}
function eq(a, b, msg) { if (a !== b) throw new Error((msg || "") + ` expected ${b}, got ${a}`); }

// deterministic rng for reproducible tests
function seeded(seed) { let s = seed; return () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648; }

t("zoneOf maps all 54 nodes to crosswalk canon (Mauka/Kula/Makai/Universal)", () => {
  eq(M.zoneOf(1), "mauka"); eq(M.zoneOf(14), "mauka");
  eq(M.zoneOf(15), "kula"); eq(M.zoneOf(27), "kula");
  eq(M.zoneOf(28), "makai"); eq(M.zoneOf(41), "makai");
  eq(M.zoneOf(42), "universal"); eq(M.zoneOf(54), "universal");
});

t("suit/rank/glyph/wind follow the crosswalk mahjong-graphics mapping", () => {
  eq(M.suitOf(1), "bamboo"); eq(M.suitOf(18), "bamboo");
  eq(M.suitOf(19), "circles"); eq(M.suitOf(36), "circles");
  eq(M.suitOf(37), "chars"); eq(M.suitOf(54), "chars");
  eq(M.rankOf(1), 1); eq(M.rankOf(9), 9); eq(M.rankOf(10), 1); eq(M.rankOf(54), 9);
  eq(M.glyphOf(1), String.fromCodePoint(0x1F010), "bamboo-1 🀐");
  eq(M.glyphOf(19), String.fromCodePoint(0x1F019), "circles-1 🀙");
  eq(M.glyphOf(37), String.fromCodePoint(0x1F007), "chars-1 🀇");
  eq(M.glyphOf(54), String.fromCodePoint(0x1F00F), "chars-9 🀏");
  eq(M.windOf(1), "east"); eq(M.windOf(20), "south"); eq(M.windOf(30), "west"); eq(M.windOf(50), "north");
});

t("dealt tiles carry the full graphic layer (suit/rank/glyph/wind/phase)", () => {
  const g = M.deal(seeded(11));
  g.tiles.forEach(x => {
    if (x.suit !== M.suitOf(x.node) || x.rank !== M.rankOf(x.node) ||
        x.glyph !== M.glyphOf(x.node) || x.wind !== M.windOf(x.node)) 
      throw new Error("graphic fields inconsistent on N" + x.node);
  });
});

t("buildLayout has exactly 108 slots (54 = 108/2)", () => {
  eq(M.buildLayout().length, 108);
});

t("deal produces 108 tiles = 54 exact pairs", () => {
  const g = M.deal(seeded(42));
  eq(g.tiles.length, 108);
  const count = {};
  g.tiles.forEach(x => count[x.node] = (count[x.node] || 0) + 1);
  eq(Object.keys(count).length, 54, "distinct nodes");
  Object.values(count).forEach(c => eq(c, 2, "copies per node"));
});

t("every deal is solvable (20 seeds, full solver)", () => {
  for (let s = 1; s <= 20; s++) {
    const g = M.deal(seeded(s * 7919));
    if (!M.solve(g)) throw new Error("unsolvable deal at seed " + s);
  }
});

t("free rule: covered tile is not free", () => {
  const g = M.deal(seeded(1));
  // find a layer-0 tile directly covered by a layer-1 tile
  const covered = g.tiles.find(a => a.layer === 0 && g.tiles.some(b =>
    b.layer === 1 && Math.abs(b.col - a.col) < 1 && Math.abs(b.row - a.row) < 1));
  if (!covered) throw new Error("no covered tile found in layout");
  if (M.tileFree(covered, g)) throw new Error("covered tile reported free");
});

t("free rule: middle tile with both neighbours is not free; edge tile is", () => {
  const g = M.deal(seeded(2));
  const row0 = g.tiles.filter(x => x.layer === 0 && x.row === 0).sort((a, b) => a.col - b.col);
  const middle = row0.find(x => x.col > 0 && x.col < 11);
  const edge = row0[0];
  if (M.tileFree(middle, g)) throw new Error("boxed middle tile reported free");
  if (!M.tileFree(edge, g)) throw new Error("row edge tile not free");
});

t("canMatch: same node yes, different node no, self no", () => {
  const g = M.deal(seeded(3));
  const a = g.tiles[0];
  const twin = g.tiles.find(x => x.id !== a.id && x.node === a.node);
  const other = g.tiles.find(x => x.node !== a.node);
  if (!M.canMatch(a, twin)) throw new Error("twin should match");
  if (M.canMatch(a, other)) throw new Error("different node matched");
  if (M.canMatch(a, a)) throw new Error("self matched");
});

t("applyMatch removes exactly the matched free pair, refuses non-free", () => {
  const g = M.deal(seeded(4));
  const h = M.findHint(g);
  if (!h) throw new Error("fresh solvable deal must have a hint");
  eq(M.applyMatch(g, h[0], h[1]), true, "hint pair applies");
  eq(M.remaining(g), 106);
  // refuse a covered (non-free) pair even if faces match
  const g2 = M.deal(seeded(5));
  const buried = g2.tiles.find(a => !M.tileFree(a, g2));
  const twin = g2.tiles.find(x => x.id !== buried.id && x.node === buried.node);
  eq(M.applyMatch(g2, buried.id, twin.id), false, "buried tile must refuse");
  eq(M.remaining(g2), 108);
});

t("findHint returns a free matching pair or null; consistent with solver", () => {
  const g = M.deal(seeded(6));
  const h = M.findHint(g);
  if (!h) throw new Error("hint expected on fresh deal");
  const [a, b] = [g.tiles[h[0]], g.tiles[h[1]]];
  if (a.node !== b.node) throw new Error("hint pair faces differ");
  if (!M.tileFree(a, g) || !M.tileFree(b, g)) throw new Error("hint pair not free");
});

t("shuffleRemaining keeps tile multiset and yields a move", () => {
  const g = M.deal(seeded(7));
  // play 10 pairs then shuffle
  for (let i = 0; i < 10; i++) { const h = M.findHint(g); M.applyMatch(g, h[0], h[1]); }
  const before = {};
  g.tiles.filter(x => !x.removed).forEach(x => before[x.node] = (before[x.node] || 0) + 1);
  const ok = M.shuffleRemaining(g, seeded(99));
  const after = {};
  g.tiles.filter(x => !x.removed).forEach(x => after[x.node] = (after[x.node] || 0) + 1);
  eq(JSON.stringify(after), JSON.stringify(before), "face multiset preserved");
  if (!ok || !M.findHint(g)) throw new Error("no move after shuffle");
});

t("full game to completion via solver leaves 0 tiles", () => {
  const g = M.deal(seeded(8));
  if (!M.solve(g)) throw new Error("solver failed");
  eq(M.remaining(g), 0);
});

console.log(`\n${pass} pass / ${fail} fail`);
process.exit(fail ? 1 : 0);
