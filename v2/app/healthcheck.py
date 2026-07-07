"""
healthcheck.py — lightweight liveness probe for the app container.

Docker HEALTHCHECK or external orchestrators can call this directly:
    python /workspace/app/healthcheck.py

Exits 0 if the FastAPI service responds to /health, exits 1 otherwise.
"""
import urllib.request
import urllib.error
import sys
import os

port = int(os.getenv("APP_PORT", "8088"))
url  = f"http://127.0.0.1:{port}/health"

try:
    with urllib.request.urlopen(url, timeout=5) as r:
        if r.status == 200:
            print("healthy")
            sys.exit(0)
        print(f"unexpected status {r.status}")
        sys.exit(1)
except Exception as e:
    print(f"unhealthy: {e}")
    sys.exit(1)
