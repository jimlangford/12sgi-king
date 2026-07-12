#!/usr/bin/env python3
"""media_catalog.py — structured per-item asset and platform tracking for the
12SGI publishing pipeline.

ROLE IN THE PIPELINE
────────────────────
Each content item (a video, civic explainer, studio reel, etc.) flows through:

  AI Generation → Draft Package → WordPress Draft → Owner Approval → Publish

This catalog tracks *where every item is* across that chain, so the
Launch Center panel can show one card per item with the full status of
every asset and every destination platform.

The catalog is append-only (JSONL): writes always add new records; the
current state of an item is always the *last* record for that item_id.
This mirrors the dispatch log pattern in services/v2_workboard.py.

STORAGE
───────
Default:  data/media_catalog.jsonl
Override: MEDIA_CATALOG_PATH env var

ITEM SCHEMA
───────────
{
  "item_id":         "<slug>",
  "title":           "...",
  "content_type":    "video|civic|studio|reel|social",
  "created_at":      "ISO timestamp",
  "updated_at":      "ISO timestamp",

  "assets": {
    "video_rendered":  true|false,
    "transcript":      true|false,
    "thumbnail":       true|false,
    "social_package":  true|false,
    "metadata":        true|false
  },

  "provenance": {
    "git_commit":       "...",
    "model_version":    "...",
    "generation_source":"..."
  },

  "wordpress": {
    "draft_id":   null|int,
    "draft_url":  "",
    "status":     "none|draft|published"
  },

  "platforms": {
    "youtube":   "none|queued|draft|published",
    "tiktok":    "none|queued|draft|published",
    "facebook":  "none|queued|draft|published",
    "instagram": "none|queued|draft|published",
    "linkedin":  "none|queued|draft|published",
    "bluesky":   "none|queued|draft|published",
    "x":         "none|queued|draft|published",
    "email":     "none|queued|draft|published"
  },

  "approvals": {
    "required":  ["editorial"],
    "cleared":   []
  },

  "workboard_job_id": null|"uuid",
  "published_urls":   {}
}

USAGE
─────
  from watchers.media_catalog import register_item, update_asset, update_platform
  from watchers.media_catalog import list_pending, list_ready, list_published, get_item

  # Register a new item
  item = register_item("reef-2026-07-11", "Reef", "video")

  # Mark an asset complete
  update_asset("reef-2026-07-11", "video_rendered", True)
  update_asset("reef-2026-07-11", "transcript", True)

  # Set platform status
  update_platform("reef-2026-07-11", "youtube", "draft")

  # Record an approval
  record_approval_cleared("reef-2026-07-11", "editorial")

  # Set WordPress draft
  set_wordpress_draft("reef-2026-07-11", draft_id=418, draft_url="https://12sgi.com/?p=418")

  # CLI summary
  python watchers/media_catalog.py --list
"""
from __future__ import annotations

import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_DEFAULT_CATALOG = ROOT / "data" / "media_catalog.jsonl"
CATALOG_PATH = Path(os.environ.get("MEDIA_CATALOG_PATH") or _DEFAULT_CATALOG)

PLATFORM_STATUSES = {"none", "queued", "draft", "published", "failed"}
CONTENT_TYPES = {"video", "civic", "studio", "reel", "social", "other"}

# Platforms the catalog tracks.  Presence here does NOT imply auto-posting
# capability — see docs/SOCIAL_CONNECTORS.md for what is automated vs. manual.
ALL_PLATFORMS = ("youtube", "tiktok", "facebook", "instagram", "linkedin", "bluesky", "x", "email")


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _blank_item(item_id: str, title: str, content_type: str) -> dict:
    ct = content_type.strip().lower()
    if ct not in CONTENT_TYPES:
        ct = "other"
    return {
        "item_id": item_id,
        "title": title,
        "content_type": ct,
        "created_at": _iso_now(),
        "updated_at": _iso_now(),
        "assets": {
            "video_rendered": False,
            "transcript": False,
            "thumbnail": False,
            "social_package": False,
            "metadata": False,
        },
        "provenance": {
            "git_commit": "",
            "model_version": "",
            "generation_source": "",
        },
        "wordpress": {
            "draft_id": None,
            "draft_url": "",
            "status": "none",
        },
        "platforms": {p: "none" for p in ALL_PLATFORMS},
        "approvals": {
            "required": ["editorial"],
            "cleared": [],
        },
        "workboard_job_id": None,
        "published_urls": {},
    }


