#!/usr/bin/env python3
"""prosecutor_email.py - build the daily reports EMAIL body (Jimmy 2026-06-19: "send me an email with
links to all of the reports that you find and refine daily").

Composes a neutral, owner-facing email that LINKS to every daily-refined report (served PRIVATE on the
Tailscale King). The email body carries only aggregate counts + the links - NO named officials, dollar-
to-person detail, or allegations: that granular prosecutorial detail stays behind the private links, on
the laptop (doctrine: prosecutor files never leave the machine; the links resolve only on Jimmy's
authenticated devices).

Reads reports/_status/reports_index.json + prosecutor_daily.json. Writes reports/_status/prosecutor/
email_subject.txt + email_body.txt + email_body.html. Stdlib only. Usage: python prosecutor_email.py
"""
import os, sys, json, html
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
ST = os.path.join(PROJ, "reports", "_status")
OUT = os.path.join(ST, "prosecutor")
esc = lambda s: html.escape(str(s if s is not None else ""))


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def build():
    man = load(os.path.join(ST, "reports_index.json"), {}) or {}
    rep = load(os.path.join(OUT, "prosecutor_daily.json"), {}) or {}
    reps = man.get("reports") or []
    index_url = (man.get("base") or "") + "reports_index.html"
    date = rep.get("date") or datetime.now(HST).strftime("%Y-%m-%d")

    # neutral aggregate counts (no names, no per-person dollars)
    tenants = rep.get("tenants") or []
    mv = sum(len((t.get("findings") or {}).get("money_votes", [])) for t in tenants)
    dis = sum(((t.get("findings") or {}).get("dissent_total") or 0) for t in tenants)
    tst = sum(len((t.get("findings") or {}).get("testimony", [])) for t in tenants)
    new = rep.get("new_since_yesterday")
    newn = ("first run" if new is None else "%d new since yesterday" % len(new))
    served = [t["name"] for t in tenants if (t.get("minutes") or {}).get("records")
              or (t.get("findings") or {}).get("parity")]

    groups = {}
    for r in reps:
        groups.setdefault(r["group"], []).append(r)
    order = ["Prosecutor (owner-only)", "Civic", "Awareness & system"]

    subject = "Prosecutor — daily reports (%s)" % date

    # ---------- plaintext ----------
    T = []
    T.append("Daily reports — %s" % date)
    T.append("")
    T.append("All the reports the system finds and refines daily, in one place.")
    T.append("These links resolve only on your Tailscale-authenticated devices (private).")
    T.append("")
    T.append("DAILY REPORTS INDEX (one link to everything):")
    T.append("  %s" % index_url)
    T.append("")
    T.append("Prosecutor snapshot (%s): %d tenants covered, %d money-votes items, %d committee dissent motions, %d cross-checked testimony. %s."
             % (date, len(tenants), mv, dis, tst, newn))
    T.append("Detail (named records, dollar figures, allegations-as-questions) stays behind the private links — it never leaves the laptop.")
    T.append("")
    for g in order:
        if not groups.get(g):
            continue
        T.append("%s:" % g.upper())
        for r in groups[g]:
            T.append("  - %s" % r["title"])
            T.append("    %s" % r["url"])
        T.append("")
    T.append("Refreshed daily. Sourced + allegation-framed; gaps named and routed to UIPA; never fabricated. Aloha.")
    text = "\n".join(T)

    # ---------- html ----------
    seclist = []
    for g in order:
        items = groups.get(g) or []
        if not items:
            continue
        li = "".join(
            "<tr><td style='padding:7px 0;border-bottom:1px solid #eee'>"
            "<a href='%s' style='color:#0b6e4f;font-weight:600;text-decoration:none;font-size:15px'>%s</a>"
            "<div style='color:#555;font-size:13px;margin-top:2px'>%s</div></td></tr>"
            % (esc(r["url"]), esc(r["title"]), esc(r.get("desc"))) for r in items)
        seclist.append(
            "<h3 style='font-family:Arial,sans-serif;color:#333;font-size:13px;letter-spacing:.5px;"
            "text-transform:uppercase;margin:22px 0 4px'>%s</h3><table style='width:100%%;border-collapse:collapse'>%s</table>"
            % (esc(g), li))

    htmlbody = """<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;color:#222">
  <p style="background:#0f2540;border:1px solid #f0c4b4;border-radius:8px;padding:10px 14px;font-size:12px;color:#9a4a2a;margin:0 0 14px">
  🔒 Private — these links resolve only on your Tailscale-authenticated devices. Prosecutorial detail stays on the laptop and never leaves it.</p>
  <h1 style="font-size:22px;margin:6px 0">Daily reports — %s</h1>
  <p style="font-size:14px;color:#444;line-height:1.5">Every report the system finds and refines each day, in one place. The index link below always points to the latest.</p>
  <p style="margin:14px 0"><a href="%s" style="background:#0b6e4f;color:#fff;text-decoration:none;padding:11px 18px;border-radius:8px;font-weight:600;font-size:15px;display:inline-block">📂 Open the daily reports index</a></p>
  <div style="background:#0f2540;border-radius:8px;padding:12px 16px;font-size:13.5px;color:#333;line-height:1.6">
    <b>Prosecutor snapshot (%s):</b> %d tenants covered · %d money-votes items · %d committee dissent motions · %d cross-checked testimony · <b>%s</b>.<br>
    <span style="color:#666">Detail (named records, figures, allegations framed as questions) stays behind the private links.</span>
  </div>
  %s
  <p style="font-size:12px;color:#9aa8b8;margin-top:22px;border-top:1px solid #eee;padding-top:10px">Refreshed daily by the Prosecutor lane (works for JRCSL). Sourced + allegation-framed; gaps named and routed to UIPA; never fabricated. Aloha, solution-side.</p>
</div>""" % (esc(date), esc(index_url), esc(date), len(tenants), mv, dis, tst, esc(newn), "".join(seclist))

    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "email_subject.txt"), "w", encoding="utf-8", newline="\n").write(subject)
    open(os.path.join(OUT, "email_body.txt"), "w", encoding="utf-8", newline="\n").write(text)
    open(os.path.join(OUT, "email_body.html"), "w", encoding="utf-8", newline="\n").write(htmlbody)
    print("prosecutor_email: built -> %s" % OUT)
    print("SUBJECT: %s" % subject)
    print("LINKS: %d (index + %d reports)" % (len(reps) + 1, len(reps)))
    return 0


if __name__ == "__main__":
    sys.exit(build())
