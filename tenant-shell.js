/**
 * tenant-shell.js — shared shell for ALL tenant pages (studio + civic)
 * Loads from king-bridge API, renders nav, asset tree, character roster.
 * Drop <script src="../tenant-shell.js" data-tenant="film_12stones"></script>
 * on any tenant page and the shell self-assembles from Neo4j.
 */
(function () {
  'use strict';

  var BRIDGE = 'http://localhost:8109/api/v2';

  // ── Canonical tenant registry (static fallback) ───────────────────────────
  var TENANTS = {
    // Films (9)
    film_12stones:       { name:'12 STONES: The Aloha Code',           kind:'film',        render:'photoreal', status:'in_production',               icon:'🎬', color:'#2f74d0' },
    film_mokuula:        { name:'MOKUʻULA: The Awakening',             kind:'film',        render:'photoreal', status:'script_rebuilt',              icon:'🌊', color:'#2f74d0' },
    film_luna:           { name:'LUNA Chronicles',                     kind:'film',        render:'cartoon-3d',status:'trailer_only',               icon:'🌙', color:'#9b59b6' },
    film_keys:           { name:'Keys of the Starforge',               kind:'film',        render:'animated',  status:'storyboarded_beta',           icon:'🗝️', color:'#e67e22' },
    film_seventh_stone:  { name:'Seventh Stone',                       kind:'film',        render:'photoreal', status:'greenlit_treatment',          icon:'🪨', color:'#2f74d0' },
    film_the_movie:      { name:'The Movie — How Would They Feel',     kind:'film',        render:'photoreal', status:'blessing_gated_preproduction', icon:'🎞️', color:'#c0392b' },
    film_willie_k:       { name:'Willie K — William Kahaialiʻi',      kind:'film',        render:'photoreal', status:'forming',                     icon:'🎸', color:'#d4a017' },
    film_wutang:         { name:'SHAOLIN SOVEREIGN',                   kind:'film',        render:'animated',  status:'rd_private',                  icon:'☯️', color:'#8e44ad' },
    film_ka_noho_kaawale:{ name:'Ka Noho Kaʻawale — The Seat We Keep Open', kind:'film', render:'photoreal', status:'designed_producible_now', icon:'🏛️', color:'#2f74d0' },
    // Game (1)
    game_sage:           { name:'Sage Game',                           kind:'game',        render:'cartoon-3d',status:'in_production',               icon:'🎮', color:'#27ae60' },
    // Music Videos (2)
    mv_jimmy_langford:   { name:'Jimmy Langford — Music Videos',       kind:'music_video', render:'photoreal', status:'in_production',               icon:'🎵', color:'#e3ad33' },
    mv_john_saunders_band:{ name:'John Saunders Band — Music Videos', kind:'music_video', render:'photoreal', status:'proposed_internal',           icon:'🎶', color:'#e3ad33' },
    // Civic Studio (1)
    govos:               { name:'govOS Civic Studio',                  kind:'civic',       render:'animated',  status:'in_production',               icon:'⚖️', color:'#16a085' },
    // Civic
    'hi-state':    { name:'Hawaii State',             kind:'civic_gov', icon:'🏛️', color:'#2f74d0' },
    'hi-maui':     { name:'Maui County',              kind:'civic_gov', icon:'🏝️', color:'#16a085' },
    'hi-hawaii':   { name:'Hawaii County',            kind:'civic_gov', icon:'🌋', color:'#c0392b' },
    'hi-kauai':    { name:'Kauaʻi County',            kind:'civic_gov', icon:'🌿', color:'#27ae60' },
    'hi-honolulu': { name:'City & County of Honolulu',kind:'civic_gov', icon:'🏙️', color:'#8e44ad' },
    'ny':          { name:'New York',                 kind:'civic_gov', icon:'🗽', color:'#2f74d0' },
  };

  var LIPSYNC_SKILLS = {
    'restrained-dialogue':  'Restrained Dialogue',
    'mythic-dialogue':      'Mythic Dialogue',
    'ceremonial-speech':    'Ceremonial Speech',
    'rhythmic-dialogue':    'Rhythmic Dialogue',
    'sung-performance':     'Sung Performance',
    'stylized-3d-dialogue': 'Stylized 3D Dialogue',
  };

  var RENDER_LABELS = {
    'photoreal': 'Photoreal · ComfyUI',
    'cartoon-3d': 'Cartoon 3D · Stylized',
    'animated': 'Animated · 2D/3D',
  };

  var STATUS_LABELS = {
    'in_production':               'In Production',
    'script_rebuilt':              'Script Rebuilt',
    'trailer_only':                'Trailer Only',
    'storyboarded_beta':           'Storyboarded',
    'greenlit_treatment':          'Greenlit',
    'blessing_gated_preproduction':'Blessing Gated',
    'forming':                     'Forming',
    'rd_private':                  'R&D Private',
    'designed_producible_now':     'Ready to Produce',
    'proposed_internal':           'Proposed',
  };

  // ── Determine current tenant from page ────────────────────────────────────
  function currentTenantId() {
    // 1. data-tenant on <body>
    var b = document.body.getAttribute('data-tenant');
    if (b && TENANTS[b]) return b;
    // 2. data-tenant on script tag itself
    var scripts = document.querySelectorAll('script[data-tenant]');
    for (var i = 0; i < scripts.length; i++) {
      var t = scripts[i].getAttribute('data-tenant');
      if (t && TENANTS[t]) return t;
    }
    // 3. localStorage
    try { var ls = localStorage.getItem('tenant.current'); if (ls) return ls; } catch(e) {}
    // 4. URL param
    var m = location.search.match(/[?&]tenant=([^&]+)/);
    if (m) return decodeURIComponent(m[1]);
    return null;
  }

  // ── Inject tenant top-bar if not already present ──────────────────────────
  function ensureTenantBar(tenantId) {
    if (document.getElementById('tenant-topbar')) return;
    var t = TENANTS[tenantId] || {};
    var bar = document.createElement('div');
    bar.id = 'tenant-topbar';
    bar.style.cssText = [
      'position:sticky;top:56px;z-index:998;',
      'display:flex;align-items:center;gap:12px;',
      'padding:8px 20px;',
      'background:rgba(11,28,46,0.92);',
      'border-bottom:2px solid ' + (t.color || '#2f74d0') + '44;',
      '-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);',
      'font-family:-apple-system,system-ui,sans-serif;font-size:13px;',
    ].join('');

    var kindLabel = { film:'Film Division', game:'Game Division', music_video:'Music Division', civic:'Civic Division', civic_gov:'Civic Government' }[t.kind] || 'Division';
    var statusLabel = STATUS_LABELS[t.status] || (t.status || '');

    bar.innerHTML = [
      '<span style="font-size:20px;">' + (t.icon || '⭐') + '</span>',
      '<div>',
        '<div style="font-weight:700;color:#eaf2fc;font-size:15px;">' + (t.name || tenantId) + '</div>',
        '<div style="font-size:11px;color:#a7c0dd;letter-spacing:.05em;">' + kindLabel + ' &middot; ' + statusLabel + '</div>',
      '</div>',
      '<div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;" id="tenant-bar-actions">',
        '<a href="' + _landingUrl() + '" style="' + _btnStyle('#2f74d0') + '">← All Divisions</a>',
      '</div>',
    ].join('');
    // Insert after govos-nav if present, else top of body
    var nav = document.querySelector('.govos-nav');
    if (nav && nav.nextSibling) {
      nav.parentNode.insertBefore(bar, nav.nextSibling);
    } else {
      document.body.insertBefore(bar, document.body.firstChild);
    }
    // Async: add action buttons from API
    _loadBarActions(tenantId, bar.querySelector('#tenant-bar-actions'), t);
  }

  function _btnStyle(bg) {
    return [
      'background:' + bg + '22;border:1px solid ' + bg + '55;',
      'color:#eaf2fc;padding:5px 12px;border-radius:7px;',
      'font-size:12px;font-weight:600;text-decoration:none;',
      'font-family:inherit;cursor:pointer;transition:.14s;',
    ].join('');
  }

  function _landingUrl() {
    // Try to find king_landing.html relative to current page
    var depth = location.pathname.split('/').length - 2;
    var prefix = '';
    for (var i = 0; i < depth; i++) prefix += '../';
    return prefix + 'king_landing.html';
  }

  function _loadBarActions(tenantId, container, tenantMeta) {
    // Add render register badge
    if (tenantMeta.render) {
      var badge = document.createElement('span');
      badge.style.cssText = 'background:rgba(227,173,51,.15);border:1px solid rgba(227,173,51,.3);color:#e3ad33;padding:5px 10px;border-radius:7px;font-size:11px;font-family:monospace;';
      badge.textContent = RENDER_LABELS[tenantMeta.render] || tenantMeta.render;
      container.appendChild(badge);
    }
    // Async: load bridge pulse badge
    fetch(BRIDGE + '/bridge/pulse', { signal: AbortSignal.timeout(3000) })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        var p = (d.pulse || {});
        if (p.waiting_owner > 0) {
          var alert = document.createElement('span');
          alert.style.cssText = 'background:rgba(224,92,92,.2);border:1px solid rgba(224,92,92,.4);color:#e05c5c;padding:5px 10px;border-radius:7px;font-size:11px;font-weight:700;';
          alert.textContent = p.waiting_owner + ' awaiting approval';
          container.appendChild(alert);
        }
      })
      .catch(function() {});
  }

  // ── Inject asset panel ────────────────────────────────────────────────────
  function injectAssetPanel(tenantId, characters) {
    if (document.getElementById('tenant-asset-panel')) return;
    if (!characters || !characters.length) return;

    var panel = document.createElement('div');
    panel.id = 'tenant-asset-panel';
    panel.style.cssText = [
      'max-width:1060px;margin:12px auto 0;padding:14px 20px;',
      'background:rgba(22,50,78,.4);border:1px solid rgba(90,151,230,.2);',
      'border-radius:12px;-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);',
      'font-family:-apple-system,system-ui,sans-serif;',
    ].join('');

    // Deduplicate characters
    var seen = {};
    var unique = characters.filter(function(c) {
      if (seen[c.cid]) return false;
      seen[c.cid] = true;
      return true;
    });

    panel.innerHTML = [
      '<div style="font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:#e3ad33;font-weight:700;margin-bottom:10px;">Characters · Neo4j</div>',
      '<div style="display:flex;flex-wrap:wrap;gap:6px;">',
      unique.map(function(c) {
        return '<span style="background:rgba(47,116,208,.12);border:1px solid rgba(90,151,230,.25);color:#a7c0dd;padding:4px 10px;border-radius:6px;font-size:12px;font-family:monospace;">' + (c.cname || c.cid) + '</span>';
      }).join(''),
      '</div>',
    ].join('');

    var bar = document.getElementById('tenant-topbar');
    if (bar && bar.nextSibling) {
      bar.parentNode.insertBefore(panel, bar.nextSibling);
    }
  }

  // ── Inject footer breadcrumb ──────────────────────────────────────────────
  function injectFooterBreadcrumb(tenantId) {
    if (document.getElementById('tenant-breadcrumb')) return;
    var t = TENANTS[tenantId] || {};
    var crumb = document.createElement('div');
    crumb.id = 'tenant-breadcrumb';
    crumb.style.cssText = [
      'max-width:1060px;margin:32px auto 0;padding:14px 20px;',
      'border-top:1px solid rgba(90,151,230,.2);',
      'font-family:ui-monospace,monospace;font-size:11px;color:#6d89ab;',
      'display:flex;gap:16px;flex-wrap:wrap;align-items:center;',
    ].join('');
    var kindLabel = { film:'Film Division', game:'Game Division', music_video:'Music Division', civic:'Civic Studio', civic_gov:'Civic Government' }[t.kind] || '';
    crumb.innerHTML = [
      '<a href="' + _landingUrl() + '" style="color:#5a97e6;text-decoration:none;">12 Stones Global</a>',
      '<span style="color:#1f3d5f;">›</span>',
      '<span>' + kindLabel + '</span>',
      '<span style="color:#1f3d5f;">›</span>',
      '<span style="color:#eaf2fc;">' + (t.name || tenantId) + '</span>',
      '<span style="margin-left:auto;color:#1f3d5f;">Neo4j · ' + tenantId + '</span>',
    ].join('');
    var body = document.body;
    body.appendChild(crumb);
  }

  // ── Main bootstrap ────────────────────────────────────────────────────────
  function boot() {
    var tenantId = currentTenantId();
    if (!tenantId) return;

    try { localStorage.setItem('tenant.current', tenantId); } catch(e) {}

    ensureTenantBar(tenantId);
    injectFooterBreadcrumb(tenantId);

    // Load characters from bridge API
    fetch(BRIDGE + '/bridge/tree', { signal: AbortSignal.timeout(8000) })
      .then(function(r) { return r.json(); })
      .then(function(d) {
        var tree = d.tree || {};
        // Filter characters for this tenant
        var chars = (tree.characters || []).filter(function(c) {
          return !c.tid || c.tid === tenantId;
        });
        if (chars.length) injectAssetPanel(tenantId, chars);
      })
      .catch(function() {
        // Silently degrade — page still works without bridge
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

})();
