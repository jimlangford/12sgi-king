#!/usr/bin/env python3
# _honolulu_minutes_sweep.py - one-shot maximizer for hi-honolulu Granicus MINUTES.
# Enumerates MinutesViewer.php?view_id=3&clip_id=N across the full known clip range,
# keeps pages with real minutes text (drops the "has not been published" stub + 404 + thin),
# extracts text from inline HTML (and PDF via pypdf if served), writes one .txt per meeting.
# Does NOT delete existing files; skips dates/clips already present. Public record.
import os, re, io, html, json, time, urllib.request, urllib.error

UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HOME=os.path.expanduser("~")
PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
OUT=os.path.join(PROJ,"reports","minutes_text","hi-honolulu")
os.makedirs(OUT,exist_ok=True)
BASE="https://honolulu.granicus.com"
STUB="has not been published"

def get(url, timeout=45):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    return urllib.request.urlopen(req,timeout=timeout).read()

def strip_html(data):
    h=data.decode("utf-8","replace")
    h=re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>"," ",h)
    txt=html.unescape(re.sub(r"(?s)<[^>]+>"," ",h))
    txt=re.sub(r"[ \t]+"," ",txt)
    txt=re.sub(r"\n\s*\n+","\n\n",txt).strip()
    return txt

def build_clipmap():
    cm={}
    for vid in (2,3,6,7):
        for mode in ("agendas","minutes"):
            try:
                h=get("%s/ViewPublisherRSS.php?view_id=%d&mode=%s"%(BASE,vid,mode)).decode("utf-8","replace")
            except Exception:
                continue
            for it in re.findall(r"<item>(.*?)</item>",h,re.S):
                t=re.search(r"<title>(.*?)</title>",it)
                cid=re.search(r"clip_id=(\d+)",it)
                if t and cid:
                    cm.setdefault(int(cid.group(1)), html.unescape(t.group(1)).strip())
    return cm

MONTHS="January|February|March|April|May|June|July|August|September|October|November|December"
def find_date(txt, title):
    # prefer ISO date prefix in the feed title (e.g. "2024-06-27 PS - ...")
    m=re.match(r"\s*(\d{4}-\d{2}-\d{2})", title or "")
    if m: return m.group(1)
    m=re.search(r"(%s)\s+(\d{1,2}),?\s+(20\d\d)"%MONTHS, txt)
    if m:
        mo=["january","february","march","april","may","june","july","august",
            "september","october","november","december"].index(m.group(1).lower())+1
        return "%s-%02d-%02d"%(m.group(3),mo,int(m.group(2)))
    return "nodate"

def main():
    cm=build_clipmap()
    feed_ids=sorted(cm)
    lo,hi=feed_ids[0],feed_ids[-1]
    # union: every clip from the feeds + a full sweep across the observed range
    candidates=sorted(set(feed_ids) | set(range(lo,hi+1)))
    print("feed clip_ids=%d  range=%d..%d  sweeping %d candidates"%(len(feed_ids),lo,hi,len(candidates)))

    existing=set(os.listdir(OUT))
    saved=0; stub=0; notfound=0; thin=0; skipped=0; err=0
    man=[]
    for i,cid in enumerate(candidates):
        fn="min%d.txt"%cid
        # any existing file already ending with this clip marker?
        if any(x.endswith("__min%d.txt"%cid) for x in existing):
            skipped+=1; continue
        url="%s/MinutesViewer.php?view_id=3&clip_id=%d"%(BASE,cid)
        try:
            data=get(url)
        except urllib.error.HTTPError as e:
            if e.code==404: notfound+=1
            else: err+=1
            time.sleep(0.15); continue
        except Exception:
            err+=1; time.sleep(0.3); continue
        if data[:4]==b"%PDF":
            try:
                from pypdf import PdfReader
                txt="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
                status="minutes-pdf"
            except Exception:
                txt=""; status="pdf-fail"
        else:
            txt=strip_html(data)
            status="minutes-html"
        low=txt.lower()
        if STUB in low and len(txt)<400:
            stub+=1; time.sleep(0.15); continue
        if len(txt)<400:
            thin+=1; time.sleep(0.15); continue
        title=cm.get(cid,"")
        date=find_date(txt,title)
        body=title or ("clip %d"%cid)
        outfn="%s__min%d.txt"%(re.sub(r"[^0-9-]","",date) or "nodate", cid)
        header=("MINUTES | hi-honolulu | %s | %s\nSOURCE: %s\nSTATUS: %s\n%s\n\n"
                %(body,date,url,status,"-"*60))
        with open(os.path.join(OUT,outfn),"w",encoding="utf-8",newline="\n") as fh:
            fh.write(header+txt)
        existing.add(outfn)
        saved+=1
        man.append({"clip_id":cid,"date":date,"body":body,"chars":len(txt),"status":status,"file":outfn})
        if saved%25==0:
            print("  ...saved=%d (idx %d/%d) stub=%d 404=%d thin=%d"%(saved,i+1,len(candidates),stub,notfound,thin))
        time.sleep(0.25)
    print("DONE saved=%d stub(unpublished)=%d notfound404=%d thin=%d err=%d skipped(existing)=%d"
          %(saved,stub,notfound,thin,err,skipped))
    json.dump({"saved":saved,"manifest":man},
              open(os.path.join(PROJ,"reports","_status","minutes","sweep_hi-honolulu.json"),"w",encoding="utf-8"),
              indent=1,ensure_ascii=False)
    return saved

if __name__=="__main__":
    import sys
    if os.name=="nt":
        sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    main()
