#!/usr/bin/env python3
"""progressive_selfheal.py — the MEASURE→RATCHET layer the Audit quad-os thread owns
   (docs/AUDITOR_COVENANT.md: "a self-heal is progressive when each cycle leaves the system at a
   HIGHER floor than the last"). Ordinary self-heal answers "did it heal?"; this answers
   "is it MORE healed than last cycle?" with a NUMBER that must trend up.

WHAT IT DOES, per area: score the area from real signals (0–100), append the score to a series
(reports/_status/progressive_selfheal.json — one row per area per cycle), then RATCHET: the new
score must be ≥ the area's previous floor; a regression is itself a TOP FINDING. The deliverable
each run = a higher (or held) floor + the trend, persisted, so progress is a number not a feeling.

Integrity unchanged (covenant): solution-side, finding-as-question, leak-gate, no fabrication.
PRIVATE: the series + dashboard live in reports/_status (never published). Stdlib only.
Folds into audit_cycle after selfheal + selfheal_learn.
"""
import os, sys, json, time, subprocess
from datetime import datetime, timezone, timedelta

HERE   = os.path.dirname(os.path.abspath(__file__))
HOME   = os.path.expanduser("~")
PROJECT= os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
STATUS = os.path.join(PROJECT, "reports", "_status")
SERIES = os.path.join(STATUS, "progressive_selfheal.json")      # the score series (PRIVATE)
HST    = timezone(timedelta(hours=-10))
if HERE not in sys.path: sys.path.insert(0, HERE)
def now_hst(): return datetime.now(HST)
def _load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

# ── MEASURE: each area returns (score 0–100, one-line detail). Honest: missing signal -> None. ──
def m_self_heal():
    sp = os.path.join(MAUIOS, "selfheal.json")
    # FRESHNESS GUARD (Jimmy 2026-06-20: "fix what was broken in the heal systems until it works").
    # The bug: this scored selfheal.json BLINDLY, so a STALE file (selfheal.py skipped/failed, or
    # progressive run out-of-order) produced a phantom score -> a FALSE regression that dropped the
    # ratchet floor on data that was never real. Fix: if the file is missing or stale (>6h), regenerate
    # it first; if STILL not fresh, SKIP scoring (return None = not ratcheted) instead of firing a false
    # regression. The floor only ever moves on real, current signal.
    STALE = 6 * 3600
    stale = (not os.path.exists(sp)) or (time.time() - os.path.getmtime(sp) > STALE)
    if stale:
        try:
            subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "selfheal.py")],
                           cwd=PROJECT, capture_output=True, timeout=300)
        except Exception:
            pass
    d = _load(sp, {})
    s = d.get("summary") or {}
    tot = (s.get("PASS", 0) + s.get("WARN", 0) + s.get("FAIL", 0)) or 0
    if not tot:
        return None, "selfheal.json unavailable (SKIPPED - not scored, no false regression)"
    if time.time() - os.path.getmtime(sp) > STALE:   # regen didn't refresh it -> don't score phantom data
        return None, "selfheal.json stale >6h after regen attempt (SKIPPED - run selfheal.py)"
    score = round(100 * s.get("PASS", 0) / tot)
    return score, "selfheal %d pass / %d warn / %d fail" % (s.get("PASS", 0), s.get("WARN", 0), s.get("FAIL", 0))

def m_commerce():
    d = _load(os.path.join(STATUS, "charge_chain.json"), {})
    # POSITIVE checks must be True; ALARM flags (security_alarm) are inverse — True = bad, so a
    # False alarm is the healthy state. Don't score an absent alarm as a failed check.
    ALARMS = {"security_alarm"}
    checks = {k: v for k, v in d.items() if isinstance(v, bool) and k not in ALARMS}
    if not checks: return None, "charge_chain.json not present"
    alarm = bool(d.get("security_alarm"))
    score = round(100 * sum(1 for v in checks.values() if v) / len(checks))
    if alarm: score = max(0, score - 50)                          # an active security alarm halves the floor
    bad = [k for k, v in checks.items() if not v]
    return score, "%d/%d charge-chain checks true; alarm=%s%s" % (sum(checks.values()), len(checks), alarm, (" — gaps: " + ",".join(bad)) if bad else "")

