#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agenda_approve.py  --  Approval gateway for agenda reels → auto-post.

Two modes:
  submit <slug>   — queue a built reel for Jimmy's review: email + ntfy link, write approval.json=pending
  approve <slug>  — called by king_serve /api/approve-agenda after owner gate passes: post the reel public
  reject  <slug>  — owner rejected: log reason, leave reel private

Flow:
  agenda_reel.py builds reel → calls submit() → ntfy/email → Jimmy taps Approve on phone →
  King /api/approve-agenda (Tailscale-gated) → approve() → upload_shorts.py --public → SHIPPED

The "gate we built already" = publish_policy.json allowlist (agenda slugs pass automatically).
Never calls upload_shorts.py unless verdict=approve from the owner via Tailscale.

Usage:
  python tools/kilo-aupuni/agenda_approve.py submit  <slug>
  python tools/kilo-aupuni/agenda_approve.py approve <slug>
  python tools/kilo-aupuni/agenda_approve.py reject  <slug> [reason]
  python tools/kilo-aupuni/agenda_approve.py pending          # list all pending approvals
"""
from __future__ import annotations
import os, sys, json, time, shutil, subprocess

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

HERE    = os.path.dirname(os.path.abspath(__file__))
ROOT    = os.path.dirname(os.path.dirname(HERE))
REELS   = os.path.join(ROOT, "reports", "_status", "agenda_reels")
FINALS  = os.path.join(ROOT, "finals", "shorts")
DISPATCH= os.path.join(ROOT, "app", "server", "dispatch.py")
PY      = sys.executable
NW      = 0x08000000 if os.name == "nt" else 0
TS_HOST = "https://12sgianonymous.tail760750.ts.net"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reel_dir(slug: str) -> str:
    return os.path.join(REELS, slug)


def _approval_path(slug: str) -> str:
    return os.path.join(_reel_dir(slug), "approval.json")


def _read_approval(slug: str) -> dict:
    try:
        return json.load(open(_approval_path(slug), encoding="utf-8"))
    except Exception:
        return {}


def _write_approval(slug: str, rec: dict):
    rec["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(_approval_path(slug), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)


def _dispatch(msg: str):
    try:
        subprocess.run(
            [PY, DISPATCH, ROOT, "--log-event", msg, "--source", "kilo-aupuni"],
            capture_output=True, timeout=20, creationflags=NW
        )
    except Exception:
        pass


def _notify(title: str, body: str, click: str = ""):
    try:
        notify_py = os.path.join(ROOT, "tools", "ops", "notify_phone.py")
        args = [PY, notify_py, title, body[:200]]
        if click:
            args.append(click)
        subprocess.run(args, capture_output=True, timeout=15, creationflags=NW)
    except Exception:
        pass


def _email(slug: str, reel_dir: str, meta: dict):
    """Build and send a rich HTML approval email from metadata.json + storyboard.json."""
    try:
        approve_url = "%s/king/api/approve-agenda?slug=%s&action=approve" % (TS_HOST, slug)
        reject_url  = "%s/king/api/approve-agenda?slug=%s&action=reject"  % (TS_HOST, slug)

        # Pull structured data
        yt          = meta.get("youtube", {})
        title       = yt.get("title", slug)[:90]
        description = yt.get("description", "")[:500]
        date_str    = meta.get("pretty") or meta.get("date", "")
        tenant      = meta.get("tenant", "Maui County")
        source_url  = meta.get("source", "")
        hook        = (meta.get("marketing") or {}).get("hook", "")
        people      = [p.get("name","") for p in meta.get("people_tags", [])]
        tiktok_cap  = (meta.get("tiktok") or {}).get("caption", "")[:200]

        # Storyboard beats (if present)
        sb_path = os.path.join(reel_dir, "storyboard.json")
        beats = []
        try:
            sb = json.load(open(sb_path, encoding="utf-8"))
            beats = sb.get("beats", [])
        except Exception:
            pass

        # Reel file size
        mp4 = os.path.join(reel_dir, "reel.mp4")
        size_kb = os.path.getsize(mp4) / 1024.0 if os.path.exists(mp4) else 0

        def esc(s):
            return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

        # Beat rows HTML
        beat_rows = ""
        beat_icons = {"hook": "🎯", "what": "📋", "law": "⚖️", "money": "💰",
                      "deadline": "⏰", "testify": "🎤", "close": "🌺"}
        for b in beats:
            icon = beat_icons.get(b.get("kind",""), "•")
            beat_rows += (
                '<tr><td style="padding:5px 10px;font-size:13px;color:#8696ab;width:28px">%s</td>'
                '<td style="padding:5px 8px;font-size:12px;color:#5a6b82;font-variant:small-caps;'
                'letter-spacing:.04em">%s</td>'
                '<td style="padding:5px 8px;font-size:14px;font-weight:600;color:#11213a">%s</td></tr>'
            ) % (icon, esc(b.get("eyebrow","")).title(), esc(b.get("big","")))

        # Council member pills
        people_html = " ".join(
            '<span style="display:inline-block;background:#eef2f8;color:#0f4d92;'
            'border-radius:12px;padding:2px 9px;font-size:12px;margin:2px">%s</span>' % esc(n)
            for n in people
        ) if people else ""

        body_html = """
