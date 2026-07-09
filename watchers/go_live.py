#!/usr/bin/env python3
"""go_live.py — OWNER one-command activation of the civic payment backend (Jimmy 2026-06-18).

The backend is built + proven (access-grant flow verified, Stripe request shapes correct, sk_live key valid).
It runs KEYLESS by default so Claude never activates charging. THIS script — run by JIMMY — flips it live:

  1) validates the Stripe key (read-only GET /v1/balance — no charge)
  2) checks Stripe IDENTITY is enabled (creates a verification session; you CANCEL it in the dashboard — a
     created-but-unverified session is not billed; only a COMPLETED verification is $1.50)
  3) relaunches the backend on :8810 with the key ACTIVE (drops the keyless guard) so it can charge
  4) optional --public-url <URL>: writes verify_api_base (config/beta.json) + rebuilds the public board so
     the signup/checkout buttons call the backend. Without it, the backend is live on your TAILNET only
     (test the whole flow yourself at https://<your-tailnet>/api before exposing it publicly).

Claude will NOT run this — it activates real charging with your live key. You run it; you own the charge.

  python tools/kilo-aupuni/go_live.py                 # validate + go live on tailnet (test it yourself)
  python tools/kilo-aupuni/go_live.py --public-url https://pay.yourdomain   # + wire the public site
"""
import os, sys, json, time, subprocess, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
CFG = os.path.join(PROJ, "config", "stripe.json")
BETA = os.path.join(PROJ, "config", "beta.json")
PORT = 8810


def _key():
    for ev in ("STRIPE_SECRET_KEY", "STRIPE_RESTRICTED_KEY"):
        v = (os.environ.get(ev) or "").strip()
        if v and not v.startswith("PASTE_"): return v
    try:
        d = json.load(open(CFG, encoding="utf-8"))
        for f in ("secret_key", "restricted_key"):
            v = (d.get(f) or "").strip()
            if v and not v.startswith("PASTE_"): return v
    except Exception:
        pass
    return ""


def _stripe(method, path, form=None):
    import urllib.parse
    key = _key()
    if not key: return 0, {"error": {"message": "no key"}}
    data = urllib.parse.urlencode(form, doseq=True).encode() if form is not None else None
    req = urllib.request.Request("https://api.stripe.com/v1/" + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try: return e.code, json.load(e)
        except Exception: return e.code, {"error": {"message": "HTTP %s" % e.code}}
    except Exception as e:
        return 0, {"error": {"message": str(e)[:140]}}


def check_key():
    st, j = _stripe("GET", "balance")
    if st == 200:
        return True, "key VALID + livemode=%s" % j.get("livemode")
    if st == 401:
        return False, "key INVALID/expired"
    if st == 403:
        return True, "key valid but scoped (restricted) — use the sk_live secret key for full go-live"
    return False, "balance check -> %s: %s" % (st, (j.get("error") or {}).get("message", ""))


def check_identity():
    st, j = _stripe("POST", "identity/verification_sessions",
                    {"type": "document", "options[document][require_matching_selfie]": "true"})
    if st == 200:
        return True, "Identity ENABLED — test session %s created (CANCEL it in the dashboard; not billed)" % j.get("id")
    msg = (j.get("error") or {}).get("message", "")
    if "enable" in msg.lower() or "activate" in msg.lower() or st == 400:
        return False, "Identity NOT enabled — turn it on: https://dashboard.stripe.com/settings/identity (%s)" % msg[:80]
    return False, "Identity check -> %s: %s" % (st, msg[:100])


def relaunch_live():
    """Relaunch the backend KEY-ACTIVE (no keyless guard). Returns True if it answers."""
    py = os.path.join(os.environ.get("LocalAppData", ""), "Programs", "Python", "Python311", "pythonw.exe")
    py = py if os.path.exists(py) else sys.executable
    env = dict(os.environ); env.pop("CIVIC_NO_LOCAL_KEY", None)        # key ACTIVE now
    env["ALLOWED_ORIGIN"] = env.get("ALLOWED_ORIGIN", "https://jimlangford.github.io")
    DETACHED = 0x00000008 | 0x00000200
    subprocess.Popen([py, "-X", "utf8", os.path.join(HERE, "stripe_identity_backend.py"), "--serve", str(PORT)],
                     cwd=PROJ, creationflags=DETACHED, close_fds=True, env=env,
                     stdout=open(os.path.join(PROJ, "logs", "civic_api_live.out"), "a"), stderr=subprocess.STDOUT)
    for _ in range(10):
        time.sleep(1)
        try:
            d = json.load(urllib.request.urlopen("http://127.0.0.1:%d/health" % PORT, timeout=4))
            if d.get("key_configured"): return True
        except Exception: pass
    return False


def wire_public(url):
    try:
        c = json.load(open(BETA, encoding="utf-8")) if os.path.exists(BETA) else {}
    except Exception:
        c = {}
    c["verify_api_base"] = url.rstrip("/")
    json.dump(c, open(BETA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # rebuild the public board so its buttons point at the backend
    bp = os.path.join(HERE, "feature_board.py")
    subprocess.run([sys.executable, "-X", "utf8", bp], cwd=PROJ, timeout=120)
    return c["verify_api_base"]


def main():
    pub = None
    if "--public-url" in sys.argv:
        i = sys.argv.index("--public-url")
        pub = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    print("== GO LIVE — civic payment backend ==")
    ok, m = check_key(); print(("  [OK] " if ok else "  [!!] ") + "Stripe key: " + m)
    if not ok:
        print("  -> fix the key in config/stripe.json (use sk_live secret key), then re-run."); return 1
    iok, im = check_identity(); print(("  [OK] " if iok else "  [!!] ") + "Identity: " + im)
    live = relaunch_live()
    print(("  [OK] " if live else "  [!!] ") + "Backend relaunched key-ACTIVE on :%d (key_configured=%s)" % (PORT, live))
    if pub:
        u = wire_public(pub); print("  [OK] Public site wired: verify_api_base=%s + board rebuilt (publish to deploy)" % u)
    else:
        print("  [i ] Tailnet-only: test the full flow yourself at https://<your-tailnet>/api before going public.")
    print("\n  %s" % ("READY TO CHARGE — do a real test purchase to confirm." if (ok and live) else
                       "Not fully live yet — resolve the [!!] items above."))
    if not iok:
        print("  (Enable Identity first if you want the free-tier signup gate; subscriptions can charge without it.)")
    return 0 if (ok and live) else 1


if __name__ == "__main__":
    raise SystemExit(main())
