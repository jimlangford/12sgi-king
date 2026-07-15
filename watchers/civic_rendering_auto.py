#!/usr/bin/env python3
"""
civic_rendering_auto.py — Automatic civic schedule rendering + tenant page projection + Tailscale linker

Purpose:
  Bridge civic schedule data (calendar_civic.py output) → tenant backend (v2 tenant service)
  → redesigned civic pages → Tailscale URLs for instant tenant access.

  This creates a closed loop:
  1. Civic schedule events (civic_calendar.py) → json queue
  2. Tenant backend ingests events → stores as tenant-accessible civic_signals
  3. Redesigned pages (element_lotus_public/civic.html) auto-render from tenant API
  4. Tailscale URL generator creates shareable links → owner console + email

Workflow:
  1. calendar_civic.py generates civic_calendar_queue.json (meetings, deadlines, reviews)
  2. civic_rendering_auto.py ingests that queue → projects to tenant civic_signals table
  3. civic_metrics_api.py (new) exposes GET /api/v2/civic/public-metrics (live data)
  4. element_lotus_public/civic.html fetches metrics → renders live dashboard
  5. civic_rendering_auto.py generates Tailscale URLs → posts to owner console + dispatch

Integrations:
  - Tenant service: POST /api/v2/civic-signals (new) — store public civic events
  - Metrics API: GET /api/v2/civic/public-metrics (new) — live dashboard data
  - Element Lotus: element_lotus_public/civic.html auto-renders (updated)
  - Tailscale: generates URLs like https://king.tail760750.ts.net/civic/...
  - Event bus: publishes civic.event.rendered, civic.metrics.updated

Run:
  python watchers/civic_rendering_auto.py        # one-shot render + projection
  python watchers/civic_rendering_auto.py --watch # daemon mode (checks every 5 min)
  
Cron (daily):
  0 6 * * * python /path/to/watchers/civic_rendering_auto.py >> /data/dispatch/civic_render.log 2>&1

Environment:
  TENANT_SERVICE_URL     — default http://tenant:8102
  CIVIC_CALENDAR_QUEUE   — default config/civic_calendar_queue.json
  DISPATCH_LOG           — default /data/dispatch/govos_v2_dispatch.jsonl
  TAILSCALE_HOST         — default king.tail760750.ts.net
  OWNER_EMAIL            — for Tailscale link notifications
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Config ────────────────────────────────────────────────────────────────────
TENANT_SERVICE_URL = os.environ.get("TENANT_SERVICE_URL", "http://tenant:8102")
CIVIC_CALENDAR_QUEUE = os.environ.get("CIVIC_CALENDAR_QUEUE", "config/civic_calendar_queue.json")
DISPATCH_LOG = os.environ.get("WORKBOARD_DISPATCH_LOG", "/data/dispatch/govos_v2_dispatch.jsonl")
TAILSCALE_HOST = os.environ.get("TAILSCALE_HOST", "king.tail760750.ts.net")
INTERNAL_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
TIMEOUT = 10


def say(msg: str):
    """Log to stdout + dispatch log."""
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}", flush=True)
    try:
        Path(DISPATCH_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(DISPATCH_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "kind": "watcher.civic_rendering",
                        "iso": ts,
                        "message": msg,
                    }
                )
                + "\n"
            )
    except Exception as e:
        print(f"[dispatch log write failed: {e}]", flush=True)


def _load_json(path: str, default=None):
    """Load JSON file safely."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _post_json(url: str, payload: dict, headers: Optional[dict] = None) -> dict | None:
    """POST JSON to service, return response or None."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Internal-Service-Token": INTERNAL_TOKEN,
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            say(f"POST {url} failed: {e.code} — {err}")
        except Exception:
            say(f"POST {url} failed: {e.code}")
        return None
    except Exception as e:
        say(f"POST {url} failed: {str(e)[:150]}")
        return None


def _get_json(url: str, headers: Optional[dict] = None) -> dict | None:
    """GET JSON from service, return response or None."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Internal-Service-Token": INTERNAL_TOKEN,
            **(headers or {}),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        say(f"GET {url} failed: {str(e)[:150]}")
        return None


