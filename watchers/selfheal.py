#!/usr/bin/env python3
"""selfheal.py — the system re-asserts its own truth on every build.

Every clarification we reached on this journey becomes an INVARIANT checked here, so the system catches
its own drift instead of waiting for a human to notice. Run it locally (full picture) or on CI (checks
what's present). Writes a public-safe integrity summary (reports/mauios/selfheal.html) + a detailed
local JSON. PASS/WARN/FAIL per check. See docs/SAGE_REALM_MODEL.md §2 (self-healing principle).

Stdlib only. Never fails the build by itself — it reports; the operator decides.
"""
import os, re, json, html
from urllib.parse import unquote
from datetime import datetime, timezone, timedelta

HERE   = os.path.dirname(os.path.abspath(__file__))
PROJ   = os.path.abspath(os.path.join(HERE, "..", ".."))
MAUIOS = os.path.join(PROJ, "reports", "mauios")
HOME   = os.path.expanduser("~")
HST    = timezone(timedelta(hours=-10))
def esc(s): return html.escape(str(s or ""))

# Find the publish repo (local desktop path, else CI checkout = cwd).
def _repo():
    for c in (os.path.join(HOME, "Documents", "Claude", "12sgi-king"), os.getcwd()):
        if os.path.isdir(os.path.join(c, "watchers")) or os.path.isfile(os.path.join(c, "build_site.py")):
            return c
    return os.getcwd()
REPO = _repo()

PRIVATE_NAMES = ("prosecutor.py", "case_files.html", "recusal_evidence.html",  # owner-only back end — never publish
                 "ram_loop.html", "onboard_readiness.html",   # real-estate loop + prosecutorial onboarding — owner-only
                 "king_message.html",                         # curse-breaker w/ held RE numbers — owner-only until RE report ships
                 "maui_re_report.html",                       # RE report PRIVATE review build (named $ + property) — owner-only until approved public
                 "minutes_review.html",                       # prosecutorial red-flag + missing-minutes review — owner-only, never public
                 "private_completeness.html",
                 "testifiers.json", "testifiers_index.txt",   # testifier×money cross-ref (prosecutor) — public PAGE only, not the join
                 "nay_narratives.json",                       # dissent-vote spine (prosecutor) — public PAGE only, not the JSON
                 "daily_brief.html", "DAILY_BRIEF.md", "TODO_BACKLOG.md",  # owner-only cross-thread current-state — never public
                 "beta.json", "stripe.json", "verified_sessions.json",  # beta config + Stripe keys + verified-status store — never public
                 "paid_orders.jsonl", "civic_quotes.jsonl", "fulfilled_orders.jsonl",  # paid-render ledgers (no PII) — owner-only
                 "civic_pricing.json", "grant_service_offerings.json", "agenda_post_policy.json", "publish_policy.json",  # pricing + grant-service offerings — keep out of the public repo
                 "comfy_cloud.json", "opencorporates.json")  # API keys (ComfyUI Cloud, OpenCorporates) — never publish