<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:560px;color:#11213a;margin:0 auto">

  <!-- Header bar -->
  <div style="background:#0f4d92;color:#fff;padding:16px 22px;border-radius:10px 10px 0 0">
    <div style="font-size:11px;letter-spacing:.1em;opacity:.7;margin-bottom:4px">ELEMENTLOTUS · AGENDA REEL</div>
    <div style="font-size:20px;font-weight:700;line-height:1.25">%s</div>
    <div style="font-size:13px;opacity:.8;margin-top:4px">%s &middot; %s &middot; %.0f KB</div>
  </div>

  <!-- Hook -->
  <div style="background:#f4f8ff;border-left:4px solid #0f4d92;padding:12px 18px;font-size:15px;
              font-style:italic;color:#1a3a6b">%s</div>

  <!-- Storyboard beats -->
  %s

  <!-- YouTube description -->
  <div style="padding:14px 18px 4px;font-size:13px;color:#5a6b82;line-height:1.6">%s</div>

  <!-- Council members -->
  %s

  <!-- Action buttons -->
  <div style="padding:20px 18px;background:#fff;border-top:1px solid #e8edf5;margin-top:8px">
    <div style="font-size:13px;color:#8696ab;margin-bottom:12px">
      Tap <b>Approve</b> on Tailscale to post this public, or <b>Reject</b> to hold it.
    </div>
    <a href="%s"
       style="display:inline-block;background:#1f8a4c;color:#fff;text-decoration:none;
              padding:13px 28px;border-radius:9px;font-weight:700;font-size:16px;margin-right:10px">
      ✓ Approve &amp; Post
    </a>
    <a href="%s"
       style="display:inline-block;background:#c0392b;color:#fff;text-decoration:none;
              padding:13px 20px;border-radius:9px;font-weight:700;font-size:16px">
      ✗ Reject
    </a>
  </div>

  <!-- Footer -->
  <div style="padding:10px 18px 14px;font-size:11px;color:#aab4c4">
    slug: %s &middot;
    <a href="%s" style="color:#0f4d92">official source</a>
  </div>

