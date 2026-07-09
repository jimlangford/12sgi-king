#!/usr/bin/env python3
"""maui_causes_feed.py — Daily ingestion of Maui Causes RSS feed.

Maui Causes (https://mauicauses.org) is a civic media partner:
crowd-funded media for Maui accountability — government transparency,
developer oversight, water rights, environmental protection.
Sam Small is the primary content creator.

This tool:
  1. Fetches the RSS feed (mauicauses.org/feed/)
  2. Parses posts into structured JSON
  3. Generates a daily brief section for the civic dashboard
  4. Writes to reports/civic/maui_causes_<date>.json
  5. Updates site/maui-causes.html for the King site

Usage:
  python tools/kilo-aupuni/maui_causes_feed.py            # fetch + report
  python tools/kilo-aupuni/maui_causes_feed.py --dry      # no writes, print only
  python tools/kilo-aupuni/maui_causes_feed.py --html     # also write site page

Called daily by maintenance.py alongside daily_brief.py.

ATTRIBUTION: All content is sourced from and attributed to mauicauses.org.
Never republish without attribution. Never claim as kilo-aupuni findings.
Cross-reference allowed: if MauiCauses posts about a council member,
the civic channel can note "Maui Causes reported on [X] — see mauicauses.org."
"""
import os, sys, re, json, argparse, urllib.request, urllib.error
from datetime import datetime

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.dirname(os.path.dirname(HERE))
OUTDIR = os.path.join(ROOT, "reports", "civic")
SITE   = os.path.join(ROOT, "site")

RSS_URL     = "https://mauicauses.org/feed/"
YT_RSS_URL  = "https://www.youtube.com/feeds/videos.xml?channel_id=UCHa_XMCaQ9M1TRSlbCBNUlw"
YT_HANDLE   = "@samsmall808"
YT_CHANNEL  = "UCHa_XMCaQ9M1TRSlbCBNUlw"
ORG_URL     = "https://mauicauses.org"
ORG_NAME    = "Maui Causes"
ORG_BYLINE  = "Crowd-funded media for Maui's accountability"


