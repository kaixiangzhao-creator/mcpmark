#!/usr/bin/env python3
"""AEnv health endpoint and WebArena process-supervisor bootstrap."""

import signal
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer


supervisor = subprocess.Popen(
    ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisord.conf"],
)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        healthy = self.path == "/health" and supervisor.poll() is None
        self.send_response(200 if healthy else 503 if self.path == "/health" else 404)
        self.end_headers()
        self.wfile.write(b"ok" if healthy else b"")

    def log_message(self, *_args):
        pass


def shutdown(_signum, _frame):
    if supervisor.poll() is None:
        supervisor.terminate()
    raise SystemExit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
HTTPServer(("0.0.0.0", 49999), HealthHandler).serve_forever()
