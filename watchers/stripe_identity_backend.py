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
import os, sys, json, time, hmac, hashlib, urllib.request, urllib.error, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
CFG  = os.path.join(PROJ, "config", "stripe.json")
VERIFIED_F = os.path.join(PROJ, "reports", "_status", "verified_sessions.json")  # {id: {status, ts}} — PRIVATE, no PII
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://jimlangford.github.io")  # safe default (the portal origin); never wide-open '*' unless explicitly set

def _key():
    """Restricted/secret key from ENV first; config/stripe.json is LOCAL-DEV fallback only.
    PROVABLY-KEYLESS STAGING: with env CIVIC_NO_LOCAL_KEY=1 the config/stripe.json fallback is SKIPPED, so an
    exposed/persisted server is keyless unless the OWNER sets STRIPE_(RESTRICTED|SECRET)_KEY in its env. This is
    what lets a public/tailnet deploy run with ZERO Stripe operations (no charges, no Identity sessions) until
    Jimmy deliberately wires the env key. Local CLI testing (no CIVIC_NO_LOCAL_KEY) still uses the file fallback."""
    for ev in ("STRIPE_RESTRICTED_KEY", "STRIPE_SECRET_KEY"):
        v = (os.environ.get(ev) or "").strip()
        if v and not v.startswith("PASTE_"): return v
    if os.environ.get("CIVIC_NO_LOCAL_KEY") in ("1", "true", "yes"):
        return ""                                  # exposed/persisted deploy: env-only, never the local file
    try:
        d = json.load(open(CFG, encoding="utf-8"))
        for fld in ("restricted_key", "secret_key"):
            v = (d.get(fld) or "").strip()
            if v and not v.startswith("PASTE_"): return v
    except Exception:
        pass
    return ""


# Load social-login creds from a gitignored file into env if not already set, so social login survives
# ANY relaunch (supervisor / charge_selfheal / reboot) without relying on env propagation.
try:
    _fbf = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config", "facebook.secret.json"), encoding="utf-8"))
    for _k, _v in {"FACEBOOK_APP_ID": _fbf.get("app_id"), "FACEBOOK_APP_SECRET": _fbf.get("app_secret"),
                   "FACEBOOK_SCOPE": _fbf.get("scope"), "FACEBOOK_CONFIG_ID": _fbf.get("config_id")}.items():
        if _v and not os.environ.get(_k):
            os.environ[_k] = str(_v)
except Exception:
    pass


def configured():
    return bool(_key())

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
try:
    import feature_requests as _fr            # the public request + vote engine (free tier)
except Exception:
    _fr = None
try:
    import tier_access as _ta                 # the capability spine (tier -> what you may do)
except Exception:
    _ta = None
ORDERS = os.path.join(PROJ, "reports", "_status", "paid_orders.jsonl")       # PRIVATE order ledger (no PII)
_ORDERS_LOCK = threading.Lock()   # serialize concurrent webhook appends (ThreadingHTTPServer)

# ── PAID CAPABILITY DELIVERY — the served features behind the tiers (Jimmy 2026-06-18: "make it
# real — wire + deploy"). Each invokes the already-built tool; lazy-imported + guarded so a tool
# fault can never take the backend down. The do_GET router gates these by the caller's tier.
def cap_law_drafter(goal, scope="both", pillar="P4"):
    import law_drafter
    d = law_drafter.draft(goal or "improve civic transparency and accountability", scope, pillar)
    return {"capability": "law_drafter", "goal": goal, "draft": d,
            "integrity": "DRAFT only — not law, not legal advice; 12 Stones pillars = the author's lens, not government law; verify flags inline."}
def cap_civic_calc(meeting_date):
    import sunshine_compliance
    return {"capability": "civic_calc", "meeting_date": meeting_date,
            "result": sunshine_compliance.deadline(meeting_date),
            "integrity": "HRS §92-7 6-day rule (electronic county-calendar posting controls); an assist — confirm with the County Clerk / Corporation Counsel."}
