#!/usr/bin/env python3
# system_monitor.py - always-on REAL-TIME dashboard service (Jimmy's go page link).
#   One windowless process: a background thread regenerates the dashboard every 15s,
#   and an HTTP server on :8781 serves reports/_status/ (the private system dashboard).
#   Reachable on the laptop (127.0.0.1:8781) AND over Tailscale
#   (http://king.tail760750.ts.net:8781/system_status.html) = the go-page card.
#   Launched windowless via run_hidden.vbs + a logon scheduled task (no-popup policy).
import os, sys, time, threading, importlib, http.server, socketserver

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
HOME     = os.path.expanduser("~")
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
STATUS_DIR = os.path.join(PROJECT, "reports", "_status")
PORT = 8781
if TOOL_DIR not in sys.path: sys.path.insert(0, TOOL_DIR)
os.makedirs(STATUS_DIR, exist_ok=True)

def refresh_loop():
    import system_status
    # GPU-share balance guard (audit-quad-os 2026-06-21, Jimmy "local reasoning + render GPU share must be
    # perfectly balanced"). tools/ops is a sibling of this (kilo-aupuni) dir. Flag-only here; --yield is manual.
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(TOOL_DIR), "ops"))
        import gpu_balance_guard as _gbg
    except Exception:
        _gbg = None
    try:
        import gpu_stale_evict as _gse   # server-quad-os: auto-evict stale ollama strays squatting the card during a render
    except Exception:
        _gse = None
    _tick, _blocked_flagged = 0, False
    while True:
        try:
            importlib.reload(system_status)
            system_status.main()
        except Exception:
            pass
        _tick += 1
        if _gbg and _tick % 20 == 0:   # ~every 5 min
            try:
                a = _gbg.assess()
                if a.get("render_blocked_by_brain") and not _blocked_flagged:
                    _gbg.dispatch("FINDING (balance-guard / 15s monitor): RENDER BLOCKED BY BRAIN VRAM — "
                                  "board %d MiB > conductor gate %d, brain resident, conductor backing off, not "
                                  "rendering. The brain must yield. `python tools/ops/gpu_balance_guard.py --yield` "
                                  "frees the card; durable fix = brain yields during renders." % (a["used_mib"], a["gate_mib"]))
                    # PLAIN-ENGLISH owner action with a link to the INTERACTIVE /fix page (Jimmy 2026-07-01:
                    # "the link opened to nothing I can fix"). Now: tap -> /fix -> "Free the card now" button.
                    try:
                        import subprocess as _sp
                        _sp.run([sys.executable, os.path.join(os.path.dirname(TOOL_DIR), "ops", "owner_actions.py"),
                                 "--add", "Render card is full :: Your local AI brain is holding the graphics card, so video renders cannot run (and it can warm up). Tap to free the card.",
                                 "--link", "http://king.tail760750.ts.net:8781/fix",
                                 "--lane", "server-quad-os", "--priority", "1"], capture_output=True, timeout=30)
                    except Exception:
                        pass
                    _blocked_flagged = True
                elif not a.get("render_blocked_by_brain"):
                    _blocked_flagged = False   # reset so a NEW episode re-flags (de-dup, no spam)
            except Exception:
                pass
        if _gse and _tick % 4 == 0:   # ~every 60s: ACT (not just flag) - keep stale ollama models off the card during a render
            try:
                _er = _gse.evict()
                if _er.get("evicted") and _gbg:
                    _gbg.dispatch("SHIPPED (gpu_stale_evict / monitor): freed the card for a render - ollama-stopped "
                                  "stale model(s): %s (card %d MiB). king-reason kept." % (", ".join(_er["evicted"]), _er.get("used_mib", 0)))
            except Exception:
                pass
        time.sleep(15)