def m_publish():
    try:
        import publish_audit; r = publish_audit.audit()
    except Exception as e:
        return None, "publish_audit unavailable (%s)" % str(e)[:60]
    denom = (r["ok"] + r["gap_count"]) or 1
    score = round(100 * r["ok"] / denom)
    return score, "%d current, %d gap(s) on the public floor" % (r["ok"], r["gap_count"])

def m_ops():
    d = _load(os.path.join(STATUS, "system_status.json"), {})
    srv = d.get("servers") or {}
    if not srv: return None, "system_status.json not present"
    up = sum(1 for v in srv.values() if v)
    score = round(100 * up / len(srv))
    if d.get("attention"): score = max(0, score - 10 * len(d["attention"]))   # real attention items dock the floor
    return score, "%d/%d servers up; %d attention item(s)" % (up, len(srv), len(d.get("attention") or []))

def m_civic_audit():
    # coverage of tenant case documents that meet the audit-wisdom gate (review-ready), the civic core.
    try:
        import case_document, prosecutor
        cases = prosecutor.build_cases()
        for c in cases:
            v, _ = case_document.gate(c); c["_v"] = v
        ready = sum(1 for c in cases if c["_v"] == "REVIEW-READY")
        score = round(100 * ready / len(cases)) if cases else None
        return score, "%d/%d Maui matters review-ready (sourced+framed+strength>=3)" % (ready, len(cases))
    except Exception as e:
        return None, "case logic unavailable (%s)" % str(e)[:60]

def m_skills():
    d = _load(os.path.join(HERE, "selfheal_skills.json"), {})
    learn = sum(len(s.get("learnings", [])) for s in d.get("skills", []))
    # cumulative learnings is monotonic by design — the ratchet of the system's own knowledge.
    return learn, "%d cumulative learnings across %d skills" % (learn, len(d.get("skills", [])))

def _txt(p):
    try: return open(p, encoding="utf-8", errors="replace").read().lower()
    except Exception: return ""

def m_jrcsl():
    """JRCSL DECIDE-GATE health across EVERY aspect of the system + hosting (Jimmy 2026-06-19:
    'progressively self-heal this concept across every aspect of the system and hosting'). The concept:
    JRCSL decides by Jimmy's codified will and only escalates the real fork. Score = the judge exists +
    carries the gate, the skill carries the gate, EVERY-thread coverage (quad-sync), HOSTING decisions
    run through JRCSL, and live ADOPTION (JRCSL-call decisions on the bus, not over-asking). Ratchets up
    as the concept spreads; a regression (the gate removed anywhere) drops the floor = a top finding."""
    score, parts = 0, []
    if "jrcsl decides by default" in _txt(os.path.join(PROJECT, "docs", "JRCSL_DOCTRINE.md")):
        score += 20; parts.append("doctrine-gate")
    if "decide or escalate" in _txt(os.path.join(PROJECT, ".claude", "skills", "jrcsl", "SKILL.md")):
        score += 20; parts.append("skill-gate")
    qs = _txt(os.path.join(PROJECT, ".claude", "skills", "quad-sync", "SKILL.md"))
    if "jrcsl" in qs and "decide" in qs:
        score += 20; parts.append("all-thread")                 # every lane inherits the gate
    coc = _txt(os.path.join(PROJECT, "docs", "CHAIN_OF_COMMAND.md"))
    if "jrcsl" in coc and ("hosting" in coc or "wordpress" in coc or "elementlotus" in coc or "12sgi.com" in coc):
        score += 15; parts.append("hosting")                    # hosting/domain calls run through JRCSL
    # live adoption: JRCSL-call decisions on the bus = the system deciding by his doctrine, not over-asking
    n = 0
    try:
        for l in open(os.path.join(PROJECT, ".dispatch_log.jsonl"), encoding="utf-8", errors="replace"):
            if "jrcsl call" in l.lower() or "jrcsl verdict" in l.lower() or "jrcsl decid" in l.lower():
                n += 1
    except Exception: pass
    score += min(25, 5 * n)
    parts.append("adoption:%d" % n)
    return score, "decide-gate spread: " + (", ".join(parts) or "none yet")

