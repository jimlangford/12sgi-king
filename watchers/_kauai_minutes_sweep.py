#!/usr/bin/env python3
# _kauai_minutes_sweep.py  (claude-home-thread, 2026-06-16)
# Maximize hi-kauai Granicus minutes/agenda-packet coverage.
# Granicus path: ViewPublisher.php?view_id=N lists every meeting's AgendaViewer link.
#   AgendaViewer.php?view_id=2&clip_id=K  -> JS shell that embeds the real PDF as either
#     DocumentViewer.php?file=kauai_<hash>.pdf   OR  s3 .../kauai/<hash>.pdf
#   Many older agenda packets are SCANNED (no text layer) -> pypdf returns ~nothing; skipped.
# Writes reports/minutes_text/hi-kauai/<date>__c<clip_id>.txt  with a header.
# Never deletes existing files. Polite small sleeps.
import os, re, io, ssl, sys, time, json, html, urllib.request
HOME=os.path.expanduser("~")
PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
OUT=os.path.join(PROJ,"reports","minutes_text","hi-kauai")
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CTX=ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
from pypdf import PdfReader

def get(url, ctx=None, timeout=60):
    req=urllib.request.Request(url, headers={"User-Agent":UA})
    return urllib.request.urlopen(req, timeout=timeout, context=ctx).read()

def list_clip_ids(view_id):
    try:
        h=get("https://kauai.granicus.com/ViewPublisher.php?view_id=%d"%view_id, timeout=120).decode("utf-8","replace")
    except Exception as e:
        print("  view %d list fail: %s"%(view_id,str(e)[:60])); return []
    return sorted({int(x) for x in re.findall(r'clip_id=(\d+)', h)})

DATE_RE=re.compile(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})', re.I)
MON={"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06","jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"}
def parse_date(h):
    m=DATE_RE.search(h)
    if not m: return "nodate", ""
    mo=MON[m.group(1)[:3].lower()]; d="%02d"%int(m.group(2)); y=m.group(3)
    return "%s-%s-%s"%(y,mo,d), m.group(0)

def title_of(h):
    m=re.search(r'<title>([^<]*)</title>', h)
    return (m.group(1).strip() if m else "").replace("AgendaViewer.php","").strip()

def pdf_url_from_agenda(h):
    m=re.search(r'(kauai_[a-f0-9]{20,}\.pdf)', h)
    if m: return "https://kauai.granicus.com/DocumentViewer.php?file=%s&view=1"%m.group(1)
    m=re.search(r'granicus_production_attachments\.s3\.amazonaws\.com/kauai/([a-f0-9]{20,}\.pdf)', h)
    if m: return "https://s3.amazonaws.com/granicus_production_attachments/kauai/"+m.group(1)
    return None

def fetch_pdf_text(url):
    try:
        data=get(url, ctx=(CTX if "s3.amazonaws" in url else None), timeout=90)
    except Exception:
        # s3 path-style retry
        try: data=get(url, ctx=CTX, timeout=90)
        except Exception as e: return "", "fetch-fail:%s"%str(e)[:40]
    if data[:4]!=b"%PDF": return "", "not-pdf"
    try:
        txt="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    except Exception as e:
        return "", "pdf-fail:%s"%str(e)[:40]
    return txt, ("pdf" if len(txt.strip())>400 else "pdf-scanned")

def existing_clip_ids():
    ids=set()
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            m=re.search(r'__c(\d+)\.txt$', f)
            if m: ids.add(int(m.group(1)))
    return ids

def main():
    os.makedirs(OUT, exist_ok=True)
    limit=int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else 10**9
    views=[2,8,7]  # 2=master County Council/Planning archive, 8=Planning Commission, 7=Board of Ethics
    clip_ids=[]; seen=set()
    for v in views:
        for c in list_clip_ids(v):
            if c not in seen: seen.add(c); clip_ids.append((c,v))
    clip_ids.sort(reverse=True)  # newest first
    print("total distinct clip_ids: %d (views %s)"%(len(clip_ids), views))
    have=existing_clip_ids()
    print("already have %d clip-id .txt files"%len(have))
    saved=0; scanned=0; nodoc=0; fail=0; tried=0
    for cid,view in clip_ids:
        if cid in have: continue
        if tried>=limit: break
        tried+=1
        try:
            h=get("https://kauai.granicus.com/AgendaViewer.php?view_id=%d&clip_id=%d"%(view,cid)).decode("utf-8","replace")
        except Exception as e:
            fail+=1; time.sleep(0.2); continue
        purl=pdf_url_from_agenda(h)
        if not purl: nodoc+=1; time.sleep(0.2); continue
        date,_=parse_date(h); body=title_of(h)
        txt,status=fetch_pdf_text(purl)
        if status=="pdf":
            fn="%s__c%d.txt"%(date, cid)
            header=("MINUTES | hi-kauai | %s | %s\nSOURCE: %s\nVIA: AgendaViewer.php?view_id=%d&clip_id=%d\nSTATUS: granicus-pdf\n%s\n\n"
                    %(body, date, purl, view, cid, "-"*60))
            with open(os.path.join(OUT,fn),"w",encoding="utf-8",newline="\n") as fh:
                fh.write(header+txt)
            saved+=1
            if saved%10==0: print("  ...saved %d (scanned %d, nodoc %d)"%(saved,scanned,nodoc))
        elif status=="pdf-scanned":
            scanned+=1
        else:
            fail+=1
        time.sleep(0.25)
    print("DONE: saved=%d new  scanned(no-text-layer)=%d  no-doc=%d  fail=%d  tried=%d"%(saved,scanned,nodoc,fail,tried))
    return saved

if __name__=="__main__":
    if sys.platform=="win32":
        sys.stdout=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
