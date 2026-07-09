#!/usr/bin/env python3
# minutes_ingest.py - save the actual MEETING MINUTES as searchable .txt (Jimmy 2026-06-16: "minutes saved as a
# searchable txt file on our private server for the prosecutor ... all the connections are readily available, all
# committee et al, the people incriminate themselves. we need to know that cold. save all of it in txt on the git").
#
# Reads the minutes index (reports/_status/minutes/index_*.jsonl) -> for each record, fetches minutes_url,
# follows the redirect to the document, extracts the TEXT (PDF via pypdf; HTML by tag-strip), and writes a
# searchable .txt per meeting. Granicus AgendaViewer -> the minutes PDF (clean text). CivicClerk portal pages
# are JS shells (their PDFs sit behind the portal API) -> flagged 'portal-pending' for the API follow-on.
#
# Output (PUBLIC RECORD — minutes are public; the prosecutorial ANALYSIS stays private):
#   reports/minutes_text/<tenant>/<date>__<n>.txt      (source of truth)
#   reports/minutes_text/_manifest.jsonl               (date, tenant, body, chars, url, status)
#   mirrored to king-local (private prosecutor copy) AND 12sgi-king/minutes_text (git).
# Stdlib + pypdf. Run: python minutes_ingest.py [--tenant hi-hawaii] [--limit N]
import os, sys, re, io, json, html, time, urllib.request
# provenance.py (sibling) is the ONE source_type convention for the whole civic chain.
# Robust import + safe fallback so this ingester never breaks if the helper is missing.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import provenance as _prov
    def prov_type(status=None, url=None, note=None): return _prov.classify(status, url, note)
    def prov_badge(st): return _prov.badge_html(st)
except Exception:                                    # pragma: no cover - fallback only
    def prov_type(status=None, url=None, note=None):
        blob=" ".join(str(x) for x in (status,url,note) if x).lower()
        return "transcribed" if ("transcript" in blob or "transcrib" in blob) else "sourced"
    def prov_badge(st):
        st="transcribed" if str(st).lower()=="transcribed" else "sourced"
        col={"sourced":"#1f8a5b","transcribed":"#b8860b"}[st]
        return '<span style="border:1px solid %s;color:%s;border-radius:99px;padding:1px 6px;font:600 10px monospace">%s</span>'%(col,col,st)
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
IDXDIR=os.path.join(PROJ,"reports","_status","minutes")
OUT=os.path.join(PROJ,"reports","minutes_text")
MAUIOS=os.path.join(PROJ,"reports","mauios")            # civic tree (private) - provenance HTML view lives here
KING=os.path.join(HOME,"AppData","Local","king-extract","deploy","king-local","minutes_text")
GIT=os.path.join(HOME,"Documents","Claude","12sgi-king","minutes_text")
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
def slug(s): return re.sub(r"[^A-Za-z0-9._-]","_",str(s))[:80]

def fetch_text(url):
    url=html.unescape(url or "").strip()
    if not url: return "", "no-url"
    try:
        req=urllib.request.Request(url, headers={"User-Agent":UA})
        data=urllib.request.urlopen(req, timeout=45).read()
    except Exception as e:
        return "", "fetch-fail:%s"%(str(e)[:60])
    if data[:4]==b"%PDF":
        try:
            from pypdf import PdfReader
            r=PdfReader(io.BytesIO(data))
            txt="\n".join((p.extract_text() or "") for p in r.pages)
            return txt, ("pdf" if txt.strip() else "pdf-empty")
        except Exception as e:
            return "", "pdf-fail:%s"%(str(e)[:50])
    # HTML
    h=data.decode("utf-8","replace")
    if "civicclerk" in h.lower() and len(h)<4000:
        return "", "portal-pending"     # CivicClerk JS shell — real PDF is behind the portal API (follow-on)
    h=re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>"," ",h)
    txt=html.unescape(re.sub(r"(?s)<[^>]+>"," ",h)); txt=re.sub(r"[ \t]+"," ",txt); txt=re.sub(r"\n\s*\n+","\n\n",txt).strip()
    return txt, ("html" if len(txt)>400 else "html-thin")

CIVICCLERK_API="https://mauicounty.api.civicclerk.com/v1"   # Maui's CivicClerk OData API (portal PDFs)

def _existing_cc_fileids(tenant_dir="hi-maui"):
    """fileIds already ingested (from reports/minutes_text/<tenant>/<date>__cc<fid>.txt).
    Backfill uses this to walk PRESENT->BACKWARDS and only fetch what we don't yet have."""
    ids=set(); d=os.path.join(OUT,tenant_dir)
    if os.path.isdir(d):
        for f in os.listdir(d):
            m=re.search(r'__cc(\d+)\.txt$', f)
            if m: ids.add(int(m.group(1)))
    return ids

