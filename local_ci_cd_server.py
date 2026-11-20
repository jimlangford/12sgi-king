#!/usr/bin/env python3
"""
12sgi-king Local CI/CD System
Self-hosted deployment automation independent of GitHub billing.

Provides:
- Git webhook receiver (watches repo for pushes)
- Automated test execution
- Docker image building
- Service deployment orchestration
- Health monitoring and alerts
- Auto-recovery for failed services
"""

import json
import subprocess
import time
import sys
import logging
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import hmac
import hashlib
import argparse
import os
import re

# Configuration
REPO_PATH = Path(__file__).resolve().parent
WEBHOOK_PORT = 9000
LOG_DIR = Path(REPO_PATH) / "logs" / "ci-cd"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DeploymentPipeline:
    """Main CI/CD pipeline orchestrator."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.is_deploying = False
        self._deploy_lock = threading.Lock()

    def _compose_command(self, *args):
        return ["docker", "compose", "--env-file", ".env.v2",
                "-f", "docker-compose.v2.yml", *args]
        
    def run(self, commit_sha: str, branch: str = "main", update_code: bool = True):
        """Execute full deployment pipeline."""
        logger.info(f"🚀 Starting deployment pipeline: {commit_sha[:7]} on {branch}")
        
        if not self._deploy_lock.acquire(blocking=False):
            logger.warning("⏳ Deployment already in progress, skipping")
            return False
        
        self.is_deploying = True
        try:
            # Step 1: Pull latest code
            if update_code and not self._git_pull(branch):
                return False

            if not self._preflight():
                return False
            
            # Step 2: Run tests
            if not self._run_tests():
                return False
            
            # Step 3: Build Docker images
            if not self._build_images():
                return False
            
            # Step 4: Deploy services
            if not self._deploy_services():
                return False
            
            # Step 5: Verify health
            if not self._verify_health():
                return False
            
            # Step 6: Log deployment
            self._log_deployment(commit_sha, "success")
            
            logger.info("✅ Deployment pipeline completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            self._log_deployment(commit_sha, "failed", str(e))
            return False
        finally:
            self.is_deploying = False
            self._deploy_lock.release()

    def _preflight(self):
        from setup_tailscale_hosting import validate_config
        from health_check import check_tailscale, check_disk

        for check in (check_tailscale, check_disk):
            if not check()[0]:
                return False
        result = subprocess.run(
            self._compose_command("config", "--format", "json"), cwd=self.repo_path,
            capture_output=True, text=True, timeout=30, check=True
        )
        validate_config(json.loads(result.stdout))
        return True
    
    def _git_pull(self, branch: str) -> bool:
        """Pull latest code from repository."""
        logger.info("📥 Pulling latest code...")
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only", "origin", branch],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info("✓ Code pulled successfully")
                return True
            else:
                logger.error(f"Git pull failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Git pull error: {e}")
            return False
    
    def _run_tests(self) -> bool:
        """Run smoke tests."""
        logger.info("🧪 Running tests...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/v2/test_v2_contract.py", "-v"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                logger.info("✓ Tests passed")
                return True
            else:
                logger.error(f"Tests failed: {result.stdout}\n{result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Test error: {e}")
            return False
    
    def _build_images(self) -> bool:
        """Build Docker images."""
        logger.info("🔨 Building Docker images...")
        try:
            result = subprocess.run(
                self._compose_command("build"),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=600
            )
            if result.returncode == 0:
                logger.info("✓ Docker images built successfully")
                return True
            else:
                logger.error(f"Build failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Build error: {e}")
            return False
    
    def _deploy_services(self) -> bool:
        """Deploy services."""
        logger.info("🚀 Deploying services...")
        try:
            result = subprocess.run(
                self._compose_command("up", "-d", "--wait", "--wait-timeout", "120"),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=150
            )
            if result.returncode == 0:
                logger.info("✓ Services deployed")
                time.sleep(10)  # Wait for services to start
                return True
            else:
                logger.error(f"Deployment failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Deployment error: {e}")
            return False
    
    def _verify_health(self) -> bool:
        """Verify all services are healthy."""
        logger.info("❤️ Verifying service health...")
        try:
            result = subprocess.run(
                [sys.executable, "health_check.py"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=180
            )
            if result.returncode == 0:
                logger.info("✓ All services healthy")
                return True
            else:
                logger.warning(f"⚠ Health check warnings: {result.stdout}")
                return False
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False
    
    def _log_deployment(self, commit_sha: str, status: str, error: str = ""):
        """Log deployment result."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "commit_sha": commit_sha,
            "status": status,
            "error": error
        }
        
        log_dir = self.repo_path / "logs" / "ci-cd"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "deployments.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        logger.info(f"📋 Deployment logged: {status}")