</div>
""" % (
            esc(title), esc(tenant), esc(date_str), size_kb,
            esc(hook),
            ('<table style="width:100%;border-collapse:collapse;margin:0;background:#fafcff">'
             + beat_rows + '</table>') if beat_rows else "",
            esc(description).replace("\n", "<br>"),
            ('<div style="padding:10px 18px">' + people_html + '</div>') if people_html else "",
            approve_url, reject_url,
            esc(slug), esc(source_url)
        )

        body_text = (
            "AGENDA REEL READY FOR APPROVAL\n\n"
            "%s\n%s · %s\n\n"
            "%s\n\n"
            "Beats: %s\n\n"
            "Council: %s\n\n"
            "APPROVE: %s\n"
            "REJECT:  %s\n\n"
            "Source: %s"
        ) % (
            title, tenant, date_str, hook,
            " | ".join(b.get("big","") for b in beats),
            ", ".join(people),
            approve_url, reject_url, source_url
        )

        sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))
        import mail_send
        subject = "[APPROVE?] Agenda Reel: %s — %s" % (tenant, date_str)
        r = mail_send.send(
            to_addr="elementlotus@gmail.com",
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            prefer="elementlotus"
        )
        return bool(r.get("ok"))
    except Exception as e:
        print("agenda_approve._email failed: %s" % e)
        return False


def _publish_gate(slug: str) -> bool:
    """Check publish_policy.json allowlist — agenda slugs are pre-approved for public."""
    try:
        pol = json.load(open(os.path.join(ROOT, "config", "publish_policy.json"), encoding="utf-8"))
        pats = pol.get("public_allow_slug_patterns", [])
    except Exception:
        pats = ["moon", "mahina", "blessing", "agenda", "sunshine", "council", "kilo"]
    s = (slug or "").lower()
    return any(p.lower() in s for p in pats)


def _stage_for_upload(slug: str, reel_dir: str, meta: dict) -> str:
    """Copy reel.mp4 + build clip_01.json in finals/shorts/<slug>/ for upload_shorts.py."""
    dest_dir = os.path.join(FINALS, slug)
    os.makedirs(dest_dir, exist_ok=True)

    # Copy reel.mp4 → clip_01.mp4
    src_mp4 = os.path.join(reel_dir, "reel.mp4")
    dst_mp4 = os.path.join(dest_dir, "clip_01.mp4")
    if not os.path.exists(src_mp4):
        raise FileNotFoundError("reel.mp4 not found at %s" % src_mp4)
    shutil.copy2(src_mp4, dst_mp4)

    # Build clip_01.json from metadata.json
    yt = meta.get("youtube", {})
    clip_meta = {
        "title":          yt.get("title", slug),
        "description":    yt.get("description", ""),
        "tags":           yt.get("tags", []),
        "category_id":    yt.get("category_id", "25"),
        "_privacy_default": "private",
        "_tiktok":        meta.get("tiktok", {}),
        "_instagram_reels": meta.get("instagram_reels", {}),
        "_status":        "APPROVED",
        "_approved_ts":   time.strftime("%Y-%m-%d %H:%M:%S"),
        "_source_slug":   slug,
    }
    with open(os.path.join(dest_dir, "clip_01.json"), "w", encoding="utf-8") as f:
        json.dump(clip_meta, f, ensure_ascii=False, indent=2)

    return dest_dir


# ---------------------------------------------------------------------------
# Main operations
# ---------------------------------------------------------------------------

def submit(slug: str) -> dict:
    """Queue a reel for Jimmy's approval. Called after agenda_reel.py builds the reel."""
    reel_dir = _reel_dir(slug)
    mp4 = os.path.join(reel_dir, "reel.mp4")
    meta_path = os.path.join(reel_dir, "metadata.json")

    if not os.path.exists(mp4):
        return {"ok": False, "error": "reel.mp4 not found — build the reel first"}
    if not os.path.exists(meta_path):
        return {"ok": False, "error": "metadata.json missing"}

    meta = json.load(open(meta_path, encoding="utf-8"))

    # Check if already approved/pending
    existing = _read_approval(slug)
    if existing.get("status") in ("approved", "posted"):
        return {"ok": True, "status": existing["status"], "note": "already handled"}

    if not _publish_gate(slug):
        return {"ok": False, "error": "publish gate: slug not in allowlist (not an agenda slug?)"}

    # Write pending record
    rec = {
        "slug": slug,
        "status": "pending",
        "submitted": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reel_mp4": mp4,
        "approve_url": "%s/king/api/approve-agenda?slug=%s&action=approve" % (TS_HOST, slug),
        "reject_url":  "%s/king/api/approve-agenda?slug=%s&action=reject"  % (TS_HOST, slug),
    }
    _write_approval(slug, rec)

    # Notify Jimmy
    board = meta.get("youtube", {}).get("title", slug)[:60]
    _notify(
        "Approve agenda reel?",
        "%s — tap to open review" % board,
        rec["approve_url"]
    )
    _email(slug, reel_dir, meta)

    _dispatch("ATTENTION (kilo-aupuni): agenda reel READY FOR APPROVAL — %s. "
              "Tap approve on phone or visit %s" % (slug, rec["approve_url"]))

    print("agenda_approve: submitted %s — awaiting Jimmy's approval" % slug)
    return {"ok": True, "status": "pending", "approve_url": rec["approve_url"]}


