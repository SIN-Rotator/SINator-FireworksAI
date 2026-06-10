#!/usr/bin/env python3
"""
SIN-Hermes Pool Router v3

Lokaler Mini-Proxy der Requests an sinatorpool-router weiterleitet.
Bei 413/429/412/5xx automatischer Failover zum naechsten Pool MIT Cooldown.

Fix v3 (2026-05-28):
  - 413 zur Retry-Liste hinzugefuegt (vorher: sofortiger raise -> 500)
  - 413/429/412/5xx: alle Pools probieren, gleichen Fehler durchreichen
  - pool_failures mit Timestamp-Tracking -> 60s Cooldown statt permanent dead
  - Pool-skip nur wenn 3 failures INNERHALB 60s
  - Health endpoint GET /health
  - Besseres Logging mit Pool-Namen + Status

Usage:
    python3 pool-router.py &
    # Dann in config.yaml:
    #   base_url: http://localhost:9998/inference/v1

Pools (Reihenfolge = Prioritaet):
    1. http://localhost:8888
    2. http://localhost:8889
    3. http://localhost:8890
    ...
    10. http://localhost:8897

Docs: pool-router.doc.md
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import json
import sys
import os
import time
import threading

POOLS = [
    "http://localhost:8888",
    "http://localhost:8889",
    "http://localhost:8890",
    "http://localhost:8891",
    "http://localhost:8892",
    "http://localhost:8893",
    "http://localhost:8894",
    "http://localhost:8895",
    "http://localhost:8896",
    "http://localhost:8897",
]

PORT = int(os.environ.get("POOL_ROUTER_PORT", "9998"))
TIMEOUT = int(os.environ.get("POOL_ROUTER_TIMEOUT", "30"))
COOLDOWN_SECONDS = int(os.environ.get("POOL_ROUTER_COOLDOWN", "60"))
MAX_FAILURES = int(os.environ.get("POOL_ROUTER_MAX_FAILURES", "3"))

# Issue #24 — Cloudflare Worker fallback. When every local pool is dead/skipped
# the router transparently forwards to the CF Worker (D1-backed key rotation).
CF_WORKER_URL = os.environ.get("CF_WORKER_URL", "").rstrip("/")
CF_AUTH_TOKEN = os.environ.get("SINATOR_AUTH_TOKEN", "").strip()

# Auth token for incoming requests (same as proxy's SINATOR_AUTH_TOKEN).
# All requests EXCEPT /health must carry `Authorization: Bearer {AUTH_TOKEN}`.
AUTH_TOKEN = os.environ.get("SINATOR_AUTH_TOKEN", "").strip()

# Timestamp-based failure tracking: {pool_idx: [timestamp, timestamp, ...]}
_pool_failure_timestamps = {i: [] for i in range(len(POOLS))}
_lock = threading.Lock()


def _get_recent_failures(idx):
    """Return number of failures in the last COOLDOWN_SECONDS window."""
    now = time.time()
    cutoff = now - COOLDOWN_SECONDS
    with _lock:
        ts_list = _pool_failure_timestamps[idx]
        fresh = [t for t in ts_list if t > cutoff]
        _pool_failure_timestamps[idx] = fresh
        return len(fresh)


def _record_failure(idx):
    """Record a failure timestamp for the pool."""
    with _lock:
        _pool_failure_timestamps[idx].append(time.time())


def _record_success(idx):
    """Remove one failure (oldest) on success."""
    with _lock:
        ts_list = _pool_failure_timestamps[idx]
        if ts_list:
            ts_list.pop(0)


def _is_pool_available(idx):
    """Check if pool can be tried (less than MAX_FAILURES in window)."""
    return _get_recent_failures(idx) < MAX_FAILURES


def _pool_status():
    """Return human-readable pool status for health endpoint."""
    status = {}
    for idx, base in enumerate(POOLS):
        recent = _get_recent_failures(idx)
        status[f"pool_{idx+1}"] = {
            "url": base,
            "recent_failures": recent,
            "max_failures": MAX_FAILURES,
            "available": recent < MAX_FAILURES,
        }
    return status


class PoolHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[PoolRouter] {format % args}", flush=True)

    # ── Auth ──────────────────────────────────────────────────────────────
    def _is_authenticated(self) -> bool:
        if not AUTH_TOKEN:
            return True
        return self.headers.get("Authorization", "") == f"Bearer {AUTH_TOKEN}"

    def _send_401(self):
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "error": "unauthorized",
            "message": "Invalid or missing auth token",
        }).encode())

    # ── CF Fallback ───────────────────────────────────────────────────────
    def _try_cf_fallback(self, method, path, body=None, headers=None):
        """Issue #24: forward to the Cloudflare Worker when local pools are gone.

        Returns (response_body, status, headers) or raises so the caller can
        surface the original local error. The CF Worker handles its own D1 key
        rotation, so we just relay the request 1:1.
        """
        if not CF_WORKER_URL:
            raise RuntimeError("No CF fallback configured (CF_WORKER_URL unset)")

        url = CF_WORKER_URL + path
        req = urllib.request.Request(url, method=method)
        if headers:
            for k, v in headers.items():
                if k.lower() not in ("host", "content-length"):
                    req.add_header(k, v)
        # Ensure the Worker accepts us even if the client sent no auth.
        if CF_AUTH_TOKEN and not req.has_header("Authorization"):
            req.add_header("Authorization", f"Bearer {CF_AUTH_TOKEN}")
        if body:
            req.add_header("Content-Length", str(len(body)))
            req.data = body

        print(f"[PoolRouter] FALLBACK → Cloudflare Worker: {url}", flush=True)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                print(f"[PoolRouter] CF Worker OK ({resp.status})", flush=True)
                return (resp.read(), resp.status, dict(resp.headers))
        except urllib.error.HTTPError as e:
            # Pass the Worker's own error through — it is the authoritative
            # source once the Mac pool is exhausted.
            err_body = e.read()
            print(f"[PoolRouter] CF Worker returned {e.code}", flush=True)
            return (err_body, e.code, dict(e.headers))

    def _try_pools(self, method, path, body=None, headers=None):
        """Try each pool in order. Return (response_body, status, headers) or raise.

        If all pools fail with the SAME error, pass it through — indicates
        an upstream API issue (e.g. 413 Payload Too Large), not a pool failure.
        Only raise 'All pools exhausted' when pools fail differently.
        """
        last_error = None
        pool_errors = []  # (pool_idx, error_body, status_code)
        for idx, base in enumerate(POOLS):
            if not _is_pool_available(idx):
                recent = _get_recent_failures(idx)
                print(
                    f"[PoolRouter] Pool {idx+1} SKIPPED "
                    f"({recent} failures in {COOLDOWN_SECONDS}s window)",
                    flush=True,
                )
                continue

            url = base + path
            req = urllib.request.Request(url, method=method)

            if headers:
                for k, v in headers.items():
                    if k.lower() not in ("host", "content-length"):
                        req.add_header(k, v)

            if body:
                req.add_header("Content-Length", str(len(body)))
                req.data = body

            print(f"[PoolRouter] Trying Pool {idx+1}: {url}", flush=True)

            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    _record_success(idx)
                    print(f"[PoolRouter] Pool {idx+1} OK ({resp.status})", flush=True)
                    return (resp.read(), resp.status, dict(resp.headers))

            except urllib.error.HTTPError as e:
                last_error = e
                err_body = e.read().decode(errors="replace")[:200]
                pool_errors.append((idx, err_body, e.code))
                if e.code in (413, 429, 412, 500, 502, 503, 504):
                    recent = _get_recent_failures(idx)
                    print(
                        f"[PoolRouter] Pool {idx+1} returned {e.code} "
                        f"(recent failures: {recent}/{MAX_FAILURES})",
                        flush=True,
                    )
                    continue
                raise

            except Exception as e:
                last_error = e
                pool_errors.append((idx, str(e)[:200], 0))
                recent = _get_recent_failures(idx)
                print(
                    f"[PoolRouter] Pool {idx+1} error: {e} "
                    f"(recent failures: {recent}/{MAX_FAILURES})",
                    flush=True,
                )
                continue

        # Did EVERY pool get skipped (Mac dead / all in cooldown)? Then there is
        # no live local pool at all → go straight to the Cloudflare fallback.
        all_unavailable = all(not _is_pool_available(i) for i in range(len(POOLS)))

        # All pools failed — check if they all failed identically
        if (
            not all_unavailable
            and pool_errors
            and len(set((body, code) for _, body, code in pool_errors)) <= 2
        ):
            # All pools returned same/similar error — upstream API issue, pass through
            _, err_body, status_code = pool_errors[-1]
            print(
                f"[PoolRouter] All pools returned same error → passing through "
                f"(status {status_code})",
                flush=True,
            )
            return (err_body.encode(), status_code or 500, {"Content-Type": "application/json"})

        # Issue #24: local pool exhausted → try Cloudflare Worker fallback.
        if CF_WORKER_URL:
            try:
                return self._try_cf_fallback(method, path, body, headers)
            except Exception as cf_err:
                print(f"[PoolRouter] CF fallback failed: {cf_err}", flush=True)

        err_msg = f"All pools exhausted (and CF fallback unavailable). Last error: {last_error}"
        raise RuntimeError(err_msg)

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            status = {
                "status": "ok",
                "cooldown_seconds": COOLDOWN_SECONDS,
                "max_failures": MAX_FAILURES,
                "pools": _pool_status(),
            }
            self.wfile.write(json.dumps(status).encode())
            return
        if not self._is_authenticated():
            return self._send_401()
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
        if not self._is_authenticated():
            return self._send_401()

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

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


class ThreadedPoolServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    print(f"[PoolRouter v3] Starting on port {PORT}")
    print(f"[PoolRouter] Pools: {POOLS}")
    print(f"[PoolRouter] Retry on: 413, 429, 412, 500, 502, 503, 504")
    print(f"[PoolRouter] Max failures: {MAX_FAILURES} per {COOLDOWN_SECONDS}s window")
    if CF_WORKER_URL:
        print(f"[PoolRouter] CF fallback: {CF_WORKER_URL}")
    else:
        print("[PoolRouter] CF fallback: DISABLED (set CF_WORKER_URL to enable)")
    print(f"[PoolRouter] Health: http://localhost:{PORT}/health")

    with ThreadedPoolServer(("", PORT), PoolHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[PoolRouter] Shutting down")
            sys.exit(0)


if __name__ == "__main__":
    main()
