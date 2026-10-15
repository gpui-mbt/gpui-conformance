#!/usr/bin/env python3
"""Serve the complete lab with the shared-memory WASM response headers."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

class IsolatedHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()

parser = argparse.ArgumentParser()
parser.add_argument("directory", nargs="?", default="_build/browser-lab")
parser.add_argument("--port", type=int, default=8080)
args = parser.parse_args()
server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(IsolatedHandler, directory=args.directory))
print(f"http://127.0.0.1:{args.port}/", flush=True)
server.serve_forever()