# ---- ONE MASTER CONSOLE (Jimmy 2026-07-01: "one master layout, Yale blue dark, no popups, perfect links on
# each level"). Every level renders through _shell: Home overview -> the thing -> the fix, all same layout, all
# same nav, every link resolves. No modals, no new tabs. ----
_TOK = ("--bg:#071626;--panel:#0e2439;--panel2:#14304d;--line:#22415f;--blue:#00356b;--link:#5ea0e6;"
        "--accent:#2f6fd0;--ink:#e9f1fa;--muted:#93aecb;--ok:#46c98a")

def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _shell(title, inner):
    css = (":root{" + _TOK + "}"
           "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);"
           "font-family:-apple-system,Segoe UI,system-ui,sans-serif;-webkit-text-size-adjust:100%}"
           "a{color:var(--link);text-decoration:none}a:active{opacity:.55}"
           "header{background:var(--blue);padding:14px 18px}"
           "header .b{font-weight:700;font-size:17px;color:#fff}header .b small{font-weight:400;color:#bcd3ee;font-size:12px}"
           "nav{display:flex;gap:8px;padding:10px 14px;background:var(--panel);border-bottom:1px solid var(--line);flex-wrap:wrap}"
           "nav a{padding:7px 13px;border-radius:9px;font-size:14px;background:var(--panel2)}"
           "main{max-width:760px;margin:0 auto;padding:18px 16px 60px}"
           "h2{font-size:21px;margin:4px 0 12px}"
           "h3{color:var(--link);font-size:15px;margin:24px 0 8px;border-bottom:1px solid var(--line);padding-bottom:6px}"
           ".card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px 16px;margin:0 0 12px}"
           ".row{display:block;background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--accent);"
           "border-radius:12px;padding:13px 15px;margin:9px 0}.row:active{opacity:.55}"
           ".row .t{font-size:15px;color:var(--ink);font-weight:600}.row .m{font-size:12px;color:var(--muted);margin-top:3px}"
           ".btn{display:inline-block;background:var(--accent);color:#fff;font-weight:700;font-size:17px;"
           "padding:13px 22px;border:0;border-radius:12px;text-decoration:none;margin-top:10px;cursor:pointer}"
           "p{font-size:15px;line-height:1.6}.muted{color:var(--muted)}"
           "textarea{width:100%;min-height:74px;background:var(--panel2);color:var(--ink);border:1px solid var(--line);"
           "border-radius:11px;padding:11px;font:15px inherit}"
           ".ev{border-left:3px solid var(--line);padding:6px 11px;margin:7px 0;font-size:13px;line-height:1.45}"
           ".ev .w{color:var(--muted);font-family:ui-monospace,monospace}"
           "footer{color:#5b7595;font-size:12px;text-align:center;padding:22px}")
    nav = "<nav><a href='/'>Home</a><a href='/fix'>Render card</a></nav>"
    return ("<!doctype html><html><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            "<meta name=theme-color content='#00356b'><title>" + _esc(title) + " - elementLOTUS</title>"
            "<style>" + css + "</style></head><body>"
            "<header><div class='b'>elementLOTUS <small>console - " + _esc(title) + "</small></div></header>"
            + nav + "<main>" + inner + "</main>"
            "<footer>Private - your devices only - Ua mau ke ea o ka aina i ka pono</footer></body></html>")

def _gpu():
    try:
        import subprocess
        out = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8).stdout.strip()
        return [x.strip() for x in out.split(",")]
    except Exception:
        return None

def _pulse():
    g = _gpu()
    if not g or len(g) < 4:
        return "<div class='card'><b>Render card</b><div class='muted'>status unavailable right now</div></div>"
    t, u, mu, mt = g
    warm = " (warm)" if (t.isdigit() and int(t) >= 75) else " (cool)"
    return ("<div class='card'><b>Render card</b><p style='margin:6px 0 0'>" + _esc(t) + " degrees" + warm
            + " &middot; " + _esc(u) + "% busy &middot; " + _esc(mu) + " of " + _esc(mt) + " MB used.</p></div>")

