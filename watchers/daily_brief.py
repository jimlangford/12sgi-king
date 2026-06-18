#!/usr/bin/env python3
# daily_brief.py - "keep me current each day" (Jimmy 2026-06-17). Scans the cross-thread dispatch log
# (.dispatch_log.jsonl — the single coordination channel for ALL threads) and surfaces what's OPEN and what's
# been MISSED, so nothing slips between surfaces. Plus a carried BACKLOG (docs/TODO_BACKLOG.md) that persists
# day to day. Writes a dated docs/DAILY_BRIEF.md (project) AND a PRIVATE king-local daily_brief.html (owner-only).
# Stdlib only; windowless-safe (no subprocess, no popups).
import os, sys, re, json, glob
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
LOG=os.path.join(PROJ,".dispatch_log.jsonl"); DOCS=os.path.join(PROJ,"docs")
BRIEF_MD=os.path.join(DOCS,"DAILY_BRIEF.md"); BACKLOG_MD=os.path.join(DOCS,"TODO_BACKLOG.md")
KING=[os.path.join(HOME,"AppData","Local","king-extract","deploy","king-local"),os.path.join(PROJ,"king-local")]
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# open-work signals in event text (case-insensitive); BLOCKER/HANDOFF prefixes are first-class
OPEN_RX=re.compile(r"\b(pending|still (?:to|need|await)|awaits?|to do|todo|not yet|blocked on|phase 2|"
                   r"next trace|when .* (?:token|key) (?:arrives|lands)|holds? until|held until|gated on|"
                   r"left to|remaining|to wire|to ingest|to break|placeholder|thin)\b",re.I)
# status-prefixed log lines are records, not open work — only BLOCKER/HANDOFF (binned separately) + un-prefixed
# "we still need X" notes count as open. This keeps the open/missed bucket signal, not the whole shipped log.
SKIP_PREFIX=re.compile(r"^(SHIPPED|DECISION|RESOLVED|DONE|POLICY|FINDING|OWNERSHIP|BLOCKER|HANDOFF)\b",re.I)

def _events(days=10):
    out=[];
    if not os.path.exists(LOG): return out
    cutoff=(datetime.now(HST)-timedelta(days=days)).strftime("%Y-%m-%d")
    for ln in open(LOG,encoding="utf-8",errors="replace").read().splitlines():
        try: d=json.loads(ln)
        except Exception: continue
        iso=(d.get("iso") or "")[:16]
        if iso[:10] < cutoff: continue
        out.append({"iso":iso,"src":d.get("source") or "?","ev":(d.get("event") or "").strip()})
    return out

def _scan():
    evs=_events()
    blockers=[e for e in evs if e["ev"].upper().startswith("BLOCKER")]
    handoffs=[e for e in evs if e["ev"].upper().startswith("HANDOFF")]
    # "open work" = non-done events whose text carries an open-work signal (skip the blockers/handoffs already binned)
    seen=set(); openw=[]
    for e in evs:
        if SKIP_PREFIX.match(e["ev"]): continue          # records (shipped/decision/etc.) are not open work
        if OPEN_RX.search(e["ev"]):
            key=e["ev"][:90].lower()
            if key in seen: continue
            seen.add(key); openw.append(e)
    # newest first
    for L in (blockers,handoffs,openw): L.sort(key=lambda e:e["iso"],reverse=True)
    # per-thread activity tally (last 10d) so missed/quiet threads are visible
    bythread={}
    for e in evs: bythread[e["src"]]=bythread.get(e["src"],0)+1
    return blockers,handoffs,openw,bythread,len(evs)

def _backlog():
    """Carried backlog (persists day to day). Seeded on first run with the known current gaps; hand-edit freely."""
    if not os.path.exists(BACKLOG_MD):
        os.makedirs(DOCS,exist_ok=True)
        seed=("# TODO Backlog — carried across days (hand-curated + daily_brief seed)\n\n"
              "_Add items as `- [ ] thing`. daily_brief.py surfaces the open ones each day; check them off when done._\n\n"
              "- [ ] Two tenants still thin vs Maui depth (hi-state, ny) — bring to 9-dimension parity\n"
              "- [ ] Minutes reachable for only 2/6 venues — break state, Hawaiʻi, Kauaʻi, NYC minutes\n"
              "- [ ] OpenCorporates token pending — when it lands, run oc_officers.py + people_trace.py to merge registered boards\n"
              "- [ ] Beta portal: wire config/beta.json (Stripe Identity link + constituent + council form URLs)\n"
              "- [ ] Testifiers + nay narratives are Maui-only — extend when other counties' minutes are ingested\n")
        open(BACKLOG_MD,"w",encoding="utf-8",newline="\n").write(seed)
    items=[]
    for ln in open(BACKLOG_MD,encoding="utf-8",errors="replace").read().splitlines():
        m=re.match(r"\s*-\s*\[( |x|X)\]\s*(.+)",ln)
        if m: items.append((m.group(1).lower()=="x",m.group(2).strip()))
    return items

