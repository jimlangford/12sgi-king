"""
blog_engine.py — Generate blog.html from config/blog_posts.json.
Outputs to the king-local deploy directory and serves via King server /king/blog.
Vendored at repo root for CI (build-mirror; source = project tools/ops/blog_engine.py) —
same pattern as civic_shell.py. blog_posts_seed.json sits alongside it as the CI fallback
data source (a public-safe, published-only snapshot) since CI has no access to the live
project's config/ directory.

Usage:
  python tools/ops/blog_engine.py           # generate blog.html
  python tools/ops/blog_engine.py --list    # list posts
"""
import os, sys, json, datetime, argparse

ROOT     = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG   = os.path.join(ROOT, "config")
POSTS_F  = os.path.join(CONFIG, "blog_posts.json")
# CI FALLBACK (Jimmy 2026-07-02 heal-forward): the live blog_posts.json only exists on the laptop.
# build_site.py's push-triggered CI run has no access to $PROJECT/config/, so blog.html silently never
# got written on a CI-only deploy (404 on the public site) -- same class of gap as civic_shell.py,
# which is "vendored at repo root for CI". blog_posts_seed.json is a same-directory, public-safe
# (published-only) snapshot committed alongside the vendored copy of THIS file at the 12sgi-king repo
# root; falls back to it only when the live config file isn't present.
SEED_POSTS_F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blog_posts_seed.json")

KING_LOCAL = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "king-extract", "deploy", "king-local"
)
OUT_HTML = os.path.join(KING_LOCAL, "blog.html")

# ── Design tokens (matches quados_dashboard) ──────────────────────────────
CSS = """
:root{--bg:#0a0805;--surf:#161210;--surf2:#1e1810;--gold:#c8a060;--text:#e8dcc8;--muted:#8a7a6a;--border:rgba(200,160,96,.2);--red:#c04040;--grn:#3a8a60}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:-apple-system,'Segoe UI',sans-serif;font-size:15px;line-height:1.65;padding-top:46px;min-height:100vh}
a{color:var(--gold);text-decoration:none}a:hover{text-decoration:underline}
/* NAV */
nav{position:fixed;top:0;left:0;right:0;height:46px;background:var(--surf);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 20px;gap:2px;z-index:100;font-size:13px}
nav a{color:var(--muted);text-decoration:none;padding:5px 10px;border-radius:5px}
nav a:hover{color:var(--text);background:rgba(200,160,96,.1)}
.brand{color:var(--gold)!important;font-weight:700;letter-spacing:.06em;margin-right:10px;font-size:15px}
/* LAYOUT */
.wrap{max-width:760px;margin:0 auto;padding:40px 20px 80px}
.page-head{margin-bottom:36px;padding-bottom:20px;border-bottom:1px solid var(--border)}
.page-title{font-size:26px;font-weight:700;color:var(--gold);letter-spacing:.03em}
.page-sub{font-size:13px;color:var(--muted);margin-top:6px}
/* POST CARD (list view) */
.post-card{background:var(--surf);border:1px solid var(--border);border-radius:8px;padding:22px 24px;margin-bottom:16px;transition:border-color .15s}
.post-card:hover{border-color:var(--gold)}
.post-date{font-size:11px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;margin-bottom:8px}
.post-title{font-size:20px;font-weight:700;color:var(--text);margin-bottom:6px;line-height:1.3}
.post-title a{color:var(--text)}
.post-title a:hover{color:var(--gold)}
.post-subtitle{font-size:13px;color:var(--muted);margin-bottom:10px}
.post-summary{font-size:14px;color:var(--text);line-height:1.6;opacity:.9}
.post-tags{margin-top:12px;display:flex;gap:6px;flex-wrap:wrap}
.tag{font-size:10px;padding:2px 8px;border-radius:10px;border:1px solid var(--border);color:var(--muted);letter-spacing:.04em}
.read-link{margin-top:14px;font-size:13px;color:var(--gold)}
/* POST FULL (article view) */
.article-head{margin-bottom:32px}
.article-title{font-size:30px;font-weight:700;color:var(--gold);line-height:1.25;margin-bottom:8px}
.article-subtitle{font-size:16px;color:var(--muted);margin-bottom:10px}
.article-meta{font-size:11px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;font-family:'JetBrains Mono',monospace}
.article-body{margin-top:28px}
.article-body p{margin-bottom:18px;font-size:15px;line-height:1.75}
.article-body h2{font-size:18px;font-weight:700;color:var(--gold);margin:28px 0 10px;letter-spacing:.02em}
.article-body blockquote{border-left:3px solid var(--gold);padding:10px 18px;margin:22px 0;color:var(--muted);font-style:italic;font-size:15px;background:var(--surf2);border-radius:0 6px 6px 0}
.lede{font-size:17px;line-height:1.8;color:var(--text);margin-bottom:22px;font-weight:400}
.cta-block{background:var(--surf2);border:1px solid var(--border);border-radius:8px;padding:18px 22px;margin-top:30px;font-size:14px;line-height:1.65;color:var(--muted)}
.back{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--muted);margin-bottom:28px}
.back:hover{color:var(--gold)}
"""

