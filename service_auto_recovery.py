#!/usr/bin/env python3
"""
Auto-recovery system for 12sgi-king services.
Monitors health and automatically restarts failed services.
"""

import subprocess
import time
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class ServiceMonitor:
    def __init__(self, compose_file: str = "docker-compose.v2.yml"):
        self.repo_path = Path(__file__).resolve().parent
        self.compose_file = str((self.repo_path / compose_file).resolve())
        self.env_file = str(self.repo_path / ".env.v2")
        self.check_interval = 30  # seconds
        self.max_restarts = 3
        self.restart_counts = {}
        self.healthy_since = {}
        self.recovery_window = 300

    def compose_command(self, *args):
        return ["docker", "compose", "--env-file", self.env_file,
                "-f", self.compose_file, *args]
    
    def check_health(self):
        """Check all services health."""
        try:
            result = subprocess.run(
                self.compose_command("ps", "--all", "--format", "json"),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to check health: {result.stderr}")
                return []
            
            text = result.stdout.strip()
            if not text:
                return []
            try:
                containers = json.loads(text)
            except json.JSONDecodeError:
                containers = [json.loads(line) for line in text.splitlines() if line.strip()]
            if isinstance(containers, dict):
                containers = [containers]
            if not isinstance(containers, list) or not all(isinstance(c, dict) for c in containers):
                raise ValueError("Invalid Compose status")
            return containers
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return []
    
    def restart_service(self, service_name: str):
        """Restart a failed service."""
        if self.restart_counts.get(service_name, 0) >= self.max_restarts:
            logger.error(f"❌ {service_name} exceeded max restarts ({self.max_restarts})")
            return False
        
        if service_name not in {
            "auth", "tenant", "documents", "storage", "ai", "health", "gpu-router",
            "board-api", "king-bridge", "connector-runner", "github-workflow-monitor",
            "web-server",
        }:
            logger.error("Refusing to restart unknown service: %s", service_name)
            return False
        # Count failed attempts too, so persistent failures cannot loop forever.
        self.restart_counts[service_name] = self.restart_counts.get(service_name, 0) + 1
        logger.warning(f"↻ Restarting {service_name}...")
        try:
            result = subprocess.run(
                self.compose_command("restart", service_name),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"✓ {service_name} restarted (attempt {self.restart_counts[service_name]})")
                return True
            else:
                logger.error(f"Failed to restart {service_name}: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Restart error for {service_name}: {e}")
            return False
    
    def monitor(self):
        """Run continuous monitoring loop."""
        logger.info("🔍 Starting service monitor...")
        
        try:
            while True:
                containers = self.check_health()
                
                for container in containers:
                    name = container.get("Service", "unknown")
                    state = container.get("State", "unknown")
                    
                    health = container.get("Health", "")
                    if state not in {"running", "restarting"} or health == "unhealthy":
                        self.healthy_since.pop(name, None)
                        logger.warning(f"⚠ {name} is {state}")
                        self.restart_service(name)
                    elif state == "running" and health in {"", "healthy"}:
                        # A single green poll must not reset a flapping service's budget.
                        since = self.healthy_since.setdefault(name, time.monotonic())
                        if (self.restart_counts.get(name, 0) > 0
                                and time.monotonic() - since >= self.recovery_window):
                            logger.info(f"✓ {name} recovered")
                            self.restart_counts[name] = 0
                    else:
                        self.healthy_since.pop(name, None)
                
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("🛑 Monitor stopped")
        except Exception as e:
            logger.error(f"Monitor error: {e}")


if __name__ == "__main__":
    monitor = ServiceMonitor()
    monitor.monitor()