def _write(record: dict, catalog: Path | None = None) -> None:
    path = catalog or CATALOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    record["updated_at"] = _iso_now()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_all(catalog: Path | None = None) -> list[dict]:
    path = catalog or CATALOG_PATH
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _current_state(catalog: Path | None = None) -> dict[str, dict]:
    """Build the current state map {item_id: latest_record} from the append log."""
    state: dict[str, dict] = {}
    for rec in _read_all(catalog):
        iid = rec.get("item_id")
        if iid:
            state[iid] = rec
    return state


# ─── Public API ──────────────────────────────────────────────────────────────

def register_item(
    item_id: str,
    title: str,
    content_type: str = "other",
    *,
    approval_types: list | None = None,
    provenance: dict | None = None,
    workboard_job_id: str | None = None,
    catalog: Path | None = None,
) -> dict:
    """Register a new content item or refresh an existing one.

    If the item already exists its latest state is loaded and only the
    fields explicitly passed are updated, preserving asset/platform progress.
    If it is new a blank record is created.
    """
    state = _current_state(catalog)
    if item_id in state:
        item = deepcopy(state[item_id])
        item["title"] = title
        item["content_type"] = content_type.strip().lower() or item["content_type"]
    else:
        item = _blank_item(item_id, title, content_type)

    if approval_types is not None:
        item["approvals"]["required"] = list(approval_types)
    if provenance:
        item["provenance"].update(provenance)
    if workboard_job_id:
        item["workboard_job_id"] = workboard_job_id

    _write(item, catalog)
    return item


def get_item(item_id: str, *, catalog: Path | None = None) -> dict | None:
    """Return the current state of a catalog item, or None if not found."""
    return _current_state(catalog).get(item_id)


def update_asset(
    item_id: str,
    asset_key: str,
    value: bool,
    *,
    catalog: Path | None = None,
) -> dict | None:
    """Set an asset flag (video_rendered / transcript / thumbnail / social_package / metadata)."""
    state = _current_state(catalog)
    item = state.get(item_id)
    if item is None:
        return None
    item = deepcopy(item)
    if asset_key in item["assets"]:
        item["assets"][asset_key] = bool(value)
    _write(item, catalog)
    return item


def update_platform(
    item_id: str,
    platform: str,
    status: str,
    *,
    published_url: str | None = None,
    catalog: Path | None = None,
) -> dict | None:
    """Update the status of a destination platform for an item."""
    plat = platform.strip().lower()
    stat = status.strip().lower()
    if stat not in PLATFORM_STATUSES:
        stat = "queued"
    state = _current_state(catalog)
    item = state.get(item_id)
    if item is None:
        return None
    item = deepcopy(item)
    if plat in item["platforms"]:
        item["platforms"][plat] = stat
    if published_url and stat == "published":
        item["published_urls"][plat] = published_url
    _write(item, catalog)
    return item


def set_wordpress_draft(
    item_id: str,
    *,
    draft_id: int | None = None,
    draft_url: str | None = None,
    status: str | None = None,
    catalog: Path | None = None,
) -> dict | None:
    """Record WordPress draft metadata for an item."""
    state = _current_state(catalog)
    item = state.get(item_id)
    if item is None:
        return None
    item = deepcopy(item)
    if draft_id is not None:
        item["wordpress"]["draft_id"] = draft_id
    if draft_url is not None:
        item["wordpress"]["draft_url"] = draft_url
    if status is not None:
        item["wordpress"]["status"] = status
    _write(item, catalog)
    return item


def record_approval_cleared(
    item_id: str,
    approval_type: str,
    *,
    catalog: Path | None = None,
) -> dict | None:
    """Mark an approval type as cleared for an item."""
    state = _current_state(catalog)
    item = state.get(item_id)
    if item is None:
        return None
    item = deepcopy(item)
    if approval_type not in item["approvals"]["cleared"]:
        item["approvals"]["cleared"].append(approval_type)
    _write(item, catalog)
    return item


