#!/usr/bin/env python3
"""own_channel_post.py — post to 12SGI's OWN Facebook/Instagram/LinkedIn channels via the
LOCAL, self-hosted Postiz instance (docker-compose.postiz.yml). Free, zero-cloud-token bridge.

DISTINCT FROM watchers/connect_post.py: that script relays posts to a CLIENT's own connected
channels through a separate Postiz deployment (per-client OAuth). This script only ever posts
to the OWNER's own configured channels, read from config/own_channels.json.

WHY NOT X (Twitter) OR YOUTUBE-TEXT-DRAFTS HERE:
  - X/Twitter's write API has no free tier as of 2026 (pay-per-call). Owner decision
    2026-07-11: X drafts route to the manual queue (config/x_manual_queue.json) instead.
  - "youtube" drafts in this repo's social_drafts batches are title/description/thumbnail
    CONCEPTS for a video that doesn't exist yet — there's no asset to post. Those route to
    config/youtube_manual_queue.json. Real YouTube video posting already exists separately via
    watchers/agenda_autopost.py for rendered agenda reels (OAuth, free within Google API quota).

SAFE BY DEFAULT: with no config/own_channels.json (or a channel not 'enabled': true with a
real integration_id), this stages the post and returns without calling anything. It never
posts autonomously — a post needs an explicit CLI invocation with an approved job/batch id
(see tools/publish_approved_social.py), matching docs/SOCIAL_CONNECTORS.md's
BUILD -> STAGE -> REVIEW -> PUBLISH -> LOG -> FAIL CLOSED lifecycle.

API:
  ready(channel)                         -> bool
  post(channel, text, media=None)        -> {status: staged|posted|error|refused, ...}
CLI:
  python watchers/own_channel_post.py --channel facebook --text "..."
  python watchers/own_channel_post.py --status
"""
import os, sys, json, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
CFG = os.path.join(PROJ, "config", "own_channels.json")
LEDGER = os.path.join(PROJ, "reports", "_status", "own_channel_post_log.jsonl")  # PRIVATE audit log
LOCK = os.path.join(PROJ, "reports", "_status", "own_channel_post.lock")


def _cfg():
    try:
        return json.load(open(CFG, encoding="utf-8"))
    except Exception:
        return {}


def _base():
    b = (_cfg().get("base_url") or "")
    return b.rstrip("/")


def _key():
    return os.environ.get(_cfg().get("api_key_env", "POSTIZ_OWN_API_KEY"), "")


def _channel_cfg(channel):
    return (_cfg().get("channels") or {}).get(channel, {})


def ready(channel):
    """True only if base_url + API key are set AND this specific channel is enabled with a
    real (non-placeholder) integration id."""
    c = _channel_cfg(channel)
    iid = c.get("integration_id", "")
    real_id = bool(iid) and not iid.startswith("PASTE_")
    return bool(_base() and _key() and c.get("enabled") and real_id)


def _record(rec):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    fd = os.open(LEDGER, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def _lock_acquire():
    """Simple file lock so two publish runs can't double-post the same instant."""
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(int(time.time())).encode())
        os.close(fd)
        return True
    except FileExistsError:
        # stale lock older than 5 min -> reclaim (a crashed run shouldn't wedge posting forever)
        try:
            age = time.time() - os.path.getmtime(LOCK)
            if age > 300:
                os.remove(LOCK)
                return _lock_acquire()
        except Exception:
            pass
        return False


def _lock_release():
    try:
        os.remove(LOCK)
    except Exception:
        pass


def post(channel, text, media=None):
    """Post to the owner's configured channel via local Postiz. Stages if unconfigured."""
    if not str(text or "").strip() and not media:
        return {"status": "refused", "reason": "empty post"}
    rec = {"ts": int(time.time()), "channel": channel, "text": str(text)[:500], "scope": "own_channel"}
    if not ready(channel):
        rec["status"] = "staged"
        rec["note"] = ("own_channels.json missing/incomplete for '%s' — recorded, NOT posted. "
                       "Connect the channel in the Postiz UI (http://localhost:4008), then set "
                       "'enabled': true + a real integration_id in config/own_channels.json." % channel)
        _record(rec)
        return rec
    if not _lock_acquire():
        rec["status"] = "needs_review"
        rec["note"] = "another publish run is in progress (lock held) — left staged, not posted."
        _record(rec)
        return rec
    try:
        rec["status"] = "publishing"
        _record(rec)
        integration_id = _channel_cfg(channel)["integration_id"]
        body = json.dumps({
            "type": "now",
            "posts": [{"integration": {"id": integration_id}, "value": [{"content": text}]}],
        }).encode()
        req = urllib.request.Request(
            _base() + "/public/v1/posts", data=body,
            headers={"Authorization": _key(), "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode() or "{}")
        rec = dict(rec, status="posted", postiz=resp.get("id") or resp)
        _record(rec)
        return rec
    except Exception as e:
        rec = dict(rec, status="error", error=str(e)[:200])
        _record(rec)
        return rec
    finally:
        _lock_release()


def cmd_status():
    cfg = _cfg()
    print("own_channel_post STATUS")
    print("  base_url:", _base() or "(not configured — copy config/own_channels.json.example)")
    print("  api_key set:", bool(_key()))
    for name, c in (cfg.get("channels") or {}).items():
        print("   - %-10s enabled=%s integration_id=%s ready=%s" % (
            name, c.get("enabled"), bool(c.get("integration_id", "").strip() and
            not c.get("integration_id", "").startswith("PASTE_")), ready(name)))


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channel", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status or not a.channel:
        cmd_status()
        return 0
    print(json.dumps(post(a.channel, a.text), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
