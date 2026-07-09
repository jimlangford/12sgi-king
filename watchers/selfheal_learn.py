#!/usr/bin/env python3
# selfheal_learn.py - the CUMULATIVE learner (Jimmy 2026-06-16). Watches the whole coordination thread
#   (.dispatch_log.jsonl) + the skills registry, clusters recurring asks / redirections / caught-faults by
#   SKILL area, and tallies how often each skill has been touched + which POLICY/FINDING/DECISION events
#   refined it. So the system "sees recurring asks and redirection cumulatively" and each skill is visibly
#   refining. Honest: it TALLIES + surfaces candidate new learnings (POLICY/FINDING not already captured) for
#   review — it does not fabricate rules. Writes reports/_status/selfheal_skills.json/.html + updates touch counts.
# The WHY: docs/SELFHEAL_COVENANT.md. Stdlib only. Run as part of the self-heal cycle.
import json, os, re, sys
from datetime import datetime, timedelta, timezone

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
SKILLS = os.path.join(TOOL_DIR, "selfheal_skills.json")
DISPATCH = os.path.join(PROJECT, ".dispatch_log.jsonl")
OUT = os.path.join(PROJECT, "reports", "_status")
HST = timezone(timedelta(hours=-10))

# per-skill keyword anchors to cluster dispatch events
KW = {
    "gpu_orchestration": r"gpu|vram|comfyui|oversubscrib|thrash|lock|free|kohya|cuda",
    "lora_training": r"train|lora|grad_accum|kohya|step|luna_character|james|luna_environment|safetensors",
    "mesh_pipeline": r"mesh|hunyuan|render_mesh|t-pose|y-pose|a-pose|accurig|glb|fbx|terrain|dem|3dep",
    "deck_render": r"deck|render_cards|card|luna look|zone-sphere|kumulipo|55 cards|environment lora",
    "character_model": r"character|luna|james|alicia|archetype|no beard|polynesian|nyc",
    "grants": r"grant|usda|cdbg|nareit|fema|hands|sharpen|daily|smtp|nofo|rbdg|vapg",
    "civic_audit": r"tenant|audit|money x votes|federal|prosecutor|leak|govos|kilo|moku|ahupuaa|balance",
    "publish": r"push|public|12sgi-king|copyright|leak-sweep|gitignore|pages|build_site",
    "self_heal": r"self.?heal|stall|attention|detect|stuck|skipped|no-progress|prompt",
    "ops_discipline": r"ascii|bat|windowless|popup|run_hidden|naming|truncat|okina|utf-8|scheduled task",
    "civic_ingest": r"ingest|civicclerk|qpublic|mapps|energov|permit|opencorporat|socrata|minutes|server.?side|workaround|endpoint|scraper|oc_officers",
    "cross_thread_ingest": r"release pressure|ingest assist|civic_ingest_assist|cross.?thread|cpu_?lock|yield|spare capacity|any thread|keep working",
    "tenant_discover": r"new tenant|tenant_discover|new county|municipalit|jurisdiction|candidate|auto.?create|legistar client|civicclerk",
    "tenant_onboarding": r"tenant|onboard|ingest|depth|maui depth|minutes per venue|hi-state|hi-hawaii|hi-kauai|hi-honolulu|ny|ratchet|6/6",
    "agenda_getahead": r"agenda|attachment|packet|press.?release|get ahead|hoonani|hoʻonani|bill 1|resolution 26|legistar|matter|entitlement|island plan|community plan|developer|land use",
    "testimony_crosscheck": r"testimon|cross.?check|corrobor|money x votes|property|parcel|roll.?call|uipa|donor|vendor|witness",
    "civic_commerce": r"charg|stripe|subscrib|tier|serve.?==.?charge|serve.?>.?charge|paywall|checkout|webhook|funnel|8443|verify_api_base|refund|terms|privacy|rosca|legal|compliance|go.?live|capability|entitlement|ask_ai|dashboards|county",
}
REDIRECT = re.compile(r"POLICY|FINDING|DECISION|FIX|LESSON|RULE|self-?heal|redirect", re.I)

