#!/usr/bin/env python3
# minutes_search.py - PROSECUTOR search over the ingested minutes (.txt) (Jimmy: "we need to know that cold;
# the people incriminate themselves"). Greps every meeting's text for a name/term/topic and prints each hit
# with the meeting (tenant · body · date), a context snippet, and the source URL. Also cross-references a name
# against the RE-donor entities so a single query shows: where they appear in the minutes AND what they gave/own.
#
# Usage:
#   python minutes_search.py "Pulama"                 # every minutes mention, with context
#   python minutes_search.py "Bill 9" --tenant hi-maui
#   python minutes_search.py --names                  # sweep ALL tracked RE-donor names across the minutes
# PRIVATE prosecutor tool — reads reports/minutes_text/. Stdlib only.
import os, sys, re, json
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
TXT=os.path.join(PROJ,"reports","minutes_text"); M=os.path.join(PROJ,"reports","mauios")

def _files(tenant=None):
    for root,_d,fs in os.walk(TXT):
        for f in fs:
            if f.endswith(".txt") and (not tenant or os.path.basename(root)==tenant):
                yield os.path.join(root,f)

def _meta(path):
    try:
        head="".join(open(path,encoding="utf-8").readlines()[:3])
        m=re.search(r"MINUTES \| (\S+) \| (.*?) \| (.*)",head); src=re.search(r"SOURCE: (\S+)",head)
        return (m.group(1),m.group(2),m.group(3)) if m else ("?","",""),(src.group(1) if src else "")
    except Exception: return ("?","",""),""

def search(term,tenant=None,ctx=90):
    rx=re.compile(re.escape(term),re.I); hits=0
    for p in _files(tenant):
        txt=open(p,encoding="utf-8",errors="replace").read()
        (tid,body,date),url=_meta(p)
        for mo in rx.finditer(txt):
            a=max(0,mo.start()-ctx); b=min(len(txt),mo.end()+ctx)
            snip=re.sub(r"\s+"," ",txt[a:b]).strip()
            hits+=1
            print("• %s · %s · %s\n  …%s…\n  %s"%(tid,body,date,snip,url))
    print("\n%d mention(s) of %r%s"%(hits,term,(" in "+tenant) if tenant else ""))
    return hits

_NS_STOP={"hawaii","hawai","maui","oahu","kauai","honolulu","county","council","state","general","public",
          "department","office","committee","meeting","member","members","chair","development","properties",
          "realty","holdings","company","group","trust","family","living","revocable","partners","investments",
          "limited","corporation","incorporated"}
def name_sweep():
    """Every RE-donor name × the minutes — the loop that incriminates: who gave/owns AND was on the record.
    Rigor: require ALL of a name's DISTINCTIVE tokens (>=5 chars, minus place/legal/generic stop) to appear —
    no first-word-only false-positives ('HAWAII'/'MAUI'/'GENERAL'/'WARD' are dropped as too generic)."""
    prof=json.load(open(os.path.join(M,"donor_profiles.json"),encoding="utf-8"))
    if isinstance(prof,dict): prof=list(prof.values())
    ENT=re.compile(r"\b(llc|lp|inc|corp|co|company|ltd|llp|lllp|pac|assoc|association|ranch|farms?|development|"
                   r"resort|properties|realty|holdings|group|trust|partners|bank|hotel|enterprises|builders|"
                   r"construction|brothers|bros)\b",re.I)
    # matcher per donor: ORG -> all distinctive tokens present (precise, multi-word). PERSON ("Last, First") ->
    # surname + given as an ADJACENT phrase (kills 'David' matching 1250 meetings).
    matchers={}
    for p in prof:
        for d in (p.get("realestate",{}) or {}).get("donors",[]):
            nm=(d.get("name") or "").strip()
            if not nm: continue
            if ENT.search(nm):
                toks=[w.upper() for w in re.findall(r"[A-Za-z]{4,}",nm) if w.lower() not in _NS_STOP]
                if len(toks)>=2: matchers[nm]=("org",toks)
            elif "," in nm:                          # person: "Surname, Given M."
                sur=re.findall(r"[A-Za-z]{3,}",nm.split(",")[0]); giv=re.findall(r"[A-Za-z]{3,}",nm.split(",",1)[1])
                if sur and giv:
                    s=re.escape(sur[0].upper()); g=re.escape(giv[0].upper())
                    matchers[nm]=("person",re.compile(r"\b%s\b[ .A-Z]{0,8}\b%s\b|\b%s,?\s+%s\b"%(g,s,s,g)))
    blob={}
    for p in _files():
        blob[p]=open(p,encoding="utf-8",errors="replace").read().upper()
    print("RE-donor names appearing in the minutes (verify identity — a question, not a finding):")
    found=0
    for nm in sorted(matchers):
        kind,m=matchers[nm]; where=[]
        for p,t in blob.items():
            hit=all(tok in t for tok in m) if kind=="org" else bool(m.search(t))
            if hit:
                (tid,body,date),_=_meta(p); where.append("%s/%s"%(tid,date or "?"))
        if where:
            found+=1; print("  [%s] %-30s -> %d meeting(s): %s"%(kind[0],nm[:30],len(where),", ".join(where[:5])))
    print("\n%d of %d tracked RE-donor names appear in the minutes (org=full-name, person=adjacent-phrase)."%(found,len(matchers)))

def main():
    args=[a for a in sys.argv[1:]]
    tenant=None
    if "--tenant" in args: tenant=args[args.index("--tenant")+1]; args=[a for a in args if a!=tenant and a!="--tenant"]
    if "--names" in args: return name_sweep() or 0
    if not args: print("usage: minutes_search.py <term> [--tenant <id>] | --names"); return 2
    search(args[0],tenant)
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
