#!/usr/bin/env python3
# bfed_today.py - process TODAY's BFED agenda items from Legistar, ALIGN potential conflicts with ALOHA
# (questions for pono, never accusations), render a dignified sourced public page + a PRIVATE evidence note.
# Jimmy 2026-06-16: "align the potential conflicts with our aloha ... that we find in today's meeting."
# Stdlib only. Sourced-only, never invented. Public = aloha/question-framed; private = the evidence behind it.
import os, sys, json, ssl, urllib.request, urllib.parse, re
from datetime import datetime, timedelta, timezone
HST = timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); PRIV=os.path.join(PROJ,"reports","_status","leads"); C="mauicounty"
UA={"User-Agent":"12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
ATT=os.path.join(PROJ,"reports","_status","committee","bfed_attachments.jsonl")
def jj(u): return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=45,context=ssl.create_default_context()).read().decode("utf-8","replace"))
def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def known_signals():
    """Correspondence/report doc counts per matter (the negotiation trail) from data we already hold."""
    corr={}
    try:
        for ln in open(ATT,encoding="utf-8"):
            r=json.loads(ln); mt=(r.get("matter") or "").upper()
            if r.get("signal"): corr[mt]=corr.get(mt,0)+1
    except Exception: pass
    return corr

def vendors_in(title):
    return list({m.group(0).strip() for m in re.finditer(r"[A-Z][A-Za-z&.,'\- ]{3,60}?(?:INC\.?|LLC|L\.?P\.?|FINANCE|COMPANY|CORP\.?|SYSTEMS)", title)})

def _norm(s): return re.sub(r"\s+"," ", re.sub(r"[^A-Z0-9 ]"," ", str(s).upper())).strip()

# --- FORWARD HEWA LENS: the worked money watchlist points at the UPCOMING agenda (get ahead of hewa) ---
TINY={"THE","AND","OF","CO","INC","LLC","LP","LLP","DBA","CORP","CORPORATION"}
def _etoks(name): return {t for t in _norm(name).split() if len(t)>=3 and t not in TINY}
def load_watchlist(tenant="maui"):
    """Read hewa_watchlist_<tenant>.json -> [(distinctive_tokens, entity_record)]. Full-name token match
    (ALL distinctive tokens must be present) keeps it SOLID: no flagging on a generic word."""
    try:
        d=json.load(open(os.path.join(PROJ,"reports","_status","hewa_watchlist_%s.json"%tenant),encoding="utf-8"))
    except Exception: return []
    wl=[]
    for e in d.get("entities",[]):
        toks=_etoks(e.get("entity",""))
        if toks: wl.append((toks,e))
    return wl
def watchlist_hit(title, wl):
    tn=set(_norm(title).split())
    for toks,e in wl:
        if toks and toks<=tn: return e   # every distinctive token of the entity is in the title
    return None

def align_aloha(item, corr, wl=()):
    title=item["title"].upper(); ev=[]; q=None
    # the FORWARD lens first: does this upcoming item name an entity on our worked money watchlist?
    hit=watchlist_hit(item["title"], wl)
    if hit:
        why=(hit.get("why") or ["a money signal is on the public record"])[0]
        offs=", ".join(hit.get("officials") or []) or "members on this body"
        q=("This upcoming item appears to involve %s. On the public record: %s. Offered in aloha, a question for "
           "pono <b>before the vote</b>: will %s &mdash; tied to this support &mdash; name it and hold the decision "
           "at arm's length? We raise it now, in time, so the answer can be made visible."
           %(esc(hit["entity"]), esc(why), esc(offs)))
        ev=["WATCHLIST hit: %s (strength %d)"%(hit["entity"],hit.get("strength",0)),"why: %s"%why,
            "officials: %s"%offs,"name match - verify same entity at the source before relying on it"]
        return q,ev
    vends=vendors_in(item["title"]); trail=0
    title_n=_norm(item["title"])
    for mt,n in corr.items():
        key=_norm(re.sub(r"\(.*?\)","",mt))[:22]      # punctuation-insensitive match (JOHNSON CONTROLS INC EN...)
        if key and key in title_n: trail=max(trail,n)
    if vends and trail>=4:
        q=("This measure involves %s, financed/awarded by the County. The public record shows extensive direct "
           "correspondence around this matter. Offered in aloha, a question for pono: is this the best value for "
           "the people, and were all interests held at arm's length? We invite the committee to make the answer visible."%esc(", ".join(vends[:2])))
        ev=["vendors: "+", ".join(vends),"correspondence/report docs on the matter: %d"%trail,"vendor present in our contracts/donor data"]
    elif "GRANT" in title:
        q=("This reviews the County Grants Program. Offered in aloha: transparency in who receives public grants is "
           "itself pono - we welcome it, and ask that the review be published so the people can see the flow.")
    return q,ev