def m_meeting_intel():
    """Civic meeting-intelligence pipeline (NEW 2026-06-19; jrcsl/civic owns the PIPE, audio owns audio->text).
    Score real signals so the new capability can't silently rot: source resolved (Akaku manifest + Teams
    links), the always-on watcher state, meetings judged, and leads delivered to the prosecutor."""
    ak = _load(os.path.join(PROJECT, "config", "akaku_stream.json"), {})
    tl = _load(os.path.join(PROJECT, "config", "teams_links.json"), {})
    mdir = os.path.join(STATUS, "jrcsl", "meetings")
    def lines(p):
        try: return sum(1 for l in open(p, encoding="utf-8") if l.strip())
        except Exception: return 0
    checks = {
        "akaku_manifest": bool(((ak.get("channels") or {}).get("53") or {}).get("live_manifest")),
        "teams_links": len(tl.get("committees") or {}) >= 1,
        "watcher_state": os.path.exists(os.path.join(STATUS, "jrcsl", "meeting_watch.json")),
        "meetings_judged": (len(os.listdir(mdir)) if os.path.isdir(mdir) else 0) >= 1,
        "prosecutor_leads": lines(os.path.join(STATUS, "prosecutor", "jrcsl_leads.jsonl")) >= 1,
    }
    if not any(checks.values()):
        return None, "meeting-intel not built yet"
    score = round(100 * sum(1 for v in checks.values() if v) / len(checks))
    bad = [k for k, v in checks.items() if not v]
    return score, "%d/%d meeting-intel signals%s" % (sum(checks.values()), len(checks), (" — missing: " + ",".join(bad)) if bad else "")

def m_code_audit():
    """Code-quality floor from code_audit.py (score 0-100, based on HIGH/MED/LOW findings).
    Reads the pre-scored JSON; re-runs the audit if stale (>4h) so the ratchet reflects the CURRENT codebase.
    A regression here = a new HIGH or MED finding shipped without being fixed."""
    import subprocess, sys as _sys
    ca = os.path.join(STATUS, "code_audit.json")
    STALE = 4 * 3600
    stale = (not os.path.exists(ca)) or (time.time() - os.path.getmtime(ca) > STALE)
    if stale:
        try:
            subprocess.run([_sys.executable, "-X", "utf8",
                            os.path.join(PROJECT, "tools", "kilo-aupuni", "code_audit.py")],
                           cwd=PROJECT, capture_output=True, timeout=120)
        except Exception:
            pass
    d = _load(ca, {})
    score = d.get("score")
    if score is None:
        return None, "code_audit.json not present (run tools/kilo-aupuni/code_audit.py)"
    by_class = d.get("by_class", {})
    total = d.get("total", 0)
    sev = d.get("by_severity", {})
    hi = sev.get("HIGH", 0)
    detail = "score=%d total=%d HIGH=%d" % (score, total, hi)
    if by_class:
        detail += " classes=" + ",".join("%s:%d" % (k, v) for k, v in sorted(by_class.items(), key=lambda x: -x[1])[:4])
    return score, detail

