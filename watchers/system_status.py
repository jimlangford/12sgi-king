#!/usr/bin/env python3
# system_status.py - REAL-TIME system dashboard (Jimmy 2026-06-15: "every request on a dashboard
#   page so I can see what is going on real time with the hardware software"). PRIVATE / owner-only:
#   writes reports/_status/system_status.{json,html} (the _status dir is NOT in the public publish
#   path, so GPU/jobs/internal state never ships to the public site). Self-refreshing HTML.
#
# Shows: GPU (util/mem/temp + who owns it) · CPU% · live LoRA training (step/total + rate + ETA) ·
#   GPU/CPU locks · servers up/down · every SURFACE's self-heal health (surfaces.json) · tenant audits
#   + the money x votes balance · last deck render. Stdlib only. Run on a ~20s loop (system_monitor).
import glob, json, os, struct, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
HOME     = os.path.expanduser("~")
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_DIR  = os.path.join(PROJECT, "reports", "_status")
HST      = timezone(timedelta(hours=-10))
if TOOL_DIR not in sys.path: sys.path.insert(0, TOOL_DIR)

def now_hst(): return datetime.now(HST)
def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _smi(q):
    try:
        return subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=8).stdout.strip()
    except Exception:
        return ""

def gpu():
    v = _smi("utilization.gpu,memory.used,memory.total,temperature.gpu").split(",")
    apps = 0
    try:
        apps = len([x for x in subprocess.run(["nvidia-smi","--query-compute-apps=pid","--format=csv,noheader"],
                    capture_output=True, text=True, timeout=8).stdout.splitlines() if x.strip()])
    except Exception: pass
    try:
        util, used, total, temp = [x.strip() for x in v]
        return {"util": int(float(util)), "mem_used": int(float(used)), "mem_total": int(float(total)),
                "temp": int(float(temp)), "procs": apps,
                "mem_pct": round(100*float(used)/float(total)) if float(total) else 0}
    except Exception:
        return {"util": None, "mem_used": None, "mem_total": None, "procs": apps}

def cpu():
    try:
        from cpu_lock import cpu_percent
        return round(cpu_percent())
    except Exception:
        return None

def _maxstep_and_rate(path):
    data = open(path, "rb").read(); i = 0; ms = 0; t0 = t1 = None
    def vi(b, i):
        r = s = 0
        while True:
            x = b[i]; r |= (x & 0x7f) << s; i += 1
            if not x & 0x80: return r, i
            s += 7
    while i + 12 <= len(data):
        ln = struct.unpack_from("<Q", data, i)[0]; i += 12
        if ln <= 0 or i + ln + 4 > len(data): break
        ev = data[i:i+ln]; i += ln + 4; j = 0; wall = step = None
        while j < len(ev):
            tag = ev[j]; j += 1; fn = tag >> 3; wt = tag & 7
            if fn == 1 and wt == 1: wall = struct.unpack_from("<d", ev, j)[0]; j += 8
            elif fn == 2 and wt == 0: step, j = vi(ev, j)
            elif wt == 0: _, j = vi(ev, j)
            elif wt == 2: l, j = vi(ev, j); j += l
            elif wt == 5: j += 4
            elif wt == 1: j += 8
            else: break
        if step is not None: ms = max(ms, step)
        if wall:
            if t0 is None: t0 = wall
            t1 = wall
    dur_min = (t1 - t0) / 60 if t0 and t1 else 0
    rate = ms / dur_min if dur_min else 0
    return ms, round(rate, 1)