def fetch_rss(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "elementLOTUS civic reader/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        print(f"[maui-causes] RSS fetch failed: {e}", flush=True)
        return None


def clean(text):
    text = re.sub(r'<[^>]+>', '', text)
    for code, rep in [("&amp;", "&"), ("&#038;", "&"), ("&#8217;", "'"),
                      ("&#8220;", '"'), ("&#8221;", '"'), ("&#8211;", "–"), ("&lt;","<"), ("&gt;",">")]:
        text = text.replace(code, rep)
    return text.strip()


def parse_rss(xml_text):
    """Parse RSS/Atom XML into list of post dicts. No external deps."""
    if not xml_text:
        return []
    # WordPress RSS
    items = re.findall(r'<item>(.*?)</item>', xml_text, re.DOTALL)
    if items:
        posts = []
        for item in items:
            def tag(name):
                m = re.search(rf'<{name}(?:[^>]*)>(.*?)</{name}>', item, re.DOTALL)
                return clean(m.group(1)) if m else ""
            title   = tag("title")
            link    = tag("link")
            pubdate = tag("pubDate")
            desc    = clean(tag("description"))[:280]
            author  = tag("dc:creator") or "Sam Small"
            cats_raw = re.findall(r'<category[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</category>', item, re.DOTALL)
            cats    = [clean(c) for c in cats_raw]
            if title and link:
                posts.append({
                    "title": title, "url": link, "date": pubdate[:16],
                    "author": author, "excerpt": desc, "categories": cats, "type": "article",
                })
        return posts[:10]
    # YouTube Atom feed
    entries = re.findall(r'<entry>(.*?)</entry>', xml_text, re.DOTALL)
    posts = []
    for entry in entries:
        def etag(name):
            m = re.search(rf'<{name}(?:[^>]*)>(.*?)</{name}>', entry, re.DOTALL)
            return clean(m.group(1)) if m else ""
        vid_id = etag("yt:videoId")
        title  = etag("title")
        pub    = etag("published")
        if vid_id and title:
            posts.append({
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "video_id": vid_id,
                "date": pub[:10],
                "author": "Sam Small",
                "excerpt": f"YouTube video — {title}",
                "categories": ["YouTube", "Video"],
                "type": "video",
            })
    return posts[:15]  # top 15 YouTube videos


def write_json(posts, dry=False):
    os.makedirs(OUTDIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    outfile = os.path.join(OUTDIR, f"maui_causes_{today}.json")
    data = {
        "source": ORG_NAME,
        "source_url": ORG_URL,
        "fetched": today,
        "attribution": "All content © Maui Causes / Sam Small. Used for civic cross-reference only.",
        "posts": posts,
    }
    if dry:
        print(json.dumps(data, indent=2)[:2000])
        return outfile
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[maui-causes] Saved {len(posts)} posts → {outfile}", flush=True)
    return outfile


def write_html(posts, dry=False):
    """Write/update site/maui-causes.html for the King civic site."""
    today = datetime.now().strftime("%B %d, %Y")
    rows = ""
    for p in posts:
        cats = ", ".join(p["categories"][:3]) if p["categories"] else "Civic"
        rows += f"""
      <article class="mc-post">
        <div class="mc-meta"><span class="mc-date">{p['date'][:10]}</span> · <span class="mc-cat">{cats}</span></div>
        <h3 class="mc-title"><a href="{p['url']}" target="_blank" rel="noopener">{p['title']}</a></h3>
        <p class="mc-excerpt">{p['excerpt'][:200]}…</p>
        <a class="mc-readmore" href="{p['url']}" target="_blank" rel="noopener">Read on Maui Causes →</a>
      </article>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Maui Causes — Community Partner | 12sgi King</title>
  <meta name="description" content="Maui Causes: crowd-funded civic media for Maui's accountability. Latest posts from Sam Small.">
  <style>
    :root {{
      --bg: #0e0e12; --surface: #1a1a24; --gold: #e3ad33;
      --text: #e8e4d9; --muted: #8a8580; --border: #2a2a38;
      font-family: 'JetBrains Mono', 'Courier New', monospace;
    }}
    body {{ background: var(--bg); color: var(--text); margin: 0; padding: 0; }}
    .page-header {{
      background: var(--surface); border-bottom: 1px solid var(--border);
      padding: 2rem 1.5rem 1.5rem;
    }}
    .page-header h1 {{ color: var(--gold); margin: 0 0 0.5rem; font-size: 1.4rem; }}
    .page-header p {{ color: var(--muted); margin: 0; font-size: 0.85rem; }}
    .partner-note {{
      background: var(--surface); border-left: 3px solid var(--gold);
      margin: 1.5rem; padding: 1rem 1.2rem; font-size: 0.85rem; color: var(--muted);
    }}
    .partner-note a {{ color: var(--gold); }}
    .posts {{ padding: 0 1.5rem 3rem; }}
    .mc-post {{
      border-bottom: 1px solid var(--border); padding: 1.2rem 0;
    }}
    .mc-meta {{ font-size: 0.75rem; color: var(--muted); margin-bottom: 0.4rem; }}
    .mc-title {{ margin: 0 0 0.5rem; font-size: 1rem; }}
    .mc-title a {{ color: var(--text); text-decoration: none; }}
    .mc-title a:hover {{ color: var(--gold); }}
    .mc-excerpt {{ color: var(--muted); font-size: 0.82rem; margin: 0 0 0.5rem; line-height: 1.5; }}
    .mc-readmore {{ color: var(--gold); font-size: 0.78rem; text-decoration: none; }}
    .attribution {{ text-align: center; padding: 2rem 1.5rem; color: var(--muted); font-size: 0.75rem; }}
    .attribution a {{ color: var(--gold); }}
    .updated {{ color: var(--muted); font-size: 0.72rem; }}
  </style>
</head>
<body>
  <div class="page-header">
    <h1>Maui Causes</h1>
    <p>{ORG_BYLINE} · <a href="{ORG_URL}" style="color:var(--gold)" target="_blank" rel="noopener">mauicauses.org</a></p>
    <p class="updated">Updated {today}</p>
  </div>

  <div class="partner-note">
    Maui Causes is an independent civic media organization producing community accountability journalism.
    Content below is sourced from <a href="{ORG_URL}" target="_blank">mauicauses.org</a> and is
    attributed to its authors. 12sgi King links here as a civic community resource, not an endorsement.
    Support their work directly at <a href="{ORG_URL}" target="_blank">mauicauses.org</a>.
  </div>

  <div class="posts">
    <h2 style="color:var(--gold);font-size:0.9rem;margin-bottom:0.5rem;">LATEST FROM MAUI CAUSES</h2>
    {rows}
  </div>

  <div class="attribution">
    All content © Maui Causes / Sam Small · <a href="{ORG_URL}" target="_blank">mauicauses.org</a><br>
    This page auto-updates daily via the 12sgi civic intelligence system.
  </div>
</body>
</html>"""

    outfile = os.path.join(SITE, "maui-causes.html")
    if dry:
        print(html[:500] + "\n...[dry run, not writing]")
        return outfile
    os.makedirs(SITE, exist_ok=True)
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[maui-causes] Site page → {outfile}", flush=True)
    return outfile


def main():
    ap = argparse.ArgumentParser(description="Maui Causes + @samsmall808 daily feed ingestion")
    ap.add_argument("--dry",  action="store_true", help="No writes — print only")
    ap.add_argument("--html", action="store_true", help="Also write site/maui-causes.html")
    args = ap.parse_args()

    # Blog posts
    print(f"[maui-causes] Blog: {RSS_URL}", flush=True)
    blog_xml = fetch_rss(RSS_URL)
    blog_posts = parse_rss(blog_xml) if blog_xml else []
    print(f"[maui-causes] {len(blog_posts)} blog posts", flush=True)

    # YouTube videos (@samsmall808)
    print(f"[maui-causes] YouTube: {YT_RSS_URL}", flush=True)
    yt_xml = fetch_rss(YT_RSS_URL)
    yt_posts = parse_rss(yt_xml) if yt_xml else []
    print(f"[maui-causes] {len(yt_posts)} YouTube videos", flush=True)

    all_posts = blog_posts + yt_posts
    # Sort by date descending (ISO date strings sort naturally)
    all_posts.sort(key=lambda p: p.get("date", ""), reverse=True)

    for p in all_posts[:5]:
        icon = "▶" if p.get("type") == "video" else "✍"
        print(f"  {icon} {p['date'][:10]}  {p['title'][:65]}")

    if not all_posts:
        print("[maui-causes] No posts fetched — check connectivity.", flush=True)
        return 1

    write_json(all_posts, dry=args.dry)
    if args.html or not args.dry:
        write_html(all_posts, dry=args.dry)

    print(f"[maui-causes] {len(blog_posts)} articles + {len(yt_posts)} videos = {len(all_posts)} total", flush=True)
    print(f"[maui-causes] Watch: @samsmall808 (UC: {YT_CHANNEL})", flush=True)
    print(f"[maui-causes] NOTE: Past catalog (full history) requires YouTube Data API v3.", flush=True)
    print(f"[maui-causes] File a WBITEM to request API key or manual export for legal archive.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
