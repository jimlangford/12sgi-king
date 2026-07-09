#!/usr/bin/env python3
# script_ingest.py - ingest the STUDIO script corpus (Jimmy added the scripts subdirectory 2026-06-16).
#   Extracts text from each source (docx=zip/xml, csv, rtf, srt, txt), counts scene headings, maps each to
#   its film, and writes a corpus index so the film pipeline knows what canonical source it has. Also parses
#   the 12 STONES scene CSV into a render-ready scene manifest. Stdlib only. PRIVATE/internal index.
import os, sys, re, json, zipfile, csv as csvmod
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
DOCS = os.path.join(PROJECT, "docs")
CFG = os.path.join(PROJECT, "config")
HST = timezone(timedelta(hours=-10))

# corpus file -> film mapping
FILM_OF = [
    (r"12.?stones|aloha.?code|01 script|00 script", "12_STONES (Film 1)"),
    (r"mokuula", "MOKUULA (Film 2)"),
    (r"luna", "LUNA_CHRONICLES (Film 3)"),
    (r"keys|starforge|langford \.rtf", "KEYS_OF_STARFORGE (Film 4)"),
    (r"neurodivergent|mind.?map|cast", "CAST / character bible"),
    (r"hammer|hokukalama|\.mp3", "SCORE / audio"),
]
def film_of(name):
    for pat, f in FILM_OF:
        if re.search(pat, name, re.I): return f
    return "unfiled"

def extract(path):
    low = path.lower()
    try:
        if low.endswith(".docx"):
            z = zipfile.ZipFile(path); xml = z.read("word/document.xml").decode("utf-8", "replace")
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))
        if low.endswith((".txt", ".rtf", ".srt", ".csv")):
            t = open(path, encoding="utf-8", errors="replace").read()
            if low.endswith(".rtf"):
                t = re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", t)        # strip rtf controls
            return re.sub(r"\s+", " ", t)
        if low.endswith(".mp3"):
            return "[audio]"
    except Exception as e:
        return "[unreadable: %s]" % str(e)[:50]
    return ""

def scene_count(t):
    return len(re.findall(r"\b(INT\.|EXT\.|FADE IN|SMASH CUT|^\s*\d+,)", t))

def parse_12stones_csv():
    """The 12 STONES First-40 CSV -> a render-ready scene manifest (like film_seventh_stone.json)."""
    src = None
    for f in os.listdir(DOCS):
        if re.search(r"12_stones.*first.*pages.*\.csv", f, re.I): src = os.path.join(DOCS, f); break
    if not src: return 0
    scenes = []
    with open(src, encoding="utf-8", errors="replace") as fh:
        for row in csvmod.DictReader(fh):
            if not row.get("Scene"): continue
            scenes.append({"scene": row.get("Scene"), "location": row.get("Location"),
                           "time": row.get("Time"), "beat": (row.get("Description") or "")[:300],
                           "dialogue_present": bool((row.get("Dialogue") or "").strip())})
    if scenes:
        out = {"_meta": {"film_id": 1, "key": "12_STONES", "title": "12 STONES: The Aloha Code",
                         "source": os.path.basename(src), "face_lock": "JAMES LANGFORD (young likeness, Keanu archetype energy)",
                         "antagonist": "MARSHALL KANE (Travolta archetype)", "look": "LUNA 3D-animated film look; live-action-grade face-lock pipeline",
                         "note": "Render-ready scene manifest parsed from Jimmy's First-40 CSV."},
               "scenes": scenes}
        json.dump(out, open(os.path.join(CFG, "film_12stones_scenes.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return len(scenes)

def main():
    rows = []
    for f in sorted(os.listdir(DOCS)):
        p = os.path.join(DOCS, f)
        if not os.path.isfile(p): continue
        if not f.lower().endswith((".docx", ".rtf", ".csv", ".srt", ".txt", ".mp3")): continue
        if f.startswith("_screenplay") or f.startswith("invideo"): continue   # already-mirrored / subtitle dumps
        t = extract(p)
        rows.append({"file": f, "film": film_of(f), "bytes": os.path.getsize(p),
                     "chars": len(t) if t and not t.startswith("[") else 0,
                     "scene_heads": scene_count(t) if t else 0, "kind": f.rsplit(".",1)[-1].lower()})
    n12 = parse_12stones_csv()
    idx = {"generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"), "corpus_files": len(rows),
           "twelve_stones_scenes_manifested": n12, "files": rows}
    os.makedirs(os.path.join(PROJECT, "reports", "_status"), exist_ok=True)
    json.dump(idx, open(os.path.join(PROJECT, "reports", "_status", "scripts_index.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    # readable index
    md = ["# Studio script corpus — index", "_Ingested %s. %d source files._\n" % (idx["generated"], len(rows)),
          "| file | film | kind | scenes | chars |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: x["film"]):
        md.append("| %s | %s | %s | %s | %s |" % (r["file"], r["film"], r["kind"], r["scene_heads"] or "-", r["chars"] or "-"))
    md.append("\n12 STONES scenes manifested from CSV: **%d** -> config/film_12stones_scenes.json" % n12)
    open(os.path.join(DOCS, "SCRIPTS_INDEX.md"), "w", encoding="utf-8").write("\n".join(md))
    print("script_ingest: %d corpus files indexed" % len(rows))
    for r in sorted(rows, key=lambda x: x["film"]):
        print("  %-44s %-28s scenes=%s" % (r["file"][:44], r["film"], r["scene_heads"] or "-"))
    print("12 STONES scenes manifested:", n12, "-> config/film_12stones_scenes.json")
    return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