def main():
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"); today=datetime.now(HST).strftime("%Y-%m-%d")
    blockers,handoffs,openw,bythread,n=_scan(); backlog=_backlog()
    open_items=[t for done,t in backlog if not done]; done_items=[t for done,t in backlog if done]
    def md_list(rows,fmt): return "\n".join(fmt(e) for e in rows) if rows else "_none_"
    md=("# DAILY BRIEF — %s\n\n"
        "_Cross-thread current-state, auto-built by daily_brief.py from the dispatch log (last 10 days, %d events) + the carried backlog._\n\n"
        "## ⛔ Open blockers (%d)\n%s\n\n"
        "## 🤝 Handoffs awaiting pickup (%d)\n%s\n\n"
        "## 🔧 Open / missed work surfaced across threads (%d)\n%s\n\n"
        "## 📋 Carried backlog (%d open)\n%s\n\n"
        "## 🧵 Thread activity (last 10 days)\n%s\n\n"
        "## ✅ Recently closed in backlog\n%s\n")%(
        today,n,
        len(blockers),md_list(blockers,lambda e:"- **%s** · %s — %s"%(e["iso"],e["src"],e["ev"][:200])),
        len(handoffs),md_list(handoffs,lambda e:"- **%s** · %s — %s"%(e["iso"],e["src"],e["ev"][:200])),
        len(openw),md_list(openw[:25],lambda e:"- %s · *%s* — %s"%(e["iso"],e["src"],e["ev"][:180])),
        len(open_items),("\n".join("- [ ] %s"%t for t in open_items) or "_none_"),
        "\n".join("- %s — %d events"%(s,c) for s,c in sorted(bythread.items(),key=lambda kv:-kv[1])),
        ("\n".join("- [x] %s"%t for t in done_items[-8:]) or "_none_"))
    os.makedirs(DOCS,exist_ok=True)
    open(BRIEF_MD,"w",encoding="utf-8",newline="\n").write(md)

    # PRIVATE king-local page (owner-only) — Yale-blue, mobile, never published
    def card(title,emoji,rows,fmt,empty="Nothing open here."):
        inner="".join(fmt(e) for e in rows) if rows else "<div class=mt>%s</div>"%empty
        return "<div class=sec><h2>%s %s <span class=ct>%d</span></h2>%s</div>"%(emoji,esc(title),len(rows),inner)
    rowfmt=lambda e:"<div class=row><span class=dt>%s</span><span class=sr>%s</span><div class=ev>%s</div></div>"%(
        esc(e["iso"]),esc(e["src"]),esc(e["ev"][:240]))
    blk=card("Open blockers","&#9940;",blockers,rowfmt)
    hnd=card("Handoffs awaiting pickup","&#129309;",handoffs,rowfmt)
    opn=card("Open / missed work across threads","&#128295;",openw[:25],rowfmt)
    bl="".join("<div class=bk>&#9744; %s</div>"%esc(t) for t in open_items) or "<div class=mt>backlog clear</div>"
    th="".join("<div class=row><span class=sr>%s</span><span class=dt>%d events</span></div>"%(esc(s),c) for s,c in sorted(bythread.items(),key=lambda kv:-kv[1]))
    html=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><meta name=theme-color content='#00356b'>"
      "<title>Daily Brief — current across all threads (PRIVATE)</title><style>"
      ":root{--bg:#fff;--panel:#e7eef8;--line:#bacde6;--ink:#13243d;--dim:#41536b;--faint:#6d7f97;--accent:#00356b;--accent2:#1259a3}"
      "*{box-sizing:border-box}body{font-family:'Segoe UI',system-ui,sans-serif;max-width:860px;margin:0 auto;padding:18px 16px 44px;color:var(--ink);background:var(--bg);font-size:16px;line-height:1.5}"
      "h1{font-size:1.45rem;margin:.2rem 0}h2{font-size:1.02rem;color:var(--accent);margin:0 0 .5rem}.ct{font:700 12px/1 Consolas,monospace;color:#fff;background:var(--accent2);border-radius:99px;padding:.12rem .5rem;vertical-align:middle}"
      ".eyebrow{letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600;font-size:.78rem}.sub{color:var(--dim);font-size:.9rem}"
      ".sec{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem;margin:.8rem 0}"
      ".row{border-bottom:1px solid #dbe5f1;padding:.4rem 0}.row:last-child{border-bottom:0}.dt{font-family:Consolas,monospace;color:var(--accent2);font-size:.78rem;margin-right:.5rem}.sr{font-family:Consolas,monospace;color:var(--faint);font-size:.76rem}"
      ".ev{color:var(--ink);font-size:.9rem;margin-top:.15rem}.mt{color:var(--faint);font-style:italic;font-size:.88rem}.bk{padding:.3rem 0;font-size:.92rem;color:var(--dim);border-bottom:1px solid #dbe5f1}"
      ".foot{margin-top:1.4rem;border-top:1px solid var(--line);padding-top:.6rem;color:var(--faint);font-size:.76rem}</style>"
      "<div class=eyebrow>govOS &middot; owner-only &middot; never published</div><h1>Daily Brief &mdash; current across all threads</h1>"
      "<p class=sub>What&rsquo;s open and what&rsquo;s been missed, from the cross-thread dispatch log (last 10 days, %d events) + the carried backlog. Generated %s.</p>"
      "%s%s%s<div class=sec><h2>&#128203; Carried backlog <span class=ct>%d</span></h2>%s</div>"
      "<div class=sec><h2>&#129525; Thread activity (10d)</h2>%s</div>"
      "<div class=foot>daily_brief.py &middot; edit docs/TODO_BACKLOG.md to add/close items &middot; PRIVATE</div>")%(
      n,esc(gen),blk,hnd,opn,len(open_items),bl,th)
    wrote=[]
    for kl in KING:
        if os.path.isdir(kl):
            open(os.path.join(kl,"daily_brief.html"),"w",encoding="utf-8",newline="\n").write(html); wrote.append(kl)
    print("daily_brief: %d blocker(s), %d handoff(s), %d open/missed, %d backlog open -> docs/DAILY_BRIEF.md + %d king-local page(s)"%(
          len(blockers),len(handoffs),len(openw),len(open_items),len(wrote)))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
