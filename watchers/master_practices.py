#!/usr/bin/env python3
# master_practices.py - THE ONE MASTER best-practices system (Jimmy 2026-06-16: "self heal leaving the
# best practices learned from that system into one master system").
#
# The practices were scattered across 6 stores (selfheal_skills.json, LEARNED_RULES.json, SYSTEM_RULES.md,
# CROSS_THREAD_BEST_PRACTICES.md, PROJECT_STATE.md §8, the design-skill CLAUDE.md). This consolidates them
# into ONE living master, docs/MASTER_PRACTICES.md, that SELF-HEALS: a stable curated CANON spine + the live
# learnings harvested from selfheal_skills.json (which selfheal_learn.py keeps current from the dispatch log)
# + dated POLICY entries from the dispatch log + an index to the deep-dive sources. Regenerated every audit
# cycle so it never goes stale. Read-only over its sources; never deletes them (they remain the inputs).
# Stdlib only.
import os, sys, json, re
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HERE=os.path.dirname(os.path.abspath(__file__))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
DISP=os.path.join(PROJ,".dispatch_log.jsonl"); DOCS=os.path.join(PROJ,"docs")
OUT=os.path.join(DOCS,"MASTER_PRACTICES.md")

# ---- the curated CANON spine: the durable best practices learned, consolidated by domain. This is the
#      stable backbone; the live sections below it refresh from the dispatch log each run. ----
CANON=[
 ("GPU is a co-tenant (one 8 GB 4070)",[
   "ONE heavy GPU job at a time. Free ComfyUI VRAM (POST :8000/free) before kohya — training while ComfyUI holds models thrashes ~30x.",
   "Gate GPU_BUSY_MIB=6000 (NOT 2500 — ComfyUI holds ~4.4 GB baseline; 2500 deadlocks the conductor). Re-check free VRAM before heavy stages; back off rather than OOM.",
   "NEVER kill the ComfyUI venv python in self-heal, and NEVER disturb a running ASHES render.",
   "Never install plain onnxruntime beside onnxruntime-gpu in one venv — the CPU pkg shadows GPU and CUDAExecutionProvider vanishes (pin numpy==1.26.4 for insightface).",
   "When engaged with ComfyUI, READ ITS REALTIME CONSOLE live (GET /internal/logs/raw), not just nvidia-smi + /history.",
 ]),
 ("Boot-persistence + self-heal (all surfaces are one app)",[
   "surface_health.py sweeps every persistent surface (servers by port · daemons by process · tasks by state · launcher-script integrity). --heal relaunches ONLY safe lightweight services, NEVER ComfyUI/GPU/Ollama.",
   "Judge a periodic task by output freshness, not liveness; judge a persistent daemon by process.",
   "A file edit never changes a RUNNING process — restart the server/daemon after patching its module.",
   "Quadrant progress % = MEAN of facet %s (equal weight) so a large-N facet (211-song catalog) can't distort the headline.",
   "The hourly Quadrant Pulse is LIGHT — heal + score only; heavy generators stay in the daily audit_cycle; never launch a render from the pulse.",
 ]),
 ("Publishing + the leak-gate (public-is-public, private leads)",[
   "Edit the CANONICAL watcher source in tools/kilo-aupuni, NOT repo copies (the auto-publisher re-syncs canonical→repo ~15 min and reverts repo-only edits). go.html is the exception: static, copied to site/ by build_site — edit it directly.",
   "One build, PRIVATE FIRST: build_site.py → site/ + king-local mirror; private = superset, public = curated subset. Publish via the `publish` verb — NEVER re-run deploy_public.py.",
   "Leak-gate MUST pass before any push: prosecutor/case_files/keys/dollar-evidence NEVER reach public. Dollar evidence is owner-only (king-local); public carries questions + the ethics standard only.",
   "Cache-bust civic CSS (?v=DATE) — stale cached CSS silently UNSTYLES civic pages; check cache before assuming a code bug.",
 ]),
 ("Civic integrity (sourced-only, aloha not accusation)",[
   "Facts + source links only; correlations are QUESTIONS, never accusations. Frame every money×votes match as a question.",
   "Never invent civic data: Maui County Code has NO Title 15; Title 16 = Buildings & Construction (a fabricated Title 15 shipped once — never reintroduce).",
   "Dissent lives in COMMITTEE; full council = unanimous (340 ayes/0 noes). Minutes carry the roll-call; recusal eligibility is checked vs Maui Charter Art.10 / HRS 84.",
   "Witnessed leads (Paramount / 175 E Lipoa) are HYPOTHESES to verify, not accusations — private dossiers, owner-only.",
 ]),
 ("Design system (self-heal forward, never lose data)",[
   "NEVER run skill-refresh /MIR to ingest a design export — it purges (stale-orphan-tools + data-loss foot-gun). Extract to temp, read, merge by hand; the 12sgi-design skill is here-managed (auto-watcher RETIRED 2026-06-14).",
   "Design adoption is ADDITIVE: install new templates beside the old (king-system stays in place); live.js reads the live /api, data.js is snapshot-only FALLBACK and must never overwrite live tenant data.",
   "Adopting a new shell on the live King build is a DELIBERATE separate step (point the build at it) — never auto-swap; the server must not be surprised.",
   "Quad-OS palette = Yale blue #00356b (light/civic); zone hexes are LOCKED CANON (Mauka #4ade80 · Kula #fbbf24 · Makai #38bdf8). Studio register = warm-dark + gold #e3ad33; pick the register, don't mix.",
   "Keep .bat files pure ASCII (a stray em-dash → cryptic 'M is not recognized'). %-format in CSS strings must escape % as %%.",
 ]),
 ("Every project is a tenant",[
   "The govOS multi-tenant model is universal: every film/game/MV project is a tenant (config/tenants.json) AND civic instances are tenants — same model, consistent treatment incl. ourselves.",
   "Each film tenant carries its CANONICAL cast sourced from its actual script — never invented. Future film = register a tenant + ingest its script's cast.",
   "Actor names are ARCHETYPE references ONLY, never likeness clones; James renders as Jimmy's own likeness. Render registers: photoreal (Jimmy) · cartoon-3d (Luna/James pair, Sage) · polynesian-archetype (Sage cards + blend cast).",
   "Sage cards are ALL-POLYNESIAN guardians, env-only LoRAs — the photoreal hero and cartoon leads never appear on a card.",
 ]),
 ("Cross-thread coordination",[
   "Coordinate before you touch: read the .dispatch_log.jsonl tail for conflicts, LOG intent + result, claim an ownership lock on shared files. Never edit the same file from two threads at once.",
   "Log with the right prefix: SHIPPED / FINDING / BLOCKER / OWNERSHIP / POLICY / DECISION / HANDOFF — dense factual prose, correct source id.",
   "VERIFY work is actually DONE (deploy/result landed, real artifacts inspected) before reporting; don't report in-progress or end with 'want me to verify?'.",
 ]),
 ("No popups / windowless (focus-steal is a bug)",[
   "Every scheduled task runs via run_hidden.vbs (wscript, style 0); every subprocess near ffmpeg/ffprobe/tasklist/ngrok uses CREATE_NO_WINDOW (0x08000000). Never reintroduce native dialogs or interactive .bat tasks.",
   "Launcher and script must never share a log file (cmd >> takes a no-share-write lock → PermissionError).",
 ]),
 ("File edits under iCloud / Documents",[
   "Files under ~/Documents get truncated by editors/mounts ('0 bytes'/'1 line'). Write natively on Windows + verify byte size + py_compile/ast.parse ON DISK after every edit to a large file.",
 ]),
]