def civicclerk_maui(top=220, skip_ids=None, cap_new=None, source_type="sourced"):
    """Maui minutes via the CivicClerk API: page events (newest-first) -> publishedFiles type=Minutes ->
    GetMeetingFileStream PDF -> text. Replaces the 70 'portal-pending' index rows the HTML path couldn't reach.

    skip_ids   : set of fileIds already ingested -> counted as skipped, PDF NOT re-downloaded. This makes
                 the pass fill to the PRESENT working present->backwards from what is already ingested.
    cap_new    : stop after this many NEW minutes are fetched (bounded runs).
    source_type: provenance tag for every record (default 'sourced' = official posted CivicClerk minutes PDF).
                 Passed through provenance.py; a per-record transcript signal can still override to 'transcribed'."""
    from pypdf import PdfReader
    skip_ids=set(skip_ids or ())
    tdir=os.path.join(OUT,"hi-maui"); os.makedirs(tdir,exist_ok=True)
    try:
        url=(CIVICCLERK_API+"/Events?$top=%d&$orderby=startDateTime desc"%top).replace(" ","%20").replace("$","%24")
        req=urllib.request.Request(url,headers={"User-Agent":UA})
        events=json.load(urllib.request.urlopen(req,timeout=60)).get("value",[])
    except Exception as e:
        print("  civicclerk events fail:",str(e)[:80]); return [],0,0
    man=[]; n=0; skipped=0
    for e in events:                                   # events already newest-first (present -> backwards)
        mf=[f for f in (e.get("publishedFiles") or []) if (f.get("type") or "").lower()=="minutes"]
        if not mf: continue
        fid=mf[0]["fileId"]; date=(e.get("eventDate") or "")[:10] or "nodate"; body=e.get("eventName") or e.get("agendaName") or ""
        if fid in skip_ids: skipped+=1; continue        # already ingested -> don't re-download (fill-to-present)
        furl=CIVICCLERK_API+"/Meetings/GetMeetingFileStream(fileId=%d,plainText=false)"%fid
        st=prov_type(status="civicclerk-pdf", url=furl, note=source_type)   # 'sourced' unless a transcript signal
        try:
            pdf=urllib.request.urlopen(urllib.request.Request(furl,headers={"User-Agent":UA}),timeout=70).read()
            txt="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages) if pdf[:4]==b"%PDF" else ""
        except Exception as ex:
            man.append({"tenant":"hi-maui","date":date,"body":body,"chars":0,"status":"cc-fail:%s"%str(ex)[:40],"source_type":st,"file":None,"url":furl}); continue
        if txt.strip():
            fn="%s__cc%d.txt"%(slug(date),fid)
            header="MINUTES | hi-maui | %s | %s\nSOURCE: %s\nSTATUS: civicclerk-pdf\nSOURCE_TYPE: %s\n%s\n\n"%(body,date,furl,st,"-"*60)
            open(os.path.join(tdir,fn),"w",encoding="utf-8",newline="\n").write(header+txt)
            man.append({"tenant":"hi-maui","date":date,"body":body,"chars":len(txt),"status":"civicclerk-pdf","source_type":st,"file":"hi-maui/"+fn,"url":furl}); n+=1
            if cap_new and n>=cap_new: break            # bounded run: stop after cap_new new minutes
        time.sleep(0.25)
    return man,n,skipped

def _mirror_out():
    """Mirror the minutes_text corpus to king-local (private prosecutor copy) + git (public record)."""
    import shutil
    for dst in (KING,GIT):
        try:
            if os.path.isdir(os.path.dirname(dst)) or dst==GIT:
                if os.path.isdir(dst): shutil.rmtree(dst)
                shutil.copytree(OUT,dst)
        except Exception as ex: print("  mirror skip:",str(ex)[:50])