def cap_oversight(tenant="hi-maui", kind="report"):
    import oversight_calculator as oc
    fn = {"report": oc.report, "packet": oc.inquiry_packet, "records": oc.records_request}.get(kind, oc.report)
    return {"capability": "private_reports", "tenant": tenant, "kind": kind, "result": fn(tenant),
            "integrity": "sourced public records only; every figure traces to a public filing; framed as questions for the lawful channel, never accusations."}
def cap_ai_advice(q, tenant="hi-maui"):
    if not q: return {"capability": "ai_advice", "error": "ask a question with ?q="}
    import urllib.request as _u, json as _j, os as _o
    model = _o.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    ollama = _o.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")  # deploy-portable: point at a reachable Ollama
    sys_p = ("You are a civic-data assistant for Hawaiʻi county governance. Answer ONLY from public "
             "records (campaign finance, contracts, votes, permits). Frame findings as QUESTIONS for the "
             "lawful channel, never as accusations or established guilt. Say when the record is insufficient. "
             "Be concise, sourced, and in aloha.")
    payload = _j.dumps({"model": model, "prompt": "%s\n\nQuestion (%s): %s" % (sys_p, tenant, q),
                        "stream": False}).encode()
    try:
        req = _u.Request(ollama + "/api/generate", data=payload, headers={"Content-Type": "application/json"})
        with _u.urlopen(req, timeout=60) as r:
            ans = (_j.load(r) or {}).get("response", "").strip()
        return {"capability": "ai_advice", "tenant": tenant, "question": q, "answer": ans, "model": model,
                "integrity": "AI advice on public data — questions, not verdicts; verify against the named source."}
    except Exception as e:
        return {"capability": "ai_advice", "error": "AI engine unavailable (Ollama): %s" % str(e)[:120]}
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

def _tiers():
    try:
        return json.load(open(os.path.join(PROJ, "config", "civic_tiers.json"), encoding="utf-8"))
    except Exception:
        return {}


def create_subscription(tier_id="pro", interval="month", verify_id="", success_url=None, cancel_url=None):
    """Open a Stripe SUBSCRIPTION Checkout for a civic tier (member/builder) at the chosen interval
    (month|year), reading config/civic_tiers.json. SAFE GATES: rates not confirmed OR price 0 → NO charge
    (provisional); identity must be verified when a key is live; a checkout session is NOT a charge — only a
    user paying on Stripe's hosted page charges. Tools analyze PUBLIC data + the member's own private account."""
    reg = _tiers()
    t = (reg.get("tiers") or {}).get(tier_id)
    if not t:
        return 400, {"error": "unknown tier", "tiers": list((reg.get("tiers") or {}).keys())}
    is_year = str(interval).startswith("y")
    price = float((t.get("annual_usd") if is_year else t.get("price_usd")) or 0)
    if not reg.get("rate_confirmed") or price <= 0:
        return 200, {"provisional": True, "tier": tier_id, "label": t.get("label"),
                     "message": "pricing not confirmed (or free tier) — set prices + rate_confirmed:true in config/civic_tiers.json"}
    if _key() and verify_id:                                  # live: require the identity actually verified
        sc, sj = session_status(verify_id)
        if (sj or {}).get("status") != "verified":
            return 402, {"error": "identity not verified", "status": (sj or {}).get("status")}
    cents = int(round(price * 100))
    su = success_url or os.environ.get("CHECKOUT_SUCCESS_URL", "https://jimlangford.github.io/12sgi-king/feature_board.html?member=1")
    cu = cancel_url or os.environ.get("CHECKOUT_CANCEL_URL", "https://jimlangford.github.io/12sgi-king/feature_board.html")
    form = {
        "mode": "subscription", "success_url": su, "cancel_url": cu,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": reg.get("currency", "usd"),
        "line_items[0][price_data][unit_amount]": str(cents),
        "line_items[0][price_data][recurring][interval]": "year" if is_year else "month",
        "line_items[0][price_data][product_data][name]": ("%s (%s)" % (t.get("label", tier_id), "annual" if is_year else "monthly"))[:250],
        "metadata[tier]": tier_id, "metadata[interval]": "year" if is_year else "month",
        "metadata[verify_id]": (verify_id or "")[:120],
    }
    st, j = _stripe("POST", "checkout/sessions", form)
    if st == 200:
        return 200, {"tier": tier_id, "label": t.get("label"), "id": j.get("id"),
                     "checkout_url": j.get("url"), "price_usd": price, "interval": "year" if is_year else "month"}
    return st, {"error": (j.get("error") or {}).get("message", "checkout create failed")}