def approve(slug: str) -> dict:
    """Owner approved via /api/approve-agenda — stage + upload public."""
    reel_dir = _reel_dir(slug)
    meta_path = os.path.join(reel_dir, "metadata.json")

    if not os.path.exists(meta_path):
        return {"ok": False, "error": "metadata.json not found"}

    meta = json.load(open(meta_path, encoding="utf-8"))
    rec = _read_approval(slug)

    if rec.get("status") == "posted":
        return {"ok": True, "note": "already posted", "status": "posted"}

    # Stage for upload_shorts.py
    try:
        dest_dir = _stage_for_upload(slug, reel_dir, meta)
    except Exception as e:
        return {"ok": False, "error": "staging failed: %s" % e}

    # Run upload_shorts.py --public
    upload_py = os.path.join(ROOT, "batch", "upload_shorts.py")
    r = subprocess.run(
        [PY, upload_py, "--slug", slug, "--public"],
        capture_output=True, text=True, timeout=120,
        cwd=ROOT, creationflags=NW
    )
    output = (r.stdout + r.stderr).strip()
    ok = r.returncode == 0

    rec.update({
        "status":   "posted" if ok else "upload_failed",
        "approved": time.strftime("%Y-%m-%d %H:%M:%S"),
        "upload_rc": r.returncode,
        "upload_out": output[:400],
    })
    _write_approval(slug, rec)

    if ok:
        _dispatch("SHIPPED (kilo-aupuni): agenda reel POSTED PUBLIC — %s. "
                  "YouTube upload complete via upload_shorts.py." % slug)
        print("agenda_approve: POSTED — %s" % slug)
    else:
        _dispatch("BLOCKER (kilo-aupuni): agenda reel upload FAILED for %s — "
                  "rc=%s :: %s" % (slug, r.returncode, output[:200]))
        print("agenda_approve: upload FAILED rc=%s :: %s" % (r.returncode, output[:200]))

    return {"ok": ok, "status": rec["status"], "output": output[:400]}


def reject(slug: str, reason: str = "") -> dict:
    """Owner rejected — log and leave private."""
    rec = _read_approval(slug)
    rec.update({"status": "rejected", "rejected": time.strftime("%Y-%m-%d %H:%M:%S"), "reason": reason})
    _write_approval(slug, rec)
    _dispatch("DECISION (kilo-aupuni): agenda reel REJECTED by owner — %s. Reason: %s" % (
        slug, reason or "(none given)"))
    print("agenda_approve: rejected %s" % slug)
    return {"ok": True, "status": "rejected"}


def list_pending() -> list[dict]:
    """Return all slugs with status=pending."""
    out = []
    try:
        for name in os.listdir(REELS):
            ap = os.path.join(REELS, name, "approval.json")
            if os.path.exists(ap):
                rec = json.load(open(ap, encoding="utf-8"))
                if rec.get("status") == "pending":
                    out.append(rec)
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pending"
    if cmd == "submit" and len(sys.argv) > 2:
        r = submit(sys.argv[2])
    elif cmd == "approve" and len(sys.argv) > 2:
        r = approve(sys.argv[2])
    elif cmd == "reject" and len(sys.argv) > 2:
        r = reject(sys.argv[2], " ".join(sys.argv[3:]))
    elif cmd == "pending":
        items = list_pending()
        print("pending approvals: %d" % len(items))
        for it in items:
            print("  %s — submitted %s" % (it.get("slug", "?"), it.get("submitted", "?")))
            print("    approve: %s" % it.get("approve_url", "?"))
        return 0
    else:
        print("usage: agenda_approve.py submit|approve|reject|pending [slug] [reason]")
        return 1
    print(json.dumps(r, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
