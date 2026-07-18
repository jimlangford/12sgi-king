import os,re,sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT=r'C:\Users\12sgi\Documents\Claude\12sgi-king'

# hue-matched map: light callout tints/borders/texts -> dark equivalents
BG={  # backgrounds
 '#f3e9dc':'#241d0e','#fbf1dd':'#241d0e','#fbf3dd':'#241d0e','#fbf6ea':'#241d0e',
 '#fbf7ec':'#241d0e','#fff4e5':'#241d0e','#fff6e0':'#241d0e','#fff6e8':'#241d0e',
 '#fff7e6':'#241d0e','#fff8e6':'#241d0e','#fff8f0':'#241d0e',
 '#f6e4e4':'#2a1416','#fbf2ec':'#2a1416','#fdeaea':'#2a1416','#fdeeee':'#2a1416',
 '#f0f8f1':'#0e2a20','#f3faf5':'#0e2a20',
 '#f3f7fc':'#0f2540','#f3f8ff':'#0f2540','#f4f6f9':'#0f2540','#f4f7fb':'#0f2540',
 '#f6f8fa':'#0f2540','#f6f9fc':'#0f2540','#f6f9fd':'#0f2540','#f7fafe':'#0f2540',
 '#fbfdff':'#0f2540',
}
BORDER={
 '#e0c080':'#5c4a1e','#e2c893':'#5c4a1e','#e4d6a8':'#5c4a1e','#e6cf8f':'#5c4a1e',
 '#e6d3a3':'#5c4a1e','#e6d8a8':'#5c4a1e','#f0c080':'#5c4a1e','#f0c98a':'#5c4a1e',
 '#e3bcbc':'#6a3030','#e6bcbc':'#6a3030','#f0c5c5':'#6a3030',
 '#aad4b2':'#1e5c3e','#cde9d6':'#1e5c3e',
 '#bacde6':'#26456a','#cdd7df':'#26456a','#cfe0f2':'#26456a','#d6e2f0':'#26456a',
}
TEXT={
 '#5a4a16':'#e3c98a','#5a4a1e':'#e3c98a','#5a4d22':'#e3c98a','#6d4c00':'#e3c98a',
 '#7a5a10':'#e3c98a','#8a5a12':'#e3c98a','#9a6a12':'#e3c98a',
 '#7a3030':'#f0b0b0','#9a242c':'#f0b0b0','#9a2b2b':'#f0b0b0',
 '#1f5c2a':'#8fe0b0',
 '#0e4a84':'#7fb2ff',
 '#1a2233':'#c8d6e6','#5b6b78':'#9fb2c8',
}

def flip(t):
    n=0
    for a,b in BG.items():
        t2=re.sub(r'background:\s*'+re.escape(a), 'background:'+b, t, flags=re.I)
        if t2!=t: n+=1; t=t2
    for a,b in BORDER.items():
        t2=t.replace(a,b); t2=t2.replace(a.upper(),b)
        if t2!=t: n+=1; t=t2
    for a,b in TEXT.items():
        t2=re.sub(r'color:\s*'+re.escape(a), 'color:'+b, t, flags=re.I)
        if t2!=t: n+=1; t=t2
    return t,n

changed=[]
for sub in ['watchers','seed_reports','reports','king_public_src']:
    d=os.path.join(ROOT,sub)
    if not os.path.isdir(d): continue
    for dp,dn,fn in os.walk(d):
        for f in fn:
            if not f.endswith(('.py','.html','.css')): continue
            p=os.path.join(dp,f)
            try: t=open(p,encoding='utf-8',errors='replace').read()
            except: continue
            nt,n=flip(t)
            if nt!=t:
                open(p,'w',encoding='utf-8').write(nt)
                changed.append(os.path.relpath(p,ROOT))
print('files changed:', len(changed))
for c in changed[:60]: print(' ',c)
