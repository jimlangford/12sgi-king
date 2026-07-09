#!/usr/bin/env python3
"""approval_email.py — email Jimmy a PREVIEW of each pending outbound item with Approve / Reject buttons
that work from his mail (Jimmy 2026-06-19: "send them to me first with an approval button").

For every queued item still awaiting approval (outbox.py, status=pending, not yet notified), this sends
Jimmy a preview (who it goes to, subject, full body) with two big buttons. The button URLs carry the
item's single-use token and resolve via config/approval.json:
  - mode 'tailscale' (LIVE today, secure): buttons -> <approve_base>/approve|reject?id=..&t=..  (King endpoint)
  - mode 'public'   (off 12sgi.com): buttons -> <public_base>/approve.html?id=..&t=..&a=send|reject
    (the static page calls the public backend; requires the :8443 funnel up + the funnel-leak finding
    cleared + api.12sgi.com — server-lane/owner-gated, NOT live yet).

No-ops cleanly until the SMTP credential exists. PRIVATE; stdlib only; ASCII.
Usage: python approval_email.py
"""
import os, sys, json, html

HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
CFG = os.path.join(PROJ, "config", "approval.json")
esc = lambda s: html.escape(str(s if s is not None else ""))

sys.path.insert(0, os.path.join(PROJ, "tools", "kilo-aupuni"))
import outbox  # noqa: E402


def cfg():
    try:
        return json.load(open(CFG, encoding="utf-8"))
    except Exception:
        return {"mode": "tailscale",
                "approve_base": "https://12sgianonymous.tail760750.ts.net/king",
                "public_base": "https://12sgi.com", "owner_email": "jimlangford@me.com"}


def urls(c, item):
    iid, tok = item["id"], item["token"]
    if c.get("mode") == "public":
        b = c.get("public_base", "https://12sgi.com")
        return ("%s/approve.html?id=%s&t=%s&a=send" % (b, iid, tok),
                "%s/approve.html?id=%s&t=%s&a=reject" % (b, iid, tok))
    b = c.get("approve_base", "https://12sgianonymous.tail760750.ts.net/king")
    return ("%s/approve?id=%s&t=%s" % (b, iid, tok),
            "%s/reject?id=%s&t=%s" % (b, iid, tok))


def render(item, approve_url, reject_url):
    body_prev = (item.get("body_text") or "")
    text = ("APPROVAL NEEDED before this is sent on your behalf.\n\n"
            "TO: %s\nSUBJECT: %s\n\n--- message ---\n%s\n--- end ---\n\n"
            "APPROVE & SEND: %s\nREJECT: %s\n\n"
            "(Approving sends it from jrcsl@12sgi.com to the recipient above. The link is single-use.)"
            % (item.get("to"), item.get("subject"), body_prev, approve_url, reject_url))
    htmlbody = """<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#222">
  <p style="background:#fff8e6;border:1px solid #e8d28a;border-radius:8px;padding:10px 14px;font-size:13px;color:#7a5a10;margin:0 0 14px">
  ✋ <b>Approval needed</b> — this will be sent on your behalf only after you approve. Single-use links.</p>
  <table style="width:100%%;background:#f6f8f7;border-radius:8px;font-size:13.5px;color:#333">
    <tr><td style="padding:10px 14px"><b>To:</b> %s<br><b>Subject:</b> %s<br><b>From:</b> jrcsl@12sgi.com</td></tr>
  </table>
  <pre style="white-space:pre-wrap;background:#fff;border:1px solid #eee;border-radius:8px;padding:14px;font-size:13px;line-height:1.5;color:#222;font-family:Georgia,serif">%s</pre>
  <p style="margin:18px 0">
    <a href="%s" style="background:#0b6e4f;color:#fff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:700;font-size:16px;display:inline-block;margin-right:10px">✅ Approve &amp; send</a>
    <a href="%s" style="background:#a23a2a;color:#fff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:700;font-size:16px;display:inline-block">✖ Reject</a>
  </p>
  <p style="font-size:11.5px;color:#999">Approving sends it from jrcsl@12sgi.com to the recipient above. If a button doesn't open, copy this link: %s</p>
</div>""" % (esc(item.get("to")), esc(item.get("subject")), esc(body_prev),
            esc(approve_url), esc(reject_url), esc(approve_url))
    return text, htmlbody


def main():
    c = cfg()
    owner = c.get("owner_email", "jimlangford@me.com")
    pend = [it for it in outbox.list_items("pending") if not it.get("notified")]
    if not pend:
        print("approval_email: no new pending items to preview")
        return 0
    sys.path.insert(0, os.path.join(PROJ, "tools", "ops"))
    try:
        import mail_send
    except Exception as e:
        print("approval_email: hub mailer unavailable (%s); %d preview(s) waiting." % (e, len(pend))); return 0
    n = 0
    for it in pend:
        a_url, r_url = urls(c, it)
        text, htmlbody = render(it, a_url, r_url)
        try:
            res = mail_send.send(to_addr=owner, subject="Approve to send: %s" % (it.get("subject") or it["id"]),
                                 body_text=text, body_html=htmlbody)
        except Exception as e:
            res = {"ok": False, "tried": str(e)[:120]}
        if not (res and res.get("ok")):
            print("approval_email: send FAILED for %s (%s)" % (it["id"], res.get("tried"))); continue
        it["notified"] = True
        outbox._save(it)
        n += 1
        print("approval_email: previewed %s -> %s (via %s)" % (it["id"], owner, res.get("via")))
    print("approval_email: %d preview(s) sent (mode=%s)" % (n, c.get("mode")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
