#!/usr/bin/env python3
"""outbox.py — the email APPROVAL-GATE queue (Jimmy 2026-06-19: "send them to me first with an approval
button that works from my mail").

Nothing outbound to a third party (UIPA letters to the County Clerk, civic outreach, etc.) sends until
Jimmy approves. Flow:
  1. enqueue(...) puts the outbound email in the queue (status=pending) with a long single-use TOKEN.
  2. approval_email.py emails Jimmy a PREVIEW of each pending item with Approve / Reject buttons whose
     links carry the token (the buttons resolve via the King approve endpoint -> see config/approval.json).
  3. Jimmy taps Approve (works remotely from his mail) -> the endpoint calls approve(id, token) here.
  4. send_approved() (run in the daily tick / on demand) sends every approved item to its REAL recipient
     from the 12sgi identity (jrcsl@12sgi.com) and marks it sent. Tokens are single-use.

INTEGRITY: tokens are long + random + single-use; approve()/reject() only flip an EXISTING queued
item's status — they can never inject a new recipient or body. PRIVATE; stdlib only; ASCII.
CLI: python outbox.py list | send | enqueue-uipa
"""
import os, sys, json, time, hmac, secrets

HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
DIR = os.path.join(PROJ, "reports", "_status", "outbox")
UIPA = os.path.join(PROJ, "reports", "_status", "uipa")


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _path(item_id):
    return os.path.join(DIR, item_id + ".json")


def _save(item):
    os.makedirs(DIR, exist_ok=True)
    open(_path(item["id"]), "w", encoding="utf-8", newline="\n").write(
        json.dumps(item, ensure_ascii=False, indent=2))
    return item


def get(item_id):
    try:
        return json.load(open(_path(item_id), encoding="utf-8"))
    except Exception:
        return None