def _scan_corpus():
    """Rebuild manifest rows from the .txt files on disk (the source of truth). Used when the on-disk
    _manifest.json is only a summary (no per-record array) so a re-index never SHRINKS the record.
    Non-destructive: reads only. Parses the header for body/source/status/source_type."""
    rows=[]
    if not os.path.isdir(OUT): return rows
    for tid in sorted(os.listdir(OUT)):
        td=os.path.join(OUT,tid)
        if not os.path.isdir(td): continue
        for fn in sorted(os.listdir(td)):
            if not fn.endswith(".txt"): continue
            fp=os.path.join(td,fn)
            date=fn.split("__")[0]; body=""; url=""; status=""; st=None
            try:
                with open(fp,encoding="utf-8") as fh:
                    for _ in range(8):
                        try: ln=next(fh)
                        except StopIteration: break
                        if ln.startswith("MINUTES |"):
                            parts=[p.strip() for p in ln.split("|")]
                            if len(parts)>=3: body=parts[2]
                        elif ln.startswith("SOURCE:"): url=ln.split("SOURCE:",1)[1].strip()
                        elif ln.startswith("STATUS:"): status=ln.split("STATUS:",1)[1].strip()
                        elif ln.startswith("SOURCE_TYPE:"): st=ln.split("SOURCE_TYPE:",1)[1].strip()
            except Exception: pass
            try: chars=os.path.getsize(fp)
            except Exception: chars=0
            rows.append({"tenant":tid,"date":date,"body":body,"chars":chars,"status":status or "on-disk",
                         "source_type":prov_type(status=st or status,url=url),"file":"%s/%s"%(tid,fn),"url":url})
    return rows

def _prov_counts(manifest):
    """Count records by provenance source_type (untagged rows normalize to 'sourced')."""
    c={"sourced":0,"transcribed":0}
    for m in manifest:
        st=prov_type(status=m.get("source_type") or m.get("status"), url=m.get("url"))
        c[st]=c.get(st,0)+1
    return c

def _tag_manifest(manifest):
    """Ensure EVERY record carries a provenance source_type (default 'sourced'). Idempotent."""
    for m in manifest:
        m["source_type"]=prov_type(status=m.get("source_type") or m.get("status"), url=m.get("url"))
    return manifest

def _tenant_arg():
    if "--tenant" in sys.argv:
        i=sys.argv.index("--tenant")+1
        if i<len(sys.argv): return sys.argv[i]
    return None

