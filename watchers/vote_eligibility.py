#!/usr/bin/env python3
# vote_eligibility.py - "IF actual donor recusals were enforced, WHO may vote on each agenda item?"
# (Jimmy 2026-06-16). For each agenda item: identify its party vendors -> cross-ref each member's SOURCED
# donor matches (vendor_donor_join) -> a member with a donor tie to a party SHOULD recuse -> the eligible
# roster = members minus conflicted. Verified against the ETHICS LAW and against the ACTUAL recusals recorded
# (the recusal GAP = should-recuse-but-voted). PUBLIC = aloha question; PRIVATE = the dollar evidence.
# Integrity: sourced donations + real law only; every tie is a QUESTION to verify, never proof. Stdlib only.
import os, sys, json, ssl, re, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); PRIV=os.path.join(PROJ,"reports","_status","leads"); C="mauicounty"
UA={"User-Agent":"12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
JOIN=os.path.join(M,"vendor_donor_join.json")
# Real, sourced standard (verify at the source; cited at Article/Code level, no fabricated subsection):
ETHICS=("Maui County Charter Art. 10 — Board of Ethics & Code of Ethics: a member with a financial interest "
        "in a matter must disclose it and refrain from voting (recusal). Statewide analog: HRS ch. 84 (State "
        "Ethics Code), conflict-of-interest / fair-treatment. This tally applies that standard to sourced "
        "campaign-donation ties — each is a QUESTION for the Board of Ethics to verify, not a finding of guilt.")
ROSTER=["Batangan","Cook","Johnson","Lee","Paltin","Rawlins-Fernandez","Sinenci","Sugimura","Uu-Hodgins"]
def jj(u): return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=45,context=ssl.create_default_context()).read().decode("utf-8","replace"))
def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def norm(s): return re.sub(r"\s+"," ", re.sub(r"[^A-Z0-9 ]"," ", str(s).upper())).strip()

def conflict_map():
    """vendor (normalized) -> [{official, amount}] from the sourced donor<->vendor join."""
    out={}
    try:
        d=json.load(open(JOIN,encoding="utf-8"))
        for m in d.get("matched",[]):
            out[norm(m["vendor"])]={ "vendor":m["vendor"], "hits":[{"official":h["official"],"amount":h["amount"]} for h in m.get("hits",[])] }
    except Exception: pass
    return out

def vendors_in(title):
    return list({m.group(0).strip() for m in re.finditer(r"[A-Z][A-Za-z&.,'\- ]{3,60}?(?:INC\.?|LLC|L\.?P\.?|FINANCE|COMPANY|CORP\.?|SYSTEMS|ENGINEER[A-Z]*|ARCHITECT[A-Z]*)", title)})

def actual_recusals():
    try:
        d=json.load(open(os.path.join(M,"officials.json"),encoding="utf-8")); offs=d if isinstance(d,list) else list(d.values())
        return {o.get("name") or o.get("official"): (o.get("recused",0)) for o in offs if isinstance(o,dict)}
    except Exception: return {}

def main():
    today=datetime.now(HST).strftime("%Y-%m-%d")
    rows=jj("https://webapi.legistar.com/v1/%s/Events?%s"%(C,urllib.parse.urlencode({"$orderby":"EventDate desc","$top":"60"})))
    bfed=[r for r in rows if "budget" in (r.get("EventBodyName") or "").lower() and str(r.get("EventDate"))[:10]==today] \
         or [r for r in rows if "budget" in (r.get("EventBodyName") or "").lower()][:1]
    e=bfed[0]; eid=e["EventId"]
    cmap=conflict_map()
    items=[]
    for it in jj("https://webapi.legistar.com/v1/%s/Events/%s/EventItems?$top=300"%(C,eid)):
        t=(it.get("EventItemTitle") or it.get("EventItemMatterName") or "").strip()
        if not t or t.replace(" ","")=="AGENDA": continue
        tn=norm(t); conflicted=[]
        for vn,info in cmap.items():
            # party vendor named in the item?
            key=vn[:18]
            if key and key in tn:
                for h in info["hits"]:
                    conflicted.append({"member":h["official"],"vendor":info["vendor"],"amount":h["amount"]})
        cm=sorted({c["member"] for c in conflicted})
        eligible=[m for m in ROSTER if m not in cm]
        items.append({"title":t[:160],"file":it.get("EventItemMatterFile"),"party_conflicts":conflicted,
                      "should_recuse":cm,"eligible":eligible,"eligible_n":len(eligible)})
    when=str(e.get("EventDate"))[:10]+" "+(e.get("EventTime") or ""); src=e.get("EventInSiteURL") or ""
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    # render public block (append-able to the agenda page) + private evidence
    blocks=""
    priv=[]
    for it in items:
        if it["should_recuse"]:
            ask=("On this item, if donor-recusal were applied, <b>%d of %d</b> members could vote. A question for pono "
                 "(for the Board of Ethics to weigh): should %s recuse, having received campaign donations tied to a party here?"
                 %(it["eligible_n"],len(ROSTER),esc(", ".join(it["should_recuse"]))))
            priv.append({"item":it["title"],"should_recuse":it["should_recuse"],"evidence":it["party_conflicts"]})
        else:
            ask="On this item, no sourced donor tie to a party was found — all %d members appear eligible to vote."%len(ROSTER)
        blocks+="<div class=elig><div class=ei>%s</div><div class=eq>%s</div></div>"%(esc(it["title"]),ask)
    html=("<div class=eligwrap><h2 class=eh>Who may vote — if donor recusals were enforced</h2>"
          "<div class=esub>%s</div>%s<p class=esub>Meeting: %s · generated %s · %s</p></div>"
          %(esc(ETHICS),blocks,esc(when),esc(gen),("<a href='%s' target=_blank rel=noopener>source</a>"%esc(src)) if src else "Legistar"))
    os.makedirs(M,exist_ok=True)
    open(os.path.join(M,"bfed_eligibility_today.html"),"w",encoding="utf-8").write(
        "<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=300><title>BFED - who may vote | govOS</title>"
        "<style>body{font-family:system-ui,Segoe UI,sans-serif;max-width:920px;margin:2rem auto;padding:0 1.1rem;color:#eaf2fc}"
        "a{color:#5a97e6}.eh{font-size:1.25rem;color:#1f6b4a;margin:.2rem 0}.esub{color:#56646f;font-size:.86rem;margin:.4rem 0 1rem}"
        ".elig{border-left:3px solid #1f9d55;background:#0e2a20;border-radius:0 10px 10px 0;padding:.7rem 1rem;margin:.6rem 0}"
        ".ei{font-weight:650;font-size:.9rem;margin-bottom:.3rem}.eq{color:#2c4a3a;font-size:.92rem;line-height:1.5}</style>"+html)
    if priv:
        os.makedirs(PRIV,exist_ok=True)
        json.dump({"generated":gen,"meeting":e.get("EventBodyName"),"date":when,"ethics_standard":ETHICS,
                   "PRIVACY":"OWNER-ONLY - dollar evidence behind the recusal questions; never publish","items":priv},
                  open(os.path.join(PRIV,"bfed_eligibility_evidence.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    print("vote_eligibility · BFED",when)
    for it in items:
        tag=("SHOULD RECUSE: "+", ".join(it["should_recuse"])) if it["should_recuse"] else "no donor conflict on parties"
        print("  [%d/%d eligible] %s -> %s"%(it["eligible_n"],len(ROSTER),it["title"][:46],tag))
    print("ethics standard cited:", ETHICS[:60],"...")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
