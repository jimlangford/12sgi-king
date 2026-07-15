"""
GitHub Workflow Monitor Service

Runs in background and continuously monitors GitHub Actions for workflow failures.
Auto-repairs fixable errors and tracks results in the owner job dashboard.

Environment Variables:
  GITHUB_WORKFLOW_MONITOR_ENABLED=true (default)
  GITHUB_REPAIR_LOOKBACK_MINUTES=60 (scan last N minutes for failures)
  GITHUB_REPAIR_INTERVAL_SECONDS=300 (monitor check interval)
  GITHUB_REPAIR_AUTONOMY_THRESHOLD=75 (min autonomy score to repair)
  GITHUB_REPAIR_MAX_CONCURRENT=3 (max repairs per cycle)

To start:
  python -m services.github_workflow_monitor_service

To test (dry-run, single cycle):
  python -m services.github_workflow_monitor_service --dry-run --once
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parents[1]))

from services.github_workflow_monitor import GitHubWorkflowMonitor


logger = logging.getLogger(__name__)


class WorkflowMonitorService:
    """Background service for GitHub workflow monitoring."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.monitor = GitHubWorkflowMonitor()
        self.monitor.executor.dry_run = dry_run
        self.running = False
    
    async def run_cycle(self):
        """Run a single monitoring cycle."""
        lookback = int(os.environ.get("GITHUB_REPAIR_LOOKBACK_MINUTES", "60"))
        stats = self.monitor.monitor_and_repair(lookback)
        return stats
    
    async def run_continuous(self, interval_seconds: int = 300):
        """Run continuous monitoring."""
        self.running = True
        logger.info(f"Starting continuous monitoring (interval={interval_seconds}s)")
        
        cycle = 0
        try:
            while self.running:
                cycle += 1
                logger.info(f"--- Cycle {cycle} ---")
                
                stats = await self.run_cycle()
                logger.info(f"Cycle {cycle} complete: {stats}")
                
                if self.running:
                    await asyncio.sleep(interval_seconds)
        
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitoring error: {e}", exc_info=True)
        finally:
            self.running = False
    
    def stop(self):
        """Stop the service."""
        self.running = False


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="GitHub Workflow Monitor Service")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually commit repairs")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--interval", type=int, default=300, help="Monitoring interval (seconds)")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(name)s %(levelname)s: %(message)s"
    )
    
    # Check if enabled
    enabled = os.environ.get("GITHUB_WORKFLOW_MONITOR_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("GitHub workflow monitor is disabled (GITHUB_WORKFLOW_MONITOR_ENABLED=false)")
        return 0
    
    # Check for GitHub token. Under `restart: unless-stopped` an exit here just
    # crash-loops the container forever (2026-07-15, found live: same error every
    # ~30s). Idle instead -- log once, then wait for the token to appear so the
    # container self-heals the moment it's configured, no manual restart needed.
    if not os.environ.get("GITHUB_TOKEN"):
        if args.once:
            logger.error("GITHUB_TOKEN is required but not set")
            return 1
        logger.warning("GITHUB_TOKEN not set -- idling (will start monitoring once it's configured)")
        while not os.environ.get("GITHUB_TOKEN"):
            await asyncio.sleep(args.interval)
        logger.info("GITHUB_TOKEN detected -- starting monitor")
    
    service = WorkflowMonitorService(dry_run=args.dry_run)
    
    if args.once:
        logger.info("Running single monitoring cycle (--once)")
        stats = await service.run_cycle()
        logger.info(f"Results: {stats}")
        return 0 if stats.get("repaired", 0) > 0 or stats.get("failed", 0) == 0 else 1
    else:
        await service.run_continuous(args.interval)
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
