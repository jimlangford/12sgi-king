#!/usr/bin/env python3
# spark.py - the CREATIVE SPARK ledger (Jimmy 2026-06-16: "I take notes while I read your realtime feed.
#   sometimes your words bring up different areas of my creative thought. it's worth tracking in our
#   dashboards."). A spark = a cross-domain creative thought that fires while reading the feed. We capture
#   it with a timestamp, the note, an optional trigger (what sparked it), and an auto-tagged domain, so the
#   emergent ideas of the collaboration are never lost — and we can SEE where the work lights Jimmy up.
#   Usage:  python spark.py "the note"  [--trigger "what I was saying/doing"]  [--domain film]
#           python spark.py --render        # just rebuild the dashboard
# Output: reports/_status/sparks/creative_sparks.jsonl + creative_sparks.html. Stdlib only.
import os, sys, json, re, argparse
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT = os.path.join(PROJECT, "reports", "_status", "sparks")
LEDGER = os.path.join(OUT, "creative_sparks.jsonl")
HST = timezone(timedelta(hours=-10))

# auto-tag the domain from the note text (the Quadcast surfaces + the work areas)
DOMAINS = [
    ("film",    r"film|wick|constantine|screenplay|scene|seventh stone|act\b|cast|keanu"),
    ("music",   r"music|song|video|mv\b|lyric|chord|verse|distrokid|suno"),
    ("game",    r"game|sage|deck|card|node|ue5|mesh|character|luna|zone|portal"),
    ("civic",   r"civic|govos|tenant|council|minutes|vote|nay|dissent|granicus|legistar|money|contract|district"),
    ("farm",    r"farm|hfev|soil|biodiversity|moon|kaulana|fishing|harvest|mauka|crop"),
    ("render",  r"render|comfy|wan|distorch|lora|sdxl|vram|face-?lock"),
    ("spirit",  r"kumulipo|ao|pō|aloha|christ|covenant|pono|lineage|ancestral|holy"),
]
def tag(text):
    t = text.lower()
    hits = [d for d, pat in DOMAINS if re.search(pat, t)]
    return hits or ["unfiled"]

def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def load():
    out = []
    if os.path.exists(LEDGER):
        for ln in open(LEDGER, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try: out.append(json.loads(ln))
                except Exception: pass
    return out

def render(rows):
    os.makedirs(OUT, exist_ok=True)
    from collections import Counter
    dom = Counter(d for r in rows for d in r.get("domains", []))
    chips = " ".join("<span class=chip>%s · %d</span>" % (esc(d), c) for d, c in dom.most_common())
    items = ""
    for r in reversed(rows[-200:]):
        ds = " ".join("<span class=tag>%s</span>" % esc(d) for d in r.get("domains", []))
        trig = ("<div class=trig>↳ from: %s</div>" % esc(r["trigger"])) if r.get("trigger") else ""
        items += ("<div class=spark><div class=when>%s %s</div><div class=note>%s</div>%s</div>"
                  % (esc(r.get("ts","")), ds, esc(r.get("note","")), trig))
    html = ("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=120>"
        "<title>Creative Sparks — the collaboration ledger</title><style>"
        "body{font-family:system-ui,Segoe UI,sans-serif;max-width:820px;margin:1.4rem auto;padding:0 1rem;background:#0d1117;color:#e6edf3}"
        "h1{font-size:1.35rem;margin:.2rem 0}.sub{color:#8b949e;font-size:.86rem;margin-bottom:.8rem}"
        ".chips{margin:.5rem 0 1.1rem}.chip{display:inline-block;background:#161b22;border:1px solid #30363d;border-radius:99px;padding:.18rem .6rem;margin:.15rem .2rem;font-size:.75rem;color:#9db4d0}"
        ".spark{border-left:3px solid #6e5494;background:#11151c;border-radius:0 10px 10px 0;padding:.6rem .9rem;margin:.55rem 0}"
        ".when{color:#8b949e;font-size:.72rem;margin-bottom:.25rem}.note{font-size:.98rem;line-height:1.45}"
        ".tag{display:inline-block;background:#1f2630;border-radius:5px;padding:.02rem .35rem;margin-left:.3rem;font-size:.66rem;color:#8aa6c8;text-transform:uppercase;letter-spacing:.04em}"
        ".trig{color:#7d8893;font-size:.78rem;margin-top:.3rem;font-style:italic}</style>"
        "<h1>Creative Sparks ✶ <span class=sub>where the realtime feed opens new doors</span></h1>"
        "<div class=sub>Jimmy's cross-domain creative thoughts, captured as they fire while reading the feed. "
        "%d sparks. Private — the collaboration's emergent ideas, never lost.</div>"
        "<div class=chips>%s</div>%s" % (len(rows), chips, items or "<div class=sub>No sparks yet — add one with: python spark.py \"your thought\"</div>"))
    open(os.path.join(OUT, "creative_sparks.html"), "w", encoding="utf-8").write(html)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("note", nargs="*")
    ap.add_argument("--trigger", default=None)
    ap.add_argument("--domain", default=None)
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args()
    rows = load()
    note = " ".join(a.note).strip()
    if note:
        rec = {"ts": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"), "note": note,
               "trigger": a.trigger, "domains": [a.domain] if a.domain else tag(note)}
        os.makedirs(OUT, exist_ok=True)
        _line = json.dumps(rec, ensure_ascii=False) + "\n"   # atomic append (single os.write, O_APPEND)
        _fd = os.open(LEDGER, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try: os.write(_fd, _line.encode("utf-8"))
        finally: os.close(_fd)
        rows.append(rec)
        print("spark captured ✶  domains: %s" % ", ".join(rec["domains"]))
    render(rows)
    print("ledger: %d sparks -> reports/_status/sparks/creative_sparks.html" % len(rows))
    return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