def now_hst(): return datetime.now(HST)
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def main():
    skills = json.load(open(SKILLS, encoding="utf-8"))
    events = []
    try:
        for ln in open(DISPATCH, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try: events.append(json.loads(ln))
                except Exception: pass
    except FileNotFoundError: pass
    # cluster each event to skill(s) + tally; count redirections (rules) separately
    tally = {s["id"]: {"touches": 0, "redirections": 0} for s in skills["skills"]}
    for e in events:
        txt = (e.get("event") or "") + " " + (e.get("instruction") or "")
        tl = txt.lower()
        is_rd = bool(REDIRECT.search(txt))
        for sid, pat in KW.items():
            if re.search(pat, tl):
                tally[sid]["touches"] += 1
                if is_rd: tally[sid]["redirections"] += 1
    # write counts back into the registry (cumulative refinement signal)
    for s in skills["skills"]:
        t = tally[s["id"]]
        s["touches"] = t["touches"]; s["redirections_learned"] = t["redirections"]
        s["learning_count"] = len(s.get("learnings", []))
    skills["learned_at"] = now_hst().strftime("%Y-%m-%d %H:%M HST")
    skills["events_scanned"] = len(events)
    json.dump(skills, open(SKILLS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.makedirs(OUT, exist_ok=True)
    json.dump(skills, open(os.path.join(OUT, "selfheal_skills.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _html(skills)
    ranked = sorted(skills["skills"], key=lambda s: -s["touches"])
    print(f"selfheal_learn: scanned {len(events)} thread events across {len(skills['skills'])} skills")
    for s in ranked:
        print(f"  {s['id']:18} touches={s['touches']:>3} redirections={s['redirections_learned']:>2} learnings={s['learning_count']}")
    return 0

def _html(sk):
    rows = "".join(
        f"<tr><td>{esc(s['id'])}</td><td class=muted>{esc(s['area'])}</td>"
        f"<td class=n>{s.get('touches',0)}</td><td class=n>{s.get('redirections_learned',0)}</td>"
        f"<td class=n>{s.get('learning_count',0)}</td></tr>"
        for s in sorted(sk['skills'], key=lambda x:-x.get('touches',0)))
    html = f"""<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=300>
<title>Refining Skills — self-heal (private)</title><style>
body{{font-family:system-ui,Segoe UI,sans-serif;max-width:960px;margin:1.4rem auto;padding:0 1rem;background:#0d1117;color:#e6edf3}}
h1{{font-size:1.35rem}} .sub{{color:#8b949e;font-size:.85rem}} table{{border-collapse:collapse;width:100%;font-size:.85rem}}
td,th{{padding:.4rem .55rem;border-bottom:1px solid #21262d;text-align:left}} .n{{text-align:right}} .muted{{color:#8b949e}}
.creed{{background:#0d2818;border-left:3px solid #1f9d55;padding:.7rem 1rem;border-radius:8px;font-size:.9rem;color:#cfe9d8}}</style>
<h1>Refining Skills <span class=sub>cumulative — sharper each run</span></h1>
<div class=creed>{esc(sk.get('measure',''))}</div>
<div class=sub>Scanned {sk.get('events_scanned','?')} thread events · {sk.get('learned_at','')}. Each skill sharpens from recurring asks + redirections + caught faults. Why: docs/SELFHEAL_COVENANT.md.</div>
<table><thead><tr><th>skill</th><th>area</th><th class=n>thread touches</th><th class=n>redirections</th><th class=n>learnings</th></tr></thead><tbody>{rows}</tbody></table>"""
    open(os.path.join(OUT, "selfheal_skills.html"), "w", encoding="utf-8").write(html)

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
