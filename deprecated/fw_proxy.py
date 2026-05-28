#!/usr/bin/env python3
"""
Fireworks API Proxy — Auto-Swap bei Rate-Limit (402/429).

Erkennt gesperrte Keys automatisch, meldet sie an den Pool,
holt einen neuen Key und updated OpenCode auth.json — alles
transparent, der Client merkt nur eine minimale Verzögerung.

Usage:
    python tools/fw_proxy.py              # startet auf :9090
    python tools/fw_proxy.py --port 8080  # custom port

OpenCode muss auf http://localhost:9090 zeigen statt api.fireworks.ai.
"""
import json
import os
import sys
import time
import logging
import urllib.request
import urllib.error
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("fw-proxy")

AUTH_FILE = Path.home() / ".local/share/opencode/auth.json"
POOL_API = "http://localhost:8000/api/v1"
FIREWORKS_HOST = "api.fireworks.ai"
MAX_RETRIES = 3


def _get_current_key() -> str | None:
    """Read current Fireworks key from auth.json."""
    if AUTH_FILE.exists():
        auth = json.loads(AUTH_FILE.read_text())
        return auth.get("fireworks")
    return None


def _update_auth_file(new_key: str):
    """Write new key into auth.json."""
    auth = {}
    if AUTH_FILE.exists():
        auth = json.loads(AUTH_FILE.read_text())
    auth["fireworks"] = new_key
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(auth, indent=2))
    logger.info(f"auth.json updated with new key: {new_key[:20]}...")


def _report_key(bad_key: str) -> dict:
    """Call /pool/report to mark key as used and get a new one."""
    url = f"{POOL_API}/pool/report"
    body = json.dumps({"api_key": bad_key}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        logger.warning(f"Pool report failed: {e.code} {e.read().decode()[:200]}")
        return {}
    except Exception as e:
        logger.warning(f"Pool report error: {e}")
        return {}


def _is_rate_limited(status: int, body: str) -> bool:
    """Check if response indicates a rate-limited or suspended key."""
    if status in (402, 429):
        return True
    if status == 403 and ("suspended" in body.lower() or "rate limit" in body.lower()):
        return True
    return False


class FireworksProxyHandler(BaseHTTPRequestHandler):
    """Proxied requests to api.fireworks.ai with auto-swap on 402/429."""

    def do_GET(self):
        self._proxy_request("GET")

    def do_POST(self):
        self._proxy_request("POST")

    def do_PUT(self):
        self._proxy_request("PUT")

    def do_DELETE(self):
        self._proxy_request("DELETE")

    def do_PATCH(self):
        self._proxy_request("PATCH")

    def _proxy_request(self, method: str):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        retries = 0
        last_error = None
        current_key = _get_current_key()

        while retries < MAX_RETRIES:
            if not current_key:
                self._send_error(502, "No Fireworks API key found in auth.json")
                return

            try:
                status, resp_headers, resp_body = self._forward(
                    method, current_key, body
                )

                resp_text = resp_body.decode("utf-8", errors="replace")

                if _is_rate_limited(status, resp_text):
                    logger.warning(
                        f"Rate-limit/suspended detected (HTTP {status}) for "
                        f"{current_key[:20]}... — swapping..."
                    )

                    # Report key to pool, get new one
                    result = _report_key(current_key)
                    new_key = result.get("new_key")

                    if new_key and new_key != current_key:
                        _update_auth_file(new_key)
                        current_key = new_key
                        retries += 1
                        logger.info(f"Retry {retries}/{MAX_RETRIES} with new key")
                        continue
                    else:
                        logger.error("No replacement key available from pool")
                        self._send_error(
                            503, "No available API keys in pool. Run rotation."
                        )
                        return

                # Success or non-rate-limit error — forward as-is
                self.send_response(status)
                for key, val in resp_headers:
                    # Skip transfer-encoding/chunked since we're re-sending the body
                    if key.lower() in ("transfer-encoding", "content-encoding", "content-length"):
                        continue
                    self.send_header(key, val)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
                return

            except Exception as e:
                last_error = str(e)
                logger.error(f"Request failed: {e}")
                retries += 1
                time.sleep(1)

        self._send_error(502, f"Proxy error after {MAX_RETRIES} retries: {last_error}")

    def _forward(self, method: str, api_key: str, body: bytes):
        """Forward request to api.fireworks.ai and return (status, headers, body)."""
        path = self.path
        url = f"https://{FIREWORKS_HOST}{path}"

        req = urllib.request.Request(url, data=body or None, method=method)
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))

        # Forward relevant headers
        for header_name in ("Accept", "User-Agent", "Origin", "Referer"):
            if header_name in self.headers:
                req.add_header(header_name, self.headers[header_name])

        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp_body = r.read()
                return r.status, list(r.headers.items()), resp_body
        except urllib.error.HTTPError as e:
            resp_body = e.read()
            return e.code, list(e.headers.items()), resp_body

    def _send_error(self, code: int, message: str):
        """Send a JSON error response."""
        body = json.dumps({"error": {"message": message, "type": "proxy_error"}}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")


def main():
    port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--port" else 9090

    server = HTTPServer(("127.0.0.1", port), FireworksProxyHandler)
    logger.info(f"🔥 Fireworks Proxy on http://127.0.0.1:{port}")
    logger.info(f"   Point OpenCode to: http://127.0.0.1:{port}")
    logger.info(f"   Auto-swap on 402/429 → pool → update auth.json → retry")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
