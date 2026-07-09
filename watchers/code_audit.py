# -*- coding: utf-8 -*-
"""code_audit.py - the AUDIT UPGRADE: a static scanner for the RECURRING bug CLASSES.

Born from the 2026-06-18 cross-thread code review (audit lane). Each detector below codifies a
real defect class that bit us, so the audit catches the NEXT instance automatically instead of
waiting for a 6:30am crash. Report-only (never edits). Stdlib only. ASCII. Private output.

Detectors (each finding = class . file:line . evidence . fix):
  K1 os_kill_liveness   - os.kill(pid, 0) liveness without a Windows-safe guard. On Win/Py3.11 this
                          raises SystemError (NOT an OSError subclass) -> uncaught crash / inverted
                          'except: pass' -> duplicate-runner GPU runaway. (youtube/gpu lane incident.)
  K2 render_no_gate     - a ComfyUI render submit (api("prompt"/queue_prompt/submit_wait) in a file
                          that never calls gate_gpu() -> violates the 8GB co-tenant rule.
  K3 cors_star          - ALLOWED_ORIGIN / Access-Control-Allow-Origin defaulting to "*".
  K4 nonatomic_ledger   - open(<shared ledger>, "a") append with no lock (interleave -> corrupt JSONL
                          -> a dropped paid entitlement / lost board item).
  K5 bat_nonascii       - a .bat file with non-ASCII bytes (cmd emits a cryptic "'M' is not recognized").
  K6 dead_media_route   - a "/<x>-media/" or "/char-ref/" URL advertised by a producer with NO matching
                          startswith handler in the studio server (renders that can never be served).

Output: reports/_status/code_audit.json (PRIVATE, owner-only) + a stdout summary. Folds into audit_cycle.
"""
import os, sys, re, json, time

HERE    = os.path.dirname(os.path.abspath(__file__))
HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
STATUS  = os.path.join(PROJECT, "reports", "_status")
STUDIO_SERVER = os.path.join(PROJECT, "app", "studio", "studio_server.py")

SKIP_DIRS = (".git", "__pycache__", "node_modules", "site-packages", "elementlotus_v2",
             ".venv", "venv", "exports", "finals", "reports", "_archive")
SHARED_LEDGERS = (".dispatch_log.jsonl", "paid_orders.jsonl", "workboard_items.json",
                  "newsletter", "_orders", "entitlement")


