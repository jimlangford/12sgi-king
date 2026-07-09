#!/usr/bin/env python3
"""credits.py - AI-credit metering ledger (Jimmy 2026-06-21, learn-from-UnitedMasters Blueprint AI).

Sibling to tier_access.py. tier_access answers "MAY this user do X?" (yes/no, by paid tier). credits
answers "do they have a credit to SPEND on X?" - the meter that sits BEHIND a yes, so a single 8GB card
isn't drained by unlimited paid use. Spec + rationale: docs/AI_CREDIT_METERING.md.

SAFE BY DEFAULT: config/credit_policy.json enabled=false -> charge() always allows (free, no debit),
so live behavior is UNCHANGED until server-quad-os wires the debit hook + Jimmy flips enabled=true.
Honors serve==charge: only caps listed in costs{} meter; an absent cap costs 0 (never blocks).

Storage: an append-only event ledger (reports/_status/credit_ledger.jsonl) - PRIVATE (gitignored).
Balance is DERIVED by replaying signed events (grant +, topup +, debit -). Grants are idempotent per
period: monthly => period "YYYY-MM" (refreshes each month); one-time taste => period "once" (granted once
ever). Stdlib only. ASCII-safe stdout.

API:
  policy()                         -> dict (the loaded credit_policy.json)
  cost_of(cap, payload=None)       -> int  (credits a call costs; 0 if not metered)
  balance(key)                     -> int  (current spendable credits for verify_id|email)
  grant(key, tier, period=None)    -> dict (apply the tier's monthly/once allotment, idempotent)
  topup(key, units, ref="")        -> dict (add purchased pack credits; called by the Stripe webhook)
  charge(key, cap, payload=None)   -> dict {allow, cost, balance, metered, reason}  (check + debit)
  gate_and_charge(key, cap, ...)   -> dict (tier_access.can() AND charge(); one call for the backend)
"""
import os, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
import sys as _sys; _sys.path.insert(0, os.path.join(PROJ, "app", "server"))
import safe_io
POLICY = os.path.join(PROJ, "config", "credit_policy.json")
LEDGER = os.path.join(PROJ, "reports", "_status", "credit_ledger.jsonl")

try:
    import tier_access  # sibling
except Exception:  # allow import from elsewhere
    tier_access = None


def policy():
    try:
        return json.load(open(POLICY, encoding="utf-8"))
    except Exception:
        return {"enabled": False, "costs": {}, "grants": {}}


def _period_now():
    # calendar month tag for monthly refresh; stable within a month, new each month.
    return time.strftime("%Y-%m")


def cost_of(cap, payload=None):
    """Credits a call costs. Complexity hook: payload may scale cost later (e.g. long render = more);
    today it's a flat per-cap cost. A cap not in costs{} = 0 (not metered)."""
    costs = policy().get("costs", {}) or {}
    base = costs.get(cap, 0)
    try:
        return int(base)
    except Exception:
        return 0


def _norm(key):
    return str(key or "").strip().lower()


