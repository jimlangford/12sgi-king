/* King System · live feed layer — window.KingLive
   Polls a studio server's /api/overview (GPU, training, ComfyUI, disk,
   scheduled tasks, dispatch tail, in-flight renders) and tells subscribers.

   PUBLIC BUILD: no machine/tunnel URL is embedded. Live status only lights up
   when this shell is opened ON the machine (same-origin or 127.0.0.1:8770) or
   via an explicit localStorage 'king.liveBase' override the owner sets. A public
   visitor on GitHub Pages simply sees the built-in snapshot — by design. */
(() => {
  if (window.KingLive) return;

  const POLL_MS = 10000;   // overview poll while live
  const RETRY_MS = 30000;  // re-probe cycle while offline

  const subs = new Set();
  const S = {
    status: 'connecting',      // connecting | live | offline
    base: null,
    baseLabel: '',
    overview: null,            // last good /api/overview payload
    lastOk: 0,                 // epoch ms of last good fetch
  };

  const label = (base) => {
    if (!base) return '';
    if (base.includes('127.0.0.1') || base.includes('localhost')) return '127.0.0.1:8770';
    try { return new URL(base).host; } catch (e) { return base; }
  };

  const emit = () => { subs.forEach(fn => { try { fn(S); } catch (e) {} }); };

  const fetchJson = async (base, path, ms) => {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), ms || 6000);
    try {
      const r = await fetch(base + path, { signal: ctl.signal, cache: 'no-store' });
      if (!r.ok) throw new Error('http ' + r.status);
      return JSON.parse(await r.text());
    } finally { clearTimeout(t); }
  };

  const candidates = () => {
    const list = [];
    try {
      const saved = localStorage.getItem('king.liveBase');
      if (saved) list.push(saved.replace(/\/$/, ''));
    } catch (e) {}
    try {
      if (/^https?:$/.test(location.protocol) && /:(8770|8765)$/.test(location.host)) {
        list.push(location.origin);
      }
    } catch (e) {}
    list.push('http://127.0.0.1:8770');   // only resolves when viewing on the machine
    return [...new Set(list)];
  };

  let timer = null;
  const schedule = (ms) => { clearTimeout(timer); timer = setTimeout(tick, ms); };

  let probing = false;
  const probe = async () => {
    if (probing) return; probing = true;
    try {
      for (const base of candidates()) {
        try {
          const h = await fetchJson(base, '/api/health', 3500);
          if (h && typeof h === 'object') {
            S.base = base; S.baseLabel = label(base);
            return true;
          }
        } catch (e) { /* next candidate */ }
      }
      return false;
    } finally { probing = false; }
  };

  let misses = 0;
  const tick = async () => {
    if (!S.base) {
      const ok = await probe();
      if (!ok) {
        if (S.status !== 'offline') { S.status = 'offline'; emit(); }
        return schedule(RETRY_MS);
      }
    }
    try {
      const ov = await fetchJson(S.base, '/api/overview', 9000);
      misses = 0;
      S.overview = ov; S.lastOk = Date.now();
      if (S.status !== 'live') { S.status = 'live'; }
      emit();
      schedule(POLL_MS);
    } catch (e) {
      misses += 1;
      if (misses >= 2) {
        S.base = null; S.status = 'offline'; misses = 0; emit();
        schedule(RETRY_MS);
      } else {
        schedule(4000);
      }
    }
  };

  window.KingLive = {
    get: () => S,
    subscribe(fn) { subs.add(fn); try { fn(S); } catch (e) {} return () => subs.delete(fn); },
    setBase(url) {
      try {
        if (url) localStorage.setItem('king.liveBase', url);
        else localStorage.removeItem('king.liveBase');
      } catch (e) {}
      S.base = null; S.status = 'connecting'; emit(); schedule(0);
    },
    refresh() { schedule(0); },
  };

  schedule(0);
})();
