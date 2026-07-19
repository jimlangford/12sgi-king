/*
 * Tier 1.6 — Admin Console (audit-quad-os, 2026-07-15).
 *
 * Dependency-free vanilla-JS SPA (apps/* convention). Owner-facing admin surface with 3 views:
 *   · Service health  — GET {HEALTH}/api/v1/health  (public; aggregate {status, services:{name:{ok,msg}}})
 *   · Owner allowlist — GET {AUTH}/api/v2/auth/owner/allowlist  (owner-gated, READ-ONLY)
 *   · Auth activity   — honest current state of audit events (logged, not yet a queryable store)
 *
 * Token sources (same as the tenant console): #token=… redirect capture, manual paste, or a local
 * dev sign-in. Persisted under localStorage['king_ownerToken']. All dynamic values are rendered via
 * textContent / DOM construction — never innerHTML with interpolated data.
 */
(function () {
  'use strict';

  var AUTH = window.AUTH_SERVICE_URL || 'http://localhost:8101';
  var HEALTH = window.HEALTH_SERVICE_URL || 'http://localhost:8106';
  var TOKEN_KEY = 'king_ownerToken';
  var activeTab = 'health';

  // ---- safe DOM builder -----------------------------------------------------
  var $ = function (id) { return document.getElementById(id); };
  function el(tag, attrs, kids) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null) return;
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    });
    if (kids != null) (Array.isArray(kids) ? kids : [kids]).forEach(function (c) {
      if (c == null || c === false) return;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return node;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function mount(n) { var v = $('view'); clear(v); v.appendChild(n); }
  function panel(kids) { return el('div', { class: 'panel p20' }, kids); }

  var toastTimer = null;
  function toast(msg, kind) {
    var t = $('toast'); t.textContent = msg; t.className = 'show' + (kind ? ' ' + kind : '');
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.className = ''; }, 3600);
  }

  // ---- token / identity -----------------------------------------------------
  function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }
  function setToken(t) { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); renderIdentity(); }
  function claims() {
    var t = getToken();
    if (!t || t.indexOf('.') < 0) return null;
    try {
      var p = t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      p += '==='.slice((p.length + 3) % 4);
      return JSON.parse(atob(p));
    } catch (e) { return null; }
  }
  function isOwner() { var c = claims(); return !!c && c.role === 'Owner'; }
  function renderIdentity() {
    var c = claims(), who = $('whoami'); clear(who);
    if (!c) { who.textContent = 'Not signed in'; $('signout').style.display = 'none'; return; }
    var exp = c.exp ? new Date(c.exp * 1000) : null;
    var expired = exp && exp.getTime() < Date.now();
    who.appendChild(el('b', { text: c.sub || 'user' }));
    who.appendChild(document.createTextNode(' · ' + (c.role || '?') + ' · '));
    if (expired) who.appendChild(el('span', { style: 'color:var(--bad)', text: 'expired' }));
    else who.appendChild(document.createTextNode(exp ? 'exp ' + exp.toLocaleTimeString() : 'active'));
    $('signout').style.display = '';
  }
  function captureHashToken() {
    var m = (window.location.hash || '').match(/token=([^&]+)/);
    if (m) { setToken(decodeURIComponent(m[1])); history.replaceState(null, '', window.location.pathname + window.location.search); toast('Signed in from console redirect.', 'ok'); }
  }

  // ---- fetch ----------------------------------------------------------------
  function api(method, base, path, auth) {
    var headers = {};
    if (auth && getToken()) headers['Authorization'] = 'Bearer ' + getToken();
    return fetch(base + path, { method: method, headers: headers }).then(function (r) {
      return r.text().then(function (txt) {
        var data = null; try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = { raw: txt }; }
        if (!r.ok) { var err = new Error((data && (data.detail || data.message)) || ('HTTP ' + r.status)); err.status = r.status; throw err; }
        return data;
      });
    });
  }
  function friendlyError(err) {
    if (err.status === 401) return 'Not authenticated — sign in with an Owner session.';
    if (err.status === 403) return 'Owner role required to view this.';
    if (err.message === 'Failed to fetch') return 'Cannot reach the service (same-origin/CORS or service down).';
    return err.message || 'Request failed.';
  }
  function statePanel(msg, cls) { mount(el('div', { class: 'panel' }, el('div', { class: 'state ' + (cls || ''), text: msg }))); }

  // ---- view: service health -------------------------------------------------
  function viewHealth() {
    statePanel('Loading service health…');
    api('GET', HEALTH, '/api/v1/health', false)
      .then(function (data) {
        var overall = (data && data.status) || 'unknown';
        var pillCls = overall === 'ok' || overall === 'healthy' ? 'ok' : (overall === 'degraded' ? 'degraded' : 'down');
        var services = (data && data.services) || {};
        var grid = el('div', { class: 'hgrid' });
        Object.keys(services).sort().forEach(function (name) {
          var s = services[name] || {};
          var dotCls = s.ok === true ? 'ok' : (s.ok === false ? 'bad' : 'na');
          var msg = s.msg || (s.ok === true ? 'healthy' : s.ok === false ? 'down' : 'n/a');
          grid.appendChild(el('div', { class: 'hcard' }, [
            el('span', { class: 'dot ' + dotCls }),
            el('div', null, [el('div', { class: 'n', text: name }), el('div', { class: 'm', text: msg })]),
          ]));
        });
        var ts = data && data.timestamp ? new Date(data.timestamp).toLocaleString() : '';
        mount(el('div', null, [
          el('div', { class: 'status-line' }, [
            el('span', { class: 'pill ' + pillCls, text: overall }),
            el('span', { style: 'color:var(--ink-mute);font-size:12.5px', text: ts ? 'as of ' + ts : '' }),
          ]),
          panel(grid),
        ]));
      })
      .catch(function (err) { statePanel(friendlyError(err), 'err'); });
  }

  // ---- view: owner allowlist ------------------------------------------------
  function viewAllowlist() {
    if (!getToken()) { statePanel('Sign in with an Owner session to view the allowlist.'); return; }
    if (!isOwner()) { statePanel('Owner role required to view the allowlist.', 'err'); return; }
    statePanel('Loading allowlist…');
    api('GET', AUTH, '/api/v2/auth/owner/allowlist', true)
      .then(function (data) {
        var groups = [
          ['GitHub logins', data.github_logins],
          ['Google emails', data.google_emails],
          ['Passkey emails', data.passkey_emails],
          ['Magic-link emails', data.magic_emails],
        ];
        var body = el('div');
        groups.forEach(function (g) {
          var list = g[1] || [];
          var chips = el('div', { class: 'chips' });
          if (!list.length) chips.appendChild(el('span', { style: 'color:var(--ink-mute);font-size:12.5px', text: '— none —' }));
          list.forEach(function (v) { chips.appendChild(el('span', { class: 'chip', text: v })); });
          body.appendChild(el('div', { class: 'al-group' }, [el('h4', { text: g[0] }), chips]));
        });
        body.appendChild(el('div', { class: 'note' }, [
          el('b', { text: 'Read-only. ' }),
          document.createTextNode('Source: ' + (data.source || 'environment') + '. Runtime editing (mutable_at_runtime='),
          el('code', { text: String(data.mutable_at_runtime) }),
          document.createTextNode(') is a deliberate pending decision — a mutation endpoint needs a persistent override store, hot-reload, and a safeguard so the env-configured owner can never be locked out.'),
        ]));
        mount(panel(body));
      })
      .catch(function (err) { statePanel(friendlyError(err), 'err'); });
  }

  // ---- view: auth activity (honest state) -----------------------------------
  function viewActivity() {
    var body = el('div');
    body.appendChild(el('h3', { style: 'margin:0 0 10px', text: 'Auth activity' }));
    body.appendChild(el('p', { style: 'color:var(--ink-dim);font-size:14px;margin:0 0 12px',
      text: 'Every sign-in, denial, and owner-override is audited via audit_auth_event — currently emitted as structured application logs, not persisted to a queryable store.' }));
    body.appendChild(el('div', { class: 'note' }, [
      el('b', { text: 'To view live events now: ' }),
      el('code', { text: 'docker logs 12sgi-king-auth-1 | grep auth_audit' }),
      document.createTextNode('. A queryable audit feed (persisted table + owner-gated GET endpoint) is a pending backend decision in the shared authz module, since audit_auth_event is used by every service, not just auth.'),
    ]));
    mount(panel(body));
  }

  // ---- dev session ----------------------------------------------------------
  function createDevSession() {
    var role = $('role').value;
    api('GET', AUTH, '/api/v2/health', false).catch(function () {}); // warm/no-op
    fetch(AUTH + '/api/v2/auth/session', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ provider: 'passkey', subject: $('subject').value, tenant_id: 'hi-maui', role: role }),
    }).then(function (r) { return r.json(); }).then(function (res) {
      if (!res || !res.access_token) throw new Error((res && res.detail && res.detail.error && res.detail.error.message) || 'No access_token');
      setToken(res.access_token);
      toast('Dev session created as ' + role + '.', 'ok');
      render();
    }).catch(function (err) { toast('Session failed: ' + (err.message || err), 'bad'); });
  }

  // ---- routing --------------------------------------------------------------
  function render() {
    if (activeTab === 'health') viewHealth();
    else if (activeTab === 'allowlist') viewAllowlist();
    else viewActivity();
  }
  function setTab(tab) {
    activeTab = tab;
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === tab);
    });
    render();
  }

  function init() {
    captureHashToken();
    renderIdentity();
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
      b.addEventListener('click', function () { setTab(b.getAttribute('data-tab')); });
    });
    $('refreshBtn').addEventListener('click', render);
    $('createSession').addEventListener('click', createDevSession);
    $('signout').addEventListener('click', function () { setToken(''); render(); });
    $('toggleManual').addEventListener('click', function () { $('manualrow').classList.toggle('collapsed'); });
    $('useManual').addEventListener('click', function () {
      var t = ($('manualToken').value || '').trim();
      if (!t) { toast('Paste a token first.', 'bad'); return; }
      setToken(t); $('manualrow').classList.add('collapsed'); $('manualToken').value = '';
      toast('Token set.', 'ok'); render();
    });
    render(); // default: service health (public)
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
