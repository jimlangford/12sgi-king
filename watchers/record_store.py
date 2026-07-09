#!/usr/bin/env python3
"""record_store.py — the TRUTH-STORE writer for VP LISTENER (Jimmy 2026-06-20: "ingest the entire record
as txt ... always being truth").

This is the ONE library every listener/ingester calls to persist a piece of the public record as VERBATIM
text + a provenance sidecar, per docs/RECORD_INGEST_SPEC.md. VP LISTENER owns this contract; the fetch
lanes (audio/influencer/server) CALL it to store correctly. It never fetches and never paraphrases — it
just writes the truth + its provenance, idempotently and hashed, so every downstream claim can point at
exact source bytes.

  put(source, tenant, doc_id, text, url, tier, doc_type, ...) -> "written"|"unchanged"|"skip-empty"
  index() -> coverage + integrity (re-hash every .txt vs its .meta sha256)

Layout:  reports/_status/record/<source>/<tenant>/<doc_id>.txt  +  <doc_id>.meta.json
PRIVATE; stdlib only; ASCII. CLI: python record_store.py index
"""
import os, sys, json, re, hashlib
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
ROOT = os.path.join(PROJ, "reports", "_status", "record")
VALID_TIER = ("primary", "secondary")


def _slug(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(s))[:120] or "doc"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def put(source, tenant, doc_id, text, url=None, tier="primary", doc_type=None,
        title=None, person_refs=None, role=None, fetch_tool=None):
    """Persist one record verbatim + provenance. Idempotent: unchanged text -> no rewrite. Returns status."""
    if not text or not text.strip():
        return "skip-empty"
    if tier not in VALID_TIER:
        tier = "secondary"
    d = os.path.join(ROOT, _slug(source), _slug(tenant))
    os.makedirs(d, exist_ok=True)
    base = os.path.join(d, _slug(doc_id))
    txt_path, meta_path = base + ".txt", base + ".meta.json"
    sha = _sha(text)
    try:
        if os.path.exists(meta_path) and json.load(open(meta_path, encoding="utf-8")).get("sha256") == sha:
            return "unchanged"
    except Exception:
        pass
    open(txt_path, "w", encoding="utf-8", newline="\n").write(text)
    meta = {"source": source, "tenant": tenant, "doc_id": _slug(doc_id), "url": url,
            "fetched_at": datetime.now(HST).strftime("%Y-%m-%dT%H:%M:%S%z"),
            "tier": tier, "doc_type": doc_type, "title": title,
            "person_refs": person_refs or [], "role": role, "fetch_tool": fetch_tool,
            "sha256": sha, "bytes": len(text.encode("utf-8", "replace"))}
    open(meta_path, "w", encoding="utf-8", newline="\n").write(json.dumps(meta, ensure_ascii=False, indent=2))
    return "written"


def index():
    """Coverage + integrity: every .txt re-hashed against its .meta sha256 (truth not silently altered)."""
    by_source, by_tenant, total, primary, secondary, bad = {}, {}, 0, 0, 0, []
    if os.path.isdir(ROOT):
        for dp, _, files in os.walk(ROOT):
            for fn in files:
                if not fn.endswith(".meta.json"):
                    continue
                mp = os.path.join(dp, fn)
                try:
                    m = json.load(open(mp, encoding="utf-8"))
                except Exception:
                    bad.append(mp); continue
                total += 1
                by_source[m.get("source")] = by_source.get(m.get("source"), 0) + 1
                by_tenant[m.get("tenant")] = by_tenant.get(m.get("tenant"), 0) + 1
                primary += 1 if m.get("tier") == "primary" else 0
                secondary += 1 if m.get("tier") == "secondary" else 0
                tp = mp[:-len(".meta.json")] + ".txt"
                try:
                    if _sha(open(tp, encoding="utf-8").read()) != m.get("sha256"):
                        bad.append(tp + " (hash mismatch)")
                except Exception:
                    bad.append(tp + " (missing/unreadable)")
    return {"generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"), "root": ROOT,
            "total": total, "primary": primary, "secondary": secondary,
            "by_source": by_source, "by_tenant": by_tenant, "integrity_failures": bad}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "index":
        rep = index()
        os.makedirs(os.path.join(PROJ, "reports", "_status"), exist_ok=True)
        open(os.path.join(PROJ, "reports", "_status", "record_index.json"), "w",
             encoding="utf-8", newline="\n").write(json.dumps(rep, ensure_ascii=False, indent=2))
        print("record_store: %d records (%d primary / %d secondary) | by_source=%s | integrity_failures=%d"
              % (rep["total"], rep["primary"], rep["secondary"], rep["by_source"], len(rep["integrity_failures"])))
        for b in rep["integrity_failures"][:5]:
            print("  INTEGRITY:", b)
    else:
        print("usage: record_store.py index   (library: import record_store; record_store.put(...))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