def set_provenance(
    item_id: str,
    *,
    git_commit: str | None = None,
    model_version: str | None = None,
    generation_source: str | None = None,
    catalog: Path | None = None,
) -> dict | None:
    """Record provenance metadata for an item."""
    state = _current_state(catalog)
    item = state.get(item_id)
    if item is None:
        return None
    item = deepcopy(item)
    if git_commit is not None:
        item["provenance"]["git_commit"] = git_commit
    if model_version is not None:
        item["provenance"]["model_version"] = model_version
    if generation_source is not None:
        item["provenance"]["generation_source"] = generation_source
    _write(item, catalog)
    return item


# ─── Query helpers ────────────────────────────────────────────────────────────

def _assets_complete(item: dict) -> bool:
    return all(item.get("assets", {}).values())


def _approvals_complete(item: dict) -> bool:
    req = set(item.get("approvals", {}).get("required", ["editorial"]))
    cleared = set(item.get("approvals", {}).get("cleared", []))
    return req.issubset(cleared)


def list_all(*, catalog: Path | None = None) -> list[dict]:
    """Return all items in current state, newest-updated first."""
    items = list(_current_state(catalog).values())
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return items


def list_drafts(*, catalog: Path | None = None) -> list[dict]:
    """Items that have a WordPress draft but have not been fully approved yet."""
    return [
        i for i in list_all(catalog=catalog)
        if i.get("wordpress", {}).get("status") == "draft"
        and not _approvals_complete(i)
    ]


def list_ready(*, catalog: Path | None = None) -> list[dict]:
    """Items where all required approvals are cleared but nothing is published yet."""
    def _published(item: dict) -> bool:
        return any(v == "published" for v in item.get("platforms", {}).values()) or \
               item.get("wordpress", {}).get("status") == "published"

    return [
        i for i in list_all(catalog=catalog)
        if _approvals_complete(i) and not _published(i)
    ]


def list_published(*, catalog: Path | None = None) -> list[dict]:
    """Items that are live on at least one platform."""
    return [
        i for i in list_all(catalog=catalog)
        if any(v == "published" for v in i.get("platforms", {}).values())
        or i.get("wordpress", {}).get("status") == "published"
    ]


def list_needs_attention(*, catalog: Path | None = None) -> list[dict]:
    """Items with any platform in 'failed' status."""
    return [
        i for i in list_all(catalog=catalog)
        if any(v == "failed" for v in i.get("platforms", {}).values())
    ]