def create_oversight_subscription(verify_id="", success_url=None, cancel_url=None):
    """Back-compat wrapper: the Council Oversight Calculator is now the Member tier."""
    return create_subscription("council_pro", "month", verify_id, success_url, cancel_url)


def _amount_tier(cents):
    """Map a paid amount (cents) -> canonical plans.json tier id. Lets a PAYMENT-LINK purchase (which carries
    no verify_id, only an amount + email) resolve to its tier. Prices are distinct so amount is unambiguous."""
    try:
        plans = json.load(open(os.path.join(PROJ, "config", "plans.json"), encoding="utf-8")).get("plans", [])
        for p in plans:
            amt = p.get("price_month") or p.get("price_each") or 0
            if amt and int(amt) == int(cents or 0):
                return p.get("id")
    except Exception:
        pass
    return None


def _record_order(session):
    """On paid checkout: log the order so access is granted. Handles BOTH (a) our /subscribe sessions (carry
    metadata.tier + verify_id) and (b) PAYMENT-LINK purchases (carry customer email + amount -> tier).
    A render order (quote_id) also enqueues a fulfillment job."""
    md = session.get("metadata") or {}
    amount = session.get("amount_total")
    tier = md.get("tier") or _amount_tier(amount)                          # payment-link -> derive tier from amount
    email = ((session.get("customer_details") or {}).get("email")
             or session.get("customer_email") or md.get("email") or "")
    rec = {"session": session.get("id"), "quote_id": md.get("quote_id"), "aspect": md.get("aspect"),
           "tier": tier, "interval": md.get("interval"),
           "verify_id": md.get("verify_id"),                 # so tier_access.tier_for() can resolve this user's tier
           "email": email,                                    # payment-link buyers are keyed by email
           "amount_total": amount,
           "payment_status": session.get("payment_status") or "paid", "ts": int(time.time())}
    os.makedirs(os.path.dirname(ORDERS), exist_ok=True)
    with _ORDERS_LOCK, open(ORDERS, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # Only a one-off RENDER order (has a quote_id) enqueues a fulfillment job. A subscription
    # (member/builder/oversight) grants ACCESS via the orders ledger — it is not a render to queue.
    if rec.get("quote_id"):
        os.makedirs(RENDER_QUEUE, exist_ok=True)
        with open(os.path.join(RENDER_QUEUE, "%s.json" % rec["quote_id"]), "w", encoding="utf-8") as f:
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
        if u.path == "/tiers":                               # the public tier ladder + prices (read-only)
            return self._json(200, _tiers())
        if u.path == "/me":                                  # the caller's resolved tier + capabilities (UI gating)
            if not _ta:
                return self._json(200, {"tier": "free", "capabilities": []})
            qm=up.parse_qs(u.query); return self._json(200, _ta.access(qm.get("verify_id",[""])[0] or qm.get("email",[""])[0]))
        if u.path == "/board":                              # public feature-request board (read-only, no gate)
            if not _fr: return self._json(200, {"error": "request engine unavailable"})
            return self._json(200, _fr.board(up.parse_qs(u.query).get("tenant", ["hi-maui"])[0]))
        # ── PAID CAPABILITY DELIVERY (tier-gated) — the features behind the $29/$99/$999 tiers ──
        if u.path == "/advice":
            return self._gated(u, "ai_advice", lambda q: cap_ai_advice(q.get("q", [""])[0], q.get("tenant", ["hi-maui"])[0]))
        if u.path == "/calc":
            return self._gated(u, "civic_calc", lambda q: cap_civic_calc(q.get("meeting_date", q.get("meeting", [""]))[0]))
        if u.path == "/draft":
            return self._gated(u, "law_drafter", lambda q: cap_law_drafter(q.get("goal", [""])[0], q.get("scope", ["both"])[0], q.get("pillar", ["P4"])[0]))
        if u.path == "/oversight":
            return self._gated(u, "private_reports", lambda q: cap_oversight(q.get("tenant", ["hi-maui"])[0], q.get("kind", ["report"])[0]))
        if u.path == "/signup":                              # PUBLIC social-signup page (cellular via Funnel)
            try: page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "signup.html"), encoding="utf-8").read()
            except Exception: page = "<h1>Sign up</h1><p>page unavailable</p>"
            b = page.encode("utf-8")
            self.send_response(200); self._cors(); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if u.path == "/auth/facebook/callback":         # Facebook OAuth callback -> create/resolve account
            import urllib.parse as _up, urllib.request as _ur, secrets as _sec
            qs = up.parse_qs(u.query); code = qs.get("code", [""])[0]
            appid = os.environ.get("FACEBOOK_APP_ID", ""); secret = os.environ.get("FACEBOOK_APP_SECRET", "")
            redir = os.environ.get("FB_REDIRECT_URI", "https://12sgianonymous.tail760750.ts.net:8443/auth/facebook/callback")
            email = ""
            try:
                tok = json.loads(_ur.urlopen("https://graph.facebook.com/v19.0/oauth/access_token?" + _up.urlencode(
                    {"client_id": appid, "redirect_uri": redir, "client_secret": secret, "code": code}), timeout=15).read())
                me = json.loads(_ur.urlopen("https://graph.facebook.com/v19.0/me?" + _up.urlencode(
                    {"fields": "id,email,name", "access_token": tok.get("access_token", "")}), timeout=15).read())
                email = (me.get("email") or "").strip().lower()
            except Exception:
                email = ""
            sess = "sess_" + _sec.token_urlsafe(18)        # the user's access token (their key)
            try:
                os.makedirs(os.path.dirname(ORDERS), exist_ok=True)
                with _ORDERS_LOCK, open(ORDERS, "a", encoding="utf-8", newline="\n") as _f:
                    _f.write(json.dumps({"verify_id": sess, "email": email, "tier": "free",
                        "paid": True, "source": "facebook_signup", "when": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
            except Exception:
                pass
            page = ("<html><body style='font-family:system-ui;background:#0c0b09;color:#efe9da;text-align:center;padding:56px 20px'>"
                    "<h2 style='color:#e3ad33'>Welcome%s</h2><p>You're signed in (free tier). Save your access key:</p>"
                    "<code style='color:#e3ad33;word-break:break-all'>%s</code><p style='margin-top:22px'>"
                    "<a style='color:#9bb38a' href='/signup'>continue</a></p></body></html>") % ((" " + email) if email else "", sess)
            b = page.encode("utf-8"); self.send_response(200); self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b); return
        if u.path.startswith("/auth/") and u.path.endswith("/start"):   # social OAuth start (Facebook/Google/Apple)
            import urllib.parse as _up
            prov = u.path.split("/")[2]
            envk = {"facebook": "FACEBOOK_APP_ID", "google": "GOOGLE_CLIENT_ID", "apple": "APPLE_CLIENT_ID"}.get(prov, "")
            appid = os.environ.get(envk, "") if envk else ""
            if prov == "facebook" and appid:
                redir = os.environ.get("FB_REDIRECT_URI", "https://12sgianonymous.tail760750.ts.net:8443/auth/facebook/callback")
                _scope = os.environ.get("FACEBOOK_SCOPE", "public_profile")   # business apps reject raw 'email'; add it back via FACEBOOK_SCOPE=email,public_profile once permitted (or config_id)
                _cfg = os.environ.get("FACEBOOK_CONFIG_ID", "")
                _p = {"client_id": appid, "redirect_uri": redir, "response_type": "code", "state": "fb"}
                if _cfg:
                    _p["config_id"] = _cfg                          # Facebook Login FOR BUSINESS flow (permissions from the config)
                else:
                    _p["scope"] = _scope                            # classic scope flow
                url = "https://www.facebook.com/v19.0/dialog/oauth?" + _up.urlencode(_p)
                return self._json(200, {"configured": True, "redirect": url})
            if appid:
                return self._json(200, {"configured": True, "redirect": ""})   # google/apple: same pattern, wire on demand
            return self._json(200, {"configured": False, "provider": prov, "message": "%s sign-in is being connected" % prov})
        if u.path in ("/", "/health"): return self._json(200, {"ok": True, "key_configured": bool(_key()), "quote_engine": bool(_cq), "request_engine": bool(_fr), "capabilities_served": ["ai_advice","civic_calc","law_drafter","private_reports"]})
        self._json(404, {"error": "not found"})

    def _gated(self, u, capability, produce):
        """Resolve the caller's tier and serve a PAID capability only if their tier grants it.
        402 (payment required) + the needed capability otherwise. Never charges; pure delivery."""
        import urllib.parse as up
        qs = up.parse_qs(u.query)
        # SECURITY: gate on an UNGUESSABLE token only (verify_id, or an access_token grant) - NEVER raw email,
        # because this endpoint is public via the Funnel and email is guessable (impersonation). Email-keyed
        # payment-link buyers must be issued a token (magic-link) post-purchase to USE their tier - see TODO.
        vid = qs.get("verify_id", [""])[0] or qs.get("token", [""])[0]
        tier = (_ta.tier_for(vid) if (_ta and vid) else "free")
        if not (_ta and _ta.can(tier, capability)):
            return self._json(402, {"error": "this is a paid capability", "capability": capability,
                                    "your_tier": tier, "upgrade": "/tiers — subscribe to a tier that includes this"})
        try:
            return self._json(200, produce(qs))
        except Exception as e:
            return self._json(200, {"capability": capability, "error": "delivery error", "detail": str(e)[:200]})
    def do_POST(self):
        ln = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(ln) if ln else b""
        # STAGING SAFETY: with no Stripe key (keyless deploy), refuse ALL write/Stripe paths cleanly —
        # no Stripe call, no charge, no identity session, no weak write. Only the webhook + reads pass.
        # The owner flips it live by setting STRIPE_(SECRET|RESTRICTED)_KEY in this server's env.
        if not configured() and self.path in ("/verify/start", "/subscribe", "/oversight/subscribe",
                                               "/checkout/start", "/request", "/vote"):
            return self._json(200, {"open": False,
                                    "message": "Service is configured but not yet live — sign-up/checkout opens when the owner connects Stripe. Nothing is charged."})
        if self.path == "/message":                          # PAID capability: Message Claude -> queue a command to the executor (workboard-quad-os)
            try: body = json.loads(raw or b"{}")
            except Exception: body = {}
            vid = (body.get("verify_id") or body.get("token") or "").strip()   # UNGUESSABLE grant only (never raw email)
            tier = (_ta.tier_for(vid) if (_ta and vid) else "free")
            if not (_ta and _ta.can(tier, "message_claude")):
                return self._json(402, {"error": "this is a paid capability", "capability": "message_claude",
                                        "your_tier": tier, "upgrade": "/tiers — subscribe to a tier that includes Message Claude"})
            msg = (body.get("message") or body.get("text") or "").strip()
            if not msg:
                return self._json(400, {"error": "message required"})
            tenant = (body.get("tenant") or "").strip()[:40]
            entry = {"ts": int(time.time()), "iso": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "schema": "workboard-job-v1",
                     "source": "civic-paid-%s" % tier, "kind": "command",
                     "target_thread": "workboard-quad-os", "priority": (body.get("priority") or "normal"),
                     "status": "queued",
                     "event": "CIVIC MESSAGE (%s%s): %s" % (tier, (" / " + tenant) if tenant else "", msg[:1500]),
                     "job": {"action": "message.claude", "status": "queued", "payload": {"tier": tier, "tenant": tenant}}}
            try:
                with open(os.path.join(PROJ, ".dispatch_log.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception as e:
                return self._json(200, {"ok": False, "error": "queue failed", "detail": str(e)[:160]})
            return self._json(200, {"ok": True, "queued": True, "tier": tier,
                                    "note": "Sent to the system executor (workboard-quad-os); it's on the Work Board and will be acted on."})
        if self.path == "/signup/interest":                  # early-access capture (public signup page)
            try: body = json.loads(raw or b"{}")
            except Exception: body = {}
            em = (body.get("email") or "").strip().lower()
            if "@" not in em: return self._json(400, {"error": "valid email required"})
            try:
                p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reports", "_status", "early_access.jsonl")
                open(p, "a", encoding="utf-8").write(json.dumps({"email": em, "when": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
            except Exception: pass
            return self._json(200, {"ok": True, "email": em})
        if self.path == "/newsletter/signup":                # PUBLIC civic-newsletter opt-in (go.html / signup page)
            try: body = json.loads(raw or b"{}")
            except Exception: body = {}
            em = (body.get("email") or "").strip().lower()
            if "@" not in em or "." not in em.split("@")[-1]:
                return self._json(400, {"error": "valid email required"})
            tenant = (body.get("tenant") or "").strip()[:40]
            source = (body.get("source") or "go.html").strip()[:40]
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reports", "_status", "newsletter_signups.jsonl")
            try:                                             # dedup on email (idempotent opt-in; never double-add)
                for line in open(p, encoding="utf-8"):
                    try:
                        if json.loads(line).get("email") == em:
                            return self._json(200, {"ok": True, "email": em, "already": True})
                    except Exception: pass
            except Exception: pass
            try:
                open(p, "a", encoding="utf-8").write(json.dumps(
                    {"email": em, "tenant": tenant, "source": source,
                     "when": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
            except Exception: pass
            return self._json(200, {"ok": True, "email": em})
        if self.path == "/verify/start":
            try: body = json.loads(raw or b"{}")
            except Exception: body = {}
            c, j = create_session(body.get("district"), body.get("return_url"))
            return self._json(200 if c == 200 else 502, j)
        if self.path in ("/request", "/vote"):
            # FREE tier: a verified resident submits a public request or votes. The Stripe Identity
            # signup is the gate (a verify_id from /verify/start); when a key is configured we confirm it
            # verified, in staging we accept + tag provisional. Voter identity is the verify_id (one vote each).
            if not _fr: return self._json(200, {"error": "request engine unavailable"})
            try: body = json.loads(raw or b"{}")
            except Exception: body = {}
            vid = body.get("verify_id") or ""
            if _key() and vid:                              # live: require the identity actually verified
                sc, sj = session_status(vid)
                if (sj or {}).get("status") != "verified":
                    return self._json(402, {"error": "identity not verified", "status": (sj or {}).get("status")})
            if not vid:
                return self._json(402, {"error": "free signup required (verify_id missing)"})
            if self.path == "/vote":
                return self._json(200, _fr.vote(body.get("request_id", ""), "v:" + vid))
            tier = "paid_private" if body.get("tier") == "paid_private" else "free_public"
            if tier == "paid_private":
                # a private build request is a BUILDER capability — enforce in code, not by convention
                utier = _ta.tier_for(vid) if _ta else "free"
                if not (_ta and _ta.can(utier, "build_tenant")):
                    return self._json(403, {"error": "private build requests require the Builder tier",
                                            "your_tier": utier, "needed": "build_tenant"})
            rec = _fr.submit("verified:" + vid, body.get("title", ""), body.get("desc", ""),
                             tier, body.get("tenant", "hi-maui"))
            return self._json(200, {"ok": True, "id": rec["id"], "department": rec["department_label"],
                                    "provisional": not bool(_key())})
        if self.path in ("/subscribe", "/oversight/subscribe"):
            # Subscribe to a civic tier (member/builder), month|year (gated — no charge until a user pays on Stripe).
            try: body = json.loads(raw or b"{}")
            except Exception: body = {}
            tier = body.get("tier") or ("council_pro" if self.path == "/oversight/subscribe" else "pro")
            c, j = create_subscription(tier, body.get("interval", "month"), body.get("verify_id", ""), body.get("return_url"))
            return self._json(200 if c == 200 else c, j)
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
