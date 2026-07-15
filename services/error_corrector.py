"""Error detection and auto-correction system.

Monitors all services for errors, searches for solutions, logs diagnostics,
and suggests/applies fixes automatically.

Usage:
  from services.error_corrector import ErrorMonitor
  monitor = ErrorMonitor()
  monitor.check_all_services()
  monitor.auto_fix_errors()
"""

import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import dict, list

from services.web_search import search_error_solution, get_best_practices


class ErrorMonitor:
    """Detects errors across Docker, GPU, disk, and service health."""
    
    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path("logs/error_corrections")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.errors = []
        self.corrections_applied = []
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def _log(self, msg: dict):
        """Log error/correction event."""
        msg["ts"] = self._now()
        try:
            log_file = self.log_dir / f"corrections-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg) + "\n")
        except Exception as e:
            print(f"Error logging: {e}")
    
    def check_docker_health(self) -> list:
        """Check Docker daemon and containers for errors."""
        issues = []
        try:
            # Docker daemon alive?
            out = subprocess.check_output(
                ["docker", "info"],
                stderr=subprocess.DEVNULL, text=True, timeout=4
            ).strip()
            if not out:
                issues.append({
                    "service": "docker",
                    "error": "daemon not responding",
                    "severity": "critical",
                    "fix": "sudo systemctl restart docker"
                })
        except Exception as e:
            issues.append({
                "service": "docker",
                "error": str(e),
                "severity": "critical",
                "fix": "docker not installed or not running"
            })
        
        # Check containers
        try:
            out = subprocess.check_output(
                ["docker", "ps", "-a", "--format", "{{json .}}"],
                stderr=subprocess.DEVNULL, text=True, timeout=4
            ).strip()
            
            for line in out.splitlines():
                if not line:
                    continue
                try:
                    c = json.loads(line)
                    status = c.get("Status", "").lower()
                    name = c.get("Names", "unknown")
                    
                    # Exited containers
                    if "exit" in status or "stop" in status:
                        issues.append({
                            "service": f"docker:{name}",
                            "error": f"container stopped: {status}",
                            "severity": "high",
                            "fix": f"docker logs {name} --tail 50"
                        })
                    
                    # Restart loops
                    try:
                        restarts = int(subprocess.check_output(
                            ["docker", "inspect", "--format", "{{.RestartCount}}", name],
                            stderr=subprocess.DEVNULL, text=True
                        ).strip())
                        if restarts > 5:
                            issues.append({
                                "service": f"docker:{name}",
                                "error": f"restart loop ({restarts} restarts)",
                                "severity": "high",
                                "fix": f"docker logs {name} --tail 100 | tail -20"
                            })
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception as e:
            print(f"Docker container check failed: {e}")
        
        return issues
    
    def check_disk_space(self) -> list:
        """Check disk usage and alert on high usage."""
        issues = []
        try:
            import psutil
            for part in psutil.disk_partitions(all=False):
                usage = psutil.disk_usage(part.mountpoint)
                pct = int(usage.percent)
                
                if pct >= 90:
                    issues.append({
                        "service": "disk",
                        "error": f"{part.mountpoint} critically full ({pct}%)",
                        "severity": "high",
                        "fix": "docker system prune -f && rm -rf ~/Downloads/*"
                    })
                elif pct >= 75:
                    issues.append({
                        "service": "disk",
                        "error": f"{part.mountpoint} warning ({pct}%)",
                        "severity": "medium",
                        "fix": "docker system prune -f"
                    })
        except ImportError:
            pass  # psutil not available
        except Exception as e:
            print(f"Disk check failed: {e}")
        
        return issues
    
    def check_gpu_health(self) -> list:
        """Check GPU temperature, VRAM, and thermal throttling."""
        issues = []
        try:
            out = subprocess.check_output(
                ["nvidia-smi",
                 "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,thermal_throttle.reason.gpu_temp",
                 "--format=csv,noheader,nounits"],
                text=True, timeout=3
            ).strip()
            
            parts = [p.strip() for p in out.split(",")]
            if len(parts) >= 4:
                temp = int(parts[0])
                util = int(parts[1])
                vram_used = int(parts[2]) * 1024 * 1024
                vram_total = int(parts[3]) * 1024 * 1024
                throttle_reason = parts[4] if len(parts) > 4 else "none"
                
                if temp >= 85:
                    issues.append({
                        "service": "gpu",
                        "error": f"GPU overheating ({temp}°C)",
                        "severity": "critical",
                        "fix": "Stop all workloads. Check GPU fans and airflow."
                    })
                
                if throttle_reason and "gpu_temp" in throttle_reason.lower():
                    issues.append({
                        "service": "gpu",
                        "error": "GPU thermal throttling active",
                        "severity": "high",
                        "fix": "Reduce workload and improve cooling"
                    })
                
                vram_pct = int(vram_used / vram_total * 100) if vram_total else 0
                if vram_pct >= 95:
                    issues.append({
                        "service": "gpu",
                        "error": f"VRAM critically full ({vram_pct}%)",
                        "severity": "high",
                        "fix": "Stop Ollama/ComfyUI and clear VRAM"
                    })
        except FileNotFoundError:
            pass  # nvidia-smi not available
        except Exception as e:
            print(f"GPU check failed: {e}")
        
        return issues
    
    def check_service_health(self, port: int, service_name: str) -> list:
        """Check if a service responds on a port."""
        issues = []
        try:
            import urllib.request
            urllib.request.urlopen(f"http://localhost:{port}/health", timeout=3)
        except urllib.error.URLError:
            issues.append({
                "service": service_name,
                "error": f"not responding on port {port}",
                "severity": "high",
                "port": port,
                "fix": f"systemctl restart {service_name} or python -m service.main"
            })
        except Exception:
            pass  # Assume service is down
        
        return issues
    
    def check_all_services(self) -> dict:
        """Run all health checks."""
        all_issues = []
        
        all_issues.extend(self.check_docker_health())
        all_issues.extend(self.check_disk_space())
        all_issues.extend(self.check_gpu_health())
        all_issues.extend(self.check_service_health(8799, "board-api"))
        all_issues.extend(self.check_service_health(8109, "king-bridge"))
        all_issues.extend(self.check_service_health(11434, "ollama"))
        all_issues.extend(self.check_service_health(8188, "comfyui"))
        
        self.errors = all_issues
        
        return {
            "timestamp": self._now(),
            "total_issues": len(all_issues),
            "critical": len([e for e in all_issues if e.get("severity") == "critical"]),
            "high": len([e for e in all_issues if e.get("severity") == "high"]),
            "medium": len([e for e in all_issues if e.get("severity") == "medium"]),
            "issues": all_issues
        }
    
    def auto_fix_errors(self) -> dict:
        """Attempt to fix detected errors automatically."""
        results = {
            "timestamp": self._now(),
            "fixes_attempted": 0,
            "fixes_successful": 0,
            "fixes_failed": 0,
            "details": []
        }
        
        for error in self.errors:
            if error.get("severity") not in ["critical", "high"]:
                continue  # Skip low-priority errors
            
            service = error.get("service", "unknown")
            fix_cmd = error.get("fix", "")
            
            if not fix_cmd or not fix_cmd.startswith("docker "):
                continue  # Only auto-fix safe commands
            
            results["fixes_attempted"] += 1
            
            try:
                print(f"[AUTO-FIX] {service}: {fix_cmd}")
                out = subprocess.check_output(
                    fix_cmd.split(), timeout=10, text=True
                ).strip()
                
                results["fixes_successful"] += 1
                self.corrections_applied.append({
                    "service": service,
                    "command": fix_cmd,
                    "output": out[:200],
                    "success": True
                })
                self._log({
                    "type": "auto_fix",
                    "service": service,
                    "command": fix_cmd,
                    "success": True
                })
            except Exception as e:
                results["fixes_failed"] += 1
                self.corrections_applied.append({
                    "service": service,
                    "command": fix_cmd,
                    "error": str(e)[:200],
                    "success": False
                })
                self._log({
                    "type": "auto_fix_failed",
                    "service": service,
                    "command": fix_cmd,
                    "error": str(e)
                })
        
        results["details"] = self.corrections_applied
        return results
    
    def search_solutions(self) -> dict:
        """Search web for solutions to detected errors."""
        solutions = {}
        
        for error in self.errors[:5]:  # Limit to top 5 errors
            error_msg = error.get("error", "")
            service = error.get("service", "")
            
            if not error_msg:
                continue
            
            result = search_error_solution(error_msg, context=service)
            solutions[service] = result
        
        return solutions
    
    def generate_report(self) -> str:
        """Generate a human-readable error report."""
        report = f"""
═══════════════════════════════════════════════════════════════
  ERROR CORRECTION REPORT — {self._now()}
═══════════════════════════════════════════════════════════════

ISSUES DETECTED: {len(self.errors)}
"""
        for error in self.errors:
            severity = error.get("severity", "unknown").upper()
            service = error.get("service", "unknown")
            msg = error.get("error", "")
            fix = error.get("fix", "")
            
            report += f"""
  [{severity}] {service}
      Error: {msg}
      Fix: {fix}
"""
        
        if self.corrections_applied:
            report += f"""
CORRECTIONS ATTEMPTED: {len(self.corrections_applied)}
"""
            for correction in self.corrections_applied:
                status = "✓ SUCCESS" if correction.get("success") else "✗ FAILED"
                report += f"\n  {status} — {correction.get('service')}: {correction.get('command')}"
        
        report += f"\n\n═══════════════════════════════════════════════════════════════\n"
        return report