_FEED_TOPICS = ("gpu", "render", "card", "brain", "comfy", "thermal", "vram", "yield", "conductor", "free the card", "ollama")

def _feed(n=8):
    import os, json
    rows = []
    try:
        with open(os.path.join(PROJECT, ".dispatch_log.jsonl"), "rb") as f:
            f.seek(0, 2); sz = f.tell(); f.seek(max(0, sz - 300000)); data = f.read().decode("utf-8", "replace")
        for ln in reversed(data.split(chr(10))):
            if not ln.strip():
                continue
            try:
                e = json.loads(ln)
            except Exception:
                continue
            txt = e.get("event") or e.get("instruction") or ""
            if any(k in txt.lower() for k in _FEED_TOPICS):
                rows.append((e.get("iso", "")[11:16], e.get("source", "?"), txt[:150]))
            if len(rows) >= n:
                break
    except Exception:
        pass
    if not rows:
        return "<p class='muted'>No recent related activity.</p>"
    return "".join("<div class='ev'><span class='w'>" + _esc(t) + " &middot; " + _esc(s) + "</span><br>" + _esc(x) + "</div>"
                   for t, s, x in rows)

_SURFACES = (
    # label,           port, tailnet-root-relative path (works from any /* proxy since Tailscale serve
    # maps the whole king.tail760750.ts.net domain, not just /status)
    ("Work Board",  8782, "/board"),
    ("King / NAGA", 8799, "/king"),
    ("Studio",      8770, "/studio"),
    ("ComfyUI",     8000, "/comfy"),
    ("JRCSL",       8788, "/jrcsl"),
    ("Prosecutor",  8799, "/prosecutor"),
)

def _ping(port, timeout=0.6):
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except Exception:
        return False

def _open_job_count():
    import os, json
    try:
        d = json.load(open(os.path.join(PROJECT, "config", "workboard_items.json"), encoding="utf-8"))
        items = d.get("items", d) if isinstance(d, dict) else d
        items = items if isinstance(items, list) else []
        return sum(1 for i in items if isinstance(i, dict) and i.get("status") not in ("done", "archived"))
    except Exception:
        return None

def _surfaces():
    out = []
    for name, port, path in _SURFACES:
        up = _ping(port)
        dot = "#3a8a52" if up else "#c04040"
        label = "up" if up else "down"
        extra = ""
        if name == "Work Board":
            n = _open_job_count()
            if n is not None:
                extra = " &middot; " + str(n) + " open"
        elif name == "ComfyUI" and up:
            running, pending = _comfy_queue()
            _, total_assets = _comfy_assets(1)
            if running is not None:
                extra = " &middot; " + str(running) + " running, " + str(pending) + " queued &middot; " + str(total_assets) + " assets"
            path = "/comfy-queue"   # glanceable assets+queue view instead of the raw node editor
        out.append(
            "<a class='row' href='" + _esc(path) + "'>"
            "<div class='t'><span style='display:inline-block;width:9px;height:9px;border-radius:50%;"
            "background:" + dot + ";margin-right:8px;vertical-align:1px'></span>" + _esc(name) + "</div>"
            "<div class='m'>:" + str(port) + " &middot; " + label + extra + "</div></a>"
        )
    return "".join(out)

COMFY_PORT = 8000
COMFY_OUTPUT = os.path.join(HOME, "Documents", "COMFYUI", "output")
_COMFY_ASSET_EXT = (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".glb", ".wav")

def _comfy_queue():
    """Live running/pending counts straight from ComfyUI's own REST API (127.0.0.1 only, short timeout)."""
    import urllib.request, json
    try:
        with urllib.request.urlopen("http://127.0.0.1:" + str(COMFY_PORT) + "/queue", timeout=1.5) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return len(d.get("queue_running", [])), len(d.get("queue_pending", []))
    except Exception:
        return None, None