def _known_secrets():
    """The ACTUAL secret VALUES, read at runtime from the local key files — NEVER hard-coded here
    (this file is published to the public watchers/, so it must contain no secret literal). On CI the
    keys are written to config/*.txt from Actions secrets; on a fresh clone there are none and we fall
    back to the filename check only."""
    vals = set()
    cfg = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS", "config")
    for fn in ("nysenate_key.txt", "legiscan_key.txt"):
        p = os.path.join(cfg, fn)
        try:
            v = open(p, encoding="utf-8", errors="ignore").read().strip()
            if len(v) >= 12:
                vals.add(v)
        except Exception:
            pass
    # the ComfyUI Cloud API key (lives in config/comfy_cloud.json) must never appear in the public repo
    try:
        import json as _json
        k = (_json.load(open(os.path.join(cfg, "comfy_cloud.json"), encoding="utf-8")).get("COMFY_API_KEY") or "").strip()
        if len(k) >= 12 and not k.startswith("PASTE_"):
            vals.add(k)
    except Exception:
        pass
    # the OpenCorporates API token (config/opencorporates.json) must never appear in the public repo
    try:
        import json as _json
        d = _json.load(open(os.path.join(cfg, "opencorporates.json"), encoding="utf-8"))
        k = (d.get("api_token") or d.get("token") or "").strip()
        if len(k) >= 12 and not k.startswith("PASTE_"):
            vals.add(k)
    except Exception:
        pass
    # the Stripe SECRET / restricted key (config/stripe.json) must NEVER appear in the public repo. The publishable
    # key (pk_) is safe to expose and is intentionally NOT scanned; only sk_/rk_/whsec_ are treated as secret.
    try:
        import json as _json
        d = _json.load(open(os.path.join(cfg, "stripe.json"), encoding="utf-8"))
        for fld in ("secret_key", "restricted_key", "webhook_secret"):
            k = (d.get(fld) or "").strip()
            if len(k) >= 12 and not k.startswith("PASTE_"):
                vals.add(k)
    except Exception:
        pass
    # Dropbox long-lived token (config/dropbox_creds.json -> "token")
    try:
        import json as _json
        k = (_json.load(open(os.path.join(cfg, "dropbox_creds.json"), encoding="utf-8")).get("token") or "").strip()
        if len(k) >= 12 and not k.startswith("PASTE_"):
            vals.add(k)
    except Exception:
        pass
    # Supabase private keys (config/supabase.json -> jwt_secret + service_role_key)
    try:
        import json as _json
        d = _json.load(open(os.path.join(cfg, "supabase.json"), encoding="utf-8"))
        for fld in ("jwt_secret", "service_role_key"):
            k = (d.get(fld) or "").strip()
            if len(k) >= 12 and not k.startswith("PASTE_") and not k.startswith("sb_publishable"):
                vals.add(k)
    except Exception:
        pass
    # Facebook app_secret (config/facebook.secret.json -> "app_secret")
    try:
        import json as _json
        k = (_json.load(open(os.path.join(cfg, "facebook.secret.json"), encoding="utf-8")).get("app_secret") or "").strip()
        if len(k) >= 12 and not k.startswith("PASTE_"):
            vals.add(k)
    except Exception:
        pass
    # Cloudflare scoped API token (config/cloudflare_credentials.json -> "api_token")
    try:
        import json as _json
        k = (_json.load(open(os.path.join(cfg, "cloudflare_credentials.json"), encoding="utf-8")).get("api_token") or "").strip()
        if len(k) >= 12 and not k.startswith("PASTE_"):
            vals.add(k)
    except Exception:
        pass
    # WordPress application password (config/wordpress_credentials.json -> "app_password")
    try:
        import json as _json
        k = (_json.load(open(os.path.join(cfg, "wordpress_credentials.json"), encoding="utf-8")).get("app_password") or "").strip()
        if len(k) >= 8 and not k.startswith("PASTE_"):
            vals.add(k)
    except Exception:
        pass
    # .env file values — scan all VAR=VALUE lines for any non-trivial value
    try:
        env_path = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS", ".env")
        for line in open(env_path, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            if len(v) >= 16 and not v.startswith("PASTE_") and not v.startswith("http"):
                vals.add(v)
    except Exception:
        pass
    return vals

# Pattern-based secret detection (catches secrets even without config file access)
_STRIPE_SECRET   = re.compile(r"\b(sk|rk)_(live|test)_[A-Za-z0-9]{8,}|\bwhsec_[A-Za-z0-9]{8,}")  # Stripe secret/restricted/webhook keys — never public
_DROPBOX_SECRET  = re.compile(r"\bsl\.u\.[A-Za-z0-9_-]{20,}")                                      # Dropbox long-lived user token
_SUPABASE_SECRET = re.compile(r"\bsb_secret_[A-Za-z0-9_]{8,}")                                     # Supabase JWT secret prefix
_FACEBOOK_SECRET = re.compile(r"\bFACEBOOK_APP_SECRET\s*[=:]\s*[0-9a-f]{30,}")                     # FB app_secret in env/config
_CLOUDFLARE_TOK  = re.compile(r"\bcfat_[A-Za-z0-9]{20,}")                                          # Cloudflare scoped API token
_GOOGLE_OAUTH    = re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{10,}")                                      # Google OAuth client secret
# Note: WordPress app-passwords (6x4 groups) are guarded via runtime value scan from
# wordpress_credentials.json — a structural regex would generate false positives against
# civic minutes text that has similar-looking short-word sequences.
_ALL_PATTERNS    = [_STRIPE_SECRET, _DROPBOX_SECRET, _SUPABASE_SECRET, _FACEBOOK_SECRET,
                    _CLOUDFLARE_TOK, _GOOGLE_OAUTH]
def chk_no_leak():
    """No private back-end file or secret key may exist anywhere in the publish repo tree.
    Scans both known runtime values (read from config files at check time) AND structural
    patterns for Stripe, Dropbox, Supabase, Facebook, Cloudflare, Google OAuth, WordPress."""
    hits = []
    secrets = _known_secrets()
    for root, dirs, files in os.walk(REPO):
        if ".git" in dirs: dirs.remove(".git")
        for fn in files:
            if fn in PRIVATE_NAMES or (fn.endswith(".txt") and "key" in fn.lower()) or "dossier" in fn.lower():
                hits.append(os.path.relpath(os.path.join(root, fn), REPO))
            elif fn.endswith((".py", ".html", ".json", ".txt", ".md", ".js", ".env", ".sh")):
                try:
                    body = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
                    if secrets and any(s in body for s in secrets):
                        hits.append(os.path.relpath(os.path.join(root, fn), REPO) + " (secret value)")
                    for pat in _ALL_PATTERNS:
                        if pat.search(body):
                            hits.append(os.path.relpath(os.path.join(root, fn), REPO) +
                                        " (secret pattern: %s)" % pat.pattern[:30])
                            break  # one hit per file per pattern group is enough to flag
                except Exception:
                    pass
    if hits:
        return "FAIL", "private/secret artifacts in publish repo: " + ", ".join(hits[:5])
    return "PASS", "no private back-end files or secret keys in the publish repo"

def chk_mobile():
    """Every built page must be readable on iPhone/iPad without zoom — the viewport meta is present everywhere.
    The build's heal (recolor_tree + king_recolor) injects it; this verifies the heal held."""
    site = os.path.join(REPO, "site")
    if not os.path.isdir(site):
        return "WARN", "site/ not built yet — skipped"
    miss = tot = 0
    for root, _d, files in os.walk(site):
        for fn in files:
            if not fn.lower().endswith((".html", ".htm")): continue
            tot += 1
            if "width=device-width" not in open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read():
                miss += 1
    return ("PASS" if miss == 0 else "FAIL"), f"{tot-miss}/{tot} pages mobile-ready (no-zoom on iPhone/iPad)"

def chk_links():
    """Internal links in the built site resolve the way GitHub Pages serves (%20 + /12sgi-king/)."""
    site = os.path.join(REPO, "site")
    if not os.path.isdir(site):
        return "WARN", "site/ not built yet (run build_site.py) — skipped"
    href_re = re.compile(r'(?:href|src)\s*=\s*["\']([^"\'#]+)["\']', re.I)
    broken = total = 0
    for root, _d, files in os.walk(site):
        for fn in files:
            if not fn.lower().endswith((".html", ".htm")): continue
            txt = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
            for href in href_re.findall(txt):
                h = href.split("?")[0].split("#")[0].strip()
                if not h or h.startswith(("http://","https://","mailto:","tel:","data:","javascript:","//")): continue
                if "{{" in h or "}}" in h: continue
                total += 1; h = unquote(h)
                if h.startswith("/12sgi-king/"): base, rel = site, h[len("/12sgi-king/"):]
                elif h.startswith("/"): base, rel = site, h.lstrip("/")
                else: base, rel = root, h
                tgt = os.path.normpath(os.path.join(base, rel))
                if not (os.path.exists(tgt) or os.path.exists(os.path.join(tgt, "index.html"))):
                    broken += 1
    return ("PASS" if broken == 0 else "FAIL"), f"{broken} broken of {total} internal links"

def _has(fn, needle):
    p = os.path.join(MAUIOS, fn)
    if not os.path.exists(p): return None
    return needle in open(p, encoding="utf-8", errors="ignore").read()

def chk_moon():
    """The moon dimension is live on both the civic cards and the Sage board."""
    a, s = _has("agenda_explainer.html", "🌙"), _has("sage_bridge.html", "🌙")
    if a is None or s is None: return "WARN", "agenda_explainer/sage_bridge not generated yet — skipped"
    return ("PASS" if (a and s) else "FAIL"), f"moon on agenda_explainer={bool(a)} sage_bridge={bool(s)}"

def chk_watcher_parity():
    """The generators' shared dependency (moon_calendar.py) is mirrored beside them for the cron path."""
    w = os.path.join(REPO, "watchers")
    if not os.path.isdir(w): return "WARN", "no watchers/ (not the publish repo) — skipped"
    need = ["moon_calendar.py", "sage_bridge.py", "agenda_explainer.py", "olelo_watch.py"]
    miss = [n for n in need if not os.path.exists(os.path.join(w, n))]
    return ("PASS" if not miss else "FAIL"), ("all key generators mirrored" if not miss else "missing in watchers: " + ", ".join(miss))

def chk_olelo():
    """ʻŌlelo Hawaiʻi is published under a visible community-review notice."""
    ok = _has("olelo_glossary.html", "under community review")
    if ok is None: return "WARN", "olelo_glossary not generated yet — run olelo_watch.py"
    return ("PASS" if ok else "FAIL"), "ʻŌlelo glossary carries the community-review notice"

def chk_surface_liveness():
    """Boot-persistence across ALL surfaces: every server/daemon/scheduled-task that should persist is up.
    Generalized from the :8799 King + publish-watcher reboot gaps (Jimmy 2026-06-16 'consider that type of
    problem for the other surfaces'). Runs surface_health.py (report) and reads its JSON."""
    import subprocess, sys as _sys
    sh = os.path.join(HERE, "surface_health.py")
    rep = os.path.join(PROJ, "reports", "_status", "surface_health.json")
    try:
        subprocess.run([_sys.executable, sh], cwd=HERE, timeout=90,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    if not os.path.exists(rep):
        return "WARN", "surface_health not generated yet"
    try:
        d = json.load(open(rep, encoding="utf-8")); s = d["summary"]
        if s["down"] == 0:
            return "PASS", "all %d persistent surfaces up (servers/daemons/tasks)" % s["total"]
        dn = [i["surface"] for i in d["items"] if i["ok"] is False]
        return "FAIL", "%d surface(s) down: %s (run surface_health.py --heal)" % (s["down"], ", ".join(dn[:5]))
    except Exception as e:
        return "WARN", "surface_health unreadable: %s" % e

def chk_bats_ascii():
    """.bat files stay pure ASCII (a stray non-ASCII byte breaks cmd parsing)."""
    bad = []
    for rel in ("12sgi-king/sync_watchers.bat", "dispatch.bat"):
        p = os.path.join(HOME, "Documents", "Claude", rel)
        if os.path.exists(p):
            try: open(p, encoding="ascii").read()
            except UnicodeDecodeError: bad.append(rel)
    return ("PASS" if not bad else "FAIL"), ("bats pure ASCII" if not bad else "non-ASCII in: " + ", ".join(bad))

def chk_orphans():
    """No useful built surface is unreachable. Every built public page must be reachable from
    the nav or a tenant; a built-but-unwired page is an ORPHAN (the 'check for heal' guard).
    Also (re)writes site/orphans.html so the dashboard reflects exactly what shipped."""
    try:
        from orphan_check import find_orphans, main as _orphan_main
    except Exception as e:
        return "WARN", "orphan_check unavailable (%s) — skipped" % e
    res = find_orphans()
    if res is None:
        return "WARN", "site/ not built yet (run build_site.py) — skipped"
    try: _orphan_main()          # refresh orphans.json + site/orphans.html
    except Exception: pass
    orphans, reach, total = res
    if not orphans:
        return "PASS", "all %d navigable pages reachable (0 orphaned)" % reach
    return "FAIL", "%d orphan(s) unreachable from nav/tenant: %s" % (
        len(orphans), ", ".join(orphans[:6]) + (" …" if len(orphans) > 6 else ""))

def chk_no_studio_route():
    """A PUBLIC page must NEVER route a visitor to the private studio. Catches the three real
    capture/redirect vectors (James 2026-06-17: a FB-opened public page showed the studio):
      1. <link rel="manifest"> on a public page — would install a PWA that captures civic links.
      2. service-worker registration — would intercept navigations on the public origin.
      3. a LOAD-TIME hard redirect (location.replace/href/assign or meta-refresh) to the studio
         (ts.net / :8770 / tail760750).
    go.html's live probe is a no-cors *fetch* that only toggles card styling (no navigation) and
    its owner cards are tap-only links — neither trips this; only an automatic route does."""
    site = os.path.join(REPO, "site")
    if not os.path.isdir(site):
        return "WARN", "site/ not built yet — skipped"
    man = re.compile(r'rel=["\']?manifest', re.I)
    sw  = re.compile(r'serviceWorker\.register|navigator\.serviceWorker', re.I)
    redir = re.compile(r'(?:location\.(?:replace|assign|href)\s*=?\s*\(?|http-equiv=["\']refresh["\'][^>]*url=)'
                       r'["\']?[^"\'>\s]*(?:tail760750|\.ts\.net|:8770)', re.I)
    hits = []
    for root, _d, files in os.walk(site):
        for fn in files:
            if not fn.lower().endswith((".html", ".htm")):
                continue
            try:
                t = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            rel = os.path.relpath(os.path.join(root, fn), site).replace("\\", "/")
            if man.search(t):   hits.append(rel + "::manifest")
            if sw.search(t):    hits.append(rel + "::service-worker")
            if redir.search(t): hits.append(rel + "::studio-redirect")
    if hits:
        return "FAIL", "%d public page(s) could route to the private studio: %s" % (
            len(hits), ", ".join(hits[:8]))
    return "PASS", "no public page installs a PWA or routes to the studio"

def chk_external_links():
    """Outbound civic links (county .gov, Municode, Hawaiʻi GIS, MAPPS, mauirecovers, …) resolve.
    Reads the last external_links.py run — does NOT re-fetch here (that's the periodic job's work).
    Transient (403/429/5xx/timeout) are 'recheck', not broken, and never fail. A genuinely dead
    link (404/410 after retry) WARNs (never FAIL — externals are outside our control + flaky)."""
    try:
        from external_links import status_summary
    except Exception as e:
        return "WARN", "external_links unavailable (%s) — skipped" % e
    s = status_summary()
    if s is None:
        return "WARN", "external_links not run yet (run external_links.py)"
    confirmed, recheck, broken, healable, total = s
    if broken == 0:
        return "PASS", "%d civic outbound links: %d confirmed, %d recheck (transient), 0 broken" % (
            total, confirmed, recheck)
    return "WARN", "%d broken outbound link(s) of %d (%d auto-healable) — see external_links.html" % (
        broken, total, healable)

def chk_seed_parity():
    """The public floor (seed_reports/mauios) carries the current data. Pages are generated
    into the project's reports/mauios, but CI's push builds (the `publish` verb) only see the
    committed seed — watchers run on cron only. So a page missing from seed, or a stale seed
    page, silently fails to reach the people on a push deploy (the feature_board lesson). This
    is a WARN, never FAIL: a stale floor is a 'carry it over' nudge (publish_audit.py --sync),
    not a reason to block the build. Private reports/_status is never touched. selfheal.html is
    exempt (CI regenerates it every build). Solution-side framing: pages waiting to serve."""
    try:
        import sys, importlib
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import publish_audit; importlib.reload(publish_audit)
        r = publish_audit.audit()
    except Exception as e:
        return "WARN", "publish_audit unavailable (%s) — seed parity unverified" % e
    if r["clean"]:
        return "PASS", "%d page(s) current on the public floor; %d resting (moon/timestamp only)" % (
            r["ok"], len(r["cosmetic"]))
    return "WARN", "%d page(s) waiting to reach the public floor (%d missing, %d stale) — heal: publish_audit.py --sync" % (
        r["gap_count"], len(r["missing"]), len(r["drift"]))

CHECKS = [
    ("Private back end stays private", chk_no_leak),
    ("Seed mirror is current",        chk_seed_parity),
    ("Links resolve like GitHub Pages", chk_links),
    ("No public page routes to studio", chk_no_studio_route),
    ("External civic links resolve", chk_external_links),
    ("No orphaned surfaces (check for heal)", chk_orphans),
    ("Mobile-ready everywhere (no zoom)", chk_mobile),
    ("Moon dimension is live",         chk_moon),
    ("Generators share their deps",    chk_watcher_parity),
    ("ʻŌlelo held under review",       chk_olelo),
    ("Batch files pure ASCII",         chk_bats_ascii),
    ("All surfaces persist (boot)",    chk_surface_liveness),
]

# ---------------------------------------------------------------------------
# PROGRESS / best practices — self-healing is not only guarding against drift, it is advancing.
# These nudge the system forward (MET / TODO). A TODO never blocks the build; it points at next work.
# ---------------------------------------------------------------------------
def _site_pages():
    site = os.path.join(REPO, "site")
    if not os.path.isdir(site): return []
    return [f for f in os.listdir(site) if f.endswith(".html")]

def prog_narrative_coverage():
    """Best practice: every page opens with a plain-words door-in (clarity for the everyday person)."""
    pages = _site_pages()
    if not pages: return False, "site/ not built — skipped"
    with_narr = sum(1 for f in pages if "govos-narrative" in
                    open(os.path.join(REPO, "site", f), encoding="utf-8", errors="ignore").read())
    pct = round(100 * with_narr / len(pages))
    return (pct >= 90), "%d%% of %d pages carry a plain-words narrative" % (pct, len(pages))

def prog_creative_surfaced():
    """Best practice: the creative lane is visible publicly on the same sun↔moon rhythm as civic."""
    ok = _has("sage_bridge.html", "sun↔moon overlap")
    if ok is None: return False, "sage_bridge not generated — skipped"
    return bool(ok), "creative offering surfaced on the Sage board" if ok else "creative overlap panel missing"

def prog_canon_backed_up():
    """Best practice: the model canon is backed up in the public repo (not only the project)."""
    ok = os.path.exists(os.path.join(REPO, "docs", "SAGE_REALM_MODEL.md"))
    return ok, "SAGE_REALM_MODEL.md is in the public repo" if ok else "canon not yet backed up to repo"

def prog_olelo_recipient():
    """Best practice: the ʻŌlelo verification has a real recipient so the weekly draft can be prepared."""
    p = os.path.join(MAUIOS, "olelo_terms.json")
    if not os.path.exists(p): return False, "olelo_terms.json not generated"
    try: rec = json.load(open(p, encoding="utf-8")).get("recipient")
    except Exception: rec = None
    return bool(rec), ("recipient set: " + rec) if rec else "no ʻŌiwi recipient set yet"

def prog_skills_refining():
    """Best practice: the skill set is refining cumulatively — selfheal_learn.py has watched the whole
    thread and each area of work carries learnings drawn from recurring asks + redirections + caught faults.
    Runs the learner (best-effort) so the count is fresh, then reads its registry. See SELFHEAL_COVENANT.md."""
    import subprocess, sys
    learner = os.path.join(HERE, "selfheal_learn.py")
    reg = os.path.join(PROJ, "reports", "_status", "selfheal_skills.json")
    try:
        subprocess.run([sys.executable, learner], cwd=HERE, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    if not os.path.exists(reg):
        reg = os.path.join(HERE, "selfheal_skills.json")
    try:
        sk = json.load(open(reg, encoding="utf-8"))
        skills = sk.get("skills", [])
        learnings = sum(len(s.get("learnings", [])) for s in skills)
        touches = sum(s.get("touches", 0) for s in skills)
        return (learnings >= len(skills) and touches > 0), \
            "%d skills refining · %d learnings from %d thread touches" % (len(skills), learnings, touches)
    except Exception as e:
        return False, "skills registry unreadable: %s" % e

def prog_tenant_depth():
    """Best practice: drive EVERY tenant toward Maui-deep testimony (Jimmy 2026-06-16). Runs tenant_depth.py
    and reports how many tenants reach the Maui reference depth — the civic 'prosecutorial push until balanced'."""
    import subprocess, sys as _sys
    td = os.path.join(HERE, "tenant_depth.py")
    rep = os.path.join(PROJ, "reports", "_status", "tenant_depth.json")
    try:
        subprocess.run([_sys.executable, td], cwd=HERE, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    if not os.path.exists(rep):
        return False, "tenant_depth not generated yet"
    try:
        d = json.load(open(rep, encoding="utf-8")); ref = d["maui_reference_depth"]
        at = sum(1 for t in d["tenants"] if t["covered"] >= ref)
        n = len(d["tenants"]); thin = len(d.get("flaws_thin", []))
        msg = "%d/%d tenants at Maui depth (%d dims); %d thin/placeholder" % (at, n, ref, thin)
        return (at >= n and thin == 0), msg
    except Exception as e:
        return False, "tenant_depth unreadable: %s" % e

def prog_minutes_reachability():
    """Best practice / curse-breaker (Jimmy 2026-06-16): keep TESTING every venue's real minutes document
    path — never write a venue off as 'no data' from an empty API field. Runs venue_minutes.py and reports
    how many venues' minutes are confirmed reachable. Self-healing: a venue that starts publishing flips on its own."""
    import subprocess, sys as _sys
    vm = os.path.join(HERE, "venue_minutes.py")
    rep = os.path.join(PROJ, "reports", "_status", "venue_minutes.json")
    try:
        subprocess.run([_sys.executable, vm], cwd=HERE, timeout=180,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    if not os.path.exists(rep):
        return False, "venue_minutes not generated yet"
    try:
        d = json.load(open(rep, encoding="utf-8"))
        nc = [r["venue"] for r in d["rows"] if r["minutes_reachable"] not in ("reachable",)]
        return (d["reachable"] >= d["venues"]), "%d/%d venues' minutes reachable; still to break: %s" % (
            d["reachable"], d["venues"], ", ".join(nc) or "none")
    except Exception as e:
        return False, "venue_minutes unreadable: %s" % e

def prog_freshness():
    """Best practice: the public record is alive — key reports regenerated recently."""
    import time
    keys = ["agenda_explainer.html", "sage_bridge.html", "olelo_glossary.html"]
    ages = []
    for k in keys:
        p = os.path.join(MAUIOS, k)
        if os.path.exists(p): ages.append((time.time() - os.path.getmtime(p)) / 86400.0)
    if not ages: return False, "no key reports found"
    oldest = max(ages)
    return (oldest <= 8.0), "oldest key report regenerated %.1f days ago" % oldest

PROGRESS = [
    ("Plain-words on every page",   prog_narrative_coverage),
    ("Creative lane surfaced",      prog_creative_surfaced),
    ("Model canon backed up",       prog_canon_backed_up),
    ("ʻŌlelo recipient set",        prog_olelo_recipient),
    ("Skills refining cumulatively", prog_skills_refining),
    ("Every tenant to Maui depth",  prog_tenant_depth),
    ("Minutes reachable per venue", prog_minutes_reachability),
    ("Record stays fresh",          prog_freshness),
]

def run():
    now = datetime.now(HST)
    results = []
    for name, fn in CHECKS:
        try: status, detail = fn()
        except Exception as e: status, detail = "FAIL", "check errored: %s" % e
        results.append({"check": name, "status": status, "detail": detail})
    summary = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "WARN", "FAIL")}
    # progress / best-practice meter (MET / TODO — advances the system, never blocks)
    prog = []
    for name, fn in PROGRESS:
        try: met, detail = fn()
        except Exception as e: met, detail = False, "check errored: %s" % e
        prog.append({"check": name, "status": "MET" if met else "TODO", "detail": detail})
    prog_met = sum(1 for p in prog if p["status"] == "MET")
    os.makedirs(MAUIOS, exist_ok=True)
    with open(os.path.join(MAUIOS, "selfheal.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"generated": now.isoformat(), "summary": summary, "results": results,
                   "progress": prog, "progress_met": prog_met, "progress_total": len(prog)},
                  f, ensure_ascii=False, indent=1)

    color = {"PASS": "#4ade80", "WARN": "#d9b24c", "FAIL": "#e06a4a", "MET": "#4ade80", "TODO": "#d9b24c"}
    rows = "".join(
        '<tr><td>%s</td><td style="color:%s;font-weight:700">%s</td><td class="d">%s</td></tr>' % (
            esc(r["check"]), color.get(r["status"], "#999"), r["status"], esc(r["detail"])) for r in results)
    prows = "".join(
        '<tr><td>%s</td><td style="color:%s;font-weight:700">%s</td><td class="d">%s</td></tr>' % (
            esc(p["check"]), color.get(p["status"], "#999"), p["status"], esc(p["detail"])) for p in prog)
    overall = "FAIL" if summary["FAIL"] else ("WARN" if summary["WARN"] else "PASS")
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>System integrity — govOS self-check</title><style>"
        "body{margin:0;background:#0e1311;color:#e8e4d6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.5}"
        ".wrap{max-width:900px;margin:0 auto;padding:26px 18px 60px}h1{font-size:23px;margin:.2em 0}"
        ".sub{color:#9a957f;font-size:14px;margin-bottom:18px}"
        ".badge{display:inline-block;padding:3px 12px;border-radius:20px;font-weight:700;font-size:13px}"
        "table{width:100%;border-collapse:collapse;font-size:14px;margin-top:16px}"
        "td{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.07);vertical-align:top}"
        ".d{color:#9a957f;font-size:13px}footer{margin-top:22px;color:#9a957f;font-size:12px}</style></head>"
        "<body><div class='wrap'><h1>govOS system integrity — self-check</h1>"
        "<div class='sub'>The system re-checks its own promises on every build · " + esc(now.strftime("%Y-%m-%d %H:%M HST")) + "</div>"
        "<span class='badge' style='background:" + color[overall] + ";color:#0e1311'>" + overall +
        "</span> &nbsp;<span style='color:#9a957f'>" + str(summary["PASS"]) + " pass · " + str(summary["WARN"]) +
        " warn · " + str(summary["FAIL"]) + " fail</span>"
        "<h2 style='font-size:15px;margin:20px 0 0;color:#cfc9b6'>Guards — promises we keep</h2>"
        "<table><tbody>" + rows + "</tbody></table>"
        "<h2 style='font-size:15px;margin:24px 0 0;color:#cfc9b6'>Progress — best practices we advance "
        "<span style='color:#9a957f;font-weight:400'>(" + str(prog_met) + "/" + str(len(prog)) + " met)</span></h2>"
        "<table><tbody>" + prows + "</tbody></table>"
        "<footer>Self-healing is two things: we keep what we promised (guards) and we keep getting better "
        "(progress). Private stays private, public stays public, the words are held under community review. · Kilo Aupuni</footer>"
        "</div></body></html>")
    with open(os.path.join(MAUIOS, "selfheal.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("selfheal: %s — %d pass / %d warn / %d fail · progress %d/%d" % (
        overall, summary["PASS"], summary["WARN"], summary["FAIL"], prog_met, len(prog)))
    for r in results:
        print("  [%s] %s — %s" % (r["status"], r["check"], r["detail"]))
    for p in prog:
        print("  [%s] %s — %s" % (p["status"], p["check"], p["detail"]))
    return overall

if __name__ == "__main__":
    run()
