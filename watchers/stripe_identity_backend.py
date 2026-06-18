#!/usr/bin/env python3
"""stripe_identity_backend.py — the tiny server-side endpoint for the govOS Beta portal's
council verification (Jimmy 2026-06-17, "yes, build the backend"). Creates Stripe IDENTITY
verification sessions with a RESTRICTED key, reports only verified-STATUS, and records nothing
but {session_id: status} — never the ID document, name, or any PII.

WHY a backend: a restricted/secret key (rk_/sk_) is server-side only; it can never live in the
static GitHub Pages portal. This service holds the key in its ENVIRONMENT (never a committed
file) and the public page calls it cross-origin.

KEY SOURCE (in priority): env STRIPE_RESTRICTED_KEY → env STRIPE_SECRET_KEY → (LOCAL DEV ONLY)
config/stripe.json restricted_key/secret_key (gitignored). On a real deploy, set the env var;
do NOT ship the file. Webhook secret: env STRIPE_WEBHOOK_SECRET → config webhook_secret.

ENDPOINTS (all JSON; CORS limited to ALLOWED_ORIGIN env, default '*' for dev):
  POST /verify/start   body {district?, return_url?} -> {id, url}   (redirect the member to url)
  GET  /verify/status?id=vs_...                       -> {status}    (verified|processing|requires_input|canceled)
  POST /webhook        (Stripe signed)                -> {ok}        (records verified-status only)

DEPLOY (any of): a Cloudflare-tunnel'd box, Render/Railway/Fly, or your Naga server. Steps:
  1) set env STRIPE_RESTRICTED_KEY=rk_live_...  (Identity: Write scope, account Identity ENABLED)
  2) set env STRIPE_WEBHOOK_SECRET=whsec_...     (from the Stripe webhook you point at /webhook)
  3) set env ALLOWED_ORIGIN=https://jimlangford.github.io   (lock CORS to the portal)
  4) run:  python stripe_identity_backend.py --serve 8810
  5) put the public base URL into config/beta.json -> "verify_api_base", rerun beta_portal.py
Guardrails: never logs/returns the key; stores only status (no PII); CPU/stdlib only; no GPU/secrets-on-disk.
Self-test (no session created): python stripe_identity_backend.py --selftest
"""
import os, sys, json, time, hmac, hashlib, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
CFG  = os.path.join(PROJ, "config", "stripe.json")
VERIFIED_F = os.path.join(PROJ, "reports", "_status", "verified_sessions.json")  # {id: {status, ts}} — PRIVATE, no PII
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")

def _key():
    """Restricted/secret key from ENV first; config/stripe.json is LOCAL-DEV fallback only."""
    for ev in ("STRIPE_RESTRICTED_KEY", "STRIPE_SECRET_KEY"):
        v = (os.environ.get(ev) or "").strip()
        if v and not v.startswith("PASTE_"): return v
    try:
        d = json.load(open(CFG, encoding="utf-8"))
        for fld in ("restricted_key", "secret_key"):
            v = (d.get(fld) or "").strip()
            if v and not v.startswith("PASTE_"): return v
    except Exception:
        pass
    return ""