def _comfy_assets(n=12):
    """Most recent real render assets anywhere under ComfyUI's output/ (per-project subfolders),
    skipping the .archived.json bookkeeping files ComfyUI leaves behind."""
    import os
    rows = []
    try:
        for root, _dirs, files in os.walk(COMFY_OUTPUT):
            for fn in files:
                if not fn.lower().endswith(_COMFY_ASSET_EXT):
                    continue
                fp = os.path.join(root, fn)
                try:
                    st = os.stat(fp)
                except Exception:
                    continue
                rel = os.path.relpath(fp, COMFY_OUTPUT)
                rows.append((st.st_mtime, rel, st.st_size))
        rows.sort(reverse=True)
    except Exception:
        pass
    return rows[:n], len(rows)

def _comfy_page():
    running, pending = _comfy_queue()
    if running is None:
        q_html = "<div class='card'><b>Queue</b><div class='muted'>ComfyUI not reachable right now.</div></div>"
    else:
        q_html = ("<div class='card'><b>Queue</b><p style='margin:6px 0 0'>" + str(running) + " rendering now &middot; "
                  + str(pending) + " waiting</p></div>")
    recent, total = _comfy_assets(12)
    if not recent:
        a_html = "<p class='muted'>No renders found in output/ yet.</p>"
    else:
        a_html = "".join(
            "<div class='row'><div class='t'>" + _esc(fn) + "</div><div class='m'>"
            + time.strftime("%b %d, %H:%M", time.localtime(mt)) + " &middot; " + str(round(sz / 1024)) + " KB</div></div>"
            for mt, fn, sz in recent
        )
    inner = ("<h2>ComfyUI &mdash; assets &amp; queue</h2>" + q_html
             + "<h3>Recent renders (" + str(total) + " total in output/)</h3>" + a_html
             + "<p class='muted' style='margin-top:16px'><a href='/comfy'>Open the full ComfyUI node editor &rarr;</a></p>")
    return _shell("ComfyUI", inner)

def _actions():
    # owner-action queue, each a PERFECT link (card -> /fix; dead /status/owner_actions.html -> /owner_actions.html)
    import os, json
    try:
        d = json.load(open(os.path.join(PROJECT, "reports", "_status", "owner_actions.json"), encoding="utf-8"))
        items = d.get("items", d) if isinstance(d, dict) else d
        items = items if isinstance(items, list) else []
    except Exception:
        items = []
    if not items:
        return "<p class='muted'>Nothing needs you right now.</p>"
    out = []
    for it in items[:20]:
        title = it.get("title") or it.get("text") or "(untitled)"
        link = (it.get("link") or "").strip()
        low = (title + " " + link).lower()
        aid = it.get("id") or ""
        if "render card" in low or "free the card" in low or link == "/fix":
            href = "/fix"
        elif aid:
            href = "/fix/" + aid           # every action -> its OWN fix page
        elif link.startswith("http"):
            href = link
        else:
            href = "/owner_actions.html"
        out.append("<a class='row' href='" + _esc(href) + "'><div class='t'>" + _esc(title.split("::")[0][:80])
                   + "</div><div class='m'>open &rarr; " + _esc(href[:56]) + "</div></a>")
    return "".join(out)

