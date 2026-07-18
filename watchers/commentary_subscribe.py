#!/usr/bin/env python3
"""commentary_subscribe.py — $99/seat govOS Commentary subscriber management.

Manages the Commentary seat tier:
  - Generates Stripe Checkout sessions ($99/mo per seat) for new subscribers
  - Reads the Stripe webhook ledger to confirm active subscriptions
  - Writes/reads config/commentary_subscribers.json (the active-seat roster)
  - CLI for admin: list, add, deactivate

THE TIER: "commentary_seat" — $99/month per seat, govOS product.
  Delivers: running commentary for every council meeting (item-level money/compliance/testimony).
  Gate: Stripe-verified checkout → webhook records → seat active.
  PRIVATE: subscriber list stays in reports/_status, never published.

SERVE==CHARGE: before adding subscribers, verify meeting_commentary.py is generating output
(check reports/_status/meeting_commentary/ has recent files).

Stdlib only.
"""
import os, sys, json, argparse, urllib.request, urllib.parse, ssl
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
CFG  = os.path.join(PROJ, "config")
HST  = timezone(timedelta(hours=-10))

SUBSCRIBERS_F = os.path.join(CFG, "commentary_subscribers.json")
ORDERS_F      = os.path.join(PROJ, "reports", "_status", "paid_orders.jsonl")
STRIPE_BACKEND = os.environ.get("STRIPE_BACKEND_URL", "http://127.0.0.1:8810")

COMMENTARY_PLAN_ID = "commentary_seat"

