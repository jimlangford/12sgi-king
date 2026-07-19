#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a WordPress-ready Element Lotus rebuild bundle from the public shell source.

The actual rebuild happens in WordPress itself. This tool keeps the repository as the source
blueprint by turning the static Element Lotus shell into page fragments + scoped CSS that can be
copied into WordPress pages/templates without exposing private or operational surfaces.

Output:
  content/wordpress/element_lotus/
    - additional-css.css
    - manifest.json
    - front-page.html
    - about.html
    - contact.html
    - films.html
    - music.html
    - civic.html
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "element_lotus_public"
OUT_DIR = ROOT / "content" / "wordpress" / "element_lotus"
CSS_PREFIX = ".element-lotus-shell"
STATIC_BRIDGE = "https://12sgi.com/"

PAGES = (
    {"source": "index.html", "slug": "/", "output": "front-page.html", "template": "front-page"},
    {"source": "about.html", "slug": "/about/", "output": "about.html", "template": "default"},
    {"source": "contact.html", "slug": "/contact/", "output": "contact.html", "template": "default"},
    {"source": "films.html", "slug": "/films/", "output": "films.html", "template": "default"},
    {"source": "music.html", "slug": "/music/", "output": "music.html", "template": "default"},
    {"source": "civic.html", "slug": "/civic/", "output": "civic.html", "template": "default"},
)

ABSOLUTE_REWRITES = {
    "partner.html": STATIC_BRIDGE + "partner.html",
    "reports.html": STATIC_BRIDGE + "reports.html",
    "jurisdictions.html": STATIC_BRIDGE + "jurisdictions.html",
    "testify.html": STATIC_BRIDGE + "testify.html",
}

PREFIX_REWRITES = (
    ("games/", STATIC_BRIDGE + "games/"),
    ("sage/", STATIC_BRIDGE + "sage/"),
)

INTERNAL_PAGE_REWRITES = {
    "index.html": "/",
    "about.html": "/about/",
    "contact.html": "/contact/",
    "films.html": "/films/",
    "music.html": "/music/",
    "civic.html": "/civic/",
}


def _extract(pattern: str, text: str, label: str) -> str:
    match = re.search(pattern, text, re.I | re.S)
    if not match:
        raise ValueError(f"Could not find {label}")
    return match.group(1).strip()


def extract_page_parts(html_text: str) -> dict[str, str]:
    return {
        "title": _extract(r"<title[^>]*>(.*?)</title>", html_text, "title"),
        "description": _extract(
            r'<meta\s+name="description"\s+content="([^"]*)"\s*/?>',
            html_text,
            "meta description",
        ),
        "body": _extract(r"<body[^>]*>(.*?)</body>", html_text, "body"),
    }


def rewrite_url(url: str) -> str:
    if not url or re.match(r"^(?:[a-z]+:|#|//)", url, re.I):
        return url
    if url.startswith("../site/"):
        return STATIC_BRIDGE + url[len("../site/"):]
    if url.startswith("../"):
        return STATIC_BRIDGE + url[len("../"):]
    if url in INTERNAL_PAGE_REWRITES:
        return INTERNAL_PAGE_REWRITES[url]
    if url in ABSOLUTE_REWRITES:
        return ABSOLUTE_REWRITES[url]
    for old, new in PREFIX_REWRITES:
        if url.startswith(old):
            return new + url[len(old):]
    return url


def rewrite_links(html_text: str) -> str:
    attr_re = re.compile(r'(\b(?:href|src)\s*=\s*")([^"]+)(")', re.I)

    def _replace(match: re.Match[str]) -> str:
        return f'{match.group(1)}{rewrite_url(match.group(2))}{match.group(3)}'

    return attr_re.sub(_replace, html_text)


def _find_matching_brace(text: str, open_index: int) -> int:
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("Unbalanced CSS braces")


def _prefix_selector_list(selector_text: str, prefix: str) -> str:
    prefixed = []
    seen = set()
    for raw in selector_text.split(","):
        selector = raw.strip()
        if not selector:
            continue
        if selector in (":root", "html", "body"):
            mapped = prefix
        elif selector.startswith(prefix):
            mapped = selector
        else:
            mapped = f"{prefix} {selector}"
        if mapped not in seen:
            seen.add(mapped)
            prefixed.append(mapped)
    return ", ".join(prefixed)


def prefix_css(css_text: str, prefix: str = CSS_PREFIX) -> str:
    out = []
    i = 0
    n = len(css_text)
    while i < n:
        open_index = css_text.find("{", i)
        if open_index == -1:
            tail = css_text[i:].strip()
            if tail:
                out.append(tail)
            break
        selector = css_text[i:open_index].strip()
        close_index = _find_matching_brace(css_text, open_index)
        block = css_text[open_index + 1:close_index]
        if selector.startswith("@media") or selector.startswith("@supports"):
            out.append(f"{selector}{{{prefix_css(block, prefix)}}}")
        elif selector.startswith("@"):
            out.append(f"{selector}{{{block}}}")
        else:
            out.append(f"{_prefix_selector_list(selector, prefix)}{{{block}}}")
        i = close_index + 1
    return "\n".join(out) + "\n"


def build_page_fragment(source_name: str, slug: str, template: str, html_text: str) -> dict[str, str]:
    parts = extract_page_parts(html_text)
    body = "\n".join(line.rstrip() for line in rewrite_links(parts["body"]).splitlines())
    fragment = (
        f"<!-- wp:group {{\"tagName\":\"div\",\"className\":\"element-lotus-shell-wrap\"}} -->\n"
        f"<div class=\"element-lotus-shell-wrap\">\n"
        f"<!-- element_lotus_public/{source_name} | slug: {slug} | template: {template} -->\n"
        f"<div class=\"element-lotus-shell\" data-source=\"element_lotus_public/{source_name}\">\n"
        f"{body}\n"
        f"</div>\n"
        f"</div>\n"
        f"<!-- /wp:group -->\n"
    )
    return {
        "title": parts["title"],
        "description": parts["description"],
        "fragment": fragment,
    }


def build(src_dir: Path = SRC_DIR, out_dir: Path = OUT_DIR) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    css_text = (src_dir / "studio.css").read_text(encoding="utf-8")
    (out_dir / "additional-css.css").write_text(prefix_css(css_text), encoding="utf-8", newline="\n")
    manifest = {
        "source": str(src_dir),
        "output": str(out_dir),
        "css": "additional-css.css",
        "pages": [],
    }
    for page in PAGES:
        src_path = src_dir / page["source"]
        built = build_page_fragment(
            source_name=page["source"],
            slug=page["slug"],
            template=page["template"],
            html_text=src_path.read_text(encoding="utf-8"),
        )
        out_file = out_dir / page["output"]
        out_file.write_text(built["fragment"], encoding="utf-8", newline="\n")
        manifest["pages"].append({
            "source": page["source"],
            "slug": page["slug"],
            "template": page["template"],
            "title": built["title"],
            "description": built["description"],
            "output": page["output"],
        })
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


if __name__ == "__main__":
    manifest = build()
    print("deploy_elementlotus_wp: built WordPress rebuild bundle ->", OUT_DIR)
    print("  pages:", len(manifest["pages"]))
    print("  css: additional-css.css")
    print("  NEXT: paste/apply the bundle from", OUT_DIR, "into WordPress after any element_lotus_public/ change")