def _esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _write_provenance_html(base):
    """Companion .html for the .json manifest (civic convention: both an html view AND a json dataset,
    so chain_link can join). Per-tenant + per-record provenance with a visible sourced/transcribed badge.
    Question-framed, sourced links, PRIVATE (reports/mauios) - never published. Uses provenance.badge_html."""
    man=base.get("manifest",[])
    pc=base.get("source_types") or _prov_counts(man)
    from collections import defaultdict
    by_t=defaultdict(lambda:{"sourced":0,"transcribed":0,"records":0,"text":0})
    for m in man:
        st=prov_type(status=m.get("source_type") or m.get("status"), url=m.get("url"))
        t=by_t[m.get("tenant") or "?"]; t[st]+=1; t["records"]+=1; t["text"]+=1 if m.get("file") else 0
    trows="".join(
        "<tr><td>%s</td><td class=n>%d</td><td class=n>%d</td><td>%s</td><td>%s</td></tr>"%(
            _esc(t),v["records"],v["text"],prov_badge("sourced")+(" &times;%d"%v["sourced"]),
            (prov_badge("transcribed")+(" &times;%d"%v["transcribed"])) if v["transcribed"] else "<span class=z>&mdash;</span>")
        for t,v in sorted(by_t.items()))
    # newest Maui minutes with a source link (present-first)
    maui=[m for m in man if (m.get("tenant")=="hi-maui" and m.get("file"))]
    maui.sort(key=lambda m:m.get("date") or "", reverse=True)
    mrows="".join(
        "<tr><td class=d>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"%(
            _esc(m.get("date") or "nodate"),_esc((m.get("body") or "")[:70]),
            prov_badge(m.get("source_type")),
            ('<a href="%s">source</a>'%_esc(m.get("url")) if m.get("url") else "<span class=z>&mdash;</span>"))
        for m in maui[:40]) or "<tr><td colspan=4 class=z>No Maui minutes text yet.</td></tr>"
    # HEAD carries the CSS (which contains literal % like width:100%) so it must NOT go through %-formatting.
    head=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Meeting-minutes provenance &mdash; Maui &amp; Hawaii counties | govOS</title><style>"
        "body{font-family:'Segoe UI',system-ui,sans-serif;max-width:960px;margin:1.3rem auto;padding:0 1rem;color:#13243d;background:#fff;line-height:1.55}"
        "h1{font-size:1.45rem;margin:.3rem 0}h2{color:#00356b;font-size:1.02rem;margin:1.3rem 0 .4rem}.sub{color:#41536b;font-size:.9rem}"
        ".kpi{font:700 1.05rem/1.2 Consolas,monospace;color:#00356b;margin:.6rem 0}"
        ".disc{background:#0f2540;border:1px solid #1f3d5f;border-radius:10px;padding:.7rem 1rem;color:#41536b;font-size:.85rem;margin:.9rem 0}"
        ".priv{background:#fbf3dd;border:1px solid #e6d8a8;border-left:3px solid #b8860b;border-radius:10px;padding:.6rem 1rem;color:#5a4a16;font-size:.82rem;margin:.7rem 0}"
        "table{border-collapse:collapse;width:100%;font-size:.85rem;margin:.4rem 0}td,th{padding:.4rem .55rem;border-bottom:1px solid #e3e9f1;text-align:left;vertical-align:top}"
        "th{color:#41536b;font-size:.72rem;text-transform:uppercase;letter-spacing:.4px}.n{font-family:Consolas,monospace;text-align:right}.d{font-family:Consolas,monospace;white-space:nowrap}.z{color:#9aa8ba}a{color:#1259a3}"
        "</style>"
        "<div class=sub style='letter-spacing:.1em;text-transform:uppercase;color:#1259a3;font-weight:600'>govOS &middot; kilo aupuni &middot; asked in aloha</div>"
        "<h1>Meeting-minutes provenance</h1>"
        "<div class=sub>Every ingested minutes/agenda record carries a provenance tag so a reader can tell an "
        "<b>official posted document</b> apart from anything <b>derived from a meeting transcript</b>.</div>")
    # DYN contains only placeholders + entities (no literal % ) so %-formatting is safe.
    dyn=("<div class=sub>Generated %s.</div>"
        "<div class=kpi>%s &times;%d &nbsp;&nbsp; %s &times;%d &nbsp;&nbsp; <span style='color:#41536b;font-weight:400;font-size:.85rem'>of %d records, %d with searchable text</span></div>"
        "<div class=priv>PRIVATE (reports/mauios) &mdash; the minutes text is public record, but this owner-side view "
        "stays private; publishing remains owner-gated.</div>"
        "<h2>By government</h2>"
        "<table><thead><tr><th>tenant</th><th>records</th><th>with text</th><th>sourced</th><th>transcribed</th></tr></thead><tbody>%s</tbody></table>"
        "<h2>Maui &mdash; newest minutes first</h2>"
        "<table><thead><tr><th>date</th><th>body</th><th>provenance</th><th>source</th></tr></thead><tbody>%s</tbody></table>"
        "<div class=disc>These are records, offered as <b>questions to verify</b> &mdash; who met, what was decided, "
        "and does the public record match &mdash; never findings or accusations. Each row links back to its public source.</div>"
        )%(_esc(base.get("generated") or time.strftime("%Y-%m-%d %H:%M")),
           prov_badge("sourced"),pc.get("sourced",0),prov_badge("transcribed"),pc.get("transcribed",0),
           base.get("records",len(man)),base.get("with_text",0),trows,mrows)
    html_doc=head+dyn
    os.makedirs(MAUIOS,exist_ok=True)
    p=os.path.join(MAUIOS,"minutes_provenance.html")
    tmp=p+".tmp"
    open(tmp,"w",encoding="utf-8",newline="\n").write(html_doc)
    os.replace(tmp,p)
    return p