def summary(*, catalog: Path | None = None) -> dict:
    """Return a compact summary suitable for KING_DATA injection."""
    all_items = list_all(catalog=catalog)
    drafts = list_drafts(catalog=catalog)
    ready = list_ready(catalog=catalog)
    published = list_published(catalog=catalog)
    attention = list_needs_attention(catalog=catalog)
    return {
        "total": len(all_items),
        "drafts": len(drafts),
        "ready": len(ready),
        "published": len(published),
        "needs_attention": len(attention),
        "items": {
            "drafts": drafts,
            "ready": ready,
            "published": published,
            "needs_attention": attention,
        },
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _asset_glyph(val: bool) -> str:
    return "✓" if val else "○"


def _print_card(item: dict) -> None:
    assets = item.get("assets", {})
    wp = item.get("wordpress", {})
    approvals = item.get("approvals", {})
    plats = item.get("platforms", {})

    print(f"\n  ── {item.get('title', item['item_id'])} ─────────────────")
    print(f"     ID: {item['item_id']}  type: {item.get('content_type')}  updated: {item.get('updated_at', '')[:16]}")
    print(f"     Assets: video={_asset_glyph(assets.get('video_rendered'))}  "
          f"transcript={_asset_glyph(assets.get('transcript'))}  "
          f"thumbnail={_asset_glyph(assets.get('thumbnail'))}  "
          f"social={_asset_glyph(assets.get('social_package'))}  "
          f"meta={_asset_glyph(assets.get('metadata'))}")
    wp_status = wp.get("status", "none")
    wp_id = wp.get("draft_id", "")
    print(f"     WordPress: {wp_status}" + (f"  draft_id={wp_id}  {wp.get('draft_url','')}" if wp_id else ""))
    req = approvals.get("required", [])
    clr = approvals.get("cleared", [])
    print(f"     Approvals: required={req}  cleared={clr}")
    plat_line = "  ".join(f"{p}={v}" for p, v in plats.items() if v != "none")
    if plat_line:
        print(f"     Platforms: {plat_line}")
    prov = item.get("provenance", {})
    if any(prov.values()):
        print(f"     Provenance: commit={prov.get('git_commit','?')[:12]}  model={prov.get('model_version','?')}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="List all items")
    ap.add_argument("--summary", action="store_true", help="Print JSON summary")
    ap.add_argument("--item", default="", help="item_id to inspect")
    ap.add_argument("--register", default="", metavar="ITEM_ID", help="Register a new item (requires --title)")
    ap.add_argument("--title", default="", help="Title for --register")
    ap.add_argument("--type", default="other", dest="content_type", help="Content type for --register")
    ap.add_argument("--set-asset", nargs=2, metavar=("KEY", "TRUE/FALSE"),
                    help="Set an asset flag: --set-asset video_rendered true --item ITEM_ID")
    ap.add_argument("--set-platform", nargs=2, metavar=("PLATFORM", "STATUS"),
                    help="Set platform status: --set-platform youtube draft --item ITEM_ID")
    ap.add_argument("--set-wp-draft", nargs=2, metavar=("DRAFT_ID", "DRAFT_URL"),
                    help="Record WordPress draft: --set-wp-draft 418 https://... --item ITEM_ID")
    ap.add_argument("--approve", default="", metavar="APPROVAL_TYPE",
                    help="Mark an approval type cleared: --approve editorial --item ITEM_ID")
    ap.add_argument("--catalog", default="", help="Override catalog path")

    args = ap.parse_args()
    cat = Path(args.catalog) if args.catalog else None

    if args.summary:
        print(json.dumps(summary(catalog=cat), indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.list:
        items = list_all(catalog=cat)
        if not items:
            print("No items in catalog.")
        else:
            print(f"{len(items)} item(s):")
            for it in items:
                _print_card(it)
        sys.exit(0)

    if args.item and not any([args.set_asset, args.set_platform, args.set_wp_draft, args.approve]):
        it = get_item(args.item, catalog=cat)
        if it:
            _print_card(it)
        else:
            print(f"Item not found: {args.item}")
        sys.exit(0)

    if args.register:
        if not args.title:
            print("--title is required with --register")
            sys.exit(1)
        it = register_item(args.register, args.title, args.content_type, catalog=cat)
        print(f"Registered: {it['item_id']}")
        sys.exit(0)

    if args.set_asset:
        if not args.item:
            print("--item is required with --set-asset")
            sys.exit(1)
        key, val = args.set_asset
        result = update_asset(args.item, key, val.lower() in ("1", "true", "yes"), catalog=cat)
        if result:
            print(f"Updated asset {key} on {args.item}")
        else:
            print(f"Item not found: {args.item}")
        sys.exit(0)

    if args.set_platform:
        if not args.item:
            print("--item is required with --set-platform")
            sys.exit(1)
        plat, stat = args.set_platform
        result = update_platform(args.item, plat, stat, catalog=cat)
        if result:
            print(f"Updated platform {plat}={stat} on {args.item}")
        else:
            print(f"Item not found: {args.item}")
        sys.exit(0)

    if args.set_wp_draft:
        if not args.item:
            print("--item is required with --set-wp-draft")
            sys.exit(1)
        did, durl = args.set_wp_draft
        result = set_wordpress_draft(args.item, draft_id=int(did), draft_url=durl, status="draft", catalog=cat)
        if result:
            print(f"WordPress draft set on {args.item}: id={did}")
        else:
            print(f"Item not found: {args.item}")
        sys.exit(0)

    if args.approve:
        if not args.item:
            print("--item is required with --approve")
            sys.exit(1)
        result = record_approval_cleared(args.item, args.approve, catalog=cat)
        if result:
            print(f"Approval '{args.approve}' cleared on {args.item}")
        else:
            print(f"Item not found: {args.item}")
        sys.exit(0)

    ap.print_help()
    sys.exit(0)
