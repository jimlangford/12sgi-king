/*
 * Tier 1.5 — Tenant Case Console (audit-quad-os, 2026-07-15).
 *
 * A dependency-free vanilla-JS SPA (matching the repo's apps/* convention) bound to the
 * LIVE tenant service. Real endpoints, verified this session:
 *   GET  {TENANT}/api/v2/cases          -> { cases: [ {id,tenant_id,title,status,notes,created_at,created_by} ] }
 *   POST {TENANT}/api/v2/cases          -> the created case (201); needs scope tenant:write
 *   GET  {TENANT}/api/v2/cases/{id}      -> one case (or 404)
 * Auth: Bearer JWT from the auth service. Owner role sees every tenant; scoped roles see their own.
 *
 * Token sources, in priority order:
 *   1. #token=… in the URL hash (real console OAuth/passkey/magic-link redirect) — captured on load.
 *   2. A manually pasted bearer token.
 *   3. A local "dev sign-in" that mints a session via POST /api/v2/auth/session (local dev only).
 * The token persists under localStorage['king_ownerToken'] — the same key the kickoff spec uses.
 *
 * SECURITY: all case data is rendered via textContent / DOM construction (never innerHTML with
 * interpolated values), so a malicious case title/notes cannot inject markup.
 */
(function () {
  'use strict';

  var AUTH = window.AUTH_SERVICE_URL || 'http://localhost:8101';
  var TENANT = window.TENANT_SERVICE_URL || 'http://localhost:8102';
  var TOKEN_KEY = 'king_ownerToken';
  var STATUSES = ['open', 'in_review', 'awaiting_records', 'closed'];

  // ---- DOM builder (safe by construction) -----------------------------------
  var $ = function (id) { return document.getElementById(id); };

  // el('div', {class:'x', text:'hi', onclick:fn, 'data-id':'7'}, [childNode, 'text'])
  function el(tag, attrs, kids) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null) return;
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;                 // safe: never parsed as HTML
      else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    });
    if (kids != null) (Array.isArray(kids) ? kids : [kids]).forEach(function (c) {
      if (c == null || c === false) return;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return node;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function mount(node) { var v = $('view'); clear(v); v.appendChild(node); }

  var toastTimer = null;
  function toast(msg, kind) {
    var t = $('toast');
    t.textContent = msg;
    t.className = 'show' + (kind ? ' ' + kind : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.className = ''; }, 3600);
  }

  function panel(children) {
    var p = el('div', { class: 'panel' });
    (Array.isArray(children) ? children : [children]).forEach(function (c) { if (c) p.appendChild(c); });
    return p;
  }
  function statePanel(msg, cls) {
    mount(panel(el('div', { class: 'state ' + (cls || ''), text: msg })));
  }
  function badge(status) {
    return el('span', { class: 'badge', 'data-status': status || '', text: status || '—' });
  }

  // ---- token / identity -----------------------------------------------------
  function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
  function setToken(t) {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
    renderIdentity();
  }

  // Display-only decode of the JWT payload (NO verification — the services verify).
  function claims() {
    var t = getToken();
    if (!t || t.indexOf('.') < 0) return null;
    try {
      var p = t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      p += '==='.slice((p.length + 3) % 4);
      return JSON.parse(atob(p));
    } catch (e) { return null; }
  }
  function hasScope(s) {
    var c = claims();
    if (!c) return false;
    var sc = c.scopes || c.scope || [];
    if (typeof sc === 'string') sc = sc.split(/[\s,]+/);
    return sc.indexOf(s) >= 0;
  }
  function isOwner() { var c = claims(); return !!c && c.role === 'Owner'; }

  function renderIdentity() {
    var c = claims();
    var who = $('whoami');
    clear(who);
    if (!c) {
      who.textContent = 'Not signed in';
      $('signout').style.display = 'none';
      $('ownerFilterWrap').style.display = 'none';
      return;
    }
    var exp = c.exp ? new Date(c.exp * 1000) : null;
    var expired = exp && exp.getTime() < Date.now();
    who.appendChild(el('b', { text: c.sub || 'user' }));
    var tail = ' · ' + (c.role || '?') + (c.tenant_id ? ' · ' + c.tenant_id : '');
    who.appendChild(document.createTextNode(tail + ' · '));
    if (expired) who.appendChild(el('span', { style: 'color:var(--bad)', text: 'expired' }));
    else who.appendChild(document.createTextNode(exp ? 'exp ' + exp.toLocaleTimeString() : 'active'));
    $('signout').style.display = '';
    $('ownerFilterWrap').style.display = isOwner() ? '' : 'none';
  }

  // Capture a token handed off in the URL hash (#token=… from the console redirect).
  function captureHashToken() {
    var m = (window.location.hash || '').match(/token=([^&]+)/);
    if (m) {
      setToken(decodeURIComponent(m[1]));
      history.replaceState(null, '', window.location.pathname + window.location.search);
      toast('Signed in from console redirect.', 'ok');
    }
  }

  // ---- fetch wrapper --------------------------------------------------------
  function api(method, base, path, body) {
    var headers = {};
    var token = getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;
    if (body !== undefined) headers['content-type'] = 'application/json';
    return fetch(base + path, {
      method: method, headers: headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }).then(function (r) {
      return r.text().then(function (txt) {
        var data = null;
        try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = { raw: txt }; }
        if (!r.ok) {
          var err = new Error((data && (data.detail || data.message || data.error)) || ('HTTP ' + r.status));
          err.status = r.status; err.data = data;
          throw err;
        }
        return data;
      });
    });
  }
  function friendlyError(err) {
    if (err.status === 401) return 'Not authenticated — sign in again (token missing or expired).';
    if (err.status === 403) return 'Forbidden — your session lacks the required scope for this action.';
    if (err.status === 404) return 'Not found.';
    if (err.message === 'Failed to fetch') return 'Cannot reach the tenant service at ' + TENANT + '.';
    return err.message || 'Request failed.';
  }

  // ---- views ----------------------------------------------------------------
  function loadCases() {
    if (!getToken()) { statePanel('Sign in to load cases.'); return; }
    statePanel('Loading cases…');
    var q = '';
    if (isOwner()) {
      var f = ($('tenantFilter').value || '').trim();
      if (f) q = '?tenant_id=' + encodeURIComponent(f);
    }
    api('GET', TENANT, '/api/v2/cases' + q)
      .then(function (data) { renderCaseList((data && data.cases) || []); })
      .catch(function (err) { statePanel(friendlyError(err), 'err'); });
  }

  function renderCaseList(cases) {
    if (!cases.length) {
      statePanel('No cases yet.' + (hasScope('tenant:write') ? ' Use “+ New case” to create one.' : ''));
      return;
    }
    var thead = el('thead', null, el('tr', null,
      ['Title', 'Status', 'Tenant', 'Created', 'By'].map(function (h) { return el('th', { text: h }); })));
    var tbody = el('tbody');
    cases.forEach(function (c) {
      var created = c.created_at ? new Date(c.created_at).toLocaleString() : '—';
      var tr = el('tr', { 'data-id': c.id, onclick: function () { openCase(c.id); } }, [
        el('td', { text: c.title || '(untitled)' }),
        el('td', null, badge(c.status)),
        el('td', { class: 'mono', text: c.tenant_id || '—' }),
        el('td', { text: created }),
        el('td', { class: 'mono', text: c.created_by || '—' }),
      ]);
      tbody.appendChild(tr);
    });
    var wrap = el('div');
    wrap.appendChild(panel(el('table', null, [thead, tbody])));
    wrap.appendChild(el('p', {
      style: 'color:var(--ink-mute);font-size:12.5px;margin:10px 2px',
      text: cases.length + ' case' + (cases.length === 1 ? '' : 's') + ' · click a row for detail',
    }));
    mount(wrap);
  }

  function openCase(id) {
    statePanel('Loading case…');
    api('GET', TENANT, '/api/v2/cases/' + encodeURIComponent(id))
      .then(renderCaseDetail)
      .catch(function (err) { statePanel(friendlyError(err), 'err'); });
  }

  function renderCaseDetail(c) {
    var created = c.created_at ? new Date(c.created_at).toLocaleString() : '—';
    var dl = el('dl');
    function pair(term, ddChild) { dl.appendChild(el('dt', { text: term })); dl.appendChild(el('dd', null, ddChild)); }
    pair('Case ID', el('span', { class: 'mono', style: 'font-family:var(--mono);font-size:13px', text: c.id }));
    pair('Status', badge(c.status));
    pair('Tenant', document.createTextNode(c.tenant_id || '—'));
    pair('Created', document.createTextNode(created));
    pair('Created by', document.createTextNode(c.created_by || '—'));
    pair('Notes', c.notes
      ? el('div', { class: 'notes', text: c.notes })
      : el('span', { style: 'color:var(--ink-mute)', text: '— none —' }));

    var card = el('div', { class: 'panel p20 detail' }, [
      el('button', { class: 'link', style: 'padding-left:0', text: '← All cases', onclick: loadCases }),
      el('h2', { style: 'margin:6px 0 18px', text: c.title || '(untitled)' }),
      dl,
    ]);
    mount(card);
  }

  // ---- new-case modal -------------------------------------------------------
  function openNewCaseModal() {
    if (!getToken()) { toast('Sign in first.', 'bad'); return; }
    if (!hasScope('tenant:write')) {
      toast('Your session lacks tenant:write — mint a dev session with write scope.', 'bad');
      return;
    }
    var c = claims() || {};
    var tenantVal = c.tenant_id || $('tenantId').value || 'hi-maui';

    var titleIn = el('input', { id: 'm_title', placeholder: 'Short case title' });
    var statusSel = el('select', { id: 'm_status' }, STATUSES.map(function (s) { return el('option', { value: s, text: s }); }));
    // tenant_id is REQUIRED by the API on every create (422 otherwise). An Owner may target any
    // tenant; other create-capable roles (Municipality) are bound to their own — the server enforces
    // the scope — but the field must always be present and sent.
    var tenantIn = el('input', { id: 'm_tenant', value: tenantVal });
    var tenantLabel = isOwner() ? 'Tenant ID (owner override)' : 'Tenant ID';
    var notesIn = el('textarea', { id: 'm_notes', rows: '4', placeholder: 'Optional notes' });
    var saveBtn = el('button', { class: 'primary', text: 'Create case' });

    var fields = [
      el('div', { class: 'field' }, [el('label', { for: 'm_title', text: 'Title' }), titleIn]),
      el('div', { class: 'field' }, [el('label', { for: 'm_status', text: 'Status' }), statusSel]),
      el('div', { class: 'field' }, [el('label', { for: 'm_tenant', text: tenantLabel }), tenantIn]),
      el('div', { class: 'field' }, [el('label', { for: 'm_notes', text: 'Notes' }), notesIn]),
    ];

    var root = $('modal-root');
    var close = function () { clear(root); document.removeEventListener('keydown', onKey); };
    function onKey(e) { if (e.key === 'Escape') close(); }

    var modal = el('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true' }, [
      el('h3', { text: 'New case' }),
    ].concat(fields, [
      el('div', { class: 'modal-actions' }, [
        el('button', { class: 'ghost', text: 'Cancel', onclick: close }),
        saveBtn,
      ]),
    ]));
    var veil = el('div', { class: 'modal-veil', onclick: function (e) { if (e.target === veil) close(); } }, modal);
    clear(root); root.appendChild(veil);
    document.addEventListener('keydown', onKey);
    titleIn.focus();

    saveBtn.addEventListener('click', function () {
      var title = (titleIn.value || '').trim();
      if (!title) { toast('Title is required.', 'bad'); return; }
      var tenant = (tenantIn.value || '').trim();
      if (!tenant) { toast('Tenant ID is required.', 'bad'); return; }
      var payload = { title: title, status: statusSel.value, tenant_id: tenant, notes: (notesIn.value || '').trim() || null };
      saveBtn.disabled = true; saveBtn.textContent = 'Creating…';
      api('POST', TENANT, '/api/v2/cases', payload)
        .then(function (created) {
          close();
          toast('Case created.', 'ok');
          if (created && created.id) openCase(created.id); else loadCases();
        })
        .catch(function (err) {
          toast(friendlyError(err), 'bad');
          saveBtn.disabled = false; saveBtn.textContent = 'Create case';
        });
    });
  }

  // ---- dev session ----------------------------------------------------------
  function createDevSession() {
    var role = $('role').value;
    // Omit `scopes` on purpose: the auth service assigns the role's full DEFAULT scope set
    // (Owner/Municipality include tenant:write and can create cases; Resident/Partner are
    // read-only). Requesting scopes a role isn't granted is rejected as "scopes exceed role
    // permissions", so we let the server — the single source of the role→scope map — decide.
    var body = {
      provider: 'passkey',
      subject: $('subject').value,
      tenant_id: $('tenantId').value,
      role: role,
    };
    api('POST', AUTH, '/api/v2/auth/session', body)
      .then(function (res) {
        if (!res || !res.access_token) throw new Error('No access_token in response');
        setToken(res.access_token);
        toast('Dev session created as ' + role + '.', 'ok');
        loadCases();
      })
      .catch(function (err) { toast('Session failed: ' + friendlyError(err), 'bad'); });
  }

  // ---- wire up --------------------------------------------------------------
  function init() {
    captureHashToken();
    renderIdentity();

    $('createSession').addEventListener('click', createDevSession);
    $('signout').addEventListener('click', function () { setToken(''); statePanel('Signed out.'); });
    $('newCaseBtn').addEventListener('click', openNewCaseModal);
    $('refreshBtn').addEventListener('click', loadCases);
    $('tenantFilter').addEventListener('keydown', function (e) { if (e.key === 'Enter') loadCases(); });

    $('toggleManual').addEventListener('click', function () { $('manualrow').classList.toggle('collapsed'); });
    $('useManual').addEventListener('click', function () {
      var t = ($('manualToken').value || '').trim();
      if (!t) { toast('Paste a token first.', 'bad'); return; }
      setToken(t);
      $('manualrow').classList.add('collapsed');
      $('manualToken').value = '';
      toast('Token set.', 'ok');
      loadCases();
    });

    if (getToken()) loadCases();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
