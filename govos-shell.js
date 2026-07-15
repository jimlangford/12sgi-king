/**
 * govOS Shell v2 — shared nav, tenant switcher, search
 * Loaded by every page. Reads data-tenant on <body> or <nav>.
 * API_BASE points to studio-assets service (wired as govOS tenant).
 */
(function () {
  'use strict';

  var API_BASE = 'http://localhost:8108/api/v2';

  /* ── Tenant registry (static fallback if API unavailable) ── */
  var TENANT_REG = {
    'hi-state':   { name: 'Hawaii State',             reports: [['Who governs','lege/legislator_scorecard.html'],['Money behind them','statewide_money_patterns.html'],['Contracts & spending','contracts_state.html'],['Federal dollars','federal_money.html'],['Money × votes','parity_state.html'],['Upcoming agendas','agendas_state.html'],['Charter ↔ Law','crosswalk_state.html'],['Audit balance','audit_balance.html']] },
    'hi-maui':    { name: 'Maui County',               reports: [['Who governs','officials_scorecard.html'],['Money behind them','money_behind_officials.html'],['Contracts & spending','maui_contract_awards.html'],['Federal dollars','federal_money.html'],['Money × votes','contracts_x_donors.html'],['990 Nonprofits','nonprofits_maui.html'],['Subcontractor chain','subcontracts_maui.html'],['Upcoming agendas','agendas_maui.html'],['Meeting minutes','minutes_hi-maui.html'],['Council votes & dissent','council_votes_maui.html'],['Charter ↔ Law','crosswalk_maui.html'],['Audit balance','audit_balance.html']] },
    'hi-hawaii':  { name: 'Hawaii County',             reports: [['Money behind them','statewide_money_patterns.html'],['Contracts & spending','contracts_hawaii.html'],['Federal dollars','federal_money_hawaii.html'],['Upcoming agendas','agendas_hawaii.html'],['Meeting minutes','minutes_hi-hawaii.html'],['Charter ↔ Law','crosswalk_hawaii.html'],['Audit balance','audit_balance.html']] },
    'hi-kauai':   { name: 'Kauaʻi County',             reports: [['Money behind them','statewide_money_patterns.html'],['Contracts & spending','contracts_kauai.html'],['Federal dollars','federal_money_kauai.html'],['Upcoming agendas','agendas_kauai.html'],['Meeting minutes','minutes_hi-kauai.html'],['Charter ↔ Law','crosswalk_kauai.html'],['Audit balance','audit_balance.html']] },
    'hi-honolulu':{ name: 'City & County of Honolulu', reports: [['Money behind them','statewide_money_patterns.html'],['Contracts & spending','contracts_honolulu.html'],['Federal dollars','federal_money_honolulu.html'],['Money × votes','parity_honolulu.html'],['Upcoming agendas','agendas_honolulu.html'],['Meeting minutes','minutes_hi-honolulu.html'],['Charter ↔ Law','crosswalk_honolulu.html'],['Audit balance','audit_balance.html']] },
    'ny':         { name: 'New York',                  reports: [['Money behind them','money_nyc.html'],['Contracts & spending','contracts_nyc.html'],['Money × votes','parity_nyc.html'],['Upcoming agendas','agendas_nyc.html']] },
  };

  /* Report-class routing — on tenant switch, route to same class in new tenant */
  var TCLASS = {
    govern:      { 'hi-maui':'officials_scorecard.html',    'hi-state':'lege/legislator_scorecard.html' },
    money:       { 'hi-maui':'money_behind_officials.html', 'hi-state':'statewide_money_patterns.html', 'hi-hawaii':'statewide_money_patterns.html', 'hi-kauai':'statewide_money_patterns.html', 'hi-honolulu':'statewide_money_patterns.html', 'ny':'money_nyc.html' },
    contracts:   { 'hi-maui':'maui_contract_awards.html',   'hi-state':'contracts_state.html',           'hi-hawaii':'contracts_hawaii.html',           'hi-kauai':'contracts_kauai.html',           'hi-honolulu':'contracts_honolulu.html',           'ny':'contracts_nyc.html' },
    federal:     { 'hi-maui':'federal_money.html',          'hi-state':'federal_money.html',             'hi-hawaii':'federal_money_hawaii.html',        'hi-kauai':'federal_money_kauai.html',        'hi-honolulu':'federal_money_honolulu.html' },
    crossref:    { 'hi-maui':'contracts_x_donors.html',     'hi-state':'parity_state.html',              'hi-honolulu':'parity_honolulu.html',           'ny':'parity_nyc.html' },
    nonprofits:  { 'hi-maui':'nonprofits_maui.html' },
    subcontracts:{ 'hi-maui':'subcontracts_maui.html' },
    agendas:     { 'hi-maui':'agendas_maui.html',           'hi-state':'agendas_state.html',             'hi-hawaii':'agendas_hawaii.html',             'hi-kauai':'agendas_kauai.html',             'hi-honolulu':'agendas_honolulu.html',             'ny':'agendas_nyc.html' },
    minutes:     { 'hi-maui':'minutes_hi-maui.html',                                                     'hi-hawaii':'minutes_hi-hawaii.html',           'hi-kauai':'minutes_hi-kauai.html',           'hi-honolulu':'minutes_hi-honolulu.html' },
    council_votes:{ 'hi-maui':'council_votes_maui.html' },
    charter:     { 'hi-maui':'crosswalk_maui.html',         'hi-state':'crosswalk_state.html',           'hi-hawaii':'crosswalk_hawaii.html',            'hi-kauai':'crosswalk_kauai.html',            'hi-honolulu':'crosswalk_honolulu.html' },
    audit:       { 'hi-maui':'audit_balance.html',          'hi-state':'audit_balance.html',             'hi-hawaii':'audit_balance.html',               'hi-kauai':'audit_balance.html',              'hi-honolulu':'audit_balance.html' },
  };

  /* All pages for search index */
  var PAGE_INDEX = [
    { title:'Officials Scorecard', desc:'Council votes + recusals from the minutes', href:'officials_scorecard.html', tenant:'hi-maui' },
    { title:'Money Behind Officials', desc:'Campaign finance per tracked official', href:'money_behind_officials.html', tenant:'hi-maui' },
    { title:'Maui Contract Awards', desc:'Every public Notice of Award to Maui County', href:'maui_contract_awards.html', tenant:'hi-maui' },
    { title:'Federal Dollars', desc:'Federal contracts + grants landing in Hawaiʻi', href:'federal_money.html', tenant:'hi-maui' },
    { title:'Contracts × Donors', desc:'Contract awardees name-matched to campaign donors', href:'contracts_x_donors.html', tenant:'hi-maui' },
    { title:'Council Votes & Dissent', desc:'Every Maui Council split vote + dissenter words', href:'council_votes_maui.html', tenant:'hi-maui' },
    { title:'Statewide Money Patterns', desc:'Campaign money across all 4 counties + State', href:'statewide_money_patterns.html', tenant:'hi-state' },
    { title:'HI Legislator Scorecard', desc:'Per-member roll-call votes, 2010+', href:'lege/legislator_scorecard.html', tenant:'hi-state' },
    { title:'Upcoming Agendas', desc:"Today's meetings, agenda items, what to ask", href:'agendas_maui.html', tenant:'hi-maui' },
    { title:'Meeting Minutes', desc:'Official record — who moved, who voted, what carried', href:'minutes_hi-maui.html', tenant:'hi-maui' },
    { title:'Audit Balance', desc:'The money×votes equation scorecard', href:'audit_balance.html', tenant:'hi-maui' },
    { title:'County Dashboard', desc:'Coverage map + lens activity + money trail', href:'county_dashboard.html', tenant:'hi-maui' },
    { title:'Charter → Law → Evidence', desc:'12 Stones Charter bound to existing enforceable law', href:'charter_application.html', tenant:'hi-maui' },
    { title:'Aloha ʻĀina', desc:'Food security as land vitality, 57 certified operations', href:'aloha_aina.html', tenant:'hi-maui' },
    { title:'Testify', desc:'How to testify at a public meeting', href:'testify.html', tenant:'hi-maui' },
    { title:'Open Data', desc:'Raw public records behind every dashboard', href:'datasets.html', tenant:'hi-maui' },
    { title:'Oversight: Maui', desc:'Public oversight questions, sourced and framed for review', href:'oversight_hi-maui.html', tenant:'hi-maui' },
    { title:'Oversight: Hawaii State', desc:'Public oversight questions for State of Hawaiʻi', href:'oversight_hi-state.html', tenant:'hi-state' },
    { title:'Wildfire Recovery Watch', desc:'Where the $22M+ Maui wildfire recovery money went', href:'wildfire_recovery_watch.html', tenant:'hi-maui' },
    { title:'Lobby + Money', desc:'Entities that both lobby the State and donate to officials', href:'lobby_money_watch.html', tenant:'hi-maui' },
    { title:'Sunshine Law Watch', desc:'HRS §92-7 meeting notice compliance', href:'sunshine_maui.html', tenant:'hi-maui' },
    { title:'Public Factual Feed', desc:'Curated public-record questions, leak-gated', href:'data/prosecutor_public_feed.json', tenant:'hi-maui' },
  ];

  /* ── Helpers ── */
  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function storedTenant() { try { return localStorage.getItem('govos.tenant'); } catch(e) { return null; } }
  function saveTenant(t) { try { localStorage.setItem('govos.tenant', t); } catch(e) {} }

  /* ── Determine current tenant ── */
  function currentTenant() {
    var nav = qs('.govos-nav');
    var t = storedTenant() || (nav && nav.getAttribute('data-tenant')) || 'hi-maui';
    if (!TENANT_REG[t]) t = 'hi-maui';
    return t;
  }

  /* ── Inject nav HTML if not present ── */
  function ensureNav() {
    if (qs('.govos-nav')) return; // already present (static injection)
    var tenant = currentTenant();
    var reg = TENANT_REG[tenant] || {};
    var el = document.createElement('nav');
    el.className = 'govos-nav';
    el.setAttribute('data-tenant', tenant);
    el.innerHTML = [
      '<a class="gn-brand" href="reports.html"><span class="mk">&#10022;</span><b>govOS</b><span class="sub">Kilo Aupuni</span></a>',
      '<button class="gn-burger" aria-label="Menu">&#9776;</button>',
      '<div class="gn-menu">',
        '<span class="gn-here">viewing: <b>' + (reg.name || tenant) + '</b></span>',
        '<div class="gn-group">',
          '<button class="gn-top">Across govOS <span class="ar">&#9662;</span></button>',
          '<div class="gn-panel">',
            '<a href="jurisdictions.html">All jurisdictions</a>',
            '<a href="datasets.html">Open data</a>',
            '<a href="agenda_explainer.html">Agenda explainer</a>',
            '<a href="sage_bridge.html">Sage</a>',
            '<a href="olelo_glossary.html">&#699;&#332;lelo</a>',
          '</div>',
        '</div>',
        '<a class="gn-lead" href="testify.html">&#9878; Testify</a>',
        '<a class="gn-link" href="request_records.html">Request Records</a>',
        '<a class="gn-cta" href="take_action.html">Take part</a>',
      '</div>',
    ].join('');
    document.body.insertBefore(el, document.body.firstChild);
  }

  /* ── Wire nav interactivity ── */
  function wireNav() {
    var nav = qs('.govos-nav');
    if (!nav) return;
    var burger = qs('.gn-burger', nav);
    if (burger) burger.addEventListener('click', function () { nav.classList.toggle('open'); });
    nav.querySelectorAll('.gn-top').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var grp = btn.parentNode;
        var wasOpen = grp.classList.contains('open');
        nav.querySelectorAll('.gn-group').forEach(function (g) { g.classList.remove('open'); });
        if (!wasOpen) grp.classList.add('open');
      });
    });
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target)) nav.querySelectorAll('.gn-group').forEach(function (g) { g.classList.remove('open'); });
    });
  }

  /* ── Tenant switcher ── */
  function wireTenantSwitcher() {
    var govSel = document.getElementById('tnav-gov');
    var viewSel = document.getElementById('tnav-view');
    var hereEl = qs('.tn-here');
    if (!govSel) return;

    var curPage = window.location.pathname.split('/').pop() || 'index.html';
    var curClass = null;
    Object.keys(TCLASS).forEach(function (cls) {
      Object.keys(TCLASS[cls]).forEach(function (tid) {
        if (TCLASS[cls][tid] === curPage) curClass = cls;
      });
    });

    function fillView(tid) {
      if (!viewSel) return;
      viewSel.innerHTML = '';
      var rs = (TENANT_REG[tid] || {}).reports || [];
      if (!rs.length) {
        var o = document.createElement('option');
        o.textContent = 'overview';
        o.value = 'tenant_' + tid + '.html';
        viewSel.appendChild(o);
        return;
      }
      rs.forEach(function (r) {
        var o = document.createElement('option');
        o.textContent = r[0];
        o.value = r[1];
        if (r[1] === curPage) o.selected = true;
        viewSel.appendChild(o);
      });
    }

    var initTenant = govSel.value || currentTenant();
    fillView(initTenant);

    govSel.addEventListener('change', function () {
      var t = this.value;
      saveTenant(t);
      if (hereEl) hereEl.innerHTML = 'on <b>' + ((TENANT_REG[t] || {}).name || t) + '</b>';
      var navHere = qs('.gn-here b');
      if (navHere) navHere.textContent = (TENANT_REG[t] || {}).name || t;
      if (curClass && TCLASS[curClass] && TCLASS[curClass][t]) {
        location.href = TCLASS[curClass][t];
      } else {
        fillView(t);
      }
    });

    if (viewSel) {
      viewSel.addEventListener('change', function () {
        if (this.value) location.href = this.value;
      });
    }
  }

  /* ── Search ── */
  function wireSearch() {
    var input = document.getElementById('govos-search');
    var results = document.getElementById('govos-search-results');
    if (!input || !results) return;

    input.addEventListener('input', function () {
      var q = this.value.trim().toLowerCase();
      if (!q) { results.classList.remove('open'); return; }
      var hits = PAGE_INDEX.filter(function (p) {
        return p.title.toLowerCase().includes(q) || p.desc.toLowerCase().includes(q);
      }).slice(0, 8);
      if (!hits.length) {
        results.innerHTML = '<span class="search-result">No results</span>';
        results.classList.add('open');
        return;
      }
      results.innerHTML = hits.map(function (p) {
        return '<a class="search-result" href="' + p.href + '"><strong>' + p.title + '</strong>' + p.desc + '</a>';
      }).join('');
      results.classList.add('open');
    });

    document.addEventListener('click', function (e) {
      if (!input.closest('.search-wrap').contains(e.target)) results.classList.remove('open');
    });
  }

  /* ── Load tenants from v2 API (progressive enhancement) ── */
  function loadTenantsFromAPI() {
    var govSel = document.getElementById('tnav-gov');
    if (!govSel) return;
    fetch(API_BASE + '/tenants').then(function (r) { return r.json(); }).then(function (data) {
      var civicTenants = (data.tenants || []).filter(function (t) { return t.kind === 'civic'; });
      if (!civicTenants.length) return;
      var cur = govSel.value;
      govSel.innerHTML = civicTenants.map(function (t) {
        return '<option value="' + t.id + '"' + (t.id === cur ? ' selected' : '') + '>' + t.name + '</option>';
      }).join('');
    }).catch(function () { /* silently fall back to static options */ });
  }

  /* ── DOMContentLoaded bootstrap ── */
  function boot() {
    ensureNav();
    wireNav();
    wireTenantSwitcher();
    wireSearch();
    loadTenantsFromAPI();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

})();