# the deep-dive sources this master consolidates (kept as inputs; this master is what you READ)
SOURCES=[
 ("config/LEARNED_RULES.json","render/creative rules — SINGLE SOURCE OF TRUTH for likeness, style, canon, voice"),
 ("tools/kilo-aupuni/selfheal_skills.json","live self-heal learnings (cumulative, from the dispatch log)"),
 ("docs/SYSTEM_RULES.md","enforced runtime canon (Kula not Farmlands, etc.)"),
 ("docs/CROSS_THREAD_BEST_PRACTICES.md","file ownership, edit-truncation defense, render-collision avoidance"),
 ("docs/PROJECT_STATE.md","§8 hard-won operating rules + cross-surface state"),
 (".claude/skills/12sgi-design/CLAUDE.md","design-system build lessons + canon rulings"),
]

def live_learnings():
    try: d=json.load(open(os.path.join(HERE,"selfheal_skills.json"),encoding="utf-8"))
    except Exception: return [],0,0
    sk=d.get("skills",[]); total=sum(len(s.get("learnings",[])) for s in sk)
    return sk,total,d.get("events_scanned",0)

def policies():
    out=[]; seen=set()
    try:
        for ln in open(DISP,encoding="utf-8"):
            try: e=json.loads(ln)
            except Exception: continue
            ev=e.get("event","")
            if ev.startswith("POLICY"):
                body=re.sub(r"^POLICY[^:]*:\s*","",ev).strip()
                key=body[:60].lower()
                if key in seen: continue
                seen.add(key); out.append((e.get("iso","")[:10],body[:240]))
    except Exception: pass
    return out[-40:]

def main():
    sk,total,events=live_learnings(); pol=policies()
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    L=[]
    L.append("# MASTER PRACTICES — the one system\n")
    L.append("> THE single best-practices system for 12sgi / elementLOTUS. **Read this first.** It is "
             "SELF-HEALED: a curated canon spine + live learnings harvested from the self-heal + dated "
             "policies from the dispatch log + an index to the deep-dive sources. Regenerated every audit "
             "cycle by `tools/kilo-aupuni/master_practices.py` — do not hand-edit below the canon; edit the "
             "sources and it re-consolidates.\n")
    L.append("_Generated %s · %d live learnings across %d skills (%s dispatch events) · %d dated policies._\n"%(
             gen,total,len(sk),events,len(pol)))
    L.append("\n---\n\n## 1 · Canon — the durable best practices\n")
    for title,rules in CANON:
        L.append("\n### %s\n"%title)
        for r in rules: L.append("- %s"%r)
        L.append("")
    L.append("\n---\n\n## 2 · Live learnings (self-healed from the dispatch log)\n")
    for s in sorted(sk,key=lambda x:-len(x.get("learnings",[]))):
        lr=s.get("learnings",[])
        if not lr: continue
        L.append("\n### %s — %s\n"%(s.get("id","?"),s.get("area","")))
        for x in lr: L.append("- %s"%x)
    L.append("\n---\n\n## 3 · Policies (dated, from dispatch)\n")
    for d,b in reversed(pol): L.append("- **%s** — %s"%(d,b))
    L.append("\n---\n\n## 4 · Deep-dive sources (the inputs this master consolidates)\n")
    for path,what in SOURCES: L.append("- `%s` — %s"%(path,what))
    L.append("\n_This master never deletes its sources; it consolidates them. To change a practice, edit the "
             "source (or log a POLICY) and the next self-heal re-folds it in._\n")
    open(OUT,"w",encoding="utf-8").write("\n".join(L))
    print("master_practices: MASTER_PRACTICES.md written")
    print("  canon domains: %d · live learnings: %d (%d skills) · policies: %d · sources: %d"%(
          len(CANON),total,len(sk),len(pol),len(SOURCES)))
    print("  -> docs/MASTER_PRACTICES.md")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
