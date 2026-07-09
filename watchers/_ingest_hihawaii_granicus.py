#!/usr/bin/env python3
# One-shot: maximize hi-hawaii minutes coverage from Granicus ViewPublisher archive.
# Enumerates EVERY AgendaViewer link (clip_id/event_id) on hawaiicounty.granicus.com view_id=1,
# follows AgendaViewer -> DocumentViewer PDF, extracts text with pypdf, writes
#   reports/minutes_text/hi-hawaii/<date>__<idkind><id>.txt  with a header line.
# Skips ids already saved (read from existing file headers). Does NOT delete anything. Polite sleeps.
import os, sys, re, io, json, html, time, urllib.request
if sys.platform=="win32":
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr=io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from pypdf import PdfReader

PROJ="C:/Users/12sgi/Documents/Claude/Projects/Video System elementLOTUS"
OUT=os.path.join(PROJ,"reports","minutes_text","hi-hawaii")
ARCHIVE="https://hawaiicounty.granicus.com/ViewPublisher.php?view_id=1"
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MONTHS=("(?:January|February|March|April|May|June|July|August|September|October|November|December)")

def slug(s): return re.sub(r"[^A-Za-z0-9._-]","_",str(s))[:80]

def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":UA}), timeout=timeout).read()

def existing_ids():
    done=set()
    if not os.path.isdir(OUT): return done
    for fn in os.listdir(OUT):
        if not fn.endswith(".txt"): continue
        try:
            with open(os.path.join(OUT,fn),encoding="utf-8") as f:
                head="".join([next(f,"") for _ in range(3)])
        except Exception:
            continue
        m=re.search(r'(clip_id|event_id)=(\d+)', head)
        if m: done.add((m.group(1),m.group(2)))
    return done

def parse_archive(h):
    rows=re.split(r'(?i)<tr', h); out=[]; seen=set()
    for r in rows:
        am=re.search(r'AgendaViewer\.php\?view_id=1&(?:amp;)?(clip_id|event_id)=(\d+)', r)
        if not am: continue
        idkind, idval = am.group(1), am.group(2)
        if (idkind,idval) in seen: continue
        seen.add((idkind,idval))
        nm=(re.search(r'headers="Name"[^>]*>(.*?)</td>', r, re.S)
            or re.search(r'id="Event[^"]*"[^>]*>(.*?)</td>', r, re.S))
        name=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',nm.group(1)))).strip() if nm else ""
        out.append((idkind, idval, name))
    return out

def main():
    os.makedirs(OUT, exist_ok=True)
    done=existing_ids()
    print("already-saved ids:", len(done), flush=True)
    try:
        h=get(ARCHIVE).decode("utf-8","replace")
    except Exception as e:
        print("ARCHIVE FETCH FAIL:", str(e)[:120]); return 1
    meetings=parse_archive(h)
    print("archive meetings parsed:", len(meetings), flush=True)
    todo=[m for m in meetings if (m[0],m[1]) not in done]
    print("to fetch (new):", len(todo), flush=True)

    saved=0; empty=0; notpdf=0; fail=0; usednames=set()
    for i,(idkind,idval,name) in enumerate(todo):
        url="https://hawaiicounty.granicus.com/AgendaViewer.php?view_id=1&%s=%s"%(idkind,idval)
        try:
            data=get(url, timeout=70)
        except Exception as e:
            fail+=1
            if i%50==0: print("  [%d/%d] fail %s=%s %s"%(i,len(todo),idkind,idval,str(e)[:50]), flush=True)
            time.sleep(0.4); continue
        if data[:4]!=b"%PDF":
            notpdf+=1; time.sleep(0.35); continue
        try:
            txt="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
        except Exception as e:
            fail+=1; time.sleep(0.4); continue
        if not txt.strip():
            empty+=1; time.sleep(0.35); continue
        dm=re.search(MONTHS+r"\s+\d{1,2},?\s+\d{4}", txt)
        if dm:
            try:
                from datetime import datetime
                dt=datetime.strptime(re.sub(r",","",dm.group(0)), "%B %d %Y")
                date=dt.strftime("%Y-%m-%d")
            except Exception:
                date="nodate"
        else:
            date="nodate"
        fn="%s__%s%s.txt"%(slug(date), idkind.replace("_id",""), idval)
        while fn in usednames:
            fn="%s__%s%s_b.txt"%(slug(date), idkind.replace("_id",""), idval)
        usednames.add(fn)
        header=("MINUTES | hi-hawaii | %s | %s\nSOURCE: %s\nSTATUS: granicus-pdf\n%s\n\n"
                %(name, date, url, "-"*60))
        with open(os.path.join(OUT,fn),"w",encoding="utf-8",newline="\n") as f:
            f.write(header+txt)
        saved+=1
        if saved%25==0:
            print("  [%d/%d] saved=%d empty=%d notpdf=%d fail=%d (last %s)"
                  %(i+1,len(todo),saved,empty,notpdf,fail,fn), flush=True)
        time.sleep(0.35)
    print(json.dumps({"new_saved":saved,"empty":empty,"not_pdf":notpdf,"fail":fail,
                      "archive_meetings":len(meetings),"already":len(done)}), flush=True)
    return 0

if __name__=="__main__":
    sys.exit(main())