def _webhook_secret():
    v = (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    if v and not v.startswith("PASTE_"): return v
    try:
        return (json.load(open(CFG, encoding="utf-8")).get("webhook_secret") or "").strip()
    except Exception:
        return ""

def _stripe(method, path, form=None):
    """Minimal Stripe API call (stdlib). form is a dict -> x-www-form-urlencoded. Returns (status, json)."""
    key = _key()
    if not key:
        return 0, {"error": {"message": "no Stripe key configured (set STRIPE_RESTRICTED_KEY)"}}
    import urllib.parse
    data = urllib.parse.urlencode(form, doseq=True).encode() if form is not None else None
    req = urllib.request.Request("https://api.stripe.com/v1/" + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/x-www-form-urlencoded",
                                          "Stripe-Version": "2024-06-20"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: body = json.loads(e.read().decode())
        except Exception: body = {"error": {"message": "HTTP %s" % e.code}}
        return e.code, body
    except Exception as e:
        return 0, {"error": {"message": str(e)[:160]}}

def create_session(district=None, return_url=None):
    """Create a hosted Identity verification session. Returns (status, {id,url} | {error})."""
    form = {"type": "document", "options[document][require_matching_selfie]": "true"}
    if district: form["metadata[district]"] = str(district)[:60]
    form["metadata[role]"] = "maui_council"
    if return_url: form["return_url"] = return_url
    st, j = _stripe("POST", "identity/verification_sessions", form)
    if st == 200:
        return st, {"id": j.get("id"), "url": j.get("url")}
    return st, {"error": (j.get("error") or {}).get("message", "create failed"), "code": st}

def session_status(vid):
    """Return ONLY the status — never verified_outputs / PII."""
    if not (vid or "").startswith("vs_"): return 400, {"error": "bad session id"}
    st, j = _stripe("GET", "identity/verification_sessions/" + vid)
    if st == 200:
        s = j.get("status")
        _record(vid, s)
        return 200, {"status": s}
    return st, {"error": (j.get("error") or {}).get("message", "lookup failed")}

def _record(vid, status):
    """Persist {id: {status, ts}} only — no PII ever. PRIVATE (reports/_status)."""
    try:
        os.makedirs(os.path.dirname(VERIFIED_F), exist_ok=True)
        d = {}
        if os.path.exists(VERIFIED_F):
            d = json.load(open(VERIFIED_F, encoding="utf-8"))
        d[vid] = {"status": status, "ts": int(time.time())}
        json.dump(d, open(VERIFIED_F, "w", encoding="utf-8"), indent=1)
    except Exception:
        pass

def verify_webhook(payload, sig_header):
    """Stripe signature check (stdlib HMAC) — no `stripe` lib needed."""
    secret = _webhook_secret()
    if not secret or not sig_header: return False
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    t = parts.get("t"); v1 = parts.get("v1")
    if not (t and v1): return False
    signed = ("%s.%s" % (t, payload.decode("utf-8", "replace"))).encode()
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)

# --- paid premium-render checkout (the agenda-generator monetization) ---
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import civic_quote as _cq
except Exception:
    _cq = None
ORDERS = os.path.join(PROJ, "reports", "_status", "paid_orders.jsonl")       # PRIVATE order ledger (no PII)
RENDER_QUEUE = os.path.join(PROJ, "reports", "_status", "render_jobs")        # fulfillment queue (phase 2 renders these)

def create_checkout(aspect, tier="premium_reel", seconds=20, success_url=None, cancel_url=None,
                    tenant="hi-maui", priority="standard"):
    """Quote the requested explainer, then open a Stripe Checkout Session for the price. SAFE GATES:
    free tier → no charge; provisional pricing (rate not yet calibrated) → no charge, returns the quote."""
    if not _cq:
        return 0, {"error": "quote engine unavailable"}
    q = _cq.quote(aspect, tier, int(seconds or 20), tenant or "hi-maui", priority or "standard")
    if q["price_usd"] <= 0:
        return 200, {"free": True, "quote": q}
    if q.get("provisional"):
        return 200, {"provisional": True, "quote": q,
                     "message": "pricing not yet calibrated — set token_usd_rate + rate_confirmed in config/civic_pricing.json before charging"}
    cents = int(round(q["price_usd"] * 100))
    su = success_url or os.environ.get("CHECKOUT_SUCCESS_URL", "https://jimlangford.github.io/12sgi-king/beta_requests.html?paid=1")
    cu = cancel_url or os.environ.get("CHECKOUT_CANCEL_URL", "https://jimlangford.github.io/12sgi-king/beta_requests.html")
    form = {
        "mode": "payment", "success_url": su, "cancel_url": cu,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": q.get("currency", "usd"),
        "line_items[0][price_data][unit_amount]": str(cents),
        "line_items[0][price_data][product_data][name]": ("%s — %s" % (q["tier_label"], q["aspect"]))[:250],
        "metadata[quote_id]": q["quote_id"], "metadata[tier]": tier, "metadata[aspect]": q["aspect"][:120],
        "payment_intent_data[metadata][quote_id]": q["quote_id"],
    }
    st, j = _stripe("POST", "checkout/sessions", form)
    if st == 200:
        return 200, {"quote": q, "id": j.get("id"), "checkout_url": j.get("url")}
    return st, {"error": (j.get("error") or {}).get("message", "checkout create failed"), "quote": q}

def _record_order(session):
    """On paid checkout: log the order (no PII) + enqueue a fulfillment render job. Phase-2 worker renders it."""
    md = session.get("metadata") or {}
    rec = {"session": session.get("id"), "quote_id": md.get("quote_id"), "aspect": md.get("aspect"),
           "tier": md.get("tier"), "amount_total": session.get("amount_total"),
           "payment_status": session.get("payment_status"), "ts": int(time.time())}
    os.makedirs(os.path.dirname(ORDERS), exist_ok=True)
    with open(ORDERS, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.makedirs(RENDER_QUEUE, exist_ok=True)
    with open(os.path.join(RENDER_QUEUE, "%s.json" % (rec["quote_id"] or session.get("id"))), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return rec

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self._cors()
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass  # never log (avoid any chance of leaking headers)
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_GET(self):
        import urllib.parse as up
        u = up.urlparse(self.path)
        if u.path == "/verify/status":
            vid = up.parse_qs(u.query).get("id", [""])[0]
            c, j = session_status(vid); return self._json(c if c in (200,400) else 200, j)
        if u.path == "/quote":
            qs = up.parse_qs(u.query)
            if not _cq: return self._json(200, {"error": "quote engine unavailable"})
            q = _cq.quote(qs.get("aspect", [""])[0], qs.get("tier", ["premium_reel"])[0],
                          int(qs.get("seconds", ["20"])[0] or 20), qs.get("tenant", ["hi-maui"])[0],
                          qs.get("priority", ["standard"])[0])
            return self._json(200, q)                       # non-financial: just the price quote
        if u.path in ("/", "/health"): return self._json(200, {"ok": True, "key_configured": bool(_key()), "quote_engine": bool(_cq)})
        self._json(404, {"error": "not found"})
    def do_POST(self):
        ln = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(ln) if ln else b""
        if self.path == "/verify/start":
            try: body = json.loads(raw or b"{}")
            except Exception: body = {}
            c, j = create_session(body.get("district"), body.get("return_url"))
            return self._json(200 if c == 200 else 502, j)
        if self.path == "/checkout/start":
            try: body = json.loads(raw or b"{}")
            except Exception: body = {}
            c, j = create_checkout(body.get("aspect", ""), body.get("tier", "premium_reel"),
                                   body.get("seconds", 20), body.get("return_url"), None,
                                   body.get("tenant", "hi-maui"), body.get("priority", "standard"))
            return self._json(200 if c == 200 else 502, j)
        if self.path == "/webhook":
            if not verify_webhook(raw, self.headers.get("Stripe-Signature")):
                return self._json(400, {"error": "bad signature"})
            try: ev = json.loads(raw)
            except Exception: ev = {}
            obj = (ev.get("data") or {}).get("object") or {}
            if ev.get("type") == "checkout.session.completed":
                _record_order(obj)                          # paid → log + enqueue the render
            elif obj.get("id", "").startswith("vs_"):
                _record(obj["id"], obj.get("status"))
            return self._json(200, {"ok": True})
        self._json(404, {"error": "not found"})

def main():
    a = sys.argv[1:]
    if "--selftest" in a:
        key = _key()
        print("key configured:", bool(key), "| mode:", ("LIVE" if "_live" in key else "TEST" if "_test" in key else "?"))
        st, j = create_session(district="Test")
        if st == 200: print("Identity ENABLED — session created:", j.get("id"), "(cancel it in the dashboard)")
        else: print("Identity create -> HTTP %s: %s" % (st, j.get("error")))
        print("webhook secret configured:", bool(_webhook_secret()))
        return 0
    if "--serve" in a:
        port = int(a[a.index("--serve") + 1]) if len(a) > a.index("--serve") + 1 else 8810
        print("stripe_identity_backend serving on :%d (origin=%s, key=%s)" % (port, ALLOWED_ORIGIN, bool(_key())))
        ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever(); return 0
    print(__doc__); return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
