#!/usr/bin/env python3
"""
SIN-Hermes Pool Router

Lokaler Mini-Proxy der Requests an sinatorpool1/2/3 weiterleitet.
Bei 429/412/5xx automatischer Failover zum nächsten Pool.

Usage:
    python3 pool-router.py &
    # Dann in config.yaml:
    #   base_url: http://localhost:9998/inference/v1

Pools (Reihenfolge = Priorität):
    1. https://sinatorpool1.delqhi.com/inference/v1
    2. https://sinatorpool2.delqhi.com/inference/v1
    3. https://sinatorpool3.delqhi.com/inference/v1
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import json
import sys
import os

POOLS = [
    "https://sinatorpool1.delqhi.com",
    "https://sinatorpool2.delqhi.com",
    "https://sinatorpool3.delqhi.com",
]

PORT = int(os.environ.get("POOL_ROUTER_PORT", "9998"))
TIMEOUT = int(os.environ.get("POOL_ROUTER_TIMEOUT", "30"))

# Health tracking
pool_failures = {i: 0 for i in range(len(POOLS))}
MAX_FAILURES = 3


class PoolHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[PoolRouter] {fmt % args}", flush=True)

    def _try_pools(self, method, path, body=None, headers=None):
        """Try each pool in order. Return (response_body, status, headers) or raise."""
        for idx, base in enumerate(POOLS):
            if pool_failures[idx] >= MAX_FAILURES:
                print(f"[PoolRouter] Pool {idx+1} skipped (too many failures)", flush=True)
                continue

            url = base + path
            req = urllib.request.Request(url, method=method)

            # Copy headers from client, replace Host
            if headers:
                for k, v in headers.items():
                    if k.lower() not in ("host", "content-length"):
                        req.add_header(k, v)

            if body:
                req.add_header("Content-Length", str(len(body)))
                req.data = body

            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    pool_failures[idx] = max(0, pool_failures[idx] - 1)
                    return (resp.read(), resp.status, dict(resp.headers))

            except urllib.error.HTTPError as e:
                # Retry-triggering status codes
                if e.code in (429, 412, 500, 502, 503, 504):
                    pool_failures[idx] += 1
                    print(f"[PoolRouter] Pool {idx+1} returned {e.code} (failures: {pool_failures[idx]})", flush=True)
                    continue
                # Non-retryable: re-raise
                raise
            except Exception as e:
                pool_failures[idx] += 1
                print(f"[PoolRouter] Pool {idx+1} error: {e} (failures: {pool_failures[idx]})", flush=True)
                continue

        raise RuntimeError("All pools exhausted")

    def do_GET(self):
        self._proxy("GET")

    def do_POST(self):
        self._proxy("POST")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _proxy(self, method):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # Capture headers
        headers = {k: v for k, v in self.headers.items()}

        try:
            resp_body, status, resp_headers = self._try_pools(method, self.path, body, headers)

            self.send_response(status)
            for k, v in resp_headers.items():
                if k.lower() not in ("transfer-encoding", "content-encoding", "content-length"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)

        except RuntimeError as e:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())


if __name__ == "__main__":
    print(f"[PoolRouter] Starting on port {PORT}")
    print(f"[PoolRouter] Pools: {POOLS}")
    print(f"[PoolRouter] Retry on: 429, 412, 500, 502, 503, 504")
    print(f"[PoolRouter] Max failures before skip: {MAX_FAILURES}")

    with socketserver.TCPServer(("", PORT), PoolHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[PoolRouter] Shutting down")
            sys.exit(0)
