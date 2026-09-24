#!/usr/bin/env python3
"""
Simple 12sgi.com local server on port 8080.
"""

import http.server
import socketserver
from pathlib import Path
import sys

PORT = 8080

class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        """Translate URL path to file system path."""
        path = super().translate_path(path)
        
        # Remove leading repo path if present
        if '\\' in path:  # Windows
            parts = path.split('\\')
            if '12sgi-king' in parts:
                idx = parts.index('12sgi-king')
                path = '\\'.join(parts[idx+1:])
        
        return path

print(f"\n{'='*70}")
print(f"12sgi.com Local Server")
print(f"{'='*70}")
print(f"Port: {PORT}")
print(f"URL: http://localhost:{PORT}/")
print(f"\nServing files from: {Path.cwd()}")
print(f"\nRouting:")
print(f"  /               → king_landing.html")
print(f"  /site/*         → site/ directory")
print(f"  /apps/*         → apps/ directory")
print(f"  /content/*      → content/ directory")
print(f"\nPress Ctrl+C to stop")
print(f"{'='*70}\n")

try:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"✓ Server running on http://localhost:{PORT}/")
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n✓ Server stopped")
    sys.exit(0)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