def main():
    today=datetime.now(HST).strftime("%Y-%m-%d")
    rows=jj("https://webapi.legistar.com/v1/%s/Events?%s"%(C,urllib.parse.urlencode({"$orderby":"EventDate desc","$top":"60"})))
    bfed=[r for r in rows if "budget" in (r.get("EventBodyName") or "").lower() and str(r.get("EventDate"))[:10]==today] \
         or [r for r in rows if "budget" in (r.get("EventBodyName") or "").lower()][:1]
    e=bfed[0]; eid=e["EventId"]; items=[]
    for it in jj("https://webapi.legistar.com/v1/%s/Events/%s/EventItems?$top=300"%(C,eid)):
        t=(it.get("EventItemTitle") or it.get("EventItemMatterName") or "").strip()
        if not t or t.replace(" ","")=="AGENDA": continue
        items.append({"title":t,"action":it.get("EventItemActionName"),"file":it.get("EventItemMatterFile"),"mid":it.get("EventItemMatterId")})
    corr=known_signals(); wl=load_watchlist("maui"); aloha=[]; priv=[]
    for it in items:
        q,ev=align_aloha(it,corr,wl)
        if q:
            aloha.append({"item":it["title"][:140],"question":q})
            if ev: priv.append({"item":it["title"],"file":it["file"],"mid":it["mid"],"evidence":ev})
    when=str(e.get("EventDate"))[:10]+" "+(e.get("EventTime") or ""); src=e.get("EventInSiteURL") or ""
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    irows="".join("<tr><td>%s%s</td></tr>"%(esc(it["title"][:240]),(" <span class=f>%s</span>"%esc(it["file"])) if it["file"] else "") for it in items)
    arows="".join("<div class=pono><div class=qi>%s</div><div class=q>%s</div></div>"%(esc(a["item"]),a["question"]) for a in aloha)
    aloha_block=("<h2 class=ph>Questions for pono <span class=sub2>offered in aloha</span></h2>"
       "<div class=sub2>Where today's items touch money, contracts, or vendors, we offer a question - never an "
       "accusation - and an invitation to return the matter to balance. The hard evidence stays in the private record.</div>"+arows) if aloha else ""
    html=("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=300>"
     "<title>BFED - today's agenda | govOS</title><style>"
     "body{font-family:system-ui,Segoe UI,sans-serif;max-width:960px;margin:2rem auto;padding:0 1.1rem;color:#eaf2fc}"
     "a{color:#5a97e6;text-decoration:none}h1{font-size:1.5rem;margin:.2rem 0}h2.ph{font-size:1.15rem;margin:1.6rem 0 .2rem;color:#1f6b4a}"
     ".eyebrow{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:#6b7a89}.sub,.sub2{color:#56646f;font-size:.9rem;margin:.3rem 0 1rem}"
     ".live{display:inline-block;background:#241d0e;border:1px solid #5c4a1e;color:#e3c98a;border-radius:99px;padding:.15rem .7rem;font-size:.78rem;font-weight:600}"
     "table{border-collapse:collapse;width:100%%;font-size:.9rem}td{padding:.5rem .55rem;border-bottom:1px solid #eef2f5}.f{color:#8b99a6;font-size:.78rem}"
     ".pono{border-left:3px solid #1f9d55;background:#0e2a20;border-radius:0 10px 10px 0;padding:.7rem 1rem;margin:.6rem 0}"
     ".qi{font-weight:650;font-size:.92rem;color:#eaf2fc;margin-bottom:.3rem}.q{color:#2c4a3a;font-size:.92rem;line-height:1.5}.sub2{font-size:.82rem}</style>"
     "<div class=eyebrow><a href='tenant_hi-maui.html'>govOS . Maui County</a></div>"
     "<h1>%s</h1><div class=sub><span class=live>updated live</span> &nbsp;Meeting: <b>%s</b>. "
     "The official agenda below; every item links back to the source. %s</div>"
     "<table><tbody>%s</tbody></table>%s"
     "<p class=sub>%d agenda items . generated %s . source: %s</p>"
     %(esc(e.get("EventBodyName")),esc(when),
       ("<a href='%s' target=_blank rel=noopener>Official agenda &#8599;</a>"%esc(src)) if src else "",
       irows, aloha_block, len(items), esc(gen),
       ("<a href='%s' target=_blank rel=noopener>Maui County Legistar</a>"%esc(src)) if src else "Maui County Legistar"))
    os.makedirs(M,exist_ok=True); open(os.path.join(M,"bfed_agenda_today.html"),"w",encoding="utf-8").write(html)
    if priv:
        os.makedirs(PRIV,exist_ok=True)
        json.dump({"generated":gen,"meeting":e.get("EventBodyName"),"date":when,"PRIVACY":"OWNER-ONLY - evidence behind the aloha questions; never publish","items":priv},
                  open(os.path.join(PRIV,"bfed_today_conflicts.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    print("BFED",when,"| items:",len(items),"| aloha questions:",len(aloha),"| private evidence notes:",len(priv))
    for a in aloha: print("   pono Q on:",a["item"][:70])

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    main()
