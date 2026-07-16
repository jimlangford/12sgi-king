/* circle_core.js — the SHARED multiplayer circle client for ALL TribeGameStudios games
   (Jimmy 2026-07-15: "make multiplayer a different module for each game"). Each game ships
   its own thin adapter calling CircleCore.init(config); this core owns the chip, panel,
   turn overlay, kilo-paced polling, and turn posting. Server: /games/api/<game>/* (or a
   legacy apiBase). Feature-detects the King — silent on static hosting. Dynamic values
   enter the DOM via textContent only.
   config = {
     gameId,                 // e.g. "konane"
     apiBase,                // default "/games/api/<gameId>/"
     getState(),             // -> serialized state string
     setState(str),          // apply a received state + redraw
     moverSeat(stateObj),    // -> seat index (0/1/...) whose move it is, or null (adapter posts manually)
     seatLabel(i),           // e.g. "black"/"white"
     watchMs,                // local watch cadence (default 700) when moverSeat is used
     onCircle(active, view)  // optional: adapter reacts to circle state
   } */
(function () {
  'use strict';
  var C = {};
  var cfg = null, me = null, circle = null, pollTimer = null, watchTimer = null;
  var KEY = null;

  function $(s) { return document.querySelector(s); }
  function el(tag, css, text) {
    var e = document.createElement(tag);
    if (css) e.style.cssText = css;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function jget(u) { return fetch(cfg.apiBase + u, { credentials: 'same-origin' }).then(function (r) { return r.json(); }); }
  function jpost(u, b) {
    return fetch(cfg.apiBase + u, { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) })
      .then(function (r) { return r.json(); });
  }
  function store() { try { localStorage.setItem(KEY, JSON.stringify(circle)); } catch (e) {} }
  function loadStored() { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } }

  var BTN = 'background:#1d2a1c;color:#cfe8c8;border:1px solid #3c5a38;border-radius:8px;padding:6px;cursor:pointer;width:100%';

  function chip(txt, onclick) {
    var old = $('#circle-chip'); if (old) old.remove();
    var b = el('button', 'position:fixed;top:8px;right:8px;z-index:900;background:#1d2a1c;color:#cfe8c8;' +
      'border:1px solid #3c5a38;border-radius:14px;padding:5px 12px;font:600 11px system-ui;cursor:pointer', txt);
    b.id = 'circle-chip';
    b.addEventListener('click', onclick);
    document.body.appendChild(b);
  }
  function overlay(msg) {
    unlock();
    var o = el('div', 'position:fixed;inset:0;z-index:880;background:rgba(6,10,6,.82);display:flex;' +
      'align-items:center;justify-content:center;flex-direction:column;gap:10px;color:#e8dfc8;' +
      'font:600 15px system-ui;text-align:center;padding:20px');
    o.id = 'circle-hold';
    o.appendChild(el('div', 'font-size:26px', '🌙'));
    o.appendChild(el('div', '', msg));
    o.appendChild(el('div', 'font-size:11px;color:#9aa88f', 'the circle holds — kilo, and wait for your turn'));
    var watch = el('button', 'margin-top:8px;background:none;border:1px solid #556;color:#99a;' +
      'border-radius:8px;padding:4px 10px;font-size:10px;cursor:pointer', 'watch the board anyway');
    watch.addEventListener('click', function () { o.remove(); });
    o.appendChild(watch);
    document.body.appendChild(o);
  }
  function unlock() { var o = $('#circle-hold'); if (o) o.remove(); }
  function toastish(m) {
    var t = el('div', 'position:fixed;bottom:70px;left:50%;transform:translateX(-50%);z-index:950;' +
      'background:#243020;color:#dfe8cf;border:1px solid #46603c;border-radius:10px;padding:8px 14px;font:12px system-ui', m);
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 4200);
  }

  function panel() {
    var old = $('#circle-panel'); if (old) old.remove();
    var p = el('div', 'position:fixed;top:40px;right:8px;z-index:910;background:#14200f;color:#dfe8cf;' +
      'border:1px solid #3c5a38;border-radius:12px;padding:14px;width:230px;font:12px system-ui');
    p.id = 'circle-panel';
    p.appendChild(el('b', '', cfg.gameId + ' circle'));
    if (circle && circle.id) {
      var info = el('div', 'margin:6px 0');
      info.appendChild(el('span', '', 'code: '));
      info.appendChild(el('b', 'letter-spacing:2px', circle.code || ''));
      info.appendChild(el('div', '', 'players: ' + (circle.players || []).length +
        (cfg.seatLabel ? ' · you: ' + cfg.seatLabel(circle.seat) : '')));
      p.appendChild(info);
      var leave = el('button', BTN + ';background:#2a1d1a;color:#e0c9b8;border-color:#5a463c;margin-top:6px', 'leave the circle');
      leave.addEventListener('click', function () {
        circle = null;
        try { localStorage.removeItem(KEY); } catch (e) {}
        stopTimers(); unlock(); p.remove();
        if (cfg.onCircle) cfg.onCircle(false, null);
        boot();
      });
      p.appendChild(leave);
    } else {
      p.appendChild(el('div', 'margin:6px 0;color:#9aa88f', 'play together — turns pass around the circle'));
      var bnew = el('button', BTN, 'start a circle');
      bnew.addEventListener('click', function () {
        jpost('match/new', {}).then(function (m) {
          if (!m.ok) return toastish(m.error || 'could not start');
          circle = m; store(); p.remove(); enter();
          toastish('circle open — share the code: ' + (m.code || ''));
        });
      });
      p.appendChild(bnew);
      p.appendChild(el('div', 'margin:8px 0 4px', 'or join with a code:'));
      var inp = el('input', 'width:100%;box-sizing:border-box;background:#0d140a;color:#dfe8cf;border:1px solid #3c5a38;' +
        'border-radius:8px;padding:6px;text-transform:uppercase;letter-spacing:3px');
      inp.maxLength = 6;
      p.appendChild(inp);
      var bjoin = el('button', BTN + ';margin-top:6px', 'join');
      bjoin.addEventListener('click', function () {
        jpost('match/join', { code: inp.value || '' }).then(function (m) {
          if (!m.ok) return toastish(m.error || 'could not join');
          circle = m; store(); p.remove(); enter();
        });
      });
      p.appendChild(bjoin);
    }
    document.body.appendChild(p);
    document.addEventListener('click', function close(e) {
      if (!p.contains(e.target) && e.target.id !== 'circle-chip') { p.remove(); document.removeEventListener('click', close); }
    });
  }

  function stopTimers() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    if (watchTimer) { clearInterval(watchTimer); watchTimer = null; }
  }

  function applyRemote(m) {
    circle = m; store();
    if (m.state && cfg.setState) { try { cfg.setState(m.state); } catch (e) {} }
    if (m.your_turn) { unlock(); toastish('your turn rises'); startWatch(); }
    else overlay((cfg.seatLabel ? cfg.seatLabel((m.players || []).indexOf(m.turn_of)) + ' — ' : '') +
                 (m.turn_of || '') + ' plays');
    if (cfg.onCircle) cfg.onCircle(true, m);
  }

  function poll() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function () {
      if (!circle || !circle.id) return;
      jget('match?id=' + encodeURIComponent(circle.id)).then(function (m) {
        if (!m.ok) return;
        if (m.rev !== circle.rev || (m.players || []).length !== (circle.players || []).length) applyRemote(m);
      }).catch(function () {});
    }, 8000);
  }

  // generic local watcher: when it is my circle-turn and the game's own mover flips
  // away from my seat, the move is complete — post it.
  function startWatch() {
    if (!cfg.moverSeat) return;
    if (watchTimer) clearInterval(watchTimer);
    watchTimer = setInterval(function () {
      if (!circle || !circle.your_turn) return;
      var s;
      try { s = cfg.getState(); } catch (e) { return; }
      var obj;
      try { obj = JSON.parse(s); } catch (e) { return; }
      var mover = cfg.moverSeat(obj);
      if (mover !== null && mover !== circle.seat) {
        C.postTurn(s);
      }
    }, cfg.watchMs || 700);
  }

  C.postTurn = function (stateStr) {
    if (!circle || !circle.id) return;
    if (watchTimer) { clearInterval(watchTimer); watchTimer = null; }
    jpost('match/turn', { id: circle.id, rev: circle.rev, state: stateStr }).then(function (m) {
      if (!m.ok) { toastish(m.error || 'the circle did not accept the turn'); startWatch(); return; }
      circle = m; store();
      overlay('turn passed — ' + (m.turn_of || '') + ' plays');
      if (cfg.onCircle) cfg.onCircle(true, m);
    });
  };
  C.inCircle = function () { return !!(circle && circle.id); };
  C.view = function () { return circle; };

  function enter() {
    chip('🌿 circle ' + (circle.code || ''), panel);
    if (circle.your_turn) { unlock(); startWatch(); }
    else overlay((circle.turn_of || '') + ' plays');
    poll();
    if (cfg.onCircle) cfg.onCircle(true, circle);
  }

  function boot() {
    jget('me').then(function (r) {
      if (!r || r.ok !== true) return;
      me = r.logged_in ? r.who : null;
      if (!me) {
        chip('🌿 circle — sign in', function () { location.href = '/login'; });
        return;
      }
      circle = loadStored();
      if (circle && circle.id) {
        jget('match?id=' + encodeURIComponent(circle.id)).then(function (m) {
          if (m.ok) { circle = m; store(); enter(); if (m.state && cfg.setState) { try { cfg.setState(m.state); } catch (e) {} } }
          else { circle = null; chip('🌿 circle', panel); }
        });
      } else {
        chip('🌿 circle', panel);
      }
    }).catch(function () { /* static hosting — solo only */ });
  }

  C.init = function (config) {
    cfg = config || {};
    cfg.apiBase = cfg.apiBase || ('/games/api/' + cfg.gameId + '/');
    KEY = 'circle_' + cfg.gameId + '_v1';
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  };
  window.CircleCore = C;
})();