def _py_files():
    for base, dirs, files in os.walk(PROJECT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(base, f)


def _read(p):
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def _rel(p):
    return os.path.relpath(p, PROJECT).replace("\\", "/")


def _lineno(src, idx):
    return src.count("\n", 0, idx) + 1


def scan():
    findings = []

    def add(cls, sev, path, line, evidence, fix):
        findings.append({"class": cls, "severity": sev, "file": _rel(path),
                         "line": line, "evidence": evidence.strip()[:200], "fix": fix})

    # --- gather the studio route table once (for K6) ---
    studio_src = _read(STUDIO_SERVER)
    route_prefixes = set(re.findall(r'p(?:ath)?\s*(?:==|\.startswith\()\s*["\'](/[A-Za-z0-9_\-]+)', studio_src))

    for p in _py_files():
        src = _read(p)
        if not src:
            continue
        imports_safe = ("from gpu_lock import _pid_alive" in src
                        or "from youtube_lock import" in src or "import youtube_lock" in src)
        # a file that gates, OR routes renders through the gated conductor (submit_wait), is GPU-safe
        gpu_safe = ("gate_gpu(" in src) or ("submit_wait(" in src) or ("def gate_gpu" in src)
        defines_gate = "def gate_gpu" in src

        # K1: os.kill(pid, 0) liveness WITHOUT a Windows-safe path. A file that ALSO uses a real
        # Windows liveness method (OpenProcess / tasklist / WMI) handles Windows there and only hits
        # os.kill on the POSIX fallback branch -> safe. Flag only files with raw os.kill and NO such path.
        has_win_safe = ("OpenProcess" in src or "tasklist" in src or "Win32_Process" in src or imports_safe)
        if not has_win_safe:
            # non-greedy [^\n]+? (was [^,]+): the OLD pattern could not match a pid arg that itself
            # contains a comma, e.g. os.kill(o.get("pid", -1), 0) - exactly how the system_status.py
            # liveness bug hid from this scanner (server-quad-os self-heal audit 2026-06-21).
            for m in re.finditer(r"os\.kill\([^\n]+?,\s*0\s*\)", src):
                add("os_kill_liveness", "HIGH", p, _lineno(src, m.start()), m.group(0),
                    "Replace with a Windows-safe OpenProcess probe (gpu_lock._pid_alive) that never raises; "
                    "only treat 'alive' as a positive, never 'probe raised'.")

        # K2: a DIRECT ComfyUI render submit (api('prompt')/queue_prompt) in a file that never gates the
        # GPU and isn't the conductor. submit_wait()-based files route through the gated conductor (exempt).
        if not gpu_safe and not defines_gate:
            render_graph = any(t in src for t in ("WanImageToVideo", "UNETLoader", "KSampler", "CheckpointLoader", "Hunyuan"))
            for pat in (r'\.api\(\s*["\']prompt["\']', r'queue_prompt\('):
                m = re.search(pat, src)
                if m and render_graph:
                    add("render_no_gate", "LOW", p, _lineno(src, m.start()), m.group(0),
                        "LOW-CONFIDENCE (confirm manually): a direct render submit with no gate_gpu()/submit_wait() "
                        "in-file. If it submits heavy work standalone, add gate_gpu() (8GB co-tenant rule).")
                    break

        # K3: CORS '*' default - flag only REAL header sets / env defaults to '*', not comments,
        # docstrings, or regex patterns that merely mention the literal (those were false positives).
        for _i, _ln in enumerate(src.splitlines(), 1):
            _code = _ln.split("#", 1)[0]      # drop inline comments (the '*' is often only mentioned there)
            if ('"*"' not in _code) and ("'*'" not in _code):
                continue
            _is_header = ("Allow-Origin" in _code) and any(h in _code for h in
                          ("send_header", "add_header", "setHeader", "set_header", "headers["))
            _is_env = ("ALLOWED_ORIGIN" in _code) and (
                        re.search(r"environ\.get\([^)]*,\s*[\"']\*[\"']", _code)
                        or re.search(r"ALLOWED_ORIGIN\s*=\s*[\"']\*[\"']", _code))
            if _is_header or _is_env:
                add("cors_star", "MED", p, _i, _ln.strip()[:80],
                    "Default the allowed origin to the production origin; require an explicit opt-in for '*' in dev only.")

        # K4: non-atomic append to a SHARED (multi-writer) ledger - interleave -> torn JSONL line.
        # Accuracy fix (server-quad-os 2026-06-20): only GENUINELY-SHARED ledgers (the dispatch bus,
        # entitlements, board items, orders/queue) carry concurrency risk. Single-writer per-module LOG files
        # (LOG_PATH/LOG_FILE/_LOG) have ONE appender -> no interleave -> they were false positives that kept the
        # count inflated (and re-fired this assignment). Dropped them; the real shared bus is now an atomic
        # os.write append (dispatch.append_sync_log). What remains = a real shared-ledger append bypassing the
        # atomic helper - worth flagging.
        for m in re.finditer(r'open\(\s*([^\n,]+?)\s*,\s*["\']a["\']', src):
            target = m.group(1)
            near = src[max(0, m.start() - 140):m.start()]
            if (any(s in target for s in SHARED_LEDGERS) or any(s in near for s in SHARED_LEDGERS)
                    or re.search(r'\b(DISPATCH|LEDGER|ORDERS|QUEUE)\b', target)):
                add("nonatomic_ledger", "LOW", p, _lineno(src, m.start()), m.group(0),
                    "Route shared-ledger appends through safe_io atomic-append (or dispatch.append_sync_log's "
                    "os.write O_APPEND); a torn line silently drops an entitlement / board item.")

        # K7: non-ASCII in a print()/raise/log string WITHOUT a UTF-8 guard -> UnicodeEncodeError crash
        # under a Windows cp1252 scheduled task (the civic engine's #1 recurring crash class). Files run
        # only through audit_cycle (which sets a process-global guard) are still flagged if run standalone.
        has_utf8_guard = ("reconfigure(encoding" in src or "PYTHONUTF8" in src
                          or "TextIOWrapper(sys.stdout" in src)
        if not has_utf8_guard:
            for ln_no, line in enumerate(src.splitlines(), 1):
                if any(ord(c) > 127 for c in line) and re.search(r'\b(print|raise)\b|\.write\(', line):
                    add("nonascii_print", "LOW", p, ln_no, line.strip()[:90],
                        "Non-ASCII in a print/raise/write with no UTF-8 guard -> UnicodeEncodeError crash on a "
                        "cp1252 console. Add sys.stdout.reconfigure(encoding='utf-8', errors='replace') at top, "
                        "or replace the char with ASCII.")
                    break  # one per file is enough to flag it

        # K6: a media URL advertised but not served by the studio route table
        for m in re.finditer(r'["\'](/[A-Za-z0-9_\-]*media/?|/char-ref/?)["\']', src):
            url = m.group(1).rstrip("/")
            prefix = "/" + url.strip("/").split("/")[0]
            if prefix and prefix not in route_prefixes and "studio_server.py" not in p:
                add("dead_media_route", "MED", p, _lineno(src, m.start()), m.group(1),
                    "Add a confined GET handler in studio_server.py for %s (mirror /storyboard-media/), "
                    "or the produced media is unreachable." % prefix)

        # K8: a BROWSER-FACING loopback URL emitted from Python HTML (href/src/action). Jimmy 2026-06-19
        # ("these links open the old localhost call on my iPad"): a hardcoded http://127.0.0.1|localhost in
        # a link opens the DEVICE's own localhost on a phone/iPad -> broken over Tailscale. Server-side
        # urlopen/requests/subprocess to 127.0.0.1 are EXEMPT (they run on the host) - the href/src/action
        # anchor is what makes this a browser link.
        for m in re.finditer(r'(?:href|src|action)\s*=\s*["\']https?://(?:127\.0\.0\.1|localhost)(?::\d+)?', src):
            add("loopback_link_cross_device", "MED", p, _lineno(src, m.start()), m.group(0),
                "Browser-facing loopback URL in emitted HTML -> opens the device's own localhost on iPad/phone "
                "(broken over Tailscale). Use a same-host RELATIVE path (/king /board /studio /comfy) served "
                "under the one ts.net host. Server-side 127.0.0.1 calls are exempt.")
            break

    # K5: non-ASCII bytes in any .bat
    for base, dirs, files in os.walk(PROJECT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.lower().endswith(".bat"):
                fp = os.path.join(base, f)
                try:
                    raw = open(fp, "rb").read()
                    raw.decode("ascii")
                except UnicodeDecodeError as e:
                    line = raw[:e.start].count(b"\n") + 1
                    # severity: non-ASCII in a COMMAND position can break cmd; in an echo/rem/:: banner it's cosmetic
                    line_start = raw.rfind(b"\n", 0, e.start) + 1
                    line_txt = raw[line_start:e.start].lstrip().lower()
                    cosmetic = line_txt.startswith((b"echo", b"rem", b"::", b"title"))
                    add("bat_nonascii", "LOW" if cosmetic else "HIGH", fp, line,
                        "non-ASCII byte at offset %d (%s)" % (e.start, "echo/banner" if cosmetic else "command position"),
                        "Keep .bat files pure ASCII (a stray em-dash makes cmd emit \"'M' is not recognized\"). "
                        + ("Banner-only -> low risk, but normalize when touched." if cosmetic else "COMMAND position -> fix now."))
                except Exception:
                    pass

    # K9: browser-facing loopback URLs in served .html (the cross-device class). Only attribute positions
    # (href/src/action), so descriptive text mentioning 127.0.0.1 is NOT flagged. Skip generated/derived
    # trees (site/, king-extract, the reports mirrors) - fix the SOURCE under app/ + tools/ + templates.
    _GEN = ("\\site\\", "/site/", "king-extract", "\\reports\\", "/reports/", "node_modules")
    for base, dirs, files in os.walk(PROJECT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.lower().endswith((".html", ".htm")):
                continue
            fp = os.path.join(base, f)
            if any(g in fp for g in _GEN):
                continue
            html = _read(fp)
            if not html:
                continue
            m = re.search(r'(?:href|src|action)\s*=\s*["\']https?://(?:127\.0\.0\.1|localhost)(?::\d+)?', html)
            if m:
                add("loopback_link_cross_device", "MED", fp, _lineno(html, m.start()), m.group(0),
                    "Browser-facing loopback link in served HTML -> opens the device's own localhost on "
                    "iPad/phone (broken over Tailscale). Use a same-host RELATIVE path (/king /board /studio /comfy).")

    # K10: the 2nd flavor of the cross-device class (Jimmy 2026-06-20: "the studio links over Tailscale have
    # the same problem as civic"). An app served under a Tailscale PATH-PREFIX (/studio :8770, /board :8782,
    # /king :8799) BREAKS when its HTML uses ROOT-RELATIVE client URLs ("/api/..", src="/x"): the browser
    # resolves them at the ts.net ROOT, escaping the prefix -> hits the wrong server on phone/iPad. The fix is
    # a base-prefix shim (keeps client requests inside the prefix; no-op locally) OR prefix-relative paths.
    # HEAL-FORWARD: flag any prefix-served page that has root-relative client links AND lacks the shim, so a
    # NEW prefix-served surface can't reintroduce this class. Cross-references the loopback fix above.
    _PREFIXED = ("app\\studio\\", "app/studio/", "app\\workboard\\", "app/workboard/")
    _ROOTREL = re.compile(r'(?:href|src|action)\s*=\s*["\']/[a-zA-Z]|fetch\s*\(\s*["\'`]/[a-zA-Z]')
    _SHIM = ("HEAL-FORWARD cross-device", "location.pathname.match(/^\\/(")
    for base, dirs, files in os.walk(os.path.join(PROJECT, "app")):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.lower().endswith((".html", ".htm")):
                continue
            fp = os.path.join(base, f)
            if any(g in fp for g in _GEN) or not any(p in fp for p in _PREFIXED):
                continue
            html = _read(fp)
            if not html:
                continue
            mm = _ROOTREL.search(html)
            if mm and not any(s in html for s in _SHIM):
                add("cross_device_link_prefix", "MED", fp, _lineno(html, mm.start()), mm.group(0)[:60],
                    "Root-relative client link in a PATH-PREFIX-served app (/studio,/board) with NO base-prefix "
                    "shim -> escapes the Tailscale prefix and breaks on phone/iPad (same family as "
                    "loopback_link_cross_device). Add the shim (pattern: app/studio/studio.html) or use prefix-relative paths.")

    return findings


def main():
    os.makedirs(STATUS, exist_ok=True)
    findings = scan()
    by_class, by_sev = {}, {}
    for f in findings:
        by_class[f["class"]] = by_class.get(f["class"], 0) + 1
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    # score 0-100: start at 100, subtract weighted by severity (capped). LOW = advisory (cosmetic
    # banners / low-confidence candidates) -> 0 weight; the score reflects ACTIONABLE MED+/HIGH debt.
    w = {"CRITICAL": 25, "HIGH": 10, "MED": 4, "LOW": 0}
    score = max(0, 100 - min(100, sum(w.get(f["severity"], 1) for f in findings)))
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "score": score,
           "total": len(findings), "by_class": by_class, "by_severity": by_sev,
           "findings": sorted(findings, key=lambda x: ({"CRITICAL": 0, "HIGH": 1, "MED": 2, "LOW": 3}.get(x["severity"], 9), x["class"]))}
    tmp = os.path.join(STATUS, "code_audit.json.tmp")
    open(tmp, "w", encoding="utf-8").write(json.dumps(out, indent=1, ensure_ascii=False))
    os.replace(tmp, os.path.join(STATUS, "code_audit.json"))
    print("code_audit: score=%d  total=%d  by_severity=%s  by_class=%s -> reports/_status/code_audit.json (PRIVATE)" % (
        score, len(findings), json.dumps(by_sev), json.dumps(by_class)))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
