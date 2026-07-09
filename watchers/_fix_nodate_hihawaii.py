#!/usr/bin/env python3
# Post-pass: rename reports/minutes_text/hi-hawaii/nodate__<id>.txt files by extracting the first
# real meeting date from the PDF text body (the ingest script had a regex-precedence bug that only
# caught December). Content is already correct; only the filename date prefix is fixed.
import os, sys, re, io
if sys.platform=="win32":
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OUT="C:/Users/12sgi/Documents/Claude/Projects/Video System elementLOTUS/reports/minutes_text/hi-hawaii"
MONTHS="(?:January|February|March|April|May|June|July|August|September|October|November|December)"
from datetime import datetime
renamed=0; still=0; used={f for f in os.listdir(OUT)}
for fn in sorted(os.listdir(OUT)):
    if not fn.startswith("nodate__") or not fn.endswith(".txt"): continue
    p=os.path.join(OUT,fn)
    with open(p,encoding="utf-8") as f:
        txt=f.read()
    # skip the 4-line header when searching for the meeting date
    body=txt.split("-"*60,1)[-1]
    m=re.search(MONTHS+r"\s+\d{1,2},?\s+\d{4}", body)
    if not m:
        still+=1; continue
    try:
        dt=datetime.strptime(re.sub(",","",m.group(0)).strip(), "%B %d %Y")
        date=dt.strftime("%Y-%m-%d")
    except Exception:
        still+=1; continue
    idpart=fn[len("nodate__"):]  # e.g. clip3436.txt
    newfn="%s__%s"%(date, idpart)
    if newfn in used and newfn!=fn:
        newfn="%s__%s"%(date, idpart.replace(".txt","_b.txt"))
    os.rename(p, os.path.join(OUT,newfn)); used.add(newfn); renamed+=1
print("renamed:", renamed, "| still nodate:", still)
