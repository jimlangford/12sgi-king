#!/usr/bin/env python3
"""civic_quote.py — the QUOTE ENGINE for paid civic explainers (Jimmy 2026-06-18, "agenda first
which triggers the others").

A member of the public can ask our AI system to explain ANY part of Maui County government and get
a shareable, AI-rendered artifact. This engine turns a request into a PRICE:

    compute estimate (ComfyUI Cloud tokens) → base cost (tokens × rate) → +20% markup → quoted price

The margin funds our OWN token budget (scheduled renders + daily moon posts, months ahead). The
*free* tier (our standard CPU reels/cards) is always $0 — this only prices the PREMIUM cloud renders.

NON-FINANCIAL: this only computes + records a quote. No money moves here. Stripe collection + the
token purchase + fulfillment happen downstream under Jimmy's account/keys (stripe_identity_backend).
Pricing comes from config/civic_pricing.json (Jimmy sets the real token→USD rate). Stdlib only.

CLI:  python civic_quote.py --aspect "Bill 9 — STR phase-out" --tier premium_reel --seconds 24
"""
import os, sys, json, hashlib, argparse
from datetime import datetime, timezone, timedelta
HST = timezone(timedelta(hours=-10))
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
PRICING = os.path.join(PROJ, "config", "civic_pricing.json")
QUOTES = os.path.join(PROJ, "reports", "_status", "civic_quotes.jsonl")  # PRIVATE quote ledger

def _pricing():
    try:
        return json.load(open(PRICING, encoding="utf-8"))
    except Exception:
        return {"token_usd_rate": 0.0, "rate_confirmed": False, "markup_pct": 0.20,
                "service_fee_usd": 0.0, "minimum_price_usd": 3.0, "currency": "usd", "tiers": {}}

def _backend_margins(price, base_cost, p):
    """Customer price is fixed (market token-rate × markup); we fulfill on the cheapest backend we control.
    Returns {backends:{name:{our_cost_usd,margin_usd,...}}, recommended} — the spread is the funding."""
    rb = p.get("render_backends", {})
    out = {}
    if "local_laptop" in rb:
        c = round(float(rb["local_laptop"].get("cost_usd", 0) or 0), 4)
        out["local_laptop"] = {"our_cost_usd": c, "margin_usd": round(price - c, 2),
                               "gpu_gated": True, "note": "GPU co-tenant — only when the card is free; never interrupt an active render (while the studio is RENDERING)"}
    if "comfy_cloud" in rb:
        out["comfy_cloud"] = {"our_cost_usd": base_cost, "margin_usd": round(price - base_cost, 2)}
    if "hourly_gpu" in rb:
        h = rb["hourly_gpu"]
        c = round(float(h.get("hourly_usd", 0) or 0) * (float(h.get("compute_seconds_per_render", 0) or 0) / 3600.0), 4)
        out["hourly_gpu"] = {"our_cost_usd": c, "margin_usd": round(price - c, 2)}
    rec = max(out.items(), key=lambda kv: kv[1]["margin_usd"])[0] if out else None
    return {"backends": out, "recommended": rec}

def _gpu_free(threshold_mib=6000):
    """Best-effort: is the laptop GPU free enough to render locally? (nvidia-smi). Returns (free?, used_mib)."""
    try:
        import subprocess
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=(0x08000000 if os.name == "nt" else 0)).stdout.strip().splitlines()
        used = int(out[0]) if out else 0
        return used < threshold_mib, used
    except Exception:
        return True, 0   # probe failed → assume free (never block a quote on a probe)

def eta(tier, priority, p):
    """ETA for the render, accounting for whether a studio render is holding the GPU."""
    mins = int((p.get("eta", {}).get("render_minutes", {}) or {}).get(tier, 5))
    thr = int(p.get("eta", {}).get("gpu_busy_mib", 6000))
    free, used = _gpu_free(thr)
    if priority == "priority":
        return {"minutes": mins, "gpu_busy": (not free), "gpu_used_mib": used, "backend_hint": "cloud/hourly (preempt)",
                "text": "~%d min — priority: renders now on cloud, no GPU wait" % mins}
    if free:
        return {"minutes": mins, "gpu_busy": False, "gpu_used_mib": used, "backend_hint": "laptop (GPU free now)",
                "text": "~%d min — the GPU is free now" % mins}
    return {"minutes": mins, "gpu_busy": True, "gpu_used_mib": used, "backend_hint": "laptop-when-free, or upgrade to priority",
            "text": "GPU busy with a studio render (%d MiB) — a standard job queues behind it (~%d min once free); upgrade to priority to render now on cloud" % (used, mins)}

