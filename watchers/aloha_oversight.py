#!/usr/bin/env python3
"""aloha_oversight.py — the PUBLIC, aloha face of the prosecutor's prep, gated by JRCSL.

The four-stage covenant (Jimmy 2026-06-20: "I want the dashboard produced by a tenant to be based on
its assets, prepared by prosecutor, audited with JRCSL, and made public with aloha"):

  1. ASSETS  — each tenant's findings come ONLY from that tenant's own public record. We reuse
               case_document.tenant_cases(): Maui gets the rich prosecutor logic, the other tenants get
               their sourced org-matters from people_trace. The no-cross-tenant-fallback rule holds —
               a thin tenant honestly surfaces nothing rather than another county's data.
  2. PREPARE — the prosecutor back end shapes each matter (theory / elements / evidence / next record).
               That work product is PRIVATE (reports/_status/case_documents/, owner-only, never published).
  3. AUDIT   — JRCSL's audit-wisdom gate (case_document.gate — ONE definition, imported, never copied)
               clears a matter for the public ONLY if it is sourced, framed as a question (not a verdict),
               names the next record, and is strength >= 3 (REVIEW-READY). Everything else stays private
               (NEEDS-RECORD -> build the record via UIPA first). A second LEAK scan guarantees no private /
               owner / file-path / prosecutorial-theory text can ever cross to the public page.
  4. ALOHA   — what clears is rendered for the public as a QUESTION on the public record: request, not
               accusation; every line sourced; pono. The prosecutorial THEORY is never shown publicly —
               only the public question + the named public records + the record we have requested. If
               nothing clears, the page says so honestly and points to the record-building in flight.

Output: reports/mauios/oversight_<tid>.html  (PUBLIC, the one Yale-blue civic style, build_site publishes it).
This module NEVER writes to reports/_status/ and never reads a secret; it only re-publishes what the gate clears.

  python tools/kilo-aupuni/aloha_oversight.py            # build every tenant's public oversight page
  python tools/kilo-aupuni/aloha_oversight.py --tenant hi-maui
"""
import os, sys, json
from datetime import datetime, timezone, timedelta

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOL_DIR not in sys.path: sys.path.insert(0, TOOL_DIR)
import case_document as CD            # the gate + tenant_cases + TENANTS (single source of truth)
import tenant_pages as TP            # the one Yale-blue civic stylesheet + esc (single source of truth)

HST = timezone(timedelta(hours=-10))
MAUIOS = CD.MAUIOS
esc = TP.esc
CODES = {"hi-maui": "001", "hi-state": "000", "hi-hawaii": "002", "hi-kauai": "003", "hi-honolulu": "004", "ny": "NY"}

# A finding must never carry private / owner / path / prosecutorial-theory text across to the public page.
# This is belt-and-suspenders: the gate already excludes verdict language, and we only render the public
# `question` + sourced evidence + requested record — but we scan the final blob anyway and HOLD on any hit.
_LEAK = ("reports/_status", "reports\\_status", "_status", "owner only", "owner-only", "private king",
         "case_file", "case_document", "prosecutor", "tailscale", "127.0.0.1", ".ts.net", ".jsonl",
         "is guilty", "proven that", "established that", "conclusively", "broke the law")


def aloha_finding(c):
    """The PUBLIC shape of a cleared matter: the question (already framed), the named public records that
    support it, and the record we have requested. The prosecutorial theory is deliberately dropped."""
    return {
        "id": c.get("id", ""),
        "title": c.get("title", ""),
        "question": (c.get("question", "") or "").strip(),
        "record": [e.get("v", "") for e in c.get("evidence", []) if e.get("v")],
        "asked": (c.get("next", "") or "").strip(),
        "strength": c.get("strength", 0),
    }


def _leaky(af):
    blob = " ".join([af["question"], " ".join(af["record"]), af["asked"], af["title"]]).lower()
    return [p for p in _LEAK if p in blob]


def cleared(tenant, maui_cases):
    """Stage 1-3 for one tenant: gather its OWN cases, audit each with the JRCSL gate + leak scan.
    Returns (public_findings, held_count, leak_blocked)."""
    cases = CD.tenant_cases(tenant, maui_cases)        # ASSETS — that tenant's record only (no fallback)
    out, held, leaked = [], 0, 0
    for c in cases:
        verdict, _reasons = CD.gate(c)                 # AUDIT — the one audit-wisdom gate
        if verdict != "REVIEW-READY":
            held += 1
            continue
        af = aloha_finding(c)
        hits = _leaky(af)
        if hits:
            leaked += 1
            held += 1
            continue
        out.append(af)
    # Distinct matters can share a question template (e.g. several orgs -> one lobby question). Collapse by
    # question so the public page never repeats itself; union the sourced records, keep the strongest + its ask.
    merged = {}
    for af in out:
        k = " ".join(af["question"].lower().split())
        if k in merged:
            m = merged[k]
            for r in af["record"]:
                if r not in m["record"]:
                    m["record"].append(r)
            if af["strength"] > m["strength"]:
                m["strength"] = af["strength"]
                if af["asked"]:
                    m["asked"] = af["asked"]
        else:
            merged[k] = dict(af, record=list(af["record"]))
    return list(merged.values()), held, leaked


