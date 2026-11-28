/* supporter.js — the Kahu Supporter premium tier, client side (Jimmy 2026-07-15: the beta TESTS the
   functionality of potentially monetizing). serve==charge, education-first: playing + inviting a friend
   stay FREE; this is the optional $5/mo premium that unlocks the research view + a gold ahupuaʻa theme +
   a supporter badge + private circles. Feature-detects the King (silent on static hosting). TEST MODE:
   the checkout is a mock Stripe-test page (no real charge) until a real Stripe test key is added.
   Dynamic values enter the DOM via textContent only. */
(function () {
  'use strict';
  // Tailscale mounts the King at /king (and strips it); loopback serves it at root. Keep our API
  // calls on the King under both by detecting the /king prefix from our own page path.
  var KP = (location.pathname.indexOf('/king/') === 0) ? '/king' : '';
  var API = KP + '/games/api/supporter/';
  var st = null;

  function $(s) { return document.querySelector(s); }
  function el(tag, css, text) {
    var e = document.createElement(tag);
    if (css) e.style.cssText = css;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function jget(u) { return fetch(API + u, { credentials: 'same-origin' }).then(function (r) { return r.json(); }); }
  function jpost(u, b) {
    return fetch(API + u, { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) })
      .then(function (r) { return r.json(); });
  }
  function toast(m) {
    var t = el('div', 'position:fixed;bottom:110px;left:50%;transform:translateX(-50%);z-index:960;' +
      'background:#243020;color:#dfe8cf;border:1px solid #46603c;border-radius:10px;padding:8px 14px;font:12px system-ui', m);
    document.body.appendChild(t); setTimeout(function () { t.remove(); }, 4600);
  }

  // premium unlocks made visible: a gold theme + a supporter badge + a research-view toggle
  function styleOnce() {
    if ($('#kahu-style')) return;
    var s = el('style'); s.id = 'kahu-style';
    s.textContent =
      '.kahu-supporter #topbar,.kahu-supporter #urail>header{box-shadow:inset 0 -2px 0 #e3ad33}' +
      '#kahu-badge{position:fixed;top:8px;left:8px;z-index:901;background:#1a1408;color:#e3ad33;' +
      'border:1px solid #e3ad33;border-radius:12px;padding:4px 10px;font:600 11px system-ui}' +
      '#kahu-cta{position:fixed;top:8px;left:8px;z-index:901;background:#1a1408;color:#e3ad33;' +
      'border:1px solid #6b551f;border-radius:12px;padding:5px 11px;font:600 11px system-ui;cursor:pointer}' +
      '#kahu-research{position:fixed;left:8px;bottom:8px;z-index:901;max-width:280px;background:#0a1a24;' +
      'color:#dfe8cf;border:1px solid #e3ad33;border-radius:10px;padding:10px 12px;font:12px system-ui;display:none}' +
      '.kahu-supporter #kahu-research.open{display:block}';
    document.head.appendChild(s);
  }

  function showCTA() {
    if ($('#kahu-cta') || $('#kahu-badge')) { var o = $('#kahu-cta'); if (o) o.remove(); var b = $('#kahu-badge'); if (b) b.remove(); }
    var c = el('button', '', '✦ Kahu Supporter · $5/mo');
    c.id = 'kahu-cta';
    c.addEventListener('click', openCheckout);
    document.body.appendChild(c);
  }
  function showSupporter() {
    var o = $('#kahu-cta'); if (o) o.remove();
    document.body.classList.add('kahu-supporter');
    if (!$('#kahu-badge')) {
      var b = el('div', '', '✦ Kahu Supporter'); b.id = 'kahu-badge';
      b.title = 'research view'; b.style.cursor = 'pointer';
      b.addEventListener('click', function () { var r = $('#kahu-research'); if (r) r.classList.toggle('open'); });
      document.body.appendChild(b);
    }
    buildResearch();
  }

  // the research/analyst view — the premium "depth" layer: the real per-zone KPI numbers under the play
  function buildResearch() {
    if ($('#kahu-research')) return;
    var r = el('div', '', ''); r.id = 'kahu-research';
    r.appendChild(el('div', 'color:#e3ad33;font-weight:700;margin-bottom:4px', '✦ Research view'));
    var body = el('div', 'font-size:11px;line-height:1.7;color:#cfe8c8');
    body.id = 'kahu-research-body';
    body.textContent = 'the real yield / water / revenue / jobs data under each play — supporter depth.';
    r.appendChild(body);
    document.body.appendChild(r);
    // if the game exposes live KPIs, reflect the ahupuaʻa totals (SAGE calc is authoritative)
    try {
      if (window.SageEngine && window.SAGE_STATE && window.SageEngine.kpisPlanted) {
        var k = window.SageEngine.kpisPlanted(window.SAGE_STATE).ahupuaa_totals;
        body.textContent = 'yield ' + k.yield_lbs_day + ' lbs/day · water ' + k.water_gal_day +
          ' gal · $' + k.revenue_day + '/day · ' + k.jobs + ' jobs (research view)';
      }
    } catch (e) {}
  }

  function openCheckout() {
    jpost('checkout', {}).then(function (j) {
      if (!j.ok) { toast(j.error || 'could not start checkout'); return; }
      // open the (test-mode) checkout page; on success it returns to /sage/?supporter=ok
      location.href = (j.url && j.url.charAt(0) === '/') ? KP + j.url : j.url;
    });
  }

  function refresh() {
    return jget('status').then(function (j) {
      if (!j || j.ok !== true) return null;
      st = j;
      styleOnce();
      if (j.is_supporter) showSupporter(); else if (j.who) showCTA();
      // if logged out, no CTA (the circle chip already prompts sign-in)
      return j;
    }).catch(function () { return null; });
  }

  function boot() {
    // returning from a completed checkout -> confirm + unlock
    try {
      if (new URLSearchParams(location.search).get('supporter') === 'ok') {
        history.replaceState({}, '', location.pathname);
        refresh().then(function (j) { if (j && j.is_supporter) toast('✦ Kahu Supporter unlocked — mahalo!'); });
        return;
      }
    } catch (e) {}
    refresh();
  }
  // expose for game adapters that want to gate a feature
  window.KahuSupporter = { isSupporter: function () { return !!(st && st.is_supporter); }, refresh: refresh };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
