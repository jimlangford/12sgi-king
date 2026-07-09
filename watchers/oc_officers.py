#!/usr/bin/env python3
# oc_officers.py - registered OFFICERS / board of directors for the top donor organizations, via OpenCorporates
# (Hawaiʻi jurisdiction us_hi). The State BREG officer search (hbe.ehawaii.gov) is reCAPTCHA-gated, which we do
# NOT bypass (policy); OpenCorporates is the legitimate KEYED API carrying the same registered-officer data.
#
# TOKEN: read from config/opencorporates.json  {"api_token":"..."}  — gitignored, never published, never echoed.
# No token yet -> graceful NO-OP (prints where to put it). When the token lands: run this, then re-run
# people_trace.py to merge the 'registered officers' layer onto orgs_<tenant>.html.
# Output: reports/_status/oc_officers.json (PRIVATE working data — org -> registered officers).
import os, sys, json, time, urllib.request, urllib.parse
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
ST=os.path.join(PROJ,"reports","_status"); CFG=os.path.join(PROJ,"config","opencorporates.json")
UA="Mozilla/5.0 (compatible; KiloAupuni/1.0)"; OC="https://api.opencorporates.com/v0.4"

def token():
    try:
        d=json.load(open(CFG,encoding="utf-8")); k=(d.get("api_token") or d.get("token") or "").strip()
        return k if (k and not k.startswith("PASTE_")) else None
    except Exception: return None

def _get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":UA}),timeout=45))

def officers_for(name, t):
    q=urllib.parse.urlencode({"q":name,"jurisdiction_code":"us_hi","api_token":t})
    try:
        comps=_get(OC+"/companies/search?"+q).get("results",{}).get("companies",[])
    except Exception as e:
        return [], "search-fail:%s"%str(e)[:50]
    if not comps: return [], "no-match"
    c=comps[0]["company"]; num=c.get("company_number")
    try:
        co=_get(OC+"/companies/us_hi/%s?%s"%(num,urllib.parse.urlencode({"api_token":t}))).get("results",{}).get("company",{})
        offs=[o["officer"] for o in (co.get("officers") or [])]
        return [{"name":o.get("name"),"position":o.get("position")} for o in offs], ("ok" if offs else "no-officers-listed")
    except Exception as e:
        return [], "officers-fail:%s"%str(e)[:50]

def main():
    t=token()
    if not t:
        print("oc_officers: NO TOKEN yet — waiting. Drop your OpenCorporates key in:")
        print("   %s   as   {\"api_token\":\"YOUR_KEY\"}"%CFG)
        print("   (it's gitignored + leak-gated — never published, never echoed.) Then re-run this + people_trace.py.")
        return 0
    ptf=os.path.join(ST,"people_trace.json")
    if not os.path.exists(ptf):
        print("oc_officers: run people_trace.py first (need the top-orgs list)."); return 2
    pt=json.load(open(ptf,encoding="utf-8"))
    seen=set(); orgs=[]
    for tid,d in pt.get("tenants",{}).items():
        for o in d.get("orgs",[])[:15]:        # top 15 orgs per tenant
            nm=(o.get("name") or "").strip()
            if not nm or nm.upper() in seen: continue
            seen.add(nm.upper()); orgs.append(nm)
    out={}; n=0
    for nm in orgs[:80]:
        offs,status=officers_for(nm,t)
        if offs: out[nm]={"officers":offs,"status":status}; n+=1
        time.sleep(0.7)        # respect OpenCorporates rate limits
    json.dump({"generated":time.strftime("%Y-%m-%d %H:%M"),"jurisdiction":"us_hi","orgs":out},
              open(os.path.join(ST,"oc_officers.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    print("oc_officers: registered officers for %d of %d orgs -> reports/_status/oc_officers.json"%(n,len(orgs)))
    print("  next: re-run people_trace.py to merge the registered-board layer onto orgs_<tenant>.html")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