def training():
    logs = glob.glob(os.path.join(PROJECT, "JIMMY_LORA", "logs", "elementlotus_*"))
    if not logs: return {"active": False}
    newest = max(logs, key=os.path.getmtime)
    ev = glob.glob(os.path.join(newest, "**", "events*"), recursive=True)
    if not ev: return {"active": False}
    ef = max(ev, key=os.path.getmtime)
    fresh = (time.time() - os.path.getmtime(ef)) < 180        # written in last 3 min = active
    name = os.path.basename(newest).split("2026")[0].rstrip("_")
    step, rate = _maxstep_and_rate(ef)
    target = 600
    eta = round((target - step) / rate) if (rate and step < target) else 0
    return {"active": fresh, "lora": name, "step": step, "target": target, "rate_per_min": rate,
            "eta_min": eta, "thrashing": bool(fresh and rate and rate < 5)}

_HEALED = []   # stale locks auto-released this refresh (the monitor reloads this module ~15s)


def _pid_alive(pid):
    """True if a process with this PID exists. MUST NOT raise, and MUST fail SAFE (return True
    when uncertain) so we NEVER release a HELD .gpu_lock/.cpu_lock. The old code used
    os.kill(pid, 0) + 'except Exception: alive=False' -- but on Windows os.kill(pid,0) raises
    SystemError for a LIVE process owned by another/privileged user, which was swallowed as
    'dead' and DELETED a held lock (-> GPU/CPU collision). Use a native OpenProcess probe;
    access-denied = the process EXISTS = alive (server-quad-os fix 2026-06-21, self-heal audit)."""
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            ERROR_ACCESS_DENIED = 5
            h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h:
                code = wintypes.DWORD()
                ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
                k32.CloseHandle(h)
                return bool(ok) and code.value == 259   # 259 = STILL_ACTIVE; else exited
            return k32.GetLastError() == ERROR_ACCESS_DENIED   # access-denied => exists => alive
        except Exception:
            return True   # never raise; never wrongly free a held lock
    try:
        os.kill(pid, 0); return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return True


def lock(fn):
    p = os.path.join(PROJECT, fn)
    if not os.path.exists(p): return {"held": False}
    try:
        o = json.load(open(p, encoding="utf-8"))
        alive = _pid_alive(o.get("pid", -1))
        if not alive:
            # SELF-HEAL: a lock held by a DEAD pid is released here and now — not "on next
            # acquire" — so the dashboard fixes itself unattended (Jimmy 2026-06-18: monitor +
            # FIX often). Only dead-pid is auto-cleared; a live-but-old lock is left for review.
            try:
                os.remove(p)
                _HEALED.append(f"{fn} (dead pid {o.get('pid')}, was {o.get('name')})")
                return {"held": False, "healed": True}
            except Exception:
                pass
            return {"held": True, "name": o.get("name"), "pid": o.get("pid"), "alive": False}
        return {"held": True, "name": o.get("name"), "pid": o.get("pid"), "alive": alive}
    except Exception:
        return {"held": False}

def servers():
    out = {}
    for name, url in [("ComfyUI :8000", "http://127.0.0.1:8000/system_stats"),
                      ("Ollama :11434", "http://127.0.0.1:11434/api/tags"),
                      ("king :8799", "http://127.0.0.1:8799/king/"),   # real route (was /api/dispatch -> 404 when UP)
                      ("studio :8770", "http://127.0.0.1:8770/")]:
        try:
            urllib.request.urlopen(url, timeout=3); out[name] = True
        except Exception as e:
            # A server that ANSWERS with a 4xx/5xx (HTTPError has .code) is UP — only conn-refused/timeout = DOWN.
            out[name] = hasattr(e, "code")
    return out

def _fresh_hours(path, hrs):
    p = os.path.join(PROJECT, path)
    if not os.path.exists(p): return None
    return (time.time() - os.path.getmtime(p)) / 3600 <= hrs

