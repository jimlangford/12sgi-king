/* SAGE · the ahupuaʻa game — js/sage_ui.js
   Pure presentation layer. ALL game logic + KPI math lives in js/sage_engine.js
   (window.SageEngine, per the ENGINE CONTRACT). This file never re-implements
   the calculator — it calls the engine and renders state.
   No innerHTML anywhere: safe DOM construction only.
   TribeGameStudios · 12sgi */

(function () {
  'use strict';

  // ---------- constants ----------
  var SAVE_KEY = 'sage_save_v1';
  var SOUND_KEY = 'sage_sound_v1';
  var COACH_KEY = 'sage_coach_v1';
  var VICTORY_ACK_KEY = 'sage_victory_ack_v1';
  var ZONES = ['Mauka', 'Kula', 'Makai'];
  var ZONE_HEX = { Mauka: '#4ade80', Kula: '#fbbf24', Makai: '#38bdf8', Universal: '#ffffff' };
  var ZONE_DESC = {
    Mauka: 'upland — where water begins',
    Kula: 'upcountry — where food grows',
    Makai: 'shoreline — where water returns',
    Universal: 'the whole ahupuaʻa'
  };
  var SUIT_GLYPH = { Diamonds: '♦', Hearts: '♥', Clubs: '♣', Spades: '♠', Joker: '★' };

  // ---------- state ----------
  var S = {
    nodes: [], cards: [], narrative: {},
    nodeById: {}, cardByName: {}, cardByNode: {},
    state: null,
    rules: {},               // spec.game_rules — teaching copy interpolates from here
    selected: null,          // selected hand card Name
    panelNode: null,         // node id shown in detail panel
    panelOpts: null,
    muted: false,
    booted: false,
    victoryAckMem: false     // fallback when localStorage is blocked
  };
  var toastTimer = null;
  var audioCtx = null;

  // ---------- tiny helpers ----------
  function $(sel) { return document.querySelector(sel); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function pad2(id) { return String(id).length < 2 ? '0' + id : String(id); }
  function cardName(entry) { return typeof entry === 'string' ? entry : (entry && entry.Name); }
  function money(x) {
    var n = Number(x) || 0;
    return '$' + n.toLocaleString('en-US', { maximumFractionDigits: 0 });
  }
  function num1(x) {
    var n = Number(x) || 0;
    return n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 1 });
  }
  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + ' → HTTP ' + r.status);
      return r.json();
    });
  }
  // kaulana mahina timing — game rule display only (|Δmoon| ≤ 1, wrapping 13). Not KPI math.
  function timingPono(cardMoon, currentMoon) {
    if (cardMoon == null || currentMoon == null) return false;
    var d = Math.abs(currentMoon - cardMoon);
    return Math.min(d, 13 - d) <= 1;
  }
  function playsLeft() {
    var st = S.state;
    if (!st) return null;
    var keys = ['playsLeft', 'plays_left', 'playsRemaining'];
    for (var i = 0; i < keys.length; i++) if (typeof st[keys[i]] === 'number') return st[keys[i]];
    if (typeof st.playsThisMoon === 'number') return Math.max(0, 3 - st.playsThisMoon);
    if (typeof st.playsUsed === 'number') return Math.max(0, 3 - st.playsUsed);
    if (typeof st.plays === 'number') return Math.max(0, 3 - st.plays);
    return null;
  }
  function logLine(entry) {
    if (typeof entry === 'string') return entry;
    if (entry && typeof entry === 'object') {
      return entry.msg || entry.text || entry.line || entry.event || JSON.stringify(entry);
    }
    return String(entry);
  }

  // ---------- sound (WebAudio two-osc pluck, ~90ms) ----------
  function pluck(freq) {
    if (S.muted) return;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === 'suspended') audioCtx.resume();
      var t = audioCtx.currentTime;
      var g = audioCtx.createGain();
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.14, t + 0.008);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.09);
      g.connect(audioCtx.destination);
      var o1 = audioCtx.createOscillator();
      o1.type = 'triangle'; o1.frequency.value = freq;
      var o2 = audioCtx.createOscillator();
      o2.type = 'sine'; o2.frequency.value = freq * 1.5;
      var g2 = audioCtx.createGain(); g2.gain.value = 0.35;
      o1.connect(g); o2.connect(g2); g2.connect(g);
      o1.start(t); o2.start(t);
      o1.stop(t + 0.1); o2.stop(t + 0.1);
    } catch (e) { /* sound is optional; never break play */ }
  }

  // ---------- toast ----------
  function toast(msg, kind) {
    var t = $('#toast');
    t.textContent = msg;
    t.className = 'mono' + (kind ? ' ' + kind : '');
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 3400);
  }

  // ---------- persistence ----------
  function save() {
    if (!S.state) return;
    try {
      var out = SageEngine.serialize(S.state);
      localStorage.setItem(SAVE_KEY, typeof out === 'string' ? out : JSON.stringify(out));
    } catch (e) { /* storage may be blocked; game still runs */ }
  }
  function tryResume() {
    var raw = null;
    try { raw = localStorage.getItem(SAVE_KEY); } catch (e) { return null; }
    if (!raw) return null;
    try { return SageEngine.deserialize(raw, S.nodes, S.cards); }
    catch (e1) {
      try { return SageEngine.deserialize(JSON.parse(raw), S.nodes, S.cards); }
      catch (e2) { return null; }
    }
  }
  function seedFromParam(v) {
    if (/^-?\d+$/.test(v)) return parseInt(v, 10);
    var h = 2166136261;
    for (var i = 0; i < v.length; i++) { h ^= v.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function freshGame(seed) {
    if (seed == null) seed = (Math.random() * 0x7fffffff) | 0;
    S.state = SageEngine.newGame(S.nodes, S.cards, { seed: seed });
    S.selected = null;
    clearVictoryAck();
    closePanel();
    hideOverlay('#victory');
    save();
    renderAll();
  }

  // ---------- victory acknowledgement (mālama mode guard) ----------
  // The engine keeps state.won true forever (by design — the ✓ stays). The
  // modal must fire only on the win itself, not on every action after
  // "keep playing (mālama mode)" nor on every reload of a won save.
  function victoryAcked() {
    if (S.victoryAckMem) return true;
    try { return localStorage.getItem(VICTORY_ACK_KEY) === '1'; } catch (e) { return false; }
  }
  function ackVictory() {
    S.victoryAckMem = true;
    try { localStorage.setItem(VICTORY_ACK_KEY, '1'); } catch (e) { }
  }
  function clearVictoryAck() {
    S.victoryAckMem = false;
    try { localStorage.removeItem(VICTORY_ACK_KEY); } catch (e) { }
  }
  function dismissVictory() {
    ackVictory();
    hideOverlay('#victory');
  }

  // ---------- engine wrappers (tolerant) ----------
  function engineKpisPlanted() {
    try { return SageEngine.kpisPlanted(S.state); } catch (e) { return null; }
  }
  // Display-only roll-up for a zone band: sums engine nodeKpis rows for planted
  // nodes (hewa at 50% on production fields — game layer, matches endMoon).
  function zoneRoll(zone) {
    var planted = 0, total = 0, yieldSum = 0, jobsSum = 0;
    for (var i = 0; i < S.nodes.length; i++) {
      var n = S.nodes[i];
      if (n.zone !== zone) continue;
      total++;
      var p = S.state && S.state.planted && S.state.planted[n.id];
      if (!p) continue;
      planted++;
      try {
        var k = SageEngine.nodeKpis(n);
        var f = p.pono ? 1 : 0.5;
        yieldSum += (k.yield_lbs_day || 0) * f;
        jobsSum += (k.jobs || 0);
      } catch (e) { /* engine not ready for this row */ }
    }
    return { planted: planted, total: total, yield: yieldSum, jobs: jobsSum };
  }

  // ---------- board (built once, updated per render) ----------
  function buildBoard() {
    var bands = $('#bands');
    clear(bands);
    ZONES.forEach(function (zone) {
      var band = el('section', 'band');
      band.dataset.zone = zone;
      var head = el('header');
      head.appendChild(el('h2', null, zone));
      head.appendChild(el('span', 'desc', ZONE_DESC[zone]));
      var roll = el('span', 'roll mono', '—');
      roll.id = 'roll-' + zone;
      roll.title = 'planted/total · lbs/day (hewa at 50%) · jobs — live zone roll-up from the calculator';
      head.appendChild(roll);
      band.appendChild(head);
      var chips = el('div', 'chips');
      S.nodes.filter(function (n) { return n.zone === zone; })
        .sort(function (a, b) { return a.id - b.id; })
        .forEach(function (n) { chips.appendChild(makeChip(n)); });
      band.appendChild(chips);
      bands.appendChild(band);
    });
    var uchips = $('#uchips');
    clear(uchips);
    S.nodes.filter(function (n) { return n.zone === 'Universal'; })
      .sort(function (a, b) { return a.id - b.id; })
      .forEach(function (n) { uchips.appendChild(makeChip(n)); });
  }
  function makeChip(node) {
    var b = el('button', 'chip');
    b.id = 'chip-' + node.id;
    b.dataset.node = node.id;
    b.style.setProperty('--zc', ZONE_HEX[node.zone] || ZONE_HEX.Universal);
    b.appendChild(el('span', 'hex', '⬡'));
    b.appendChild(el('span', 'nid', 'N' + pad2(node.id)));
    if (node.moon != null) b.appendChild(el('span', 'mn', '🌙' + node.moon));
    b.appendChild(el('span', 'rev', '↺'));
    var card = S.cardByNode[node.id];
    if (card && card.is_joker) {
      b.classList.add('joker');
      b.appendChild(el('span', 'tag', node.id === 53 ? 'override' : 'synergy'));
    }
    b.addEventListener('click', function () { onChipClick(node.id); });
    return b;
  }
  function hasRole(v) { return !!v && v !== '—'; } // '—' = not yet chartered (calc_spec _data_conventions)
  function chipTitle(node) {
    var card = S.cardByNode[node.id] || {};
    var base = 'N' + pad2(node.id) + ' · ' + node.zone +
      (node.moon != null ? ' · 🌙' + node.moon : '') +
      (hasRole(node.governance_role) ? ' · ' + node.governance_role : '');
    if (card.is_joker) {
      if (node.id === 53) return base + ' — Override joker. Never planted: when drawn, a crisis arms; at moon\'s end resilience holds or the weakest planted node falls. Click for details.';
      return base + ' — Generational Leap. Play it from your hand when every zone holds ≥4 pono nodes: aloha as completion. Click for details.';
    }
    var p = S.state && S.state.planted && S.state.planted[node.id];
    if (!p) return base + ' — unplanted. Select its card in the hand, then click here to plant (kanu). Click for the full story.';
    if (p.pono) return base + ' — planted pono, full production. Click for details.';
    // the ↺ badge carries the card's role-shadow text — the reversal teaches
    return base + ' — planted hewa, producing at 50%.' +
      (card.hewa_reversed ? ' ' + card.hewa_reversed + ' ·' : '') +
      ' Fix: discard any ' + node.zone + ' card onto it (mālama). Click for details.';
  }
  function renderChips() {
    S.nodes.forEach(function (n) {
      var b = document.getElementById('chip-' + n.id);
      if (!b) return;
      var p = S.state.planted && S.state.planted[n.id];
      b.classList.toggle('pono', !!(p && p.pono));
      b.classList.toggle('hewa', !!(p && !p.pono));
      var sel = S.selected && S.cardByName[S.selected];
      b.classList.toggle('target', !!(sel && sel.node === n.id));
      b.title = chipTitle(n);
    });
    ZONES.forEach(function (z) {
      var r = zoneRoll(z);
      var span = document.getElementById('roll-' + z);
      if (span) span.textContent = r.planted + '/' + r.total + ' · ' + num1(r.yield) + ' lbs/day · ' + num1(r.jobs) + ' jobs';
    });
    var ur = zoneRoll('Universal');
    var uspan = $('#uroll');
    if (uspan) uspan.textContent = ur.planted + '/' + ur.total;
  }
  function pulseChip(nodeId) {
    var b = document.getElementById('chip-' + nodeId);
    if (!b) return;
    b.classList.remove('pulse');
    void b.offsetWidth; // restart animation
    b.classList.add('pulse');
    setTimeout(function () { b.classList.remove('pulse'); }, 1200);
  }

  // ---------- top bar ----------
  function buildMoonDots() {
    var wrap = $('#moondots');
    clear(wrap);
    for (var m = 1; m <= 13; m++) {
      var d = el('span', 'dot');
      d.title = 'moon ' + m;
      wrap.appendChild(d);
    }
  }
  function renderTop() {
    var st = S.state;
    var dots = $('#moondots').children;
    for (var i = 0; i < dots.length; i++) {
      dots[i].className = 'dot' + (i + 1 === st.moon ? ' cur' : (i + 1 < st.moon ? ' past' : ''));
    }
    var pl = playsLeft();
    $('#moonlabel').textContent = 'moon ' + st.moon + ' of 13 · cycle ' + (st.cycle || 0) +
      (pl != null ? ' · plays ' + pl : '');
    var used = Number(st.waterUsed) || 0;
    var cap = Number(st.waterCapacity) || 0;
    var pct = cap > 0 ? Math.min(100, (used / cap) * 100) : 0;
    var fill = $('#wfill');
    fill.style.width = pct + '%';
    fill.classList.toggle('tight', pct > 85);
    $('#wtext').textContent = num1(used) + ' / ' + num1(cap) + ' gal/day';
    var sn = st.season || {};
    $('#seasonstats').textContent =
      money(sn.revenue) + ' rev · ' + money(sn.gwt) + ' gwt · ' + num1(sn.jobs) + ' jobs';
    var sc = 0;
    try { sc = SageEngine.score(st); } catch (e) { sc = 0; }
    $('#score').textContent = (Number(sc) || 0).toLocaleString('en-US', { maximumFractionDigits: 0 });
    $('#wonmark').hidden = !st.won;
    $('#seedval').textContent = String(st.seed != null ? st.seed : '—');
    $('#crisis-banner').hidden = !st.crisisArmed;
  }

  // ---------- hand ----------
  function rankLabel(card) {
    if (card.is_joker) return '★';
    var r = card.rank;
    if (r === 1) return 'A';
    if (r === 11) return 'J';
    if (r === 12) return 'Q';
    if (r === 13) return 'K';
    return String(r);
  }
  function renderHand() {
    var hand = $('#hand');
    clear(hand);
    var entries = (S.state.hand || []);
    entries.forEach(function (entry, idx) {
      var name = cardName(entry);
      var card = S.cardByName[name];
      if (!card) return;
      var b = el('button', 'card');
      b.dataset.card = name;
      b.style.setProperty('--fh', card.frame_hex || ZONE_HEX[card.zone] || 'var(--line)');
      var art = el('span', 'art');
      art.style.backgroundImage = 'url("assets/cards/thumbs/N' + pad2(card.node) + '.jpg")';
      b.appendChild(art);
      b.appendChild(el('span', 'corner', rankLabel(card) + (SUIT_GLYPH[card.suit] || '')));
      b.appendChild(el('span', 'nid', 'N' + pad2(card.node)));
      if (card.moon != null) b.appendChild(el('span', 'mbadge', '🌙' + card.moon));
      var ponoNow = timingPono(card.moon, S.state.moon);
      if (ponoNow) b.classList.add('pono-now');
      if (S.selected === name) b.classList.add('sel');
      var chk = { ok: true, reason: '' };
      try { chk = SageEngine.canPlay(S.state, name) || chk; } catch (e) { /* engine decides at play time */ }
      if (!chk.ok) b.classList.add('blocked');
      b.title = card.card_name + ' · N' + pad2(card.node) + ' · ' + card.zone +
        (card.moon != null ? ' · 🌙' + card.moon : '') +
        (card.is_joker ? '' : (ponoNow ? ' — on its moon: plants pono' : ' — off its moon: plants hewa (50%)')) +
        (!chk.ok && chk.reason ? ' — ' + chk.reason : '') +
        ' · press ' + (idx + 1) + ' or click to select';
      b.addEventListener('click', function () { onHandClick(name); });
      hand.appendChild(b);
    });
    $('#deckcount').textContent =
      'deck ' + ((S.state.deck || []).length) + ' · discard ' + ((S.state.discard || []).length);
  }

  // ---------- log drawer ----------
  function renderLog() {
    var list = $('#loglist');
    clear(list);
    var log = (S.state.log || []).slice(-200).reverse();
    if (!log.length) {
      list.appendChild(el('div', 'line', 'no events yet — play a card, then end the moon'));
      return;
    }
    log.forEach(function (entry) {
      list.appendChild(el('div', 'line', logLine(entry)));
    });
  }

  // ---------- renderAll ----------
  function renderAll() {
    if (!S.state) return;
    renderTop();
    renderChips();
    renderHand();
    renderLog();
    if (S.panelNode != null && !$('#panel').hidden) renderPanel(S.panelNode, S.panelOpts);
  }
  function afterAction() {
    save();
    renderAll();
    if (S.state.won && !victoryAcked()) showVictory();
  }

  // ---------- selection + actions ----------
  function onHandClick(name) {
    var card = S.cardByName[name];
    if (!card) return;
    if (S.selected === name) {
      S.selected = null;
      closePanel();
      renderChips(); renderHand();
      return;
    }
    S.selected = name;
    renderChips(); renderHand();
    openPanel(card.node, { fromHand: true, cardName: name });
  }
  function onChipClick(nodeId) {
    var node = S.nodeById[nodeId];
    if (!node) return;
    if (S.selected) {
      var card = S.cardByName[S.selected];
      if (card && card.node === nodeId) { tryPlay(S.selected); return; }
      var p = S.state.planted && S.state.planted[nodeId];
      if (card && p && !p.pono && card.zone === node.zone) {
        openPanel(nodeId, { malamaWith: S.selected });
        return;
      }
    }
    openPanel(nodeId);
  }
  function tryPlay(name) {
    var chk;
    try { chk = SageEngine.canPlay(S.state, name); }
    catch (e) { toast('engine error — ' + e.message, 'warn'); return; }
    if (!chk || !chk.ok) {
      toast(chk && chk.reason ? chk.reason : 'cannot play that card now', 'warn');
      return;
    }
    var card = S.cardByName[name];
    var ponoNow = card ? timingPono(card.moon, S.state.moon) : false;
    var res;
    try { res = SageEngine.play(S.state, name); }
    catch (e) { toast('engine error — ' + e.message, 'warn'); return; }
    if (res && res.ok === false) {
      toast(res.reason || 'cannot play that card now', 'warn');
      return;
    }
    S.selected = null;
    if (card && !card.is_joker) {
      pulseChip(card.node);
      pluck(ponoNow ? 523.25 : 392);
      toast(ponoNow
        ? 'planted N' + pad2(card.node) + ' pono — on its moon'
        : 'planted N' + pad2(card.node) + ' hewa — off-moon, producing at 50%. mālama with a ' + card.zone + ' card', ponoNow ? 'gold' : 'warn');
    } else if (card) {
      pluck(659.25);
    }
    afterAction();
  }
  function doMalama(nodeId, discardName) {
    var res;
    try { res = SageEngine.malama(S.state, nodeId, discardName); }
    catch (e) { toast('engine error — ' + e.message, 'warn'); return; }
    if (res && res.ok === false) {
      toast(res.reason || 'cannot mālama that node now', 'warn');
      return;
    }
    S.selected = null;
    pulseChip(nodeId);
    pluck(440);
    toast('mālama — N' + pad2(nodeId) + ' restored pono', 'gold');
    S.panelOpts = null;
    afterAction();
  }
  function doDiscard(name) {
    var res;
    try { res = SageEngine.discardCard(S.state, name); }
    catch (e) { toast('engine error — ' + e.message, 'warn'); return; }
    if (res && res.ok === false) {
      toast(res.reason || 'cannot discard that card now', 'warn');
      return;
    }
    if (S.selected === name) S.selected = null;
    pluck(293.66);
    toast('discarded — the hand refills at end of moon');
    closePanel();
    afterAction();
  }
  function doEndMoon() {
    if (!S.state) return;
    try { SageEngine.endMoon(S.state); }
    catch (e) { toast('engine error — ' + e.message, 'warn'); return; }
    pluck(329.63);
    toast('moon ended — production booked, hand refilled');
    afterAction();
  }

  // ---------- detail panel (P2 education pillar) ----------
  function openPanel(nodeId, opts) {
    S.panelNode = nodeId;
    S.panelOpts = opts || null;
    renderPanel(nodeId, S.panelOpts);
    $('#panel').hidden = false;
    if (window.matchMedia('(max-width: 980px)').matches) $('#scrim').hidden = false;
  }
  function closePanel() {
    $('#panel').hidden = true;
    $('#scrim').hidden = true;
    S.panelNode = null;
    S.panelOpts = null;
  }
  function section(label, textNode) {
    var s = el('div', 'p-sec');
    s.appendChild(el('span', 'eyebrow', label));
    s.appendChild(textNode);
    return s;
  }
  function renderPanel(nodeId, opts) {
    var node = S.nodeById[nodeId];
    var card = S.cardByNode[nodeId];
    if (!node || !card) return;
    var body = $('#panel-body');
    clear(body);
    var p = S.state.planted && S.state.planted[nodeId];
    var zc = ZONE_HEX[node.zone] || ZONE_HEX.Universal;

    var eye = el('div', 'p-eyebrow eyebrow');
    eye.appendChild(el('span', 'gold', 'real practice · real funding pathways'));
    body.appendChild(eye);

    var artwrap = el('div', 'artwrap');
    var img = document.createElement('img');
    img.loading = 'lazy';
    img.alt = card.card_name;
    img.addEventListener('error', function () { clear(artwrap); artwrap.textContent = '⬡'; });
    img.src = 'assets/cards/N' + pad2(nodeId) + '.jpg';
    artwrap.appendChild(img);
    body.appendChild(artwrap);

    var nameRow = el('div', 'p-name', card.card_name);
    nameRow.appendChild(el('span', 'suit',
      (SUIT_GLYPH[card.suit] || '') + ' ' + card.suit + (card.is_joker ? '' : ' · ' + rankLabel(card))));
    body.appendChild(nameRow);
    body.appendChild(el('div', 'p-node',
      'N' + pad2(nodeId) + ' · ' + node.zone + ' · ' + (card.ECardType || '') + ' · ' + (card.ECardRarity || '')));
    if (hasRole(node.governance_role)) body.appendChild(el('div', 'p-role', node.governance_role));

    // status line — blunt, names the fix
    var stCls = 'p-status', stTxt;
    if (card.is_joker) {
      stTxt = nodeId === 53
        ? 'override — the system remembers. resilience holds or the weakest falls.'
        : 'the win condition — every zone ≥4 pono, then play this. aloha as completion.';
    } else if (!p) {
      stTxt = 'unplanted — select its card in the hand, then click the N' + pad2(nodeId) + ' chip to plant (kanu)';
    } else if (p.pono) {
      stCls += ' pono';
      stTxt = 'planted pono' + (p.plantedMoon != null ? ' on moon ' + p.plantedMoon : '') + ' — full production';
    } else {
      stCls += ' hewa';
      stTxt = 'planted hewa — producing at 50%. fix: discard any ' + node.zone + ' card onto this node (mālama)';
    }
    var stEl = el('div', stCls, stTxt);
    stEl.style.setProperty('--zc', zc);
    body.appendChild(stEl);

    // narrative (tolerate missing)
    var narr = S.narrative && S.narrative['N' + pad2(nodeId)];
    if (narr && narr.line) body.appendChild(el('div', 'p-narr', narr.line));

    // pono / hewa readings
    var ph = el('div', 'p-sec');
    ph.appendChild(el('span', 'eyebrow', 'pono · upright'));
    ph.appendChild(el('p', 'up', card.pono_upright));
    var he = el('span', 'eyebrow', 'hewa · reversed');
    he.style.marginTop = '6px';
    ph.appendChild(he);
    ph.appendChild(el('p', 'down', card.hewa_reversed));
    body.appendChild(ph);

    if (card.farm && card.farm !== '—') {
      body.appendChild(section('farm practice', el('p', null, card.farm)));
    }
    if (card.fishing && card.fishing !== '—') {
      body.appendChild(section('fishing', el('p', null, card.fishing)));
    }
    body.appendChild(section('akua · element · kumulipo',
      el('p', 'p-meta', card.akua + ' · ' + card.element + ' · ' + (card.wa_phase || '') +
        (card.kumulipo_wa != null ? ' · wā ' + card.kumulipo_wa : ''))));
    if (node.kaulana_timing) {
      body.appendChild(section('kaulana mahina timing', el('p', 'p-meta', node.kaulana_timing)));
    }
    var grants = node.grant_programs || card.grant_programs || [];
    if (grants.length) {
      var pills = el('div', 'pills');
      grants.forEach(function (g) { pills.appendChild(el('span', 'pill', g)); });
      body.appendChild(section('grant programs — real funding pathways', pills));
    }

    // per-node calculator row (engine math, verbatim)
    try {
      var k = SageEngine.nodeKpis(node);
      body.appendChild(section('calculator row — sage_calc.py parity',
        el('p', 'p-meta', num1(k.yield_lbs_day) + ' lbs/day · ' + num1(k.water_gal_day) + ' gal/day · resil ' +
          num1(k.resilience) + ' · fish ' + num1(k.fishing_lbs_day) + ' lbs/day · ' + money(k.revenue_day) +
          '/day · gwt ' + money(k.gwt_day) + '/day · ' + num1(k.jobs) + ' jobs')));
    } catch (e) { /* engine not ready — panel still educates */ }

    // actions
    var actions = el('div', 'p-actions');
    var inHand = (S.state.hand || []).some(function (e2) { return cardName(e2) === card.Name; });
    if (inHand && !card.is_joker && !p) {
      var ponoNow = timingPono(card.moon, S.state.moon);
      var btn = el('button', 'btn gold',
        '▶ plant N' + pad2(nodeId) + (ponoNow ? ' — pono this moon' : ' — hewa this moon (50%)'));
      btn.title = ponoNow
        ? 'this moon is within one of 🌙' + card.moon + ' — it plants pono, full production'
        : 'this moon misses 🌙' + card.moon + ' — it plants hewa at 50% until you mālama it';
      btn.addEventListener('click', function () { tryPlay(card.Name); });
      actions.appendChild(btn);
    }
    if (inHand && card.is_joker && nodeId === 54) {
      var winBtn = el('button', 'btn gold', '▶ play Generational Leap — aloha as completion');
      winBtn.title = 'playable when every zone holds ≥4 planted pono nodes — the engine will say what is missing';
      winBtn.addEventListener('click', function () { tryPlay(card.Name); });
      actions.appendChild(winBtn);
    }
    // free discard — the pressure valve when water blocks every play
    if (inHand && nodeId !== 54 && typeof SageEngine.discardCard === 'function') {
      var dMax = (S.rules && S.rules.discards_per_moon != null) ? S.rules.discards_per_moon : 1;
      var dLeft = Math.max(0, dMax - ((S.state.discardsUsed | 0)));
      var db = el('button', 'btn', '↺ discard to the pile — ' +
        (dLeft > 0 ? 'free, ' + dLeft + ' left this moon' : 'none left this moon'));
      db.title = 'gives this card to the discard pile as a free action (' + dMax +
        ' per moon). it cycles back through the reshuffle; the hand refills at end of moon. use it when water blocks every play.';
      if (!dLeft) db.disabled = true;
      db.addEventListener('click', function () { doDiscard(card.Name); });
      actions.appendChild(db);
    }
    if (p && !p.pono) {
      var mw = opts && opts.malamaWith;
      if (mw && S.cardByName[mw] && S.cardByName[mw].zone === node.zone) {
        var mb = el('button', 'btn gold', '✓ confirm mālama — discard ' + S.cardByName[mw].card_name);
        mb.title = 'discards the selected ' + node.zone + ' card and flips this node pono';
        mb.addEventListener('click', function () { doMalama(nodeId, mw); });
        actions.appendChild(mb);
      } else {
        // offer any same-zone hand cards as heal choices (tap-only path)
        var healers = (S.state.hand || []).map(cardName).filter(function (nm) {
          var c2 = S.cardByName[nm];
          return c2 && !c2.is_joker && c2.zone === node.zone;
        });
        if (healers.length) {
          healers.forEach(function (nm) {
            var c2 = S.cardByName[nm];
            var hb = el('button', 'btn', 'mālama — discard ' + c2.card_name + ' (N' + pad2(c2.node) + ')');
            hb.title = 'discards this ' + node.zone + ' card to heal N' + pad2(nodeId) + ' back to pono';
            hb.addEventListener('click', function () { openPanel(nodeId, { malamaWith: nm }); });
            actions.appendChild(hb);
          });
        } else {
          actions.appendChild(el('div', 'p-hint',
            'no ' + node.zone + ' cards in hand — draw more at end of moon, then discard one here to heal'));
        }
      }
    }
    body.appendChild(actions);
  }

  // ---------- export KPIs ----------
  function exportKpis() {
    var payload = engineKpisPlanted();
    if (!payload) { toast('export failed — engine could not build the KPI payload', 'warn'); return; }
    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'sage_kpis_game.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
    toast('exported sage_kpis_game.json — projections, assumptions stated', 'gold');
  }

  // ---------- victory ----------
  function vicCell(label, val) {
    var c = el('div', 'cell');
    c.appendChild(el('span', 'eyebrow', label));
    c.appendChild(el('span', 'v', val == null ? '—' : String(val)));
    return c;
  }
  function showVictory() {
    var payload = engineKpisPlanted();
    var v = $('#victory');
    clear(v);
    var t = payload && payload.ahupuaa_totals ? payload.ahupuaa_totals : {};
    var modal = el('div', 'modal');
    modal.appendChild(el('span', 'eyebrow', 'aloha as completion'));
    var h1 = el('h1');
    h1.appendChild(el('span', 'hexmark', '⬡'));
    h1.appendChild(document.createTextNode('the ahupuaʻa is whole'));
    modal.appendChild(h1);
    modal.appendChild(el('p', null,
      'Every zone stands pono and the Generational Leap is played. This is the final report card — the same projection that feeds real grant applications.'));
    if (payload && payload.label) modal.appendChild(el('div', 'vic-label', payload.label));

    var grid = el('div', 'vic-grid');
    grid.appendChild(vicCell('nodes', t.nodes));
    grid.appendChild(vicCell('lbs/day', num1(t.yield_lbs_day)));
    grid.appendChild(vicCell('gal/day', num1(t.water_gal_day)));
    grid.appendChild(vicCell('fish lbs/day', num1(t.fishing_lbs_day)));
    grid.appendChild(vicCell('revenue/day', money(t.revenue_day)));
    grid.appendChild(vicCell('gwt/day', money(t.gwt_day)));
    grid.appendChild(vicCell('jobs', num1(t.jobs)));
    grid.appendChild(vicCell('annual revenue', money(t.annual_revenue)));
    grid.appendChild(vicCell('annual gwt', money(t.annual_gwt)));
    modal.appendChild(grid);

    if (payload && payload.by_zone) {
      var wrap = el('div', 'vic-tablewrap');
      var table = el('table', 'vic');
      var thr = el('tr');
      ['zone', 'nodes', 'lbs/day', 'gal/day', 'fish', 'rev/day', 'gwt/day', 'jobs'].forEach(function (hd) {
        thr.appendChild(el('th', null, hd));
      });
      table.appendChild(thr);
      Object.keys(payload.by_zone).forEach(function (z) {
        var r = payload.by_zone[z];
        var tr = el('tr');
        tr.appendChild(el('td', 'z-' + z, z));
        tr.appendChild(el('td', null, r.nodes != null ? String(r.nodes) : '—'));
        tr.appendChild(el('td', null, num1(r.yield_lbs_day)));
        tr.appendChild(el('td', null, num1(r.water_gal_day)));
        tr.appendChild(el('td', null, num1(r.fishing_lbs_day)));
        tr.appendChild(el('td', null, money(r.revenue_day)));
        tr.appendChild(el('td', null, money(r.gwt_day)));
        tr.appendChild(el('td', null, num1(r.jobs)));
        table.appendChild(tr);
      });
      wrap.appendChild(table);
      modal.appendChild(wrap);
    }

    var row = el('div', 'btnrow');
    var keep = el('button', 'btn gold', 'keep playing (mālama mode)');
    keep.title = 'endless stewardship — the cycle keeps turning';
    keep.addEventListener('click', dismissVictory);
    var exp = el('button', 'btn', '⬡ export KPIs');
    exp.title = 'feeds grant_generate.py — projections, assumptions stated';
    exp.addEventListener('click', exportKpis);
    var ng = el('button', 'btn', 'new game');
    ng.title = 'fresh shuffle, fresh season';
    ng.addEventListener('click', function () { dismissVictory(); newGameFlow(true); });
    row.appendChild(keep); row.appendChild(exp); row.appendChild(ng);
    modal.appendChild(row);

    v.appendChild(modal);
    v.hidden = false;
  }
  function hideOverlay(sel) { var o = $(sel); if (o) o.hidden = true; }

  // ---------- coach (first-run onboarding) ----------
  var COACH_STEPS = [
    { t: 'welcome, kahu', b: 'You steward one ahupuaʻa — mountain to sea — across a 13-moon kaulana mahina cycle. Each card is a real restoration node with real practices and real funding pathways. Play a card to plant (kanu) its ground. Up to 3 plays per moon, plus 1 free discard when the hand is stuck.' },
    { t: 'plant on the moon', b: 'Every card carries a moon 🌙. Plant within one moon of it and the node goes in pono — full production, gold flash. Miss the window and it plants hewa, producing at half. Heal a hewa node by discarding any same-zone card onto it — mālama.' },
    { t: 'water flows mauka to makai', b: 'The ahupuaʻa starts with 500 gal/day. Kula and Makai plantings draw water — Mauka plants draw none (upland forest catches rain) and each adds +400 gal/day of watershed capacity. Plant the uplands first; the rest follows. Watch the 💧 bar.' },
    { t: 'win by synergy', b: 'Grow at least 4 pono nodes in every zone, then play the Generational Leap joker — aloha as completion. Beware the Override joker: when drawn, resilience holds or the weakest planted node falls. There is no hard loss — the score is the health of the land.' }
  ];
  // Interpolate the teaching numbers from the fetched calc_spec so a future
  // rebalance can never leave the copy stale (2026-07-02 review: the UI taught
  // +200 while the engine paid +400).
  function applyRuleCopy(gr) {
    S.rules = gr || {};
    var base = S.rules.water_base_capacity != null ? S.rules.water_base_capacity : 500;
    var bonus = S.rules.mauka_watershed_bonus != null ? S.rules.mauka_watershed_bonus : 400;
    var plays = S.rules.plays_per_moon != null ? S.rules.plays_per_moon : 3;
    var dpm = S.rules.discards_per_moon != null ? S.rules.discards_per_moon : 1;
    COACH_STEPS[0].b = 'You steward one ahupuaʻa — mountain to sea — across a 13-moon kaulana mahina cycle. Each card is a real restoration node with real practices and real funding pathways. Play a card to plant (kanu) its ground. Up to ' + plays + ' plays per moon, plus ' + dpm + ' free discard' + (dpm === 1 ? '' : 's') + ' when the hand is stuck.';
    COACH_STEPS[2].b = 'The ahupuaʻa starts with ' + base + ' gal/day. Kula and Makai plantings draw water — Mauka plants draw none (upland forest catches rain) and each adds +' + bonus + ' gal/day of watershed capacity. Plant the uplands first; the rest follows. Watch the 💧 bar.';
    var waterEl = document.querySelector('#topbar .water');
    if (waterEl) {
      waterEl.title = 'ahupuaʻa water budget — Kula and Makai plantings draw from it; Mauka plants draw none (upland forest catches rain) and each adds +' + bonus + ' gal/day of watershed capacity';
    }
  }
  var coachIdx = 0;
  function showCoach() {
    coachIdx = 0;
    renderCoach();
    $('#coach').hidden = false;
  }
  function renderCoach() {
    var c = $('#coach');
    clear(c);
    var s = COACH_STEPS[coachIdx];
    var modal = el('div', 'modal');
    modal.appendChild(el('span', 'eyebrow', 'how to play · ' + (coachIdx + 1) + ' of ' + COACH_STEPS.length));
    modal.appendChild(el('h1', null, s.t));
    modal.appendChild(el('p', null, s.b));
    var dots = el('div', 'coach-dots');
    COACH_STEPS.forEach(function (_, i) { dots.appendChild(el('span', i === coachIdx ? 'cur' : '')); });
    modal.appendChild(dots);
    var row = el('div', 'btnrow');
    if (coachIdx > 0) {
      var back = el('button', 'btn', 'back');
      back.addEventListener('click', function () { coachIdx--; renderCoach(); });
      row.appendChild(back);
    }
    var next = el('button', 'btn gold', coachIdx === COACH_STEPS.length - 1 ? 'begin' : 'next');
    next.addEventListener('click', function () {
      if (coachIdx === COACH_STEPS.length - 1) { dismissCoach(); } else { coachIdx++; renderCoach(); }
    });
    row.appendChild(next);
    var skip = el('button', 'btn', 'skip');
    skip.addEventListener('click', dismissCoach);
    row.appendChild(skip);
    modal.appendChild(row);
    c.appendChild(modal);
  }
  function dismissCoach() {
    $('#coach').hidden = true;
    try { localStorage.setItem(COACH_KEY, 'done'); } catch (e) { }
  }

  // ---------- selftest (3D parity harness) ----------
  function runSelftest() {
    var banner = $('#selftest-banner');
    banner.hidden = false;
    banner.className = '';
    banner.textContent = 'parity — running vs data/calc_vectors.json …';
    fetchJson('data/calc_vectors.json').then(function (vectors) {
      var r = SageEngine.selftest(S.nodes, vectors);
      clear(banner);
      if (r && r.pass) {
        banner.className = 'ok';
        banner.textContent = 'parity ✓ ' + (r.count != null ? r.count : S.nodes.length) + '/' + S.nodes.length + ' vs sage_calc.py';
      } else {
        banner.className = 'fail';
        var diffs = (r && r.diffs) || [];
        banner.appendChild(document.createTextNode(
          'parity ✗ ' + diffs.length + ' diff' + (diffs.length === 1 ? '' : 's') +
          ' vs sage_calc.py — fix js/sage_engine.js rounding (half-even, not Math.round)'));
        var list = el('div', 'difflist');
        diffs.slice(0, 40).forEach(function (d) {
          list.appendChild(el('div', null,
            'N' + pad2(d.node) + ' ' + d.field + ' — ours ' + d.ours + ' · truth ' + d.truth));
        });
        if (diffs.length > 40) list.appendChild(el('div', null, '… +' + (diffs.length - 40) + ' more'));
        banner.appendChild(list);
      }
    }).catch(function (e) {
      banner.className = 'fail';
      banner.textContent = 'selftest could not run — ' + e.message + ' (serve from app/sage; vectors at data/calc_vectors.json)';
    });
  }

  // ---------- new game flow (two-step confirm) ----------
  var newArmed = false;
  function newGameFlow(force) {
    var btn = $('#btn-new');
    if (!force && !newArmed) {
      newArmed = true;
      btn.textContent = 'sure? click again';
      btn.classList.add('armed');
      setTimeout(function () {
        newArmed = false;
        btn.textContent = 'new game';
        btn.classList.remove('armed');
      }, 3000);
      return;
    }
    newArmed = false;
    btn.textContent = 'new game';
    btn.classList.remove('armed');
    try { localStorage.removeItem(SAVE_KEY); } catch (e) { }
    var params = new URLSearchParams(location.search);
    var sp = params.get('seed');
    freshGame(sp != null && sp !== '' && force !== true ? seedFromParam(sp) : null);
    toast('new game — seed ' + S.state.seed);
  }

  // ---------- sound toggle ----------
  function applySoundButton() {
    var b = $('#btn-sound');
    b.textContent = S.muted ? '🔇' : '🔊';
    b.title = S.muted
      ? 'sound off — click for a small pluck on planting'
      : 'sound on — a small WebAudio pluck on plant and mālama. click to mute';
  }
  function toggleSound() {
    S.muted = !S.muted;
    try { localStorage.setItem(SOUND_KEY, S.muted ? 'off' : 'on'); } catch (e) { }
    applySoundButton();
    if (!S.muted) pluck(523.25);
  }

  // ---------- keyboard ----------
  function onKey(ev) {
    if (ev.target && /INPUT|TEXTAREA|SELECT/.test(ev.target.tagName)) return;
    if (ev.key === 'Escape') {
      if (!$('#coach').hidden) { dismissCoach(); return; }
      if (!$('#victory').hidden) { dismissVictory(); return; }
      if (!$('#panel').hidden) { closePanel(); return; }
      if ($('#logdrawer').classList.contains('open')) { $('#logdrawer').classList.remove('open'); return; }
      if (S.selected) { S.selected = null; renderChips(); renderHand(); }
      return;
    }
    if (!S.state || !S.booted) return;
    if (!$('#coach').hidden || !$('#victory').hidden) return;
    if (ev.key >= '1' && ev.key <= '7') {
      var idx = Number(ev.key) - 1;
      var entry = (S.state.hand || [])[idx];
      if (entry) onHandClick(cardName(entry));
      return;
    }
    if (ev.key === 'e' || ev.key === 'E') doEndMoon();
  }

  // ---------- fatal status (blunt, names the fix) ----------
  function fatal(msg, fix) {
    var f = $('#fatal');
    clear(f);
    var modal = el('div', 'modal');
    modal.appendChild(el('span', 'eyebrow', 'sage · status'));
    modal.appendChild(el('h1', null, 'cannot start'));
    modal.appendChild(el('p', null, msg));
    modal.appendChild(el('p', null, fix));
    f.appendChild(modal);
    f.hidden = false;
  }

  // ---------- boot ----------
  function boot() {
    if (!window.SageEngine) {
      fatal('engine missing — window.SageEngine is not defined.',
        'fix: ensure js/sage_engine.js exists and loads before js/sage_ui.js, then reload.');
      return;
    }
    Promise.all([
      fetchJson('data/DT_SGI_Nodes.json'),
      fetchJson('data/DT_SGI_Cards.json'),
      fetchJson('data/calc_spec.json'),
      fetchJson('data/node_narrative.json').catch(function () { return {}; })
    ]).then(function (res) {
      S.nodes = res[0];
      S.cards = res[1];
      var spec = res[2];
      S.narrative = res[3] || {};
      S.nodes.forEach(function (n) { S.nodeById[n.id] = n; });
      S.cards.forEach(function (c) { S.cardByName[c.Name] = c; S.cardByNode[c.node] = c; });
      if (typeof SageEngine.init === 'function') SageEngine.init(spec);
      applyRuleCopy(spec && spec.game_rules);

      buildMoonDots();
      buildBoard();

      // sound pref
      var snd = null;
      try { snd = localStorage.getItem(SOUND_KEY); } catch (e) { }
      S.muted = snd === 'off';
      applySoundButton();

      // resume or new
      var params = new URLSearchParams(location.search);
      var resumed = tryResume();
      if (resumed) {
        S.state = resumed;
        toast('resumed — moon ' + S.state.moon + ' of 13 · cycle ' + (S.state.cycle || 0));
      } else {
        var sp = params.get('seed');
        freshGame(sp != null && sp !== '' ? seedFromParam(sp) : null);
      }
      S.booted = true;
      renderAll();
      // a won save reopens the report card only until it has been acknowledged
      if (S.state && S.state.won && !victoryAcked()) showVictory();

      // selftest path
      if (params.get('selftest') === '1') runSelftest();

      // first-run coach
      var seen = null;
      try { seen = localStorage.getItem(COACH_KEY); } catch (e) { }
      if (seen !== 'done') showCoach();
    }).catch(function (e) {
      fatal('data missing — ' + e.message,
        'fix: serve from app/sage with any static server (e.g. python -m http.server) — fetch() cannot read data/*.json over file://.');
    });
  }

  // ---------- wire static controls ----------
  function wire() {
    $('#btn-end').addEventListener('click', doEndMoon);
    $('#btn-export').addEventListener('click', exportKpis);
    $('#btn-new').addEventListener('click', function () { newGameFlow(false); });
    $('#btn-sound').addEventListener('click', toggleSound);
    $('#btn-log').addEventListener('click', function () { $('#logdrawer').classList.toggle('open'); });
    $('#btn-help').addEventListener('click', showCoach);
    $('#log-close').addEventListener('click', function () { $('#logdrawer').classList.remove('open'); });
    $('#panel-close').addEventListener('click', closePanel);
    $('#scrim').addEventListener('click', closePanel);
    document.addEventListener('keydown', onKey);
    window.addEventListener('beforeunload', save);
  }

  document.addEventListener('DOMContentLoaded', function () {
    wire();
    boot();
  });

  // expose a small debug handle (read-only intent)
  window.SageUI = { state: function () { return S.state; }, render: renderAll };
})();