def main():
    if "--maui-cc" in sys.argv or ("--backfill" in sys.argv and _tenant_arg() in (None,"maui","hi-maui")):
        os.makedirs(OUT,exist_ok=True)
        backfill = "--backfill" in sys.argv
        lim=None
        if "--limit" in sys.argv: lim=int(sys.argv[sys.argv.index("--limit")+1])
        if backfill:
            # FILL TO THE PRESENT working present->backwards: page newest-first, skip fileIds already
            # ingested (no re-download), fetch only the gap up to today. Bounded by --limit (default 60).
            skip=_existing_cc_fileids("hi-maui")
            man,n,skipped=civicclerk_maui(top=300, skip_ids=skip, cap_new=(lim or 60))
            mode="--tenant maui --backfill"; extra="  (skipped %d already-ingested, walking newest-first)"%skipped
        else:
            man,n,skipped=civicclerk_maui()
            mode="--maui-cc"; extra=""
        # merge into the existing manifest (keep Granicus rows; drop old Maui portal-pending; dedupe by file)
        mp=os.path.join(OUT,"_manifest.json")
        base=json.load(open(mp,encoding="utf-8")) if os.path.exists(mp) else {"manifest":[]}
        existing=base.get("manifest") or _scan_corpus()   # rebuild from disk if manifest was only a summary
        kept=[m for m in existing if not (m.get("tenant")=="hi-maui" and m.get("status")=="portal-pending")]
        have_files={m.get("file") for m in kept if m.get("file")}
        kept+=[m for m in man if (m.get("file") is None) or (m.get("file") not in have_files)]
        _tag_manifest(kept)                              # every record gets a source_type
        wt=sum(1 for m in kept if m.get("file"))
        pc=_prov_counts(kept)
        base.update({"records":len(kept),"with_text":wt,"pending":len(kept)-wt,
                     "source_types":pc,"manifest":kept})
        base.setdefault("generated",time.strftime("%Y-%m-%d %H:%M"))
        json.dump(base,open(mp,"w",encoding="utf-8"),indent=1,ensure_ascii=False)
        _mirror_out()
        hp=_write_provenance_html(base)
        print("minutes_ingest %s: %d new Maui minutes via CivicClerk API; corpus now %d with text%s"%(mode,n,wt,extra))
        print("  provenance: %d sourced, %d transcribed (of %d records)"%(pc["sourced"],pc["transcribed"],len(kept)))
        print("  provenance html -> %s"%hp)
        return 0
    only=None; limit=None
    if "--tenant" in sys.argv: only=sys.argv[sys.argv.index("--tenant")+1]
    if "--limit" in sys.argv: limit=int(sys.argv[sys.argv.index("--limit")+1])
    recs=[]
    for f in sorted(os.listdir(IDXDIR)) if os.path.isdir(IDXDIR) else []:
        if not f.startswith("index_") or not f.endswith(".jsonl"): continue
        for ln in open(os.path.join(IDXDIR,f),encoding="utf-8"):
            try: d=json.loads(ln)
            except: continue
            if only and d.get("tenant")!=only: continue
            recs.append(d)
    if limit: recs=recs[:limit]
    os.makedirs(OUT,exist_ok=True)
    man=[]; ok=0; pend=0
    for i,d in enumerate(recs):
        tid=d.get("tenant","?"); date=d.get("date","nodate"); body=d.get("body","")
        txt,status=fetch_text(d.get("minutes_url"))
        # provenance: posted minutes/agenda docs are 'sourced'; a transcript signal flips to 'transcribed'
        st=prov_type(status=status, url=d.get("minutes_url"), note=d.get("minutes_status") or d.get("source"))
        tdir=os.path.join(OUT,slug(tid)); os.makedirs(tdir,exist_ok=True)
        fn="%s__%d.txt"%(slug(date),i)
        if txt:
            header="MINUTES | %s | %s | %s\nSOURCE: %s\nSTATUS: %s\nSOURCE_TYPE: %s\n%s\n\n"%(
                tid,body,date,html.unescape(d.get("minutes_url") or ""),status,st,"-"*60)
            open(os.path.join(tdir,fn),"w",encoding="utf-8",newline="\n").write(header+txt)
            ok+=1
        else:
            pend+=1
        man.append({"tenant":tid,"date":date,"body":body,"chars":len(txt),"status":status,"source_type":st,
                    "file":"%s/%s"%(slug(tid),fn) if txt else None,"url":html.unescape(d.get("minutes_url") or "")})
        if (i+1)%20==0: print("  ...%d/%d (%d text, %d pending)"%(i+1,len(recs),ok,pend))
        time.sleep(0.3)
    _tag_manifest(man)
    pc=_prov_counts(man)
    base={"generated":time.strftime("%Y-%m-%d %H:%M"),"records":len(recs),"with_text":ok,
          "pending":pend,"source_types":pc,"manifest":man}
    json.dump(base,open(os.path.join(OUT,"_manifest.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    _mirror_out()   # king-local (private prosecutor copy) + git (public record, per Jimmy)
    hp=_write_provenance_html(base)
    print("minutes_ingest: %d records -> %d with searchable text, %d pending (CivicClerk portal API follow-on)"%(
        len(recs),ok,pend))
    print("  provenance: %d sourced, %d transcribed"%(pc["sourced"],pc["transcribed"]))
    print("  provenance html -> %s"%hp)
    print("  -> %s  (+ king-local private + 12sgi-king/minutes_text git)"%OUT)
    return 0

if __name__=="__main__":
    # windowless-safe: under pythonw sys.stdout can be None -> keep it a valid writable object so no print() crashes
    if sys.platform=="win32" and sys.stdout is not None and hasattr(sys.stdout,"buffer"):
        import io as _io; sys.stdout=_io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    if sys.stdout is None:
        import io as _io; sys.stdout=_io.StringIO()
    sys.exit(main())
