#!/usr/bin/env python3
"""services/connectors/runner.py — token refresh daemon for platform OAuth connectors.

Watches token_store.py and calls registry.refresh() on a schedule.
Runs as a sidekick service (not exposed externally) — just watches/refreshes.

Emits workboard jobs on errors so the healing system can pick up on token expiry.
"""
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.connectors.registry import refresh, status
from services.connectors.token_store import PLATFORMS, token_status

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] connector-runner: %(levelname)s: %(message)s"
)
log = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = int(os.environ.get("CONNECTOR_REFRESH_INTERVAL", "3600"))  # 1 hour
WORKBOARD_ENABLED = os.environ.get("WORKBOARD_ENABLED", "1") == "1"


def emit_workboard_job(platform: str, status_msg: str, error: str | None = None) -> None:
    """Report connector status to workboard (best-effort)."""
    if not WORKBOARD_ENABLED:
        return
    try:
        from services.v2_workboard import emit_workboard_job as _emit

        _emit(
            source="connector-runner",
            action=f"connector.{platform}.refreshed",
            event=f"CONNECTOR STATUS: {platform} — {status_msg}",
            lane="engineering",
            status="done" if not error else "failed",
            payload={
                "platform": platform,
                "status": status_msg,
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        log.warning("Failed to emit workboard job: %s", e)


def refresh_all() -> dict:
    """Refresh tokens for all platforms. Returns {platform: (ok, reason)}."""
    results = {}
    for platform in PLATFORMS:
        try:
            s = token_status(platform)
            if s == "needs_auth":
                log.info("%s: needs authentication (skipping)", platform)
                results[platform] = (False, "needs_auth")
                continue

            ok = refresh(platform)
            if ok:
                log.info("%s: refreshed OK", platform)
                results[platform] = (True, "refreshed")
                emit_workboard_job(platform, "token refreshed OK")
            else:
                log.warning("%s: refresh failed (token still valid for now)", platform)
                results[platform] = (False, "refresh_failed")
                emit_workboard_job(platform, "refresh failed", error="Refresh attempt failed")
        except Exception as e:
            log.error("%s: exception during refresh: %s", platform, e)
            results[platform] = (False, str(e))
            emit_workboard_job(platform, f"exception: {str(e)}", error=str(e))

    return results


def main():
    log.info("Connector runner started (refresh interval: %d seconds)", REFRESH_INTERVAL_SECONDS)

    # Initial refresh at startup
    log.info("Performing initial token refresh...")
    results = refresh_all()
    for platform, (ok, reason) in results.items():
        status_str = "✓" if ok else "✗"
        log.info("  %s %s: %s", status_str, platform, reason)

    # Periodic refresh loop
    next_refresh = time.time() + REFRESH_INTERVAL_SECONDS
    while True:
        now = time.time()
        if now >= next_refresh:
            log.info("Periodic token refresh cycle...")
            results = refresh_all()
            next_refresh = now + REFRESH_INTERVAL_SECONDS
        else:
            sleep_seconds = min(REFRESH_INTERVAL_SECONDS // 10, next_refresh - now)
            time.sleep(sleep_seconds)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Connector runner stopped.")
        sys.exit(0)
    except Exception as e:
        log.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
