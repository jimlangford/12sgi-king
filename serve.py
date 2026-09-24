#!/usr/bin/env python3
"""
12sgi.com local server - serves from git repo.
Port: 8080 (or specified)
"""

import http.server
import socketserver
from pathlib import Path
import sys
import os

# Get the repo directory
REPO_DIR = Path(__file__).parent.resolve()
os.chdir(REPO_DIR)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

class RootHandler(http.server.SimpleHTTPRequestHandler):
    pass

print(f"\n{'='*70}")
print(f"12sgi.com Local Server")
print(f"{'='*70}")
print(f"Port: {PORT}")
print(f"Serving from: {REPO_DIR}")
print(f"URL: http://localhost:{PORT}/")
print(f"\nPress Ctrl+C to stop\n")

try:
    with socketserver.TCPServer(("0.0.0.0", PORT), RootHandler) as httpd:
        print(f"✓ Server running!")
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n✓ Stopped")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
