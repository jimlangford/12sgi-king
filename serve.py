#!/usr/bin/env python3
"""Serve only the built site on loopback; expose it privately using Tailscale Serve."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent


class BuiltSiteHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        root = Path(self.directory).resolve()
        path = Path(self.translate_path(self.path))
        if (not path.resolve().is_relative_to(root)
                or any(part.startswith(".") for part in path.relative_to(Path(self.directory)).parts)):
            self.send_error(404)
            return None
        return super().send_head()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int, nargs="?", default=8080)
    args = parser.parse_args(argv)
    site = REPO_DIR / "site"
    if not site.is_dir():
        parser.error("Build site/ first with build_site.py")
    handler = partial(BuiltSiteHandler, directory=str(site))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Serving built site only at http://127.0.0.1:{args.port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
