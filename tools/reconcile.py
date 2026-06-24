# -*- coding: utf-8 -*-
"""
reconcile.py - THE ONE shared "unify, never fragment" primitive (JRCSL #1).

ONE implementation, imported everywhere - building three copies of a dedup checker would itself be the
fragmentation we're fighting. Surfaces + their correct enforcement LEVEL (Jimmy 2026-06-19
"build this into the webservers and 12sgi and elementlotus with best practices"):

  - AUTHORING (Claude PreToolUse hook)  -> WARN, never block   (reconcile_check.py imports check_hook)
  - PUBLISH / CI (12sgi-king, webservers) -> BLOCK on hard dup (gate_tree, exit nonzero)  [best practice:
                                              fail the build, not the user]
  - CMS (elementlotus WordPress, pages/routes) -> IDEMPOTENT UPSERT (find_existing -> update, not create)

Best practices baked in: single source of truth, idempotent, non-destructive (never deletes - reports),
fail-closed only at the publish gate, stdlib-only, ASCII, deterministic.

CLI:
  python tools/reconcile.py --hook                              # stdin hook json -> additionalContext (warn)
  python tools/reconcile.py --gate  <dir> [exts] [--route-only] # publish gate: exit 1 if hard duplicates found
  python tools/reconcile.py --scan  <dir> [exts] [--route-only] # report duplicate clusters, always exit 0
"""
import sys, os, json, re, glob
for _s in (sys.stdout, sys.stderr):   # Hawaiian okina + em-dash break cp1252 consoles
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

STOP = set("the a an and or of to for in on is be do you your my our it this that with as at by from "
           "see use new all map for into not how what when add md skill readme index notes doc docs "
           "page the- and- v1 v2 final draft copy "
           # HTML/template boilerplate - these are SHARED by every page (that's unify, not duplication);
           # they must never trigger a dup match (the 7182-false-positive lesson, 2026-06-19)
           "html head body meta charset utf utf-8 lang div span class style script link href http https "
           "www com content name width viewport initial scale type rel stylesheet title h1 doctype "
           "nav footer header main section button svg img src alt role aria".split())
DEFAULT_EXTS = (".md", ".html")
HARD_OVERLAP = 3   # publish gate blocks at this token-overlap (very likely the same artifact)
WARN_OVERLAP = 2   # authoring hook warns at this (possible duplicate)


def toks(name):
    name = re.sub(r"\.(md|py|json|html|txt|php)$", "", os.path.basename(name).lower())
    return {w for w in re.split(r"[^a-z0-9]+", name) if w and w not in STOP and len(w) > 2}


def title_of(path):
    """The page's REAL identity line: markdown H1, or the HTML <title>/<h1> CONTENT - never the
    doctype/<meta>/<head> boilerplate (those are shared by every page = not a dup signal)."""
    try:
        head = open(path, encoding="utf-8", errors="replace").read(8000)
    except Exception:
        return ""
    if path.lower().endswith((".html", ".htm", ".php")):
        m = re.search(r"<title[^>]*>(.*?)</title>", head, re.I | re.S) or \
            re.search(r"<h1[^>]*>(.*?)</h1>", head, re.I | re.S)
        return re.sub(r"<[^>]+>", "", m.group(1)).strip().lower() if m else ""
    for ln in head.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            return s.lstrip("# ").strip().lower()
        if s and not s.startswith(("<!", "<")):
            return s.lower()
    return ""


def find_duplicates(target_path, content="", scan_dir=None, exts=DEFAULT_EXTS, min_overlap=WARN_OVERLAP):
    """Return [(overlap, relpath, shared_tokens)] of existing files that look like the same deliverable."""
    qt = toks(target_path)
    m = re.search(r"^#+\s*(.+)$", content or "", re.M)
    if m:
        qt |= toks(m.group(1))
    if not qt:
        return []
    scan_dir = scan_dir or os.path.dirname(target_path) or "."
    cands = []
    for ext in exts:
        cands += glob.glob(os.path.join(scan_dir, "*" + ext))
        cands += glob.glob(os.path.join(scan_dir, "*", "*" + ext))
    hits = []
    tlow = target_path.replace("\\", "/").lower()
    for c in cands:
        cp = c.replace("\\", "/")
        if cp.lower() == tlow:
            continue
        overlap = qt & (toks(c) | toks(title_of(c)))
        if len(overlap) >= min_overlap:
            hits.append((len(overlap), os.path.relpath(c, scan_dir).replace("\\", "/"), sorted(overlap)[:5]))
    hits.sort(reverse=True)
    return hits