def _load(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d if d is not None else {}

def _save(p, obj):
    tmp = p + ".tmp"
    open(tmp, "w", encoding="utf-8").write(json.dumps(obj, indent=2, ensure_ascii=False))
    os.replace(tmp, p)

def _now(): return datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")

# ── SUBSCRIBER ROSTER ─────────────────────────────────────────────────────────────
def _load_subs():
    d = _load(SUBSCRIBERS_F, {"_doc": "govOS Commentary seat roster — PRIVATE", "subscribers": []})
    if "subscribers" not in d:
        d["subscribers"] = []
    return d

def _save_subs(s):
    _save(SUBSCRIBERS_F, s)

def get_subscriber(email=None, stripe_customer_id=None):
    subs = _load_subs().get("subscribers", [])
    for s in subs:
        if email and s.get("email") == email:
            return s
        if stripe_customer_id and s.get("stripe_customer_id") == stripe_customer_id:
            return s
    return None

def add_subscriber(email, stripe_customer_id="", stripe_subscription_id="", name=""):
    """Add or activate a subscriber."""
    d = _load_subs()
    existing = get_subscriber(email=email)
    if existing:
        existing["status"] = "active"
        existing["updated_at"] = _now()
        if stripe_customer_id: existing["stripe_customer_id"] = stripe_customer_id
        if stripe_subscription_id: existing["stripe_subscription_id"] = stripe_subscription_id
    else:
        d["subscribers"].append({
            "email": email,
            "name": name,
            "status": "active",
            "tier": COMMENTARY_PLAN_ID,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "created_at": _now(),
            "updated_at": _now(),
        })
    d["updated"] = _now()
    _save_subs(d)
    print("commentary_subscribe: activated %s" % email)

def deactivate_subscriber(email):
    d = _load_subs()
    for s in d.get("subscribers", []):
        if s.get("email") == email:
            s["status"] = "cancelled"
            s["updated_at"] = _now()
    d["updated"] = _now()
    _save_subs(d)
    print("commentary_subscribe: deactivated %s" % email)

# ── SYNC FROM STRIPE WEBHOOK LEDGER ──────────────────────────────────────────────
def sync_from_orders():
    """Promote any paid commentary_seat orders from the webhook ledger to the subscriber roster."""
    activated = 0
    try:
        for line in open(ORDERS_F, encoding="utf-8"):
            line = line.strip()
            if not line: continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if entry.get("tier") != COMMENTARY_PLAN_ID:
                continue
            if entry.get("status") not in ("active", "paid", "verified"):
                continue
            email = entry.get("email") or entry.get("customer_email", "")
            cid   = entry.get("customer_id", "")
            sid   = entry.get("subscription_id", "")
            if email and not get_subscriber(email=email, stripe_customer_id=cid):
                add_subscriber(email, stripe_customer_id=cid, stripe_subscription_id=sid)
                activated += 1
    except FileNotFoundError:
        pass
    if activated:
        print("commentary_subscribe: synced %d new subscriber(s) from orders ledger" % activated)
    return activated

# ── STRIPE CHECKOUT (via the running stripe_identity_backend) ─────────────────────
def generate_checkout_url(email="", success_url="", cancel_url=""):
    """Generate a Stripe Checkout session for commentary_seat via the local Stripe backend.
    Returns {checkout_url} or {error}.
    """
    plans = _load(os.path.join(CFG, "plans.json"), {})
    plan = next((p for p in plans.get("plans", []) if p.get("id") == COMMENTARY_PLAN_ID), {})
    price_id = plan.get("stripe_price_id_month", "")
    if not price_id:
        return {"error": "commentary_seat Stripe price not yet created — run stripe_setup.py --apply first"}

    payload = json.dumps({
        "price_id": price_id,
        "email": email,
        "success_url": success_url or "https://king.tail760750.ts.net/king/commentary?subscribed=1",
        "cancel_url": cancel_url or "https://king.tail760750.ts.net/king/commentary?cancelled=1",
        "metadata": {"tier": COMMENTARY_PLAN_ID},
    }).encode()
    try:
        req = urllib.request.Request(
            "%s/checkout/session" % STRIPE_BACKEND,
            data=payload, headers={"Content-Type": "application/json"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

# ── STATUS ────────────────────────────────────────────────────────────────────────
def show_status():
    d = _load_subs()
    subs = d.get("subscribers", [])
    active = [s for s in subs if s.get("status") == "active"]
    plans = _load(os.path.join(CFG, "plans.json"), {})
    plan = next((p for p in plans.get("plans", []) if p.get("id") == COMMENTARY_PLAN_ID), {})
    mrr = len(active) * 99
    print("commentary_subscribe: %d active seats | MRR $%d/mo" % (len(active), mrr))
    print("  plan: %s | price: $%s/mo | Stripe price: %s" % (
        plan.get("name","commentary_seat"),
        plan.get("price_month",9900) // 100,
        plan.get("stripe_price_id_month") or "(not yet created — run stripe_setup.py --apply)"))
    for s in active:
        print("  + %-40s  sub: %-30s  since: %s" % (
            s.get("email",""), s.get("stripe_subscription_id","")[:28], s.get("created_at","")[:10]))

# ── SERVE==CHARGE GATE ────────────────────────────────────────────────────────────
def serve_gate():
    """Returns True if commentary output is being generated (serve==charge enforced)."""
    priv = os.path.join(PROJ, "reports", "_status", "meeting_commentary")
    if not os.path.exists(priv):
        return False
    files = [f for f in os.listdir(priv) if f.endswith(".json")]
    return len(files) > 0

# ── CLI ───────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="commentary_subscribe — seat management for $99/mo commentary tier")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--sync", action="store_true", help="sync active seats from Stripe webhook ledger")
    ap.add_argument("--add", metavar="EMAIL", help="manually add/activate a subscriber")
    ap.add_argument("--deactivate", metavar="EMAIL")
    ap.add_argument("--name", default="")
    ap.add_argument("--customer-id", default="")
    ap.add_argument("--sub-id", default="")
    ap.add_argument("--serve-check", action="store_true", help="verify serve==charge before enabling")
    args = ap.parse_args()

    if args.serve_check:
        ok = serve_gate()
        print("serve_gate: %s — commentary output %s" % (
            "PASS" if ok else "FAIL",
            "present (serve>=charge)" if ok else "NOT FOUND (do not charge until meeting_commentary.py generates output)"))
        return

    if args.sync:
        sync_from_orders(); show_status(); return
    if args.add:
        add_subscriber(args.add, stripe_customer_id=args.customer_id,
                       stripe_subscription_id=args.sub_id, name=args.name)
        show_status(); return
    if args.deactivate:
        deactivate_subscriber(args.deactivate); show_status(); return
    show_status()

if __name__ == "__main__":
    main()
