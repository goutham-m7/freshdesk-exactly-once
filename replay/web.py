"""Loopback-only experiment UI; never a production webhook receiver."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from replay.__main__ import demo

ASSETS = Path(__file__).parent / "static"


class ReplayHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def respond(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; "
                         "base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def trusted(self) -> bool:
        hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host")
        origin = self.headers.get("Origin")
        return host in hosts and (origin is None or origin == f"http://{host}")

    def do_GET(self):
        if not self.trusted():
            self.respond(403, b"Loopback origin required", "text/plain")
            return
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8")}
        if self.path not in assets:
            self.respond(404, b"Not found", "text/plain")
            return
        filename, kind = assets[self.path]
        self.respond(200, (ASSETS / filename).read_bytes(), kind)

    def do_POST(self):
        if not self.trusted():
            self.respond(403, b"Loopback origin required", "text/plain")
            return
        if self.path != "/api/replay":
            self.respond(404, b"Not found", "text/plain")
            return
        if self.headers.get("Content-Type") != "application/json":
            self.respond(415, b"Use application/json", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 128:
                self.respond(413, b"Request exceeds 128 bytes", "text/plain")
                return
            if json.loads(self.rfile.read(length)) != {}:
                raise ValueError("Only the fixed synthetic scenario is supported")
        except (ValueError, UnicodeDecodeError):
            self.respond(400, b"Send an empty JSON object", "text/plain")
            return
        try:
            result = demo()
        except (OSError, RuntimeError, TimeoutError):
            self.respond(500, b"Replay failed. Check server logs, then run again.", "text/plain")
            raise
        self.respond(200, json.dumps(result).encode(), "application/json")


def create_server(*, port: int) -> HTTPServer:
    # Serial requests bound CPU/process pressure. This is a local lab, not a public API.
    return HTTPServer(("127.0.0.1", port), ReplayHandler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(port=args.port)
    print(f"Replay timeline: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