def m_truth_integrity():
    """Truth coverage across ALL verbs (Jimmy: 'no one can make the system lie or be lied to'). Reuses
    tools/ops/truth_gate.audit(): % of verb integrity checks that pass — every EMIT/PUBLISH/SEND/ADVISE
    verb routes facts through a source/leak/framing guard (can't be made to lie) and every INGEST verb
    carries provenance + the instruction-source boundary (can't be lied to). RATCHET: the floor must not
    fall — no new ungated verb may ship. Honest: None if the gate is unavailable (never green-pad)."""
    try:
        import os as _os, sys as _sys
        tg = _os.path.join(PROJECT, "tools", "ops") if "PROJECT" in globals() else \
             _os.path.join(_os.path.expanduser("~"), "Documents", "Claude", "Projects", "Video System elementLOTUS", "tools", "ops")
        if tg not in _sys.path:
            _sys.path.insert(0, tg)
        import truth_gate; import importlib; importlib.reload(truth_gate)
        r = truth_gate.audit()
        if r.get("score") is None:
            return None, "truth gate produced no checks"
        gaps = (r.get("can_lie", []) or []) + (r.get("can_be_lied_to", []) or [])
        d = "%d/%d verb checks pass" % (r["checks"], r["checks_total"])
        if gaps:
            d += " — open: " + ",".join(gaps[:4])
        return r["score"], d
    except Exception as e:
        return None, "truth_gate unavailable (%s)" % str(e)[:60]

AREAS = [("self_heal", m_self_heal, "invariants passing"),
         ("code_audit", m_code_audit, "code-quality floor (HIGH/MED findings = 0 target)"),
         ("meeting_intel", m_meeting_intel, "civic meeting-intelligence pipeline"),
         ("ops", m_ops, "servers + attention"),
         ("publish", m_publish, "public-floor parity"),
         ("commerce", m_commerce, "charge-chain integrity"),
         ("civic_audit", m_civic_audit, "case matters review-ready"),
         ("jrcsl", m_jrcsl, "JRCSL decide-gate spread (system + hosting)"),
         ("truth_integrity", m_truth_integrity, "no verb can lie or be lied to (truth gate coverage)"),
         ("skills", m_skills, "cumulative learnings (monotonic)")]

def _prev_floor(series, area):
    """The HIGH-WATER score for this area = the floor that must NEVER fall (Jimmy: 'the floor only ever
    rises'). Returning the LAST score let a flagged regression silently become the new floor; max() makes
    a sustained regression keep re-firing until the score recovers above the best ever achieved."""
    scores = [r["score"] for r in series
              if r.get("area") == area and isinstance(r.get("score"), (int, float))]
    return max(scores) if scores else None

def main():
    os.makedirs(STATUS, exist_ok=True)
    series = _load(SERIES, [])
    if not isinstance(series, list): series = []
    cycle = now_hst().strftime("%Y-%m-%d %H:%M HST")
    rows, findings = [], []
    for area, fn, label in AREAS:
        try: score, detail = fn()
        except Exception as e: score, detail = None, "measure errored: %s" % str(e)[:60]
        floor = _prev_floor(series, area)
        trend = None
        if isinstance(score, (int, float)) and isinstance(floor, (int, float)):
            trend = score - floor
            if score < floor:                                   # RATCHET: a regression is a top finding
                findings.append("REGRESSION %s: %s -> %s (floor dropped %d) — %s" % (area, floor, score, floor - score, detail))
        rows.append({"cycle": cycle, "ts": int(time.time()), "area": area, "score": score,
                     "floor_was": floor, "trend": trend, "detail": detail})
    series.extend(rows)
    series = series[-600:]                                       # bound the file
    json.dump(series, open(SERIES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # honest summary: per-area score + trend arrow + the overall floor
    print("progressive self-heal · %s" % cycle)
    nums = []
    for r in rows:
        sc = r["score"]; t = r["trend"]
        arrow = "·" if t is None else ("▲+%d" % t if t > 0 else ("▼%d" % t if t < 0 else "="))
        print("  %-12s %s  %s  %s" % (r["area"], (str(sc) if sc is not None else "—").rjust(4), arrow.ljust(6), r["detail"]))
        if isinstance(sc, (int, float)) and r["area"] != "skills": nums.append(sc)
    floor = min(nums) if nums else None
    print("  ── system floor (min scored area): %s%s" % (floor, "  [REGRESSIONS: %d]" % len(findings) if findings else "  [no regressions — floor held or rose]"))
    for f in findings: print("  ! " + f)
    return 0

if __name__ == "__main__":
    sys.exit(main())