def nav_html(static=False):
    # HEAL-FORWARD (2026-07-01, server-quad-os): the private nav hardcoded /king/quados_dashboard.html
    # and /king/studio.html — both resolve fine on the private king_serve.py server but do not exist
    # anywhere in the public GitHub Pages build (king_public_src/ has no such files), so every public
    # blog page shipped two permanently dead links. static=True drops them rather than guessing a
    # substitute (never fabricate a destination), and uses relative paths ("king/", "blog.html") so the
    # nav also resolves correctly if the site is ever reached via the raw github.io project-pages URL
    # instead of the 12sgi.com custom domain — the same subpath-safe convention GitHub Pages/Jekyll
    # projects use (relative links survive both serving contexts; root-relative links do not).
    if static:
        return """<nav>
  <a href="king/" class="brand">KING</a>
  <a href="blog.html" style="color:var(--gold)">Blog</a>
</nav>"""
    return """<nav>
  <a href="/king/" class="brand">KING</a>
  <a href="/king/quados_dashboard.html">Dashboard</a>
  <a href="/king/blog" style="color:var(--gold)">Blog</a>
  <a href="/king/studio.html">Studio</a>
</nav>"""


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_body_block(block):
    t = block.get("type", "p")
    text = esc(block.get("text", ""))
    if t == "lede":
        return f'<p class="lede">{text}</p>'
    if t == "p":
        return f"<p>{text}</p>"
    if t == "h2":
        return f"<h2>{text}</h2>"
    if t == "blockquote":
        return f"<blockquote>{text}</blockquote>"
    if t == "cta":
        return f'<div class="cta-block">{text}</div>'
    return f"<p>{text}</p>"


def render_post_card(post, static=False):
    # HEAL-FORWARD (Jimmy 2026-07-01): the private king-local surface links posts via the dynamic
    # /king/blog?post=<slug> route (king_serve.py renders it server-side). That scheme does not exist
    # on the PUBLIC static site (GitHub Pages has no server to interpret it), so every mirrored post
    # became a permanent orphan the moment it published -- static=True renders the REAL static
    # filename (blog_post_<slug>.html) that build_site.py already writes to disk right next to it.
    date_str = post.get("date", "")
    title    = esc(post.get("title", ""))
    subtitle = esc(post.get("subtitle", ""))
    summary  = esc(post.get("summary", ""))
    slug     = post.get("slug", post.get("id", ""))
    tags     = post.get("tags", [])
    tag_html = "".join(f'<span class="tag">{esc(t)}</span>' for t in tags)
    href = f"blog_post_{slug}.html" if static else f"/king/blog?post={slug}"
    return f"""<div class="post-card">
  <div class="post-date">{date_str}</div>
  <div class="post-title"><a href="{href}">{title}</a></div>
  <div class="post-subtitle">{subtitle}</div>
  <div class="post-summary">{summary}</div>
  <div class="post-tags">{tag_html}</div>
  <div class="read-link"><a href="{href}">Read →</a></div>
</div>"""


def render_full_post(post, static=False):
    date_str = post.get("date", "")
    author   = esc(post.get("author", ""))
    title    = esc(post.get("title", ""))
    subtitle = esc(post.get("subtitle", ""))
    body     = post.get("body", [])
    if isinstance(body, str):
        body_html = "\n".join(
            f"<p>{esc(para.strip())}</p>"
            for para in body.split("\n\n") if para.strip()
        )
    else:
        body_html = "\n".join(render_body_block(b) for b in body)
    back_href = "blog.html" if static else "/king/blog"
    return f"""<a href="{back_href}" class="back">← All posts</a>
<div class="article-head">
  <div class="article-title">{title}</div>
  <div class="article-subtitle">{subtitle}</div>
  <div class="article-meta">{date_str} · {author}</div>
</div>
<div class="article-body">{body_html}</div>"""


def render_list_page(posts, static=False):
    cards = "\n".join(render_post_card(p, static=static) for p in posts if p.get("status") == "published")
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8">
<style id="mobile-heal">img,video,svg{{max-width:100%;height:auto}}</style>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blog — elementLOTUS</title>
<style>{CSS}</style>
</head>
<body>
{nav_html(static)}
<div class="wrap">
  <div class="page-head">
    <div class="page-title">Blog</div>
    <div class="page-sub">Studio notes · creative methodology · production dispatches</div>
  </div>
  {cards}
</div>
</body></html>"""


def render_post_page(post, static=False):
    title = post.get("title", "elementLOTUS Blog")
    body  = render_full_post(post, static=static)
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8">
<style id="mobile-heal">img,video,svg{{max-width:100%;height:auto}}</style>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — elementLOTUS</title>
<style>{CSS}</style>
</head>
<body>
{nav_html(static)}
<div class="wrap">{body}</div>
</body></html>"""


def load_posts():
    src = POSTS_F if os.path.exists(POSTS_F) else SEED_POSTS_F
    if not os.path.exists(src):
        return []
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("posts", [])


def generate():
    posts = load_posts()
    published = [p for p in posts if p.get("status") == "published"]
    published.sort(key=lambda p: p.get("date", ""), reverse=True)

    if not os.path.isdir(KING_LOCAL):
        print(f"blog_engine: king-local not found at {KING_LOCAL} — skipping write")
        return None

    # Write list page
    list_html = render_list_page(published)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(list_html)
    print(f"blog_engine: wrote {OUT_HTML} ({len(published)} posts)")

    # Write individual post pages
    for post in published:
        slug    = post.get("slug", post.get("id", ""))
        post_f  = os.path.join(KING_LOCAL, f"blog_post_{slug}.html")
        post_html = render_post_page(post)
        with open(post_f, "w", encoding="utf-8") as f:
            f.write(post_html)
        print(f"blog_engine: wrote {post_f}")

    return OUT_HTML


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        posts = load_posts()
        print(f"{len(posts)} post(s):")
        for p in posts:
            print(f"  [{p.get('status','?')}] {p.get('date','')} — {p.get('title','')}")
        return

    out = generate()
    if out:
        print(f"Blog live at: https://king.tail760750.ts.net/king/blog")


if __name__ == "__main__":
    main()