def list_items(status=None):
    out = []
    if not os.path.isdir(DIR):
        return out
    for fn in sorted(os.listdir(DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            it = json.load(open(os.path.join(DIR, fn), encoding="utf-8"))
        except Exception:
            continue
        if status is None or it.get("status") == status:
            out.append(it)
    return out


def enqueue(to, subject, body_text, body_html=None, source="", item_id=None, action=None):
    item_id = item_id or ("item-" + secrets.token_hex(6))
    item = {
        "id": item_id,
        "created": _now(),
        "source": source,
        "to": to,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        # action: a TYPED decision to APPLY on approve (None = plain email item). Set by the trusted
        # enqueue, NOT by the approve request (which only carries id+token) - so a button can never inject
        # an action; it can only fire the one that was queued. Approving APPLIES it (no email sent).
        "action": action,
        "token": secrets.token_urlsafe(24),
        "status": "pending",      # pending -> approved -> sent | applied | rejected | failed
        "approved_at": None,
        "sent_at": None,
        "notified": False,        # has Jimmy been emailed the preview?
    }
    return _save(item)


def enqueue_respond(to, subject, body_text, body_html=None, source="", item_id=None,
                    preview_subject=None, preview_body=None):
    """Queue an AUTOMATIC RESPONSE for owner approval. Jimmy gets the usual Approve/Reject preview;
    on approve, respond_approved() sends `body_text`/`body_html` to `to` from the JRCSL/12sgi identity."""
    action = {"type": "respond", "to": to, "subject": subject,
              "body_text": body_text, "body_html": body_html}
    return enqueue(to=to, subject=preview_subject or ("[RESPOND] " + subject),
                   body_text=preview_body or body_text, body_html=body_html,
                   source=source or "respond", item_id=item_id, action=action)


def enqueue_job(verb, arg=None, note="", confirm_to=None, source="", item_id=None):
    """Queue a JOB for owner approval. On approve, respond_approved() drops the allowlisted verb into
    jobs/queue/ for the runner. The verb is fixed HERE (trusted); the button can only fire it."""
    action = {"type": "run_job", "verb": verb, "arg": arg, "note": note, "confirm_to": confirm_to}
    subj = "[JOB] %s%s" % (verb, (" " + str(arg)) if arg else "")
    body = "Approve to queue job '%s'%s for execution.\n%s" % (
        verb, (" arg=" + str(arg)) if arg else "", note)
    return enqueue(to=(confirm_to or "owner"), subject=subj, body_text=body,
                   source=source or "job", item_id=item_id, action=action)


def _job_verb_allowlist():
    """Verbs a run_job approval item may drop into jobs/queue/ — sourced from config/approval.json
    (auto_respond.job_verbs), with a conservative default. The verb is fixed at ENQUEUE time; the
    approve button can only fire a pre-queued job, never choose one — so this bounds what is reachable."""
    default = ["status", "publish", "render", "deliver", "agenda_reels", "prosecutor"]
    try:
        c = json.load(open(os.path.join(PROJ, "config", "approval.json"), encoding="utf-8"))
        v = (c.get("auto_respond") or {}).get("job_verbs")
        return v if isinstance(v, list) and v else default
    except Exception:
        return default


def _send_response(to, subject, body_text, body_html=None):
    """Send an outbound RESPONSE via the branded hub mailer (JRCSL / 12sgi identity + Reply-To)."""
    if not to or "@" not in str(to):
        return {"ok": False, "error": "bad recipient"}
    sys.path.insert(0, os.path.join(PROJ, "tools", "ops"))
    import mail_send
    return mail_send.send(to_addr=to, subject=subject, body_text=body_text or "", body_html=body_html,
                          prefer="jrcsl", from_addr="JRCSL - elementLOTUS <jrcsl@12sgi.com>",
                          headers={"Reply-To": "jrcsl@12sgi.com"})


def _apply_decision(action):
    """Apply a TYPED, whitelisted decision. Reversible config appends / allowlisted job drops / a
    pre-composed response send — never arbitrary code chosen by the button."""
    try:
        t = (action or {}).get("type")
        if t == "respond":
            # Send a PRE-COMPOSED response (fixed at enqueue time) to a designated recipient.
            r = _send_response(action.get("to"), action.get("subject") or "",
                               action.get("body_text") or "", action.get("body_html"))
            if r and r.get("ok"):
                return {"ok": True, "note": "response sent -> %s (via %s)" % (action.get("to"), r.get("via"))}
            return {"ok": False, "error": "respond send failed: %s" % (r.get("tried") if r else "no mailer")}
        if t == "run_job":
            # Drop a PRE-SPECIFIED, allowlisted job into jobs/queue/ for the existing jobrunner.
            verb = action.get("verb")
            if verb not in _job_verb_allowlist():
                return {"ok": False, "error": "run_job: verb '%s' not allowlisted" % verb}
            job = {"type": verb, "arg": action.get("arg"), "source": "approved-job",
                   "queued": _now(), "note": action.get("note") or ""}
            qdir = os.path.join(PROJ, "jobs", "queue")
            os.makedirs(qdir, exist_ok=True)
            jid = "job-" + secrets.token_hex(6)
            tmp = os.path.join(qdir, jid + ".json.tmp")
            open(tmp, "w", encoding="utf-8", newline="\n").write(json.dumps(job, ensure_ascii=False, indent=2))
            os.replace(tmp, os.path.join(qdir, jid + ".json"))
            note = "job '%s' queued for the runner (%s)" % (verb, jid)
            ct = action.get("confirm_to")
            if ct and "@" in str(ct):
                try:
                    _send_response(ct, "Approved job queued: %s" % verb, note)
                except Exception:
                    pass
            return {"ok": True, "note": note, "job_id": jid}
        if t == "identity_classify":
            name, bucket = action.get("name"), action.get("bucket")
            if bucket not in ("daemons", "suppliers", "retired") or not name:
                return {"ok": False, "error": "bad classify action"}
            idp = os.path.join(PROJ, "config", "identity.json")
            d = json.load(open(idp, encoding="utf-8"))
            lst = d.get(bucket) or []
            if name not in lst:
                lst.append(name); d[bucket] = lst; d["updated"] = _now()[:10]
                tmp = idp + ".tmp"
                open(tmp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))
                os.replace(tmp, idp)
                return {"ok": True, "note": "classified '%s' -> identity.json[%s]" % (name, bucket)}
            return {"ok": True, "note": "'%s' already in %s" % (name, bucket)}
        return {"ok": False, "error": "unknown action type %s" % t}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _verify(item, token):
    return bool(item) and bool(token) and hmac.compare_digest(str(item.get("token") or ""), str(token))


def approve(item_id, token):
    it = get(item_id)
    if not _verify(it, token):
        return {"ok": False, "error": "invalid token or item"}
    if it["status"] in ("sent", "applied"):
        return {"ok": True, "status": it["status"], "note": "already done"}
    it["token"] = ""  # single-use: burn the token on approval
    action = it.get("action")
    if action:
        atype = (action or {}).get("type")
        if atype in ("respond", "run_job"):
            # DEFER to the tick responder (respond_approved) — keep the button instant; a transient
            # SMTP/job failure just retries next cycle. Mirrors how approved EMAILS wait for send.
            it["status"] = "approved"; it["approved_at"] = _now(); _save(it)
            return {"ok": True, "status": "approved", "subject": it.get("subject"),
                    "note": "approved — %s runs automatically on the next responder tick" % atype}
        res = _apply_decision(action)         # legacy synchronous decision (identity_classify)
        it["status"] = "applied" if res.get("ok") else "failed"
        it["approved_at"] = _now(); it["apply_result"] = res
        _save(it)
        return {"ok": res.get("ok"), "status": it["status"], "subject": it.get("subject"),
                "note": res.get("note") or res.get("error")}
    it["status"] = "approved"                 # EMAIL item -> queue for send
    it["approved_at"] = _now()
    _save(it)
    return {"ok": True, "status": "approved", "subject": it.get("subject"), "to": it.get("to")}


def reject(item_id, token):
    it = get(item_id)
    if not _verify(it, token):
        return {"ok": False, "error": "invalid token or item"}
    it["status"] = "rejected"
    it["token"] = ""
    _save(it)
    return {"ok": True, "status": "rejected", "subject": it.get("subject")}


def send_approved():
    """Send every approved EMAIL item to its REAL recipient via the hub failover mailer (jrcsl->brand);
    mark sent/failed. Action items (respond/run_job) are handled by respond_approved(), not here.
    No-ops cleanly if no mailer is configured."""
    approved = [it for it in list_items("approved") if not it.get("action")]
    if not approved:
        return 0
    sys.path.insert(0, os.path.join(PROJ, "tools", "ops"))
    try:
        import mail_send
    except Exception as e:
        print("outbox: hub mailer unavailable (%s); %d approved waiting." % (e, len(approved))); return 0
    sent = 0
    for it in approved:
        try:
            res = mail_send.send(to_addr=it["to"], subject=it["subject"],
                                 body_text=it.get("body_text") or "", body_html=it.get("body_html"))
        except Exception as e:
            res = {"ok": False, "tried": str(e)[:120]}
        if not (res and res.get("ok")):
            it["status"] = "failed"; it["error"] = str(res.get("tried"))[:200]; _save(it)
            print("outbox: FAILED %s -> %s (%s)" % (it["id"], it["to"], res.get("tried")))
            continue
        it["status"] = "sent"; it["sent_at"] = _now(); it["sent_via"] = res.get("via"); _save(it)
        sent += 1
        print("outbox: sent %s -> %s (via %s)" % (it["id"], it["to"], res.get("via")))
    return sent


def respond_approved():
    """AUTO-RESPOND on approved TASK & JOB items (Jimmy 2026-07-03: "respond automatically on approved
    tasks and jobs"). For every item Jimmy has APPROVED that carries a respond/run_job action, apply it:
      respond  -> send the pre-composed response to its recipient (branded JRCSL / 12sgi identity)
      run_job  -> drop the allowlisted verb into jobs/queue/ for the existing jobrunner
    Mirrors send_approved() for emails; runs in the daily maintenance tick. Idempotent: only touches
    status='approved' action items, then marks them applied/failed so they never re-fire."""
    items = [it for it in list_items("approved")
             if (it.get("action") or {}).get("type") in ("respond", "run_job")]
    if not items:
        return 0
    done = 0
    for it in items:
        res = _apply_decision(it["action"])
        it["status"] = "applied" if res.get("ok") else "failed"
        it["responded_at"] = _now(); it["apply_result"] = res
        _save(it)
        if res.get("ok"):
            done += 1
        print("outbox: responded %s (%s) -> %s" % (
            it["id"], it["action"].get("type"), res.get("note") or res.get("error")))
    return done


def enqueue_uipa():
    """Seed the 3 EXAMINE UIPA letters (already generated on disk) into the approval queue."""
    tr = get_tracker()
    reqs = tr.get("requests") if isinstance(tr, dict) else tr
    reqs = reqs if isinstance(reqs, list) else []
    n = 0
    for meta in reqs:
        rid = meta.get("id")
        if not rid or get(rid):   # skip if no id or already enqueued
            continue
        txt = os.path.join(UIPA, rid + ".txt")
        try:
            content = open(txt, encoding="utf-8").read()
        except Exception:
            continue
        subject, _, body = content.partition("\n\n")
        enqueue(to=meta.get("recipient") or "county.clerk@mauicounty.us",
                subject=(meta.get("subject") or subject).strip(),
                body_text=body.strip(),
                source="uipa", item_id=rid)
        n += 1
    print("outbox: enqueued %d UIPA letter(s) for approval" % n)
    return n


def get_tracker():
    try:
        return json.load(open(os.path.join(UIPA, "tracker.json"), encoding="utf-8"))
    except Exception:
        return {}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for it in list_items():
            print("  [%s] %s -> %s :: %s" % (it["status"].upper(), it["id"], it["to"], it["subject"][:60]))
    elif cmd == "send":
        send_approved()
    elif cmd == "respond":
        n = respond_approved()
        print("outbox: responded to %d approved task/job item(s)" % n)
    elif cmd == "enqueue-uipa":
        enqueue_uipa()
    else:
        print("usage: outbox.py list|send|respond|enqueue-uipa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