class GitWebhookHandler(BaseHTTPRequestHandler):
    """Webhook receiver for Git push events."""
    
    pipeline = None
    webhook_secret = ""
    
    def do_POST(self):
        """Handle POST webhook from Git."""
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return
        
        if not self.webhook_secret:
            self.send_error(503, "Webhook secret not configured")
            return
        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except ValueError:
            self.send_error(400, "Invalid content length")
            return
        if not 0 < content_length <= 1024 * 1024:
            self.send_error(413, "Invalid payload size")
            return
        self.connection.settimeout(10)
        try:
            body = self.rfile.read(content_length)
        except (TimeoutError, OSError):
            self.send_error(408, "Incomplete payload")
            return
        expected = "sha256=" + hmac.new(
            self.webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(self.headers.get("X-Hub-Signature-256", ""), expected):
            self.send_error(403, "Invalid signature")
            return
        
        try:
            data = json.loads(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            self.send_response(400)
            self.end_headers()
            return
        if not isinstance(data, dict):
            self.send_error(400, "Expected JSON object")
            return
        
        logger.info(f"📍 Webhook received: {data.get('ref', 'unknown')}")
        
        # Extract commit info
        repository = data.get("repository")
        commit_sha = data.get("after", "")
        branch = "main"
        if (self.headers.get("X-GitHub-Event") == "push"
                and data.get("ref") == "refs/heads/main"
                and isinstance(repository, dict)
                and repository.get("full_name") == "jimlangford/12sgi-king"
                and isinstance(commit_sha, str)
                and re.fullmatch(r"[0-9a-f]{40}", commit_sha)
                and commit_sha != "0" * 40):
            logger.info(f"🔔 New commit detected: {commit_sha[:7]} on {branch}")
            
            # Trigger deployment in background thread
            thread = threading.Thread(
                target=self.pipeline.run,
                args=(commit_sha, branch)
            )
            thread.daemon = True
            thread.start()
            
            self.send_response(202)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "deployment_started"}).encode())
        else:
            self.send_response(200)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass


def main():
    """Start local CI/CD system."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deploy-local", action="store_true",
                        help="Test/build/deploy the current checkout without GitHub or a webhook")
    args = parser.parse_args()
    if args.deploy_local:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_PATH,
            capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
        return 0 if DeploymentPipeline(REPO_PATH).run(revision, update_code=False) else 1
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if len(secret) < 32 or secret == "12sgi-king-local-ci-cd":
        logger.error("Export a unique WEBHOOK_SECRET of at least 32 characters")
        return 1
    logger.info("="*70)
    logger.info("12sgi-king Local CI/CD System Starting")
    logger.info("="*70)
    logger.info(f"Repository: {REPO_PATH}")
    logger.info(f"Webhook listening on port {WEBHOOK_PORT}")
    logger.info(f"Logs: {LOG_DIR}")
    
    # Initialize pipeline
    pipeline = DeploymentPipeline(REPO_PATH)
    GitWebhookHandler.pipeline = pipeline
    GitWebhookHandler.webhook_secret = secret
    
    # Start webhook server
    server = HTTPServer(("127.0.0.1", WEBHOOK_PORT), GitWebhookHandler)
    logger.info(f"✅ Webhook server running on 127.0.0.1:{WEBHOOK_PORT}/webhook")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