def _events(key):
    k = _norm(key)
    out = []
    try:
        for ln in open(LEDGER, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                e = json.loads(ln)
            except Exception:
                continue
            if _norm(e.get("key")) == k:
                out.append(e)
    except FileNotFoundError:
        pass
    return out


def _append(e):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    e.setdefault("iso", time.strftime("%Y-%m-%dT%H:%M:%S"))
    tmp = LEDGER + ".tmp"
    # append is atomic enough for a single-writer ledger; write then flush+fsync
    safe_io.atomic_append(LEDGER, json.dumps(e, ensure_ascii=True))
    if os.path.exists(tmp):
        try: os.remove(tmp)
        except Exception: pass


def balance(key):
    """Spendable credits = sum of signed amounts (grant/topup +, debit -)."""
    bal = 0
    for e in _events(key):
        bal += int(e.get("amount", 0))
    return max(0, bal)


def _granted_periods(key):
    return {(e.get("tier"), e.get("period")) for e in _events(key) if e.get("type") == "grant"}


def grant(key, tier, period=None):
    """Apply a tier's allotment, idempotent per (tier, period).
       monthly -> period defaults to this calendar month (refreshes monthly).
       once     -> a 'once' grant is applied a single time ever (the taste/upsell hook)."""
    pol = policy()
    g = (pol.get("grants", {}) or {}).get(tier, {}) or {}
    done = _granted_periods(key)
    applied = []
    # monthly refresh
    monthly = int(g.get("monthly", 0) or 0)
    per = period or _period_now()
    if monthly > 0 and (tier, per) not in done:
        _append({"key": _norm(key), "type": "grant", "tier": tier, "period": per, "amount": monthly})
        applied.append({"period": per, "amount": monthly})
    # one-time taste
    once = int(g.get("once", 0) or 0)
    if once > 0 and (tier, "once") not in done:
        _append({"key": _norm(key), "type": "grant", "tier": tier, "period": "once", "amount": once})
        applied.append({"period": "once", "amount": once})
    return {"key": _norm(key), "tier": tier, "applied": applied, "balance": balance(key)}


def topup(key, units, ref=""):
    """Add purchased credits (Stripe webhook calls this on a credit-pack checkout)."""
    units = int(units)
    if units <= 0:
        return {"ok": False, "reason": "units must be > 0", "balance": balance(key)}
    _append({"key": _norm(key), "type": "topup", "amount": units, "ref": ref})
    return {"ok": True, "added": units, "balance": balance(key)}


def charge(key, cap, payload=None):
    """The deliver-path meter. Call AFTER tier_access says yes.
       metering OFF (policy.enabled=false) or cap not metered -> allow, no debit.
       else: balance >= cost -> debit + allow; balance < cost -> deny (caller returns 402)."""
    pol = policy()
    cost = cost_of(cap, payload)
    if not pol.get("enabled") or cost <= 0:
        return {"allow": True, "metered": False, "cost": cost, "balance": balance(key), "reason": "not_metered"}
    bal = balance(key)
    if bal >= cost:
        _append({"key": _norm(key), "type": "debit", "cap": cap, "amount": -cost})
        return {"allow": True, "metered": True, "cost": cost, "balance": bal - cost, "reason": "charged"}
    oc = pol.get("out_of_credits", {}) or {}
    return {"allow": False, "metered": True, "cost": cost, "balance": bal,
            "reason": "out_of_credits", "http": oc.get("http", 402),
            "message": oc.get("message", "Out of AI credits.")}


def gate_and_charge(key, cap, tier=None, payload=None):
    """One call the backend can adopt: tier gate THEN credit meter.
       tier omitted -> resolve via tier_access.tier_for(key). The capability name == the cost key."""
    if tier is None and tier_access is not None:
        tier = tier_access.tier_for(key)
    tier = tier or "free"
    if tier_access is not None and not tier_access.can(tier, cap):
        return {"allow": False, "reason": "tier_gate", "tier": tier, "http": 402,
                "message": "Your plan does not include this. Upgrade to continue."}
    v = charge(key, cap, payload)
    v["tier"] = tier
    return v


def main():
    import sys, argparse
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key", default="", help="verify_id or email")
    ap.add_argument("--balance", action="store_true")
    ap.add_argument("--grant", default="", help="tier to grant (free/pro/studio_org/council_pro)")
    ap.add_argument("--topup", type=int, default=0)
    ap.add_argument("--charge", default="", help="capability to charge")
    ap.add_argument("--selftest", action="store_true", help="run an in-memory demo (uses a temp key)")
    a = ap.parse_args()

    if a.selftest:
        return _selftest()
    if not a.key:
        print("need --key (or --selftest)"); return 2
    if a.grant:
        print(json.dumps(grant(a.key, a.grant))); return 0
    if a.topup:
        print(json.dumps(topup(a.key, a.topup, ref="cli"))); return 0
    if a.charge:
        print(json.dumps(gate_and_charge(a.key, a.charge))); return 0
    if a.balance:
        print("balance:", balance(a.key)); return 0
    print("balance:", balance(a.key))
    return 0


def _selftest():
    """Verify grant(refresh+once) / debit / dry / topup against a temp ledger, then clean up."""
    global LEDGER
    real = LEDGER
    LEDGER = os.path.join(PROJ, "reports", "_status", "_credit_selftest.jsonl")
    try:
        if os.path.exists(LEDGER):
            os.remove(LEDGER)
    except Exception:
        pass
    ok = True
    try:
        k = "selftest@example.com"
        # force enabled for the test regardless of live policy
        import builtins
        orig_policy = policy.__globals__.get("policy")
        pol = policy(); pol["enabled"] = True
        globals()["policy"] = lambda: pol  # type: ignore
        print("== credits.py selftest ==")
        g = grant(k, "free")
        print("grant free:", g, "-> expect once=15, balance 15")
        ok &= balance(k) == 15
        g2 = grant(k, "free")  # idempotent
        print("re-grant free (idempotent):", g2, "-> balance still 15")
        ok &= balance(k) == 15
        c = charge(k, "studio_coach")  # cost 5
        print("charge studio_coach(5):", c, "-> allow, balance 10")
        ok &= c["allow"] and balance(k) == 10
        c2 = charge(k, "lora_train")  # cost 26 > 10
        print("charge lora_train(26):", c2, "-> DENY out_of_credits, balance 10")
        ok &= (not c2["allow"]) and balance(k) == 10
        t = topup(k, 100, ref="selftest")
        print("topup 100:", t, "-> balance 110")
        ok &= balance(k) == 110
        c3 = charge(k, "lora_train")  # now affordable (cost 26)
        print("charge lora_train(26):", c3, "-> allow, balance 84")
        ok &= c3["allow"] and balance(k) == 84
        c4 = charge(k, "unknown_cap")  # not metered
        print("charge unknown_cap:", c4, "-> allow, not metered, no debit")
        ok &= c4["allow"] and (not c4["metered"]) and balance(k) == 84
        globals()["policy"] = orig_policy  # type: ignore
    finally:
        try: os.remove(LEDGER)
        except Exception: pass
        LEDGER = real
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