def surfaces(gpu_s, train_s, srv):
    try:
        reg = json.load(open(os.path.join(TOOL_DIR, "surfaces.json"), encoding="utf-8"))["surfaces"]
    except Exception:
        return []
    out = []
    for s in reg:
        status = "amber"; note = ""
        c = s.get("check")
        if c == "server":
            up = False
            for k, v in srv.items():
                if "8000" in k and "8000" in s.get("target", ""): up = v
            status = "green" if up else "red"; note = "up" if up else "down"
        elif c == "file_fresh":
            f = _fresh_hours(s.get("target", ""), s.get("fresh_hours", 48))
            status = "green" if f else ("amber" if f is False else "red")
            note = "fresh" if f else ("stale" if f is False else "missing")
        elif c == "train":
            if train_s.get("active"):
                status = "red" if train_s.get("thrashing") else "green"
                note = f"step {train_s.get('step')}/{train_s.get('target')} @ {train_s.get('rate_per_min')}/min"
            else:
                status = "amber"; note = "idle"
        else:
            status = "green"; note = "ok"
        out.append({"id": s["id"], "name": s["name"], "pillar": s.get("pillar"),
                    "status": status, "note": note, "heal": s.get("heal", "")})
    return out

def tenants():
    t = {}
    p = os.path.join(PROJECT, "reports", "mauios", "tenant_timings.json")
    if os.path.exists(p):
        try: t["timings"] = json.load(open(p, encoding="utf-8"))
        except Exception: pass
    b = os.path.join(PROJECT, "reports", "mauios", "audit_balance.json")
    if os.path.exists(b):
        try:
            bb = json.load(open(b, encoding="utf-8"))
            t["balance"] = {"verdict": bb.get("verdict"), "open": bb.get("open_total")}
        except Exception: pass
    return t

def last_render():
    cs = glob.glob(os.path.join(PROJECT, "exports", "sage_cards", "Card_*.png"))
    if not cs: return None
    m = max(cs, key=os.path.getmtime)
    return now_hst().fromtimestamp(os.path.getmtime(m), HST).strftime("%Y-%m-%d %H:%M HST")

def attention(g, tr, gl, cl):
    """Live stall/fault detector across surfaces (selfheal_patterns.json) — so stuck/misconfigured
    states surface RED on their own instead of waiting for a prompt (Jimmy's 2026-06-15 feedback)."""
    a = []
    if tr.get("active") and (tr.get("rate_per_min") or 99) < 5:
        a.append(f"training_thrash: {tr.get('lora')} ~{tr.get('rate_per_min')}/min (GPU busy, no progress) — free the card / restart clean")
    if g.get("mem_total") and (g.get("mem_used", 0) / g["mem_total"]) > 0.92 and (g.get("procs", 0) >= 2):
        a.append(f"gpu_oversubscribed: {g.get('mem_used')}/{g.get('mem_total')} MiB, {g.get('procs')} procs — one heavy GPU job at a time")
    for nm, lk in (("GPU", gl), ("CPU", cl)):
        if lk.get("held") and lk.get("alive") is False:
            a.append(f"stale_lock: {nm} lock held by dead pid {lk.get('pid')} — auto-release on next acquire")
    # expected-output-zero: a known-nonzero KPI reading 0 = likely a path/wiring bug
    try:
        led = json.load(open(os.path.join(PROJECT, "node_map", "maui_island_ledger.json"), encoding="utf-8"))
        if (led.get("island", {}).get("federal_landed") or 0) == 0:
            a.append("expected_output_zero: island ledger federal $ = 0 (likely a read/write path mismatch) — verify federal_money path")
    except Exception: pass
    return a