def project_civic_signals(queue: dict) -> int:
    """
    Ingest civic_calendar_queue → tenant civic_signals via POST /api/v2/civic-signals

    Transforms calendar events into tenant-accessible civic signal records:
    - [CIVIC] meetings → public
    - [CIVIC ACTION] deadlines → public
    - [CIVIC REVIEW] internal approvals → owner-only
    """
    signals = []

    for event in queue.get("pending", []):
        kind = event.get("kind", "")
        tenant = event.get("tenant", "")
        summary = event.get("summary", "")
        description = event.get("desc", "")
        start = event.get("start", "")
        end = event.get("end", "")

        # Determine access level and visibility
        if kind == "review" and tenant == "system":
            # Internal review (prosecutor/board) — owner-only, never published
            visibility = "owner"
            public = False
        else:
            # Meeting or deadline — public civic event
            visibility = "public"
            public = True

        signal = {
            "event_type": f"civic.{kind}",  # e.g., civic.meeting, civic.action
            "summary": summary,
            "description": description,
            "start": start,
            "end": end,
            "tenant_id": tenant,
            "visibility": visibility,
            "public": public,
            "source": "calendar_civic",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        signals.append(signal)

    if not signals:
        return 0

    # Post signals to tenant service
    count = 0
    for sig in signals:
        url = f"{TENANT_SERVICE_URL}/api/v2/civic-signals"
        resp = _post_json(url, sig)
        if resp:
            count += 1
            say(f"✓ civic signal posted: {sig['event_type']} ({sig['summary'][:60]})")
        else:
            say(f"✗ civic signal FAILED: {sig['event_type']}")

    return count


def generate_tailscale_urls(signals: dict) -> list[str]:
    """
    Generate Tailscale URLs for newly rendered civic pages.

    Returns list of URLs like:
    - https://king.tail760750.ts.net/civic/
    - https://king.tail760750.ts.net/civic/meetings/
    - https://king.tail760750.ts.net/civic/deadlines/
    """
    urls = []

    # Main civic dashboard
    urls.append(f"https://{TAILSCALE_HOST}/civic/")

    # Category-specific pages (if any meetings/deadlines in this batch)
    has_meetings = any(s.get("event_type") == "civic.meeting" for s in signals.get("signals", []))
    has_deadlines = any(s.get("event_type") == "civic.action" for s in signals.get("signals", []))

    if has_meetings:
        urls.append(f"https://{TAILSCALE_HOST}/civic/meetings/")
    if has_deadlines:
        urls.append(f"https://{TAILSCALE_HOST}/civic/deadlines/")

    return urls


def post_dispatch_event(rendered_pages: int, tailscale_urls: list) -> bool:
    """
    Post a render completion event to the dispatch log + event bus.
    Owner sees this in the console as a "civic pages updated" notification.
    """
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "kind": "civic.pages.rendered",
        "iso": ts,
        "rendered_pages": rendered_pages,
        "tailscale_urls": tailscale_urls,
        "message": f"Civic pages auto-rendered. {rendered_pages} events. Links: {'; '.join(tailscale_urls)}",
    }

    try:
        Path(DISPATCH_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(DISPATCH_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        return True
    except Exception as e:
        say(f"failed to post dispatch event: {e}")
        return False


def render_civic_page_html(signals: list, output_path: str = "element_lotus_public/civic_dashboard.html") -> bool:
    """
    Render a live civic dashboard HTML page from signal data.
    This becomes the new civic.html, replacing the static one.

    Generates:
    - Title, description, metrics
    - Live event list (meetings, deadlines)
    - Links to jurisdictions, testify, reports
    - Last-updated timestamp
    """
    public_signals = [s for s in signals if s.get("visibility") == "public"]

    meetings = [s for s in public_signals if s.get("event_type") == "civic.meeting"]
    deadlines = [s for s in public_signals if s.get("event_type") == "civic.action"]

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Element Lotus · civic / govOS</title>
<meta name="description" content="Live civic events and transparency dashboard.">
<link rel="stylesheet" href="studio.css">
<link rel="stylesheet" href="../govos.css">
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="brand"><div class="mark">⚖</div><div class="wordmark"><strong>Civic / govOS</strong><span>Live transparency dashboard</span></div></div>
    <nav class="nav"><a href="index.html">Home</a><a href="games/">Games</a><a href="films.html">Films</a><a href="music.html">Music</a><a href="contact.html">Contact</a></nav>
  </header>

  <section class="hero">
    <div class="eyebrow">Public civic lane</div>
    <h1>govOS is here — tracking government with transparency and intention.</h1>
    <p>Follow meetings, jurisdictions, and cases. Submit testimony. Request government records. Participate in the civic work.</p>
    <div class="actions"><a class="btn primary" href="reports.html">Open the civic hub</a><a class="btn secondary" href="jurisdictions.html">Browse jurisdictions</a></div>
  </section>

  <section class="section">
    <h2>Upcoming civic events</h2>
    <div class="metrics">
      <div class="metric"><strong>{len(meetings)}</strong> <span>Meetings scheduled</span></div>
      <div class="metric"><strong>{len(deadlines)}</strong> <span>Testimony deadlines</span></div>
    </div>
  </section>

  <section class="section">
    <h2>Meetings & Public Records</h2>
    <div class="event-list">
"""

    for m in meetings[:10]:  # Show next 10
        start = m.get("start", "")[:10]
        html += f"""
      <article class="event">
        <div class="date">{start}</div>
        <div class="title">{m.get("summary", "Meeting")}</div>
        <p>{m.get("description", "")[:200]}</p>
        <a href="reports.html">View details →</a>
      </article>
"""

    html += """
    </div>
  </section>

  <section class="section">
    <h2>Testimony & Participation</h2>
    <div class="card-grid">
      <article class="card"><div class="kicker">Testify</div><h3>Public testimony</h3><p>Submit written or oral testimony on government decisions.</p><a href="testify.html">Testify →</a></article>
      <article class="card"><div class="kicker">Jurisdictions</div><h3>Government by place</h3><p>Find your elected officials and government bodies by location.</p><a href="jurisdictions.html">Browse →</a></article>
      <article class="card"><div class="kicker">Records</div><h3>Request public records</h3><p>Access government records and documents under public records laws.</p><a href="datasets.html">Request →</a></article>
    </div>
  </section>

  <section class="section split">
    <div class="panel"><h2>Boundary</h2><p>Civic pages stay public and transparent. Owner operations, workboards, and internal systems remain private.</p></div>
    <div class="panel"><h2>Return to studio</h2><p><a href="index.html">Back to Element Lotus home →</a><br><a href="games/">Games hub →</a><br><a href="films.html">Film lane →</a></p></div>
  </section>

  <footer class="footer">
    <nav><a href="index.html">Home</a><a href="reports.html">Civic hub</a><a href="jurisdictions.html">Jurisdictions</a><a href="testify.html">Testify</a></nav>
    PUBLIC civic lane · Auto-rendered from live civic schedule · Last updated: {datetime.now(timezone.utc).isoformat()}
  </footer>
</div>
<script src="../govos-shell.js" defer></script>
</body>
</html>
"""

    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        say(f"✓ civic dashboard rendered: {output_path}")
        return True
    except Exception as e:
        say(f"✗ failed to render civic dashboard: {e}")
        return False


def main_render():
    """One-shot: load calendar queue → project to tenant → render pages → generate links."""

    say("=== civic_rendering_auto START ===")

    # Load civic calendar queue
    queue_path = Path(CIVIC_CALENDAR_QUEUE) if Path(CIVIC_CALENDAR_QUEUE).exists() else Path("config/civic_calendar_queue.json")
    queue = _load_json(str(queue_path))

    if not queue.get("pending"):
        say("no pending civic events in queue — exiting")
        say("=== civic_rendering_auto END (no events) ===")
        return

    say(f"loaded {queue.get('pending_count', 0)} pending civic events from {queue_path}")

    # Project to tenant backend
    projected = project_civic_signals(queue)
    say(f"projected {projected} signals to tenant backend")

    # Render civic dashboard page
    signals_list = queue.get("pending", [])
    rendered_ok = render_civic_page_html(signals_list)

    # Generate Tailscale URLs
    tailscale_urls = generate_tailscale_urls(queue)
    say(f"generated {len(tailscale_urls)} Tailscale URL(s)")

    # Post dispatch event
    post_dispatch_event(projected, tailscale_urls)

    say("=== civic_rendering_auto END (SUCCESS) ===")


def watch_mode(interval: int = 300):
    """Daemon mode: check for updates every `interval` seconds (default 5 min)."""
    say("starting civic_rendering_auto in watch mode (checks every 5 min)")
    say("press Ctrl+C to stop")

    try:
        while True:
            main_render()
            time.sleep(interval)
    except KeyboardInterrupt:
        say("watch mode stopped by user")


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch_mode()
    else:
        main_render()
