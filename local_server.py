#!/usr/bin/env python3
"""
Local 12sgi.com static web server - serves git repo without blocking CI/CD.
Runs on port 8080 (configurable), doesn't interfere with Docker/compose.
"""

import http.server
import socketserver
import os
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

class LocalServerHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler for 12sgi.com local server."""
    
    # Root directory for serving
    BASE_DIR = Path(__file__).parent.resolve()
    
    def do_GET(self):
        """Handle GET requests with proper routing."""
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        
        # Remove leading slash
        if path.startswith('/'):
            path = path[1:]
        
        # Route rules
        if not path or path == '/':
            # Root → king_landing.html
            path = 'king_landing.html'
        elif path == 'index.html':
            # /index.html → king_landing.html
            path = 'king_landing.html'
        elif path.endswith('/') and not (self.BASE_DIR / path).is_dir():
            # /foo/ without trailing slash directory → /foo/index.html
            path = path.rstrip('/') + '/index.html'
        
        # Security: prevent directory traversal
        full_path = (self.BASE_DIR / path).resolve()
        try:
            if not str(full_path).startswith(str(self.BASE_DIR)):
                self.send_error(403, "Forbidden")
                return
        except (ValueError, OSError):
            self.send_error(400, "Bad Request")
            return
        
        # Serve file
        if full_path.is_file():
            self.serve_file(full_path)
        elif full_path.is_dir():
            # Directory: try index.html
            index_path = full_path / 'index.html'
            if index_path.exists():
                self.serve_file(index_path)
            else:
                self.send_error(404, "Not Found")
        else:
            # File not found → try with .html extension
            html_path = full_path.with_suffix('.html')
            if html_path.is_file():
                self.serve_file(html_path)
            else:
                self.send_error(404, f"Not Found: {path}")
    
    def serve_file(self, file_path):
        """Serve a file with proper MIME type."""
        try:
            mime_type = self.guess_type(str(file_path))
            
            with open(file_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', mime_type[0] or 'application/octet-stream')
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'max-age=3600')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(content)
        except IOError as e:
            self.send_error(500, f"Internal Server Error: {e}")
    
    def log_message(self, format, *args):
        """Custom logging."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        client_ip = self.client_address[0]
        message = format % args
        print(f"[{timestamp}] {client_ip} - {message}")

def run_server(host='127.0.0.1', port=8080):
    """Run the local server."""
    print(f"\n{'='*70}")
    print(f"12sgi.com Local Server")
    print(f"{'='*70}")
    print(f"✓ Serving from: {LocalServerHandler.BASE_DIR}")
    print(f"✓ Host: {host}")
    print(f"✓ Port: {port}")
    print(f"\nAccess:")
    print(f"  http://{host}:{port}/")
    print(f"  http://localhost:{port}/")
    if host == '127.0.0.1':
        print(f"\nFor 12sgi.com hostname, add to %WINDIR%\\System32\\drivers\\etc\\hosts:")
        print(f"  127.0.0.1 12sgi.com www.12sgi.com")
        print(f"  Then access: http://12sgi.com:{port}/")
    print(f"\n{'='*70}")
    print(f"Press Ctrl+C to stop\n")
    
    handler = LocalServerHandler
    with socketserver.TCPServer((host, port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n✓ Server stopped")
            sys.exit(0)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='12sgi.com local server')
    parser.add_argument('--host', default='127.0.0.1', help='Host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8080, help='Port (default: 8080)')
    parser.add_argument('--bg', action='store_true', help='Run in background')
    args = parser.parse_args()
    
    if args.bg:
        # Background mode: start in daemon thread and exit main thread
        thread = threading.Thread(target=lambda: run_server(args.host, args.port), daemon=True)
        thread.start()
        print(f"✓ Server started in background on {args.host}:{args.port}")
        # Keep process alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n✓ Server stopped")
            sys.exit(0)
    else:
        # Foreground mode
        run_server(args.host, args.port)