def _file_direction(text):
    import os, json, time
    text = (text or "").strip()[:1000]
    if not text:
        return ""
    rec = {"ts": int(time.time()), "iso": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": "command",
           "source": "owner-fix", "target": "server-quad-os", "target_thread": "server-quad-os",
           "instruction": text, "priority": "high"}
    try:
        with open(os.path.join(PROJECT, ".dispatch_log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + chr(10))
    except Exception:
        pass
    return text

def _index():
    inner = ("<h2>What needs you</h2>" + _pulse()
             + "<h3>Surfaces</h3>" + _surfaces()
             + "<h3>Needs your attention</h3>" + _actions()
             + "<h3>Live activity</h3>" + _feed(6))
    return _shell("Home", inner)

def _fix_page():
    inner = ("<h2>Render card</h2>" + _pulse()
             + "<p class='muted'>Your local AI brain and the video renderer share ONE graphics card. When the brain "
             "holds it, renders cannot run and it can warm up. The button tells the brain to let go (it keeps working, "
             "just unloads the big model) so renders run and the card cools. Safe and reversible.</p>"
             "<a class='btn' href='/fix/free-card'>Free the card now</a>"
             "<h3>Live activity &mdash; related to this</h3>" + _feed()
             + "<h3>Offer a direction</h3>"
             "<p class='muted'>Type what you want done. It goes straight to the system and the lanes act on it.</p>"
             "<form method='post' action='/fix/direct'>"
             "<textarea name='text' placeholder='e.g. keep renders on the cloud today, or free the card every night after 10pm'></textarea>"
             "<br><button class='btn' type='submit'>Send direction</button></form>")
    return _shell("Render card", inner)

def _free_card_result():
    import subprocess, os
    line = "Card freed."
    try:
        r = subprocess.run([sys.executable, os.path.join(PROJECT, "tools", "ops", "gpu_balance_guard.py"), "--yield"],
                           capture_output=True, text=True, timeout=70)
        outl = (r.stdout or r.stderr or "").strip().splitlines()
        if outl:
            line = outl[-1][:240]
    except Exception as e:
        line = "Tried to free the card: " + str(e)[:140]
    inner = ("<h2 style='color:var(--ok)'>Done</h2><div class='card'>" + _esc(line) + "</div>"
             "<p class='muted'>If the brain is protected during Maui business hours, that is on purpose &mdash; it keeps "
             "the civic brain answering; it frees after hours. Otherwise the card is free for renders and will cool.</p>"
             "<a class='row' href='/fix'><div class='t'>&larr; Back to the render card</div></a>")
    return _shell("Card freed", inner)

def _direction_result(text):
    sent = _file_direction(text)
    body = ("Your direction is on the bus: <b>" + _esc(sent) + "</b> &mdash; the lanes will act on it.") if sent else "Nothing was typed."
    inner = ("<h2 style='color:var(--ok)'>Sent</h2><div class='card'>" + body + "</div>"
             "<a class='row' href='/fix'><div class='t'>&larr; Back to the console</div></a>")
    return _shell("Sent", inner)


def _load_fixes():
    import os, json
    try:
        return json.load(open(os.path.join(PROJECT, "config", "owner_action_fixes.json"), encoding="utf-8"))
    except Exception:
        return {}

def _load_actions():
    import os, json
    for rel in (("reports", "_status", "owner_actions.json"), ("config", "owner_actions.json")):
        try:
            d = json.load(open(os.path.join(PROJECT, *rel), encoding="utf-8"))
            items = d.get("items", d) if isinstance(d, dict) else d
            if isinstance(items, list):
                return items
        except Exception:
            pass
    return []

def _action_by_id(aid):
    for it in _load_actions():
        if it.get("id") == aid:
            return it
    return {}

def _run_probe(chk):
    # read-only PROBES check (wp_token / gh_token) from owner_actions.py. Safe: exec_module runs only defs.
    if not chk:
        return None
    try:
        import importlib.util, os
        p = os.path.join(PROJECT, "tools", "ops", "owner_actions.py")
        spec = importlib.util.spec_from_file_location("oa_probe", p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        fn = getattr(m, "PROBES", {}).get(chk)
        return bool(fn()) if fn else None
    except Exception:
        return None

def _resolve_action(aid):
    try:
        import subprocess, os
        subprocess.run([sys.executable, os.path.join(PROJECT, "tools", "ops", "owner_actions.py"), "--resolve", aid],
                       capture_output=True, text=True, timeout=45)
    except Exception:
        pass

def _file_to_lane(lane, instruction, source="owner-fix"):
    import os, json, time
    rec = {"ts": int(time.time()), "iso": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": "command",
           "source": source, "target": lane or "server-quad-os", "target_thread": lane or "server-quad-os",
           "instruction": (instruction or "")[:1000], "priority": "high"}
    try:
        with open(os.path.join(PROJECT, ".dispatch_log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + chr(10))
    except Exception:
        pass

def _result_page(head, body_html, aid, ok=True):
    col = "var(--ok)" if ok else "var(--link)"
    inner = ("<h2 style='color:" + col + "'>" + _esc(head) + "</h2><div class='card'>" + body_html + "</div>"
             "<a class='row' href='/fix/" + _esc(aid) + "'><div class='t'>&larr; Back to this fix</div></a>"
             "<a class='row' href='/'><div class='t'>&larr; Back to what needs you</div></a>")
    return _shell(head, inner)

def _fix_app(aid):
    fixes = _load_fixes()
    rec = fixes.get(aid) or {}
    act = _action_by_id(aid)
    title = rec.get("app_title") or (act.get("title") or "Fix").split("::")[0][:70]
    P_ = ["<h2>" + _esc(title) + "</h2>"]
    if rec:
        P_.append("<div class='card'><b>What this is</b><p style='margin:6px 0 0'>" + _esc(rec.get("what", "")) + "</p></div>")
        if rec.get("why"):
            P_.append("<div class='card'><b>Why it matters</b><p style='margin:6px 0 0'>" + _esc(rec["why"]) + "</p></div>")
        if rec.get("owner_only"):
            P_.append("<p class='muted'>Only you can finish this one &mdash; it needs your own sign-in or a secret. "
                      "Every step and link is here, plus a Verify button; but you paste the secret in your own tools, "
                      "never on this page.</p>")
        steps = rec.get("steps") or []
        if steps:
            P_.append("<h3>Steps</h3><ol style='padding-left:20px;line-height:1.75;font-size:15px'>"
                      + "".join("<li>" + _esc(s) + "</li>" for s in steps) + "</ol>")
        cps = rec.get("config_paths") or []
        if cps:
            P_.append("<h3>Paste it into</h3>"
                      + "".join("<div class='card' style='font-family:ui-monospace,monospace;font-size:13px;word-break:break-all'>"
                                + _esc(p) + "</div>" for p in cps))
        btns = rec.get("buttons") or []
        if btns:
            P_.append("<h3>Do it</h3>")
            for i, bn in enumerate(btns):
                a = (bn.get("action") or "").lower()
                label = _esc(bn.get("label") or a or "do")
                arg = bn.get("arg") or ""
                if a == "open" and arg.startswith("http"):
                    P_.append("<a class='btn' href='" + _esc(arg) + "'>" + label + " &rarr;</a> ")
                elif a == "direction":
                    P_.append("<form method='post' action='/fix/" + _esc(aid) + "/direct'>"
                              "<textarea name='text' placeholder='" + _esc(arg or "type what you want done") + "'></textarea>"
                              "<br><button class='btn' type='submit'>" + label + "</button></form>")
                elif a in ("verify", "route", "done"):
                    P_.append("<a class='btn' href='/fix/" + _esc(aid) + "/act?b=" + str(i) + "'>" + label + "</a> ")
        links = [l for l in (rec.get("links") or []) if str(l.get("url", "")).startswith("http")]
        if links:
            P_.append("<h3>Links you need</h3>"
                      + "".join("<a class='row' href='" + _esc(l["url"]) + "'><div class='t'>" + _esc(l.get("label", "link"))
                                + "</div><div class='m'>" + _esc(l["url"][:60]) + "</div></a>" for l in links))
        sk = rec.get("skills") or []
        if sk:
            P_.append("<h3>Behind the scenes</h3><p class='muted'>The system can help with: " + _esc(", ".join(sk)) + "</p>")
    else:
        detail = (act.get("detail") or act.get("title") or "No extra detail on file yet.")[:700]
        P_.append("<div class='card'>" + _esc(detail) + "</div>")
        lane = act.get("lane") or "server-quad-os"
        P_.append("<h3>Do it</h3>"
                  "<a class='btn' href='/fix/" + _esc(aid) + "/act?b=route'>Have " + _esc(lane) + " handle it</a> "
                  "<a class='btn' href='/fix/" + _esc(aid) + "/act?b=done'>Mark done</a>")
        lk = act.get("link") or ""
        if lk.startswith("http") and "/status/owner_actions" not in lk:
            P_.append("<a class='row' href='" + _esc(lk) + "'><div class='t'>Open the link &rarr;</div><div class='m'>"
                      + _esc(lk[:60]) + "</div></a>")
    P_.append("<h3>Live activity</h3>" + _feed(5))
    P_.append("<a class='row' href='/'><div class='t'>&larr; Back to what needs you</div></a>")
    return _shell(title, "".join(P_))

def _fix_act(aid, bsel):
    rec = _load_fixes().get(aid) or {}
    act = _action_by_id(aid)
    lane = act.get("lane") or "server-quad-os"
    if bsel in ("route", "done", "verify"):
        btn = {"action": bsel, "arg": aid}
    else:
        try:
            btn = (rec.get("buttons") or [])[int(bsel)]
        except Exception:
            btn = {}
    a = (btn.get("action") or "").lower()
    arg = btn.get("arg") or ""
    if a == "verify":
        chk = rec.get("verify_check") or act.get("check")
        res = _run_probe(chk)
        if res is True:
            return _result_page("Verified", "It's working &mdash; the value is detected. You can mark this done.", aid, ok=True)
        if res is False:
            return _result_page("Not yet", "The value isn't detected yet. Re-check the step (right file, saved) and try Verify again.", aid, ok=False)
        return _result_page("Nothing to auto-check", "This one has no automatic test &mdash; if you've done the steps, mark it done.", aid, ok=False)
    if a == "done":
        _resolve_action(aid)
        return _result_page("Marked done", "Cleared from your queue. If it reappears, it wasn't fully resolved yet.", aid, ok=True)
    if a == "route":
        instr = arg if (arg and arg != aid) else ("OWNER-ROUTED: do the software part of '"
                + (act.get("title") or aid)[:120] + "' :: " + (rec.get("what") or act.get("detail") or "")[:300])
        _file_to_lane(lane, instr)
        return _result_page("Sent to the lane", "Routed to <b>" + _esc(lane) + "</b> to do the software part. Watch the feed &mdash; you'll see it act.", aid, ok=True)
    return _result_page("Nothing to do", "That button had no safe action attached.", aid, ok=False)

def _direction_result_for(aid, text):
    act = _action_by_id(aid)
    lane = act.get("lane") or "server-quad-os"
    text = (text or "").strip()[:1000]
    if text:
        _file_to_lane(lane, "OWNER DIRECTION on '" + (act.get("title") or aid)[:100] + "': " + text)
    body = ("Your direction went to <b>" + _esc(lane) + "</b>: <b>" + _esc(text) + "</b>") if text else "Nothing was typed."
    return _result_page("Sent", body, aid, ok=bool(text))


_OWNER_IPS_CACHE = {"ips": set(), "ts": 0.0}
_OWNER_SYNC_CACHE = {"ts": 0.0}

def _owner_devices_ips():
    import os, json, time
    now = time.time()
    if _OWNER_IPS_CACHE["ips"] and now - _OWNER_IPS_CACHE["ts"] < 30:
        return _OWNER_IPS_CACHE["ips"]
    try:
        d = json.load(open(os.path.join(PROJECT, "config", "owner_devices.json"), encoding="utf-8"))
        ips = set(d.get("ips") or [])
    except Exception:
        ips = set()
    ips |= {"127.0.0.1", "::1"}
    _OWNER_IPS_CACHE["ips"] = ips; _OWNER_IPS_CACHE["ts"] = now
    return ips

def _owner_ok(handler):
    """True if the request comes from one of Jimmy's devices. :8781 is 0.0.0.0-bound with no proxy, so the
    real socket peer IS the device tailnet IP (unspoofable). XFF is trusted ONLY from a loopback peer."""
    import os, time, subprocess
    peer = handler.client_address[0]
    xff = (handler.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    cand = xff if (peer in ("127.0.0.1", "::1") and xff) else peer
    ips = _owner_devices_ips()
    if cand in ips or peer in ips:
        return True
    # MISS: lazily self-heal the allowlist from live tailscale (his device IP may have drifted). Cached 120s
    # so a stranger cannot force repeated tailscale calls. The sync filters to owner-owned devices only.
    if time.time() - _OWNER_SYNC_CACHE["ts"] > 120:
        _OWNER_SYNC_CACHE["ts"] = time.time()
        try:
            subprocess.run([sys.executable, os.path.join(PROJECT, "tools", "ops", "owner_devices_sync.py")],
                           capture_output=True, timeout=25)
            _OWNER_IPS_CACHE["ts"] = 0.0  # force reload
            ips = _owner_devices_ips()
            if cand in ips or peer in ips:
                return True
        except Exception:
            pass
    return False

def _locked_page():
    return _shell("Locked", "<h2>&#128274; Locked to your devices</h2>"
                  "<div class='card'>This console only takes <b>actions</b> from your own devices on the tailnet. "
                  "If you just switched devices, tap again in a moment &mdash; it recognizes your device automatically.</div>"
                  "<a class='row' href='/'><div class='t'>&larr; Back to what needs you</div></a>")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=STATUS_DIR, **k)
    def log_message(self, *a): pass
    def _html(self, s):
        bts = s.encode("utf-8")
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(bts))); self.end_headers(); self.wfile.write(bts)
    def do_POST(self):
        pp = self.path.split("?")[0]
        if not _owner_ok(self):
            return self._html(_locked_page())
        if pp in ("/fix/direct", "/action/direct"):
            import urllib.parse
            n = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
            return self._html(_direction_result(urllib.parse.parse_qs(raw).get("text", [""])[0]))
        if pp.startswith("/fix/") and pp.endswith("/direct"):
            import urllib.parse
            aid = pp[len("/fix/"):-len("/direct")].strip("/")
            n = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(n).decode("utf-8", "replace") if n else ""
            text = urllib.parse.parse_qs(raw).get("text", [""])[0]
            return self._html(_direction_result_for(aid, text))
        self.send_response(404); self.end_headers()
    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "", "/console", "/status", "/status/"):
            return self._html(_index())
        if p in ("/fix", "/fix/", "/action", "/action/"):
            return self._html(_fix_page())
        if p in ("/fix/free-card", "/action/free-card"):
            if not _owner_ok(self):
                return self._html(_locked_page())
            return self._html(_free_card_result())
        if p.startswith("/fix/") and p not in ("/fix/", "/fix/free-card", "/action/free-card"):
            rest = p[len("/fix/"):].strip("/")
            if rest.endswith("/act"):
                if not _owner_ok(self):
                    return self._html(_locked_page())
                import urllib.parse as _up
                aid = rest[:-4].strip("/")
                qs = _up.parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
                return self._html(_fix_act(aid, qs.get("b", ["route"])[0]))
            return self._html(_fix_app(rest))
        if p in ("/comfy-queue", "/comfy-queue/"):
            return self._html(_comfy_page())
        if p in ("/full", "/full/"):
            self.path = "/system_status.html"
        return super().do_GET()


def main():
    threading.Thread(target=refresh_loop, daemon=True).start()
    socketserver.TCPServer.allow_reuse_address = True
    # 2026-07-05: was 0.0.0.0. _owner_ok() already gates on peer IP (defense #1), but tailscale serve
    # only ever proxies /status -> 127.0.0.1:8781 (see `tailscale serve status`), so there's no reason
    # to also listen on the LAN interface. Loopback-only is defense #2 and removes that surface entirely.
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    sys.exit(main())