def quote(aspect, tier="premium_reel", seconds=20, tenant="hi-maui", priority="standard", when=None):
    """Return a quote dict for rendering an explainer of `aspect` at `tier` for `tenant`. Deterministic +
    recordable. Includes per-backend cost/margin (pick the most profitable available backend), a priority
    surcharge option, and a GPU-aware ETA (so the customer sees when it'll be done if studio is rendering)."""
    p = _pricing()
    tiers = p.get("tiers", {})
    t = tiers.get(tier) or tiers.get("premium_reel") or {"engine": "cloud", "tokens_base": 0, "tokens_per_second": 0}
    seconds = max(0, int(seconds or 0))
    tokens = int(round((t.get("tokens_base", 0)) + (t.get("tokens_per_second", 0)) * seconds))
    rate = float(p.get("token_usd_rate", 0.0) or 0.0)
    markup = float(p.get("markup_pct", 0.20) or 0.0)
    fee = float(p.get("service_fee_usd", 0.0) or 0.0)
    floor = float(p.get("minimum_price_usd", 0.0) or 0.0)
    base_cost = round(tokens * rate, 4)
    if t.get("engine") == "cpu" or tokens == 0:
        price = 0.0                                   # the free local tier is always $0
    else:
        price = round(max(floor, base_cost * (1.0 + markup) + fee), 2)
    surcharge_pct = float(p.get("priority", {}).get("surcharge_pct", 0) or 0)
    if priority == "priority" and price > 0:
        price = round(price * (1.0 + surcharge_pct), 2)   # pay to preempt / cloud-guarantee
    gen = (when or datetime.now(HST)).strftime("%Y-%m-%d %H:%M:%S HST")
    qid = "q_" + hashlib.sha1(("%s|%s|%s|%d|%s" % (tenant, aspect, tier, seconds, gen)).encode()).hexdigest()[:12]
    if price > 0:
        bm = _backend_margins(price, base_cost, p)
        backends, recommended = bm["backends"], bm["recommended"]
    else:
        backends, recommended = {}, "local_cpu_free"        # the free tier renders on the laptop CPU, $0
    return {
        "quote_id": qid, "tenant": tenant, "aspect": (aspect or "").strip()[:200], "tier": tier,
        "tier_label": t.get("label", tier), "engine": t.get("engine", "cloud"),
        "seconds": seconds, "tokens": tokens,
        "token_usd_rate": rate, "base_cost_usd": base_cost,
        "markup_pct": markup, "service_fee_usd": fee, "minimum_price_usd": floor,
        "price_usd": price, "currency": p.get("currency", "usd"),
        "provisional": not bool(p.get("rate_confirmed")),    # true until Jimmy sets the real rate
        "backends": backends, "recommended_backend": recommended,
        "priority": priority, "priority_surcharge_pct": (surcharge_pct if priority == "priority" else 0.0),
        "eta": eta(tier, priority, p),
        "margin_usd": round(price - base_cost, 2) if price else 0.0,
        "generated": gen,
        "note": "Quote funds the render + a 20% margin toward our token budget. Free tier = $0. "
                "PROVISIONAL until the ComfyUI Cloud token rate is confirmed." ,
    }

def quote_for_aspects(aspect_ids, tier="premium_reel", tenant="hi-maui", priority="standard"):
    """Checkbox selection → render spec → quote. The more aspects checked, the longer/richer the explainer
    (more seconds → more tokens → higher price). Returns the quote augmented with the chosen aspect labels."""
    try:
        import explainer_intake as ei
        sp = ei.spec(aspect_ids, tenant)
        seconds = sp["seconds"]; labels = sp["labels"]; aspects = sp["aspects"]
    except Exception:
        seconds, labels, aspects = 24, [], list(aspect_ids or [])
    asp_text = (", ".join(labels) or "agenda explainer")
    q = quote(asp_text, tier, seconds, tenant, priority)
    q["aspects"] = aspects; q["aspect_labels"] = labels
    return q

def record(q):
    """Append the quote to the PRIVATE ledger (no PII; just the quote)."""
    os.makedirs(os.path.dirname(QUOTES), exist_ok=True)
    with open(QUOTES, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(q, ensure_ascii=False) + "\n")
    return q

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aspect", required=True, help="what part of Maui County government to explain")
    ap.add_argument("--tier", default="premium_reel", help="free_cpu | premium_card | premium_reel")
    ap.add_argument("--seconds", type=int, default=20, help="target length for a reel")
    ap.add_argument("--tenant", default="hi-maui", help="govOS tenant (hi-maui, hi-honolulu, hi-state, ny, ...)")
    ap.add_argument("--priority", default="standard", help="standard | priority (preempt + cloud, surcharge)")
    ap.add_argument("--record", action="store_true", help="append to the private quote ledger")
    a = ap.parse_args()
    q = quote(a.aspect, a.tier, a.seconds, a.tenant, a.priority)
    if a.record: record(q)
    print(json.dumps(q, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
