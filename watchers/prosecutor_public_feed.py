#!/usr/bin/env python3
"""Build the public prosecutor factual feed.

This is the public, leak-gated face of the prosecutor lane. It does not read
case_files.html, reports/_status, or private prosecutor work product. It only
packages the already-public oversight pages into a machine-readable JSON feed
and a small public HTML index after the legal owner gate is recorded.
"""
import html
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))


def first_existing(paths):
    for path in paths:
        if path and os.path.exists(path):
            return path
    return paths[-1]


def repo_root():
    cur = HERE
    while True:
        if os.path.isdir(os.path.join(cur, "seed_reports")) or os.path.isdir(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.dirname(HERE)
        cur = parent


ROOT = repo_root()
PROJECT = os.environ.get(
    "KA_PROJECT",
    os.path.join(os.path.expanduser("~"), "Documents", "Claude", "Projects", "Video System elementLOTUS"),
)
CONFIG = os.environ.get("PROSECUTOR_PUBLIC_FEED_CONFIG", os.path.join(HERE, "prosecutor_public_feed_config.json"))
SOURCE_DIR = os.environ.get("PROSECUTOR_PUBLIC_FEED_SOURCE_DIR") or first_existing([
    os.path.join(PROJECT, "reports", "mauios"),
    os.path.join(ROOT, "seed_reports", "mauios"),
])
OUT_DIR = os.environ.get("PROSECUTOR_PUBLIC_FEED_OUT_DIR") or os.path.join(ROOT, "seed_reports", "mauios")
OUT_JSON = os.path.join(OUT_DIR, "prosecutor_public_feed.json")
OUT_HTML = os.path.join(OUT_DIR, "prosecutor_public_feed.html")
HST = timezone(timedelta(hours=-10))

FORBIDDEN = re.compile(
    r"(sk_live|rk_live|whsec_|api_token|webhook_secret|password|"
    r"reports/_status|case_files?\.html|case_file|king-local|tail\d+\.ts\.net|"
    r"prosecutor_daily|prosecutor\.py|prosecutorial back end|recusal_evidence)",
    re.I,
)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"(?:\+?1[-.\s])?(?:\(\d{3}\)|\d{3})[-.\s]\d{3}[-.\s]\d{4}")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def strip_tags(text):
    text = re.sub(r"<script\b.*?</script>", "", text, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", "", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def blocks(page_html):
    return re.findall(r"<div class=finding>(.*?)</div></div>", page_html, re.S)


def text_between(block, class_name):
    m = re.search(r"<div class=%s>(.*?)</div>" % re.escape(class_name), block, re.S)
    return strip_tags(m.group(1)) if m else ""


def list_items(block):
    return [strip_tags(x) for x in re.findall(r"<li>(.*?)</li>", block, re.S)]


def leak_gate(value, where):
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    hits = []
    for label, rx in (("forbidden", FORBIDDEN), ("email", EMAIL), ("phone", PHONE), ("ssn", SSN)):
        if rx.search(text):
            hits.append(label)
    if hits:
        raise SystemExit("prosecutor_public_feed leak gate failed at %s: %s" % (where, ", ".join(hits)))


def approval_gate(cfg):
    approval = cfg.get("approval") or {}
    if approval.get("legal_owner_gate") != "approved":
        raise SystemExit("legal owner-gate is not approved; refusing to emit public feed")
    required = ("approved_by", "approved_at", "source_workboard_item", "scope")
    missing = [k for k in required if not approval.get(k)]
    if missing:
        raise SystemExit("legal owner-gate metadata incomplete: " + ", ".join(missing))
    leak_gate(approval, "approval")
    return approval


def dag_nodes(item_count, held_count):
    """Dependency graph for the public-feed lane, matching services.v2_workboard."""
    return [
        {
            "name": "Public oversight source pages",
            "status": "done",
            "engine": "none",
            "inputs_resolved": True,
            "outputs": ["oversight_hi-*.html"],
        },
        {
            "name": "Legal owner-gate",
            "status": "done",
            "engine": "none",
            "inputs_resolved": True,
            "depends_on": ["Public oversight source pages"],
            "outputs": ["approval.legal_owner_gate=approved"],
        },
        {
            "name": "Curate public-safe subset",
            "status": "done",
            "engine": "none",
            "inputs_resolved": True,
            "depends_on": ["Legal owner-gate"],
            "outputs": ["%d public item(s)" % item_count, "%d held private" % held_count],
        },
        {
            "name": "Leak and PII gate",
            "status": "done",
            "engine": "none",
            "inputs_resolved": True,
            "depends_on": ["Curate public-safe subset"],
            "outputs": ["leak_gate=passed", "pii_gate=passed"],
        },
        {
            "name": "Emit public artifacts",
            "status": "done",
            "engine": "none",
            "inputs_resolved": True,
            "depends_on": ["Leak and PII gate"],
            "outputs": ["prosecutor_public_feed.html", "prosecutor_public_feed.json"],
        },
        {
            "name": "Publish build verification",
            "status": "waiting",
            "engine": "none",
            "inputs_resolved": False,
            "depends_on": ["Emit public artifacts"],
            "outputs": ["12stones.com/12sgi.com public artifact verification"],
        },
    ]


def build():
    cfg = load_json(CONFIG)
    approval = approval_gate(cfg)
    findings = []
    held_total = 0
    counts = {}
    counts_path = os.path.join(SOURCE_DIR, "oversight_counts.json")
    if os.path.exists(counts_path):
        counts = load_json(counts_path)

    for src in cfg.get("source_pages", []):
        page_path = os.path.join(SOURCE_DIR, src["path"])
        if not os.path.exists(page_path):
            continue
        page = open(page_path, encoding="utf-8", errors="replace").read()
        leak_gate(page, src["path"])
        tenant_counts = counts.get(src.get("tenant"), {})
        held_total += int(tenant_counts.get("held") or 0)
        for i, block in enumerate(blocks(page), 1):
            question = text_between(block, "fq")
            record = list_items(block)
            request = ""
            ask = re.search(r"<div class=ask>(.*?)</div>", block, re.S)
            if ask:
                request = strip_tags(ask.group(1)).replace("What we have requested ", "", 1)
            item = {
                "id": "%s-%02d" % (src["tenant"], i),
                "tenant": src["tenant"],
                "tenant_name": src["name"],
                "question": question,
                "public_record": record,
                "records_requested": request,
                "source_page": src["path"],
                "frame": "question for oversight, not an accusation or finding",
            }
            leak_gate(item, item["id"])
            if question and record:
                findings.append(item)

    generated = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    feed = {
        "feed_id": cfg.get("feed_id", "prosecutor-public-factual-feed"),
        "title": cfg.get("title", "Public Factual Feed"),
        "generated_at_hst": generated,
        "approval": approval,
        "integrity": {
            "source_scope": "public oversight pages only",
            "private_findings": "withheld; never included in this feed",
            "language_gate": "allegation/question-framed, not verdict-framed",
            "leak_gate": "passed",
            "pii_gate": "passed",
        },
        "count": len(findings),
        "held_private_count": held_total,
        "dag_nodes": dag_nodes(len(findings), held_total),
        "findings": findings,
    }
    leak_gate(feed, "feed")
    return feed


def maybe_emit_workboard_job(feed):
    if os.environ.get("PROSECUTOR_PUBLIC_FEED_EMIT_JOB") not in ("1", "true", "yes"):
        return None
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from services.v2_workboard import emit_workboard_job
    except Exception as exc:
        print("prosecutor_public_feed: DAG job emit skipped (%s)" % exc)
        return None
    entry = emit_workboard_job(
        source="prosecutor_public_feed",
        action="publish_public_factual_feed",
        event="PROSECUTOR_PUBLIC_FEED",
        lane="output",
        status="pending-approval",
        priority="high",
        approval_types=["legal", "editorial"],
        correlation_id=feed["approval"].get("source_workboard_item"),
        payload={
            "feed_id": feed["feed_id"],
            "count": feed["count"],
            "held_private_count": feed["held_private_count"],
            "artifacts": ["prosecutor_public_feed.html", "data/prosecutor_public_feed.json"],
        },
        dag_nodes=feed["dag_nodes"],
    )
    print("prosecutor_public_feed: emitted DAG workboard job %s" % entry["job"]["id"])
    return entry


def render(feed):
    cards = []
    for item in feed["findings"]:
        rec = "".join("<li>%s</li>" % html.escape(x) for x in item["public_record"][:8])
        cards.append("""<article class="finding">
<div class="meta">%s - <a href="%s">%s</a></div>
<h2>%s</h2>
<div class="label">On the public record</div>
<ul>%s</ul>
<div class="label">Records requested</div>
<p>%s</p>
</article>""" % (
            html.escape(item["tenant_name"]),
            html.escape(item["source_page"]),
            html.escape(item["source_page"]),
            html.escape(item["question"]),
            rec,
            html.escape(item["records_requested"] or "None listed on the source page."),
        ))
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Public Factual Feed | 12 Stones</title>
<style>
:root{--ink:#102033;--dim:#526071;--line:#d9e2ec;--panel:#f8fbff;--accent:#00356b}
body{font-family:system-ui,Segoe UI,sans-serif;margin:0;color:var(--ink);background:white}
.wrap{max-width:980px;margin:0 auto;padding:2rem 1.1rem 3rem}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.eyebrow{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:var(--dim)}
h1{font-size:1.9rem;margin:.25rem 0}.sub{color:var(--dim);line-height:1.55;max-width:76ch}
.gate{border:1px solid var(--line);border-left:4px solid #1f9d55;background:var(--panel);padding:.85rem 1rem;margin:1rem 0}
.finding{border:1px solid var(--line);border-radius:8px;padding:1rem 1.1rem;margin:.9rem 0;background:#fff}
.finding h2{font-size:1.05rem;line-height:1.45;margin:.35rem 0;color:var(--ink);font-style:italic}
.meta,.label{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--dim)}
li,p{color:var(--dim);line-height:1.5}.json{font-weight:650}
</style><body><main class="wrap">
<div class="eyebrow"><a href="tenants_hub.html">govOS</a> - prosecutor public lane</div>
<h1>Public Factual Feed</h1>
<p class="sub">Curated public-record questions already cleared onto the public oversight pages. Private case work, held findings, and owner-only evidence are not included here.</p>
<div class="gate"><b>Gate status:</b> legal owner-gate approved (%s, %s); leak gate passed; PII scan passed. <a class="json" href="prosecutor_public_feed.json">JSON feed</a>. Public entries: %d. Held private: %d.</div>
<p class="sub">DAG status is embedded in the JSON feed so the workboard can track source pages, legal gate, curation, leak/PII gate, artifact emission, and publish verification as ordered dependency nodes.</p>
%s
</main></body></html>""" % (
        html.escape(feed["approval"]["approved_by"]),
        html.escape(feed["approval"]["approved_at"]),
        feed["count"],
        feed["held_private_count"],
        "\n".join(cards) if cards else "<p class=sub>No public entries cleared yet.</p>",
    )


def main():
    feed = build()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(OUT_HTML, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(feed))
    maybe_emit_workboard_job(feed)
    print("prosecutor_public_feed: %d public item(s), %d held private -> %s + %s" %
          (feed["count"], feed["held_private_count"], os.path.basename(OUT_HTML), os.path.basename(OUT_JSON)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
