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
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class ServiceMonitor:
    def __init__(self, compose_file: str = "docker-compose.v2.yml"):
        self.compose_file = compose_file
        self.check_interval = 30  # seconds
        self.max_restarts = 3
        self.restart_counts = {}
    
    def check_health(self):
        """Check all services health."""
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", self.compose_file, "ps", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to check health: {result.stderr}")
                return []
            
            containers = json.loads(result.stdout)
            return containers
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return []
    
    def restart_service(self, service_name: str):
        """Restart a failed service."""
        if self.restart_counts.get(service_name, 0) >= self.max_restarts:
            logger.error(f"❌ {service_name} exceeded max restarts ({self.max_restarts})")
            return False
        
        logger.warning(f"↻ Restarting {service_name}...")
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", self.compose_file, "restart", service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.restart_counts[service_name] = self.restart_counts.get(service_name, 0) + 1
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
                    
                    if state != "running":
                        logger.warning(f"⚠ {name} is {state}")
                        self.restart_service(name)
                    else:
                        # Reset restart count on healthy service
                        if self.restart_counts.get(name, 0) > 0:
                            logger.info(f"✓ {name} recovered")
                            self.restart_counts[name] = 0
                
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            logger.info("🛑 Monitor stopped")
        except Exception as e:
            logger.error(f"Monitor error: {e}")


if __name__ == "__main__":
    monitor = ServiceMonitor()
    monitor.monitor()