def _dispatch(event, source="system-monitor"):
    """Append an event to the cross-thread bus so real issues reach the executor inbox —
    i.e. the dashboard doesn't just display, it surfaces. Best-effort, never raises."""
    try:
        rec = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
               "source": source, "event": event}
        with open(os.path.join(PROJECT, ".dispatch_log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _heal_followup(s):
    """Record self-heals + alert ONCE on each new non-healable attention item (de-duped via a
    small state file, so the bus isn't spammed every 15s)."""
    if s.get("self_healed"):
        try:
            with open(os.path.join(OUT_DIR, "heal.log"), "a", encoding="utf-8") as f:
                f.write(f"[{s['generated']}] self-healed: {', '.join(s['self_healed'])}\n")
        except Exception: pass
        _dispatch("SELFHEAL (system-monitor): auto-released stale lock(s): " + "; ".join(s["self_healed"]))
    real = [a for a in s.get("attention", []) if not a.startswith("stale_lock")]
    statef = os.path.join(OUT_DIR, ".monitor_alert_state.json")
    try: seen = json.load(open(statef, encoding="utf-8")) if os.path.exists(statef) else {}
    except Exception: seen = {}
    if isinstance(seen, list): seen = {k: 0 for k in seen}  # migrate old list format
    # CRITICAL = needs a human even with no Claude open -> push to Jimmy's iPhone (notify_phone).
    # Transient/minor items (e.g. gpu_idle_behind_pause) go to the bus + dashboard only, not the phone.
    CRIT = ("down", "false", "training_thrash", "gpu_oversubscribed", "expected_output_zero", "server")
    def _dedup_key(a):
        # Attention strings include live numbers (VRAM MiB, proc count) that fluctuate each 15s cycle.
        # Dedup on the TYPE prefix (before ':') not the full string so a persistent condition doesn't
        # re-dispatch every cycle just because VRAM moved by 1 MiB. (Fix for wb1782062144000.)
        return a.split(":")[0].strip() if ":" in a else a
    for a in real:
        k = _dedup_key(a)
        _last = seen.get(k, seen.get(a, 0))  # check type-key first, fall back to full string (migration)
        if time.time() - _last > 300:  # 5-min dedup: same alert type silent until it clears or 5 min passes
            _dispatch("ATTENTION (system-monitor): " + a)
            if any(c in a.lower() for c in CRIT):
                try:
                    import sys as _s
                    _ops = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools", "ops")
                    if _ops not in _s.path: _s.path.insert(0, _ops)
                    import notify_phone
                    notify_phone.notify("elementLOTUS needs you", "Autonomous monitor flagged: " + a[:160],
                                        "https://king.tail760750.ts.net/status/system_status.html")
                except Exception: pass
            seen[k] = time.time()  # stamp the type-key immediately so next cycle within 5 min is silent
    # write state keyed by type-prefix so fluctuating numbers don't defeat the dedup
    try:
        new_state = {_dedup_key(a): seen.get(_dedup_key(a), time.time()) for a in real}
        json.dump(new_state, open(statef, "w", encoding="utf-8"))
    except Exception: pass

def collect():
    global _HEALED; _HEALED = []
    # GPU-FLAG ACCURACY (Jimmy: "make those flags very accurate... don't lose GPU time ever again"):
    # every 15s, reconcile the render-pause flag against nvidia-smi ground truth and auto-clear it the
    # instant it is stale (card free + no live condition), so the GPU is never idle behind a dead flag.
    rp = None
    try:
        import sys as _sys
        _ops = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools", "ops")
        if _ops not in _sys.path: _sys.path.insert(0, _ops)
        import gpu_guard; rp = gpu_guard.reconcile(apply=True)
    except Exception:
        rp = None
    g = gpu(); tr = training(); srv = servers()
    gl = lock(".gpu_lock"); cl = lock(".cpu_lock")
    s = {
        "generated": now_hst().strftime("%Y-%m-%d %H:%M:%S HST"),
        "gpu": g, "cpu_pct": cpu(), "training": tr,
        "gpu_lock": gl, "cpu_lock": cl,
        "servers": srv, "surfaces": surfaces(g, tr, srv),
        "tenants": tenants(), "last_render": last_render(),
        "attention": attention(g, tr, gl, cl),
        "render_pause": rp,
        "self_healed": list(_HEALED),
    }
    # surface "GPU idle behind a (still-valid) pause" as waste so it is never silent
    if rp and rp.get("idle_behind_pause"):
        s["attention"].append("gpu_idle_behind_pause: card free but render-pause held (%s) - resume if done" % rp.get("valid_because", ""))
    _heal_followup(s)
    return s

DOT = {"green": "#1f9d55", "amber": "#d9822b", "red": "#d64545"}

def html(s):
    g = s["gpu"]; tr = s["training"]
    def bar(pct, col):
        pct = pct or 0
        return f'<div class=bar><div style="width:{pct}%;background:{col}"></div></div>'
    gpu_col = "#d64545" if (g.get("util") or 0) > 90 and tr.get("thrashing") else "#1f9d55"
    train_line = ("idle" if not tr.get("active") else
        (f"<b>{tr.get('lora')}</b> &middot; step {tr.get('step')}/{tr.get('target')} &middot; "
         f"{tr.get('rate_per_min')}/min &middot; ETA ~{tr.get('eta_min')} min"
         + (" &middot; <span style='color:#d64545'>THRASHING</span>" if tr.get("thrashing") else "")))
    srv = " &nbsp; ".join(f"<span class=dot style='background:{DOT['green'] if v else DOT['red']}'></span>{k}"
                          for k, v in s["servers"].items())
    surf = "".join(
        f"<tr><td><span class=dot style='background:{DOT.get(x['status'],'#999')}'></span>{x['name']}</td>"
        f"<td class=muted>{x.get('pillar','')}</td><td>{x['note']}</td><td class=muted>{x['heal']}</td></tr>"
        for x in s["surfaces"])
    bal = (s.get("tenants", {}).get("balance") or {})
    tim = (s.get("tenants", {}).get("timings") or {})
    trow = "".join(f"<tr><td>{v.get('name')}</td><td>{v.get('total_min')} min</td><td class=muted>{v.get('last_run')}</td></tr>"
                   for v in tim.values()) or "<tr><td colspan=3 class=muted>no audits run yet</td></tr>"
    gl = s["gpu_lock"]; cl = s["cpu_lock"]
    locks = (f"GPU lock: {'held by '+str(gl.get('name')) if gl.get('held') else 'free'} &nbsp;|&nbsp; "
             f"CPU lock: {'held by '+str(cl.get('name')) if cl.get('held') else 'free'}")
    # Owner Action Queue banner: surface "things only Jimmy can do" right at the top, with a tap link.
    try:
        _oaq = json.load(open(os.path.join(OUT_DIR, "owner_actions.json"), encoding="utf-8"))
        _oc = int(_oaq.get("open_count", 0))
    except Exception:
        _oc = 0
    if _oc:
        oaq_banner = (f'<a href="/owner_actions.html" style="display:block;background:#3a2a00;'
                      f'border:1px solid #d98c00;border-radius:12px;padding:.7rem 1.1rem;margin:.7rem 0;'
                      f'color:#ffe2a8;text-decoration:none;font-size:.92rem">'
                      f'&#128081; <b>{_oc} thing{"" if _oc==1 else "s"} need you</b> &middot; '
                      f'Owner Action Queue &mdash; tap to see what only you can do &rarr;</a>')
    else:
        oaq_banner = ('<a href="/owner_actions.html" style="display:block;color:#9be7b6;'
                      'text-decoration:none;font-size:.82rem;margin:.5rem 0">'
                      '&#128081; Owner Action Queue: all clear &rarr;</a>')
    return f"""<!doctype html><html><head><meta charset=utf-8>
<meta http-equiv=refresh content=12>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>elementLOTUS — System Status</title><style>
body{{font-family:system-ui,Segoe UI,sans-serif;max-width:980px;margin:1.4rem auto;padding:0 1rem;background:#0d1117;color:#e6edf3}}
h1{{font-size:1.4rem;margin:.2rem 0}} .sub{{color:#8b949e;font-size:.85rem}}
.card{{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:.9rem 1.1rem;margin:.7rem 0}}
.k{{color:#8b949e;font-size:.78rem;text-transform:uppercase;letter-spacing:.08em}}
.big{{font-size:1.5rem;font-weight:600}} .row{{display:flex;gap:2rem;flex-wrap:wrap;align-items:center}}
.bar{{height:8px;background:#21262d;border-radius:6px;overflow:hidden;width:160px;margin-top:.3rem}} .bar>div{{height:100%}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:.4rem;vertical-align:middle}}
table{{width:100%;border-collapse:collapse;font-size:.86rem}} td{{padding:.35rem .5rem;border-bottom:1px solid #21262d;vertical-align:top}}
.muted{{color:#8b949e;font-size:.8rem}}
.attn{{background:#3d0d0d;border:1px solid #d64545;border-radius:12px;padding:.7rem 1.1rem;margin:.7rem 0;color:#ffd7d7}}
.attn b{{color:#ff8a8a}} .ok{{background:#0d2818;border:1px solid #1f9d55;border-radius:12px;padding:.5rem 1.1rem;margin:.7rem 0;color:#9be7b6;font-size:.85rem}}</style></head><body>
<h1>elementLOTUS — System Status <span class=sub>self-heal across all surfaces</span></h1>
<div class=sub>Live (auto-refresh 12s). Generated {s['generated']}. Private / owner-only.</div>
{oaq_banner}
{('<div class=attn><b>&#9888; needs attention</b><ul style=margin:.3rem_0>' + ''.join('<li>'+esc(x)+'</li>' for x in s.get('attention',[])) + '</ul></div>') if s.get('attention') else '<div class=ok>&#10003; all surfaces nominal — no stalls or faults detected</div>'}
<div class=card><div class=row>
 <div><div class=k>GPU</div><div class=big>{g.get('util','?')}%</div>{bar(g.get('util'),gpu_col)}
   <div class=muted>{g.get('mem_used','?')}/{g.get('mem_total','?')} MiB &middot; {g.get('temp','?')}&deg;C &middot; {g.get('procs','?')} procs</div></div>
 <div><div class=k>CPU</div><div class=big>{s.get('cpu_pct','?')}%</div>{bar(s.get('cpu_pct'),'#388bfd')}</div>
 <div style=flex:1><div class=k>LoRA training</div><div>{train_line}</div><div class=muted style=margin-top:.3rem>{locks}</div></div>
</div></div>
<div class=card><div class=k>Servers</div><div style=margin-top:.4rem>{srv}</div></div>
<div class=card><div class=k>Surfaces — self-heal health</div>
 <table><tbody>{surf}</tbody></table></div>
<div class=card><div class=k>Civic tenants — money &times; votes</div>
 <div style=margin:.3rem 0>{bal.get('verdict','(no balance yet)')}</div>
 <table><thead><tr><td class=muted>tenant</td><td class=muted>last update</td><td class=muted>when</td></tr></thead><tbody>{trow}</tbody></table></div>
<div class=card><div class=k>Last deck render</div><div>{s.get('last_render') or '(none yet)'}</div></div>
<div style="text-align:center;color:#8b949e;font-size:.75rem;padding:18px 0;border-top:1px solid #21262d;margin-top:14px">&copy; 2026 James RCS Langford &middot; 12 Stones Global &middot; all rights reserved</div>
<script src="https://king.tail760750.ts.net/king/quados.js" defer></script>
</body></html>"""

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    s = collect()
    with open(os.path.join(OUT_DIR, "system_status.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT_DIR, "system_status.html"), "w", encoding="utf-8") as f:
        f.write(html(s))
    t = s["training"]
    print(f"status: GPU {s['gpu'].get('util')}% / CPU {s.get('cpu_pct')}% | "
          f"train {'idle' if not t.get('active') else t.get('lora')+' step '+str(t.get('step'))+'/'+str(t.get('target'))+' @'+str(t.get('rate_per_min'))+'/min'} "
          f"-> {os.path.join(OUT_DIR,'system_status.html')}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