def render_public(tenant, findings, held):
    """Stage 4 — ALOHA: render the cleared questions as a PUBLIC, Yale-blue civic page. Honest-empty when
    nothing clears, with the record-building note (request, not accusation)."""
    tid = tenant["id"]
    code = CODES.get(tid, "")
    g = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")

    if findings:
        blocks = []
        for i, f in enumerate(findings, 1):
            rec = "".join("<li>%s</li>" % esc(r) for r in f["record"])
            asked = ("<div class=ask><span class=lab>What we have requested</span>%s</div>" % esc(f["asked"])) if f["asked"] else ""
            blocks.append(
                "<div class=finding>"
                "<div class=fq>%s</div>"
                "<div class=sec><span class=lab>On the public record</span><ul class=rec>%s</ul></div>"
                "%s</div>" % (esc(f["question"]), rec, asked))
        body = "<div class=findings>%s</div>" % "".join(blocks)
        lead = ("These are questions for oversight drawn from %s’s own public record — each one sourced, "
                "and framed as a question, never an accusation. They ask the government to show the record; "
                "they do not allege guilt." % esc(tenant["name"]))
    else:
        body = ("<div class=empty><div class=fq>The public record here is still being gathered.</div>"
                "<p class=sub>No matter has yet met the bar to be raised as a public question for %s — "
                "every claim must be sourced to a named public record before it is shown. The records we "
                "have requested are working their way through; as they come back, the questions will appear "
                "here. Until then, this government’s deeper files stay private. Aloha — we ask the record, "
                "we do not accuse.</p></div>" % esc(tenant["name"]))
        lead = ("%s’s public oversight questions are built from its own records only — and none are shown "
                "until they are sourced. Right now the record is still being gathered." % esc(tenant["name"]))

    held_note = ("<p class=sub style='margin-top:1.2rem'>%d additional matter(s) are held private at the "
                 "record-building stage — they are not shown publicly until the public record sustains them. "
                 "That is the covenant: prepared in private, raised in public only when sourced.</p>" % held) if held else ""

    css = TP.CSS + (
        ".finding{border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:14px;"
        "padding:1.05rem 1.1rem;margin:.9rem 0;background:var(--panel)}"
        ".fq{font-weight:650;font-size:1.12rem;color:var(--ink);font-style:italic;line-height:1.45}"
        ".sec{margin-top:.65rem}.lab{display:block;font-family:Consolas,monospace;font-size:.7rem;"
        "letter-spacing:.06em;text-transform:uppercase;color:var(--accent2);margin-bottom:.2rem}"
        ".rec li{font-size:.92rem;color:var(--dim);margin:.15rem 0}"
        ".ask{margin-top:.6rem;color:#33465c;font-size:.92rem}"
        ".empty{border:1px dashed var(--line);border-radius:14px;padding:1.1rem;background:#0f2540}")

    return ("<!doctype html><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            "<meta name=theme-color content='#00356b'>"
            "<title>%s — Questions for oversight | govOS</title><style>%s</style>"
            "<div class=eyebrow><a href='tenants_hub.html'>govOS</a> · <a href='tenant_%s.html'>%s</a> · tenant %s</div>"
            "<h1>Questions for oversight</h1>"
            "<div class=sub>%s <a href='oversight_help.html'>How to read this page →</a></div>"
            "%s%s"
            "<p class=sub style='margin-top:1.4rem;color:var(--faint);font-size:.85rem'>"
            "Prepared from the public record · audited for sourcing before publication · framed as questions, "
            "never accusations · the people’s records stay free · generated %s · aloha · pono</p>"
            "<p class=sub><a href='tenant_%s.html'>← %s dashboard</a> · <a href='tenants_hub.html'>all governments</a></p>"
            % (esc(tenant["name"]), css, esc(tid), esc(tenant["name"]), esc(code),
               lead, body, held_note, g, esc(tid), esc(tenant["name"])))


def build(tenant, maui_cases):
    findings, held, leaked = cleared(tenant, maui_cases)
    os.makedirs(MAUIOS, exist_ok=True)
    out = os.path.join(MAUIOS, "oversight_%s.html" % tenant["id"])
    open(out, "w", encoding="utf-8", newline="\n").write(render_public(tenant, findings, held))
    return len(findings), held, leaked, out


def build_one(tenant):
    """Build a single tenant's public oversight page — the per-tenant entry tenant_audit.py calls each
    cycle so the public page stays current. Only Maui needs the rich prosecutor cases."""
    maui_cases = []
    if tenant.get("id") == "hi-maui":
        try:
            import prosecutor
            maui_cases = prosecutor.build_cases()
        except Exception:
            maui_cases = []
    return build(tenant, maui_cases)


def main():
    only = None
    if "--tenant" in sys.argv:
        i = sys.argv.index("--tenant")
        only = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    # Maui = the rich tenant: reuse the prosecutor's verified case logic (same as case_document.main).
    maui_cases = []
    try:
        import prosecutor
        maui_cases = prosecutor.build_cases()
    except Exception as e:
        print("aloha_oversight: prosecutor.build_cases unavailable (%s) — Maui clears from org-matters only" % e)
    tenants = [t for t in CD.TENANTS if not only or t["id"] == only]
    total_pub = 0
    # counts file so the tenant dashboards can surface "N questions for oversight" + know the page exists
    # (tenant_pages reads it to label/guard the oversight card; merge so --tenant runs don't wipe others).
    cpath = os.path.join(MAUIOS, "oversight_counts.json")
    try:
        counts = json.load(open(cpath, encoding="utf-8"))
    except Exception:
        counts = {}
    for t in tenants:
        n, held, leaked, out = build(t, maui_cases)
        total_pub += n
        counts[t["id"]] = {"public": n, "held": held}
        extra = (" · %d leak-blocked" % leaked) if leaked else ""
        print("  + %-26s %d public question(s), %d held private%s -> %s"
              % (t["name"], n, held, extra, os.path.basename(out)))
    try:
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(counts, f, indent=2)
    except Exception as e:
        print("aloha_oversight: counts write failed (%s)" % e)
    print("aloha_oversight: %d public oversight page(s) written to reports/mauios/ "
          "(JRCSL-gated, sourced, aloha; prosecutor prep stays private). Public questions total: %d"
          % (len(tenants), total_pub))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
