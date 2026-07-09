#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""county_channel.py — the MauiCounty@12sgi.com channel (James 2026-07-02).

INBOUND : classify an incoming county email to the right MIRRORED department + route it (log).
OUTBOUND: PREPARE a draft email TO a county department — DRAFT ONLY.

HARD SEND-GATE (legal + rules): emailing a GOVERNMENT body is official outbound correspondence.
This tool has NO send capability — no SMTP, no API. It writes a draft to a PRIVATE drafts dir and
stops. James reviews and sends, explicitly, ONE at a time. Same discipline as the UIPA letters.

FRAMING: a PRIVATE service (12 Stones Global) reflecting PUBLIC info about Maui County — NOT an
official county system. Inbound mail + drafts are PRIVATE (owner-only; never public/leak-gated).

  python county_channel.py --status
  python county_channel.py --route "Re: SMA permit" "question about the coastal rules"
  python county_channel.py --draft planning "SMA rules inquiry" "We request the public record on ..."
"""
import os, sys, json, re, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
CFG  = os.path.join(PROJ, "config", "county_channel.json")
DEPTS_CFG = os.path.join(PROJ, "config", "maui_departments.json")
PRIV = os.path.join(PROJ, "reports", "_status", "county_channel")   # PRIVATE — never in public build
DRAFTS = os.path.join(PRIV, "drafts")
INBOX_LOG = os.path.join(PRIV, "inbound_routing.jsonl")

# reuse the transparent department keyword map from the mirror (single source)
sys.path.insert(0, HERE)
try:
    from dept_pages import DEPT_KEYWORDS
except Exception:
    DEPT_KEYWORDS = {}


def _load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def _depts():
    return {d.get("id"): d for d in (_load(DEPTS_CFG, {}) or {}).get("departments", [])}


def classify(subject, body):
    """Transparent keyword classification -> (dept_id, score) list, best first. Never guesses silently."""
    blob = ((subject or "") + " " + (body or "")).lower()
    scored = []
    for did, kws in DEPT_KEYWORDS.items():
        n = sum(1 for k in kws if k.strip() and k in blob)
        if n:
            scored.append((did, n))
    scored.sort(key=lambda x: -x[1])
    return scored


def route_inbound(subject, body):
    """Route an inbound county email to a mirrored department. Logs privately. Never sends anything."""
    scored = classify(subject, body)
    depts = _depts()
    if scored:
        did, score = scored[0]
        d = depts.get(did, {})
        result = {"routed_to": did, "department": d.get("name", did),
                  "dept_node": "reports/mauios/dept_%s_maui.html" % did,
                  "confidence": score, "alternatives": [s[0] for s in scored[1:4]]}
    else:
        result = {"routed_to": None, "department": "GENERAL INTAKE — flagged for human triage",
                  "dept_node": None, "confidence": 0, "alternatives": []}
    os.makedirs(PRIV, exist_ok=True)
    rec = {"ts": _now(), "subject": subject, **result}
    with open(INBOX_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return result


def _now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def prepare_outbound(dept_id, subject, body, sources=None):
    """Build a DRAFT email TO a county department. DRAFT ONLY — writes to a private dir, never sends.
    Recipient is the department's OFFICIAL public contact from the registry, or blank+flagged (never faked)."""
    cfg = _load(CFG, {}) or {}
    depts = _depts()
    d = depts.get(dept_id, {})
    to = (d.get("official_email") or "").strip()
    to_line = to if to else "[[RECIPIENT NOT SOURCED — confirm the department's official public contact at mauicounty.gov before sending]]"
    footer = ("\n\n---\n"
              "Sent by 12 Stones Global — a PRIVATE civic-transparency service. This message is NOT from, "
              "and does not represent, Maui County. Reply-to: MauiCounty@12sgi.com.\n"
              "12 Stones Global · [mailing address to confirm] · To stop receiving these, reply STOP.")
    src_block = ""
    if sources:
        src_block = "\n\nSources:\n" + "\n".join("  - %s" % s for s in sources)
    draft = ("DRAFT — NOT SENT. Review + approve before James sends (one at a time).\n"
             "%s\n"
             "From: MauiCounty@12sgi.com (12 Stones Global — private service, not the County)\n"
             "To:   %s\n"
             "Subject: %s\n\n"
             "%s%s%s\n") % ("=" * 66, to_line, subject or "(subject)", (body or "").strip(), src_block, footer)
    os.makedirs(DRAFTS, exist_ok=True)
    slug = re.sub(r"[^\w-]+", "_", (dept_id + "_" + (subject or "draft")))[:60]
    path = os.path.join(DRAFTS, "%s_%s.txt" % (datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"), slug))
    open(path, "w", encoding="utf-8", newline="\n").write(draft)
    return {"draft_path": os.path.relpath(path, PROJ), "to_sourced": bool(to),
            "sent": False, "gate": "DRAFT ONLY — James sends, per-email, explicitly. No SMTP in this tool."}


def status():
    cfg = _load(CFG, {}) or {}
    sg = cfg.get("send_gate", {})
    print("MauiCounty@ channel — STATUS")
    print("  address:", cfg.get("role_address"), "|", cfg.get("status"))
    print("  framing:", cfg.get("framing_disclaimer"))
    print("  SEND-GATE: auto_send=%s | draft_first=%s | per-email owner approval=%s | one-at-a-time=%s"
          % (sg.get("auto_send"), sg.get("draft_first"),
             sg.get("requires_owner_approval_per_email"), sg.get("one_at_a_time")))
    print("  who sends:", sg.get("who_sends"))
    print("  departments mirrored:", len(_depts()))
    print("  drafts dir (PRIVATE):", os.path.relpath(DRAFTS, PROJ))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--route", nargs=2, metavar=("SUBJECT", "BODY"))
    ap.add_argument("--draft", nargs=3, metavar=("DEPT", "SUBJECT", "BODY"))
    a = ap.parse_args()
    if sys.platform == "win32":
        try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    if a.route:
        print(json.dumps(route_inbound(a.route[0], a.route[1]), ensure_ascii=False, indent=1))
    elif a.draft:
        print(json.dumps(prepare_outbound(a.draft[0], a.draft[1], a.draft[2]), ensure_ascii=False, indent=1))
    else:
        status()


if __name__ == "__main__":
    main()