def _norm_title(t):
    # strip brand/section suffixes so "Take Action - Kilo Aupuni - govOS" == "Take Action"
    t = re.split(r"[—–|:]| - ", t or "")[0]
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def scan_tree(root, exts=DEFAULT_EXTS, min_overlap=HARD_OVERLAP, route_only=False):
    """Find TRUE duplicates - signal differs by surface (best practice, not one brittle rule):
      * docs (.md)        -> filename+H1 token overlap (catalog/spec forks)
      * site (.html/.php) -> SAME route (identical basename in 2 dirs) OR identical page <title>.
        Shared template/brand tokens are UNIFY, not duplication - they never trigger.
      route_only=True skips the title-based check (use in CI to avoid false-positive matches on
      per-tenant pages that intentionally share generic titles like "Agendas" or "Archive").
    -> [(a, b, reason)]."""
    md, web = [], []
    for ext in exts:
        for f in glob.glob(os.path.join(root, "**", "*" + ext), recursive=True):
            (web if ext.lower() in (".html", ".htm", ".php") else md).append(f)
    pairs = []
    # docs: token overlap
    sig = [(f, toks(f) | toks(title_of(f))) for f in md]
    for i in range(len(sig)):
        for j in range(i + 1, len(sig)):
            ov = sig[i][1] & sig[j][1]
            if len(ov) >= min_overlap:
                pairs.append((_rel(sig[i][0], root), _rel(sig[j][0], root), "shared: " + ", ".join(sorted(ov)[:6])))
    # site: same basename OR (unless route_only) same normalized title (true page duplication only)
    by_base, by_title = {}, {}
    for f in web:
        by_base.setdefault(os.path.basename(f).lower(), []).append(f)
        if not route_only:
            nt = _norm_title(title_of(f))
            if nt and len(nt) > 2:
                by_title.setdefault(nt, []).append(f)
    for base, fs in by_base.items():
        for j in range(1, len(fs)):
            pairs.append((_rel(fs[0], root), _rel(fs[j], root), "same route/basename: " + base))
    if not route_only:
        for nt, fs in by_title.items():
            if len(fs) > 1:
                bset = set()
                for j in range(1, len(fs)):
                    key = tuple(sorted((os.path.basename(fs[0]).lower(), os.path.basename(fs[j]).lower())))
                    if key in bset:
                        continue
                    bset.add(key)
                    pairs.append((_rel(fs[0], root), _rel(fs[j], root), "same <title>: " + nt))
    return pairs


def _rel(p, root):
    return os.path.relpath(p, root).replace("\\", "/")


def check_hook(stdin_text):
    """AUTHORING level: parse a PreToolUse(Write) payload -> additionalContext warning (or '')."""
    try:
        p = json.loads(stdin_text)
    except Exception:
        return ""
    if p.get("tool_name") != "Write":
        return ""
    ti = p.get("tool_input") or {}
    target = (ti.get("file_path") or "")
    if not target:
        return ""
    low = "/" + target.replace("\\", "/").lower().strip("/") + "/"
    if not ("/docs/" in low or "/.claude/skills/" in low):
        return ""
    if os.path.exists(target):   # edit, not a new fork -> allow silently
        return ""
    hits = find_duplicates(target, ti.get("content", ""))
    if not hits:
        return ""
    lines = ["RECONCILE-BEFORE-BUILD (JRCSL #1: unify, never fragment).",
             "About to CREATE a new file, but these existing ones look like the same deliverable:"]
    for n, rel, ov in hits[:5]:
        lines.append("  - %s  (shared: %s)" % (rel, ", ".join(ov)))
    lines.append("If one is canonical, EDIT it instead of forking a sibling. Else proceed - warning, not block.")
    return "\n".join(lines)


def _main(argv):
    if not argv:
        print(__doc__); return 0
    mode = argv[0]
    if mode == "--hook":
        ctx = check_hook(sys.stdin.read())
        if ctx:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ctx}}))
        return 0
    if mode in ("--gate", "--scan"):
        argv_work = [a for a in argv if a != "--route-only"]
        route_only = len(argv_work) != len(argv)
        if len(argv_work) < 2:
            print("usage: reconcile.py %s <dir> [ext,ext] [--route-only]" % mode); return 2
        root = argv_work[1]
        exts = tuple("." + e.strip(". ") for e in argv_work[2].split(",")) if len(argv_work) > 2 else DEFAULT_EXTS
        pairs = scan_tree(root, exts, route_only=route_only)
        if not pairs:
            print("reconcile: clean - no duplicate clusters in %s" % root); return 0
        print("reconcile: %d possible duplicate pair(s) in %s:" % (len(pairs), root))
        for a, b, reason in pairs:
            print("  DUP  %s  <=>  %s   (%s)" % (a, b, reason))
        # best practice: BLOCK the publish (exit 1) on --gate; report-only on --scan
        return 1 if mode == "--gate" else 0
    print("unknown mode:", mode); return 2


if __name__ == "__main__":
    try:
        sys.exit(_main(sys.argv[1:]))
    except Exception as e:
        # fail-OPEN everywhere except an explicit gate, so a checker bug never breaks a session/build
        sys.stderr.write("reconcile: %s\n" % e)
        sys.exit(0)
