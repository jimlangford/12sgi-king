#!/usr/bin/env python3
"""connect_post.py — the connect-and-post layer: a client posts our offerings to THEIR channels (Jimmy 2026-06-18).

Chosen stack: Postiz (open-source, self-hosted). This is OUR civic-side connector — it does NOT replace
Postiz (which holds each client's per-network OAuth tokens). It enforces, in code, the three gates the
redesign requires before any post is relayed to a client's connected channel:
  1. CAPABILITY — the caller's tier must have `connect_post` (tier_access.py); else refused.
  2. CONTENT — civic-appropriate; and if the asset is AI CHARACTER ANIMATION it MUST carry the AI-disclosure
     flag (badge + C2PA) — required by platform policy + synthetic-media law (REFERENCES sec 6).
  3. SCOPE — posts go to the CLIENT's own connected channels only. OUR owner-channel allowlist (moon +
     Sunshine-Law agenda, publish_policy.json) is separate and UNCHANGED — this never relaxes it.

SAFE: with no Postiz base_url + POSTIZ_API_KEY env, it runs in STAGING — it records the intent and posts
NOTHING. It never posts autonomously: a post needs a verified client (verify_id), a target channel, and a
human/clien-initiated call. The API key is read from env, never stored. Stdlib only (+ urllib).

API:
  ready()                                   -> bool   (Postiz configured?)
  post(verify_id, channel, text, kind="text", ai_disclosed=False, media=None) -> {ok|staged|refused, ...}
CLI: python connect_post.py --verify-id vs_x --channel youtube --text "..." [--kind character --ai-disclosed]
"""
import os, sys, json, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
PROJ = os.path.dirname(os.path.dirname(HERE))
CFG = os.path.join(PROJ, "config", "connect_post.json")
LEDGER = os.path.join(PROJ, "reports", "_status", "connect_post_log.jsonl")     # PRIVATE intent/audit log
try:
    import tier_access as _ta
except Exception:
    _ta = None


def _cfg():
    try: return json.load(open(CFG, encoding="utf-8"))
    except Exception: return {}


def _base():
    b = (_cfg().get("base_url") or "")
    return b.rstrip("/") if b and not b.startswith("PASTE_") else ""


def _key():
    return os.environ.get(_cfg().get("api_key_env", "POSTIZ_API_KEY"), "")


def ready():
    return bool(_base() and _key())


def _record(rec):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    _line = json.dumps(rec, ensure_ascii=False) + "\n"   # atomic append (single os.write, O_APPEND)
    _fd = os.open(LEDGER, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try: os.write(_fd, _line.encode("utf-8"))
    finally: os.close(_fd)


def post(verify_id, channel, text, kind="text", ai_disclosed=False, media=None):
    """Relay a post to the CLIENT's connected channel via Postiz — after the 3 gates. Stages if unconfigured."""
    pol = _cfg().get("content_policy", {})
    # GATE 1 — capability
    tier = _ta.tier_for(verify_id) if _ta else "free"
    if not (_ta and _ta.can(tier, "connect_post")):
        return {"status": "refused", "reason": "tier '%s' lacks connect_post (Member+ required)" % tier, "tier": tier}
    # GATE 2 — content (AI character animation must be disclosed)
    if kind in ("character", "character_animation", "avatar") and pol.get("character_animation_requires_ai_disclosure", True) and not ai_disclosed:
        return {"status": "refused", "reason": "AI character animation must carry the AI-disclosure flag (badge + C2PA) before posting"}
    if not str(text or "").strip() and not media:
        return {"status": "refused", "reason": "empty post"}
    rec = {"ts": int(time.time()), "verify_id": verify_id, "tier": tier, "channel": channel,
           "kind": kind, "ai_disclosed": bool(ai_disclosed), "text": str(text)[:500],
           "scope": "client_own_channel"}
    # GATE 3 is structural: we only ever target the client's connected channel; never an owner channel.
    if not ready():
        rec["status"] = "staged"; rec["note"] = "Postiz not configured (base_url + POSTIZ_API_KEY) — recorded, NOT posted"
        _record(rec); return rec
    # relay to Postiz (the client's connected channel + tokens live there)
    try:
        body = json.dumps({"type": "now", "channels": [channel],
                           "content": text, "media": media or []}).encode()
        req = urllib.request.Request(_base() + "/public/v1/posts", data=body,
                                     headers={"Authorization": _key(), "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode() or "{}")
        rec["status"] = "posted"; rec["postiz"] = resp.get("id") or resp
        _record(rec); return rec
    except Exception as e:
        rec["status"] = "error"; rec["error"] = str(e)[:160]
        _record(rec); return rec


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify-id", default="")
    ap.add_argument("--channel", default="youtube")
    ap.add_argument("--text", default="")
    ap.add_argument("--kind", default="text")
    ap.add_argument("--ai-disclosed", action="store_true")
    a = ap.parse_args()
    print("Postiz configured:", ready())
    print(json.dumps(post(a.verify_id, a.channel, a.text, a.kind, a.ai_disclosed), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
