import csv, re, json, os
EX="reports/mauios/property/_rpt_extracts"
STOP={"trust","llc","lp","inc","co","company","the","of","and","pac","state","hawaii","development",
      "properties","realty","group","corp","ltd","holdings","partners","investments","family","revocable","living"}
def toks(n): return set(w for w in re.findall(r"[a-z0-9]+",(n or "").lower()) if len(w)>2 and w not in STOP)

# target RE donor entities (seeds + donor_profiles real-estate donors)
targets={}
for s in ["LANAI RESORTS LLC","LEDCOR","PARDEE"]: targets[s]=toks(s)
prof=json.load(open(os.path.join(EX,"..","..","donor_profiles.json"),encoding="utf-8"))
if isinstance(prof,dict): prof=list(prof.values())
for p in prof:
    for d in (p.get("realestate",{}) or {}).get("donors",[]):
        nm=(d.get("name") or "").strip()
        if nm and toks(nm): targets[nm.upper()]=toks(nm)
print("target RE entities:",len(targets))

# 1) sales index: parcel -> [(price,date)]
sales={}
lines=(l for l in open(os.path.join(EX,"sales.csv"),encoding="utf-8",errors="replace") if l.strip())
rdr=csv.reader(lines); hdr=[h.strip() for h in next(rdr)]
pi,di,idi=hdr.index("PRICE"),hdr.index("SALEDATE"),hdr.index("PARID")
for row in rdr:
    if len(row)<=pi: continue
    try: v=float(row[pi].strip().replace(",",""))
    except: v=0
    if v>0: sales.setdefault(row[idi].strip(),[]).append((v,row[di].strip()))
print("parcels with priced sales:",len(sales))

# 2) scan owner file (fixed-width: parid=[1:13], owner=[13:53]); match to targets
hits={}  # target -> {parcels:set, owner_samples:set}
with open(os.path.join(EX,"fullownr26.txt"),encoding="utf-8",errors="replace") as f:
    for line in f:
        if len(line)<53: continue
        owner=line[13:53].strip()
        ot=toks(owner)
        if not ot: continue
        for tname,tt in targets.items():
            if tt and tt<=ot or (tt and len(tt&ot)>=max(1,len(tt)-0) and len(tt)>=2 and tt&ot==tt):
                pass
        # match: target tokens all present in owner tokens (strong) 
        for tname,tt in targets.items():
            if tt and tt.issubset(ot):
                h=hits.setdefault(tname,{"parcels":set(),"owners":set()})
                h["parcels"].add(line[1:13]); h["owners"].add(owner)
# 3) join to sales, report money
rows=[]
for tname,h in hits.items():
    psales=[]; 
    for pid in h["parcels"]:
        psales+=sales.get(pid,[])
    if not psales: continue
    tot=sum(v for v,_ in psales); psales.sort(reverse=True)
    rows.append((tot,tname,len(h["parcels"]),len(psales),psales[0],list(h["owners"])[:2]))
rows.sort(reverse=True)
print("\n=== CONNECTED: RE donor entities that own Maui parcels WITH recorded sales ===")
for tot,tname,npar,nsale,top,owns in rows[:15]:
    print("  $%-13s %-32s %d parcels, %d sales; top $%s %s | as: %s"%(
        format(int(tot),','),tname[:32],npar,nsale,format(int(top[0]),','),top[1],owns[0][:30]))
print("\nmatched entities with sales:",len(rows),"of",len(targets),"targets")
