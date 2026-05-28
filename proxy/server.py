"""
Fireworks Pool Proxy — aiohttp-based async proxy with SSE streaming.

Features:
  - SSE streaming for chat/completions (CRITICAL — old proxy couldn't do this)
  - Auto-swap on 401/402/403/412/429 errors
  - Lease-based key management (atomic, TTL-based)
  - Pre-fetch backup key for 0ms swap
  - Health + status endpoints

Usage:
  python -m proxy.server
  SIN_PROXY_PORT=8888 python -m proxy.server
"""
import os
import sys
import asyncio
import logging
import time
import json
from pathlib import Path
from typing import Optional

import aiohttp
from aiohttp import web

_script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_script_dir))
sys.path.insert(0, str(_script_dir.parent))

try:
    from proxy.config import load_config, FIREWORKS_BASE
    from proxy.pool_client import PoolClient
    from proxy.key_cache import KeyCache
except ImportError:
    from config import load_config, FIREWORKS_BASE
    from pool_client import PoolClient
    from key_cache import KeyCache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("pool-proxy")

POOL_AUTH_TOKEN = os.environ.get("SINATOR_AUTH_TOKEN", "").strip()
NO_BACKUP = os.environ.get("SIN_NO_BACKUP", "false").lower() == "true"

DEAD_KEY_CODES = {401, 402, 403, 412}
SWAP_REASONS = {
    401: "unauthorized",
    402: "credits_exhausted",
    403: "suspended",
    412: "suspended",
    429: "rate_limited",
}

PERMANENT_429_KEYWORDS = ("account.*suspended", "monthly spending limit", "reached.*limit", "suspended due to", "spending limit")
# Keine "monthly" oder "quota exceeded" allein — zu viele False Positives

# Alle Codes werden VERIFIZIERT (Body-Check + /chat/completions) bevor ein Swap passiert.
# NICHTS wird blind als "tot" angenommen — auch 402 nicht.
PERMANENT_ERROR_KEYWORDS = ("suspended", "deactivated", "disabled", "invalid api key", "revoked", "expired", "payment required")
CONFIRMED_DEAD_CODES = set()  # LEER — alles wird verifiziert
MAYBE_DEAD_CODES = {401, 402, 403, 412}

PUBLIC_PROXY_PATHS = ("/health", "/pool-status", "/v1/models")

CORS_ALLOW_HEADERS = "Authorization, Content-Type, Accept, Origin"

@web.middleware
async def _cors_middleware(request: web.Request, handler) -> web.Response:
    origin = request.headers.get("Origin", "*")
    cors_hdrs = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": CORS_ALLOW_HEADERS,
        "Access-Control-Max-Age": "86400",
    }
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=cors_hdrs)
    resp = await handler(request)
    for k, v in cors_hdrs.items():
        resp.headers[k] = v
    return resp

@web.middleware
async def _pool_auth_middleware(request: web.Request, handler) -> web.Response:
    if not POOL_AUTH_TOKEN:
        return await handler(request)
    path = request.path
    if path in PUBLIC_PROXY_PATHS:
        return await handler(request)
    peer = request.transport.get_extra_info("peername")
    if peer:
        host = peer[0]
        if host.startswith("::ffff:"):
            host = host[7:]
        if host in ("127.0.0.1", "::1"):
            return await handler(request)
    if path.startswith("/inference/") or path.startswith("/v1/") or path == "/pool-lease":
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {POOL_AUTH_TOKEN}":
            return web.json_response(
                {"error": "unauthorized", "message": "Invalid or missing auth token"},
                status=401,
            )
    return await handler(request)


class PoolProxy:
    def __init__(self):
        cfg = load_config()
        self.port = cfg.get("proxy_port", 8888)
        self.fireworks_base = cfg.get("fireworks_base", FIREWORKS_BASE)
        self.max_retries = cfg.get("max_retries", 3)
        self.pool_client = PoolClient(cfg.get("pool_api_url"))
        self.cache = KeyCache()
        self.fw_session: Optional[aiohttp.ClientSession] = None
        self.proxy_id = f"proxy-{int(time.time())}"

    def create_app(self) -> web.Application:
        app = web.Application()
        app.middlewares.append(_cors_middleware)
        app.middlewares.append(_pool_auth_middleware)
        app.router.add_get("/health", self._health)
        app.router.add_get("/pool-status", self._pool_status)
        app.router.add_get("/pool-lease", self._lease_key)
        app.router.add_get("/v1/models", self._handle_v1_models)
        app.router.add_get("/inference/v1/models", self._handle_v1_models)
        app.router.add_route("*", "/inference/v1/{path:.*}", self._handle_proxy)
        app.router.add_route("*", "/v1/{path:.*}", self._handle_proxy_v1)
        app.on_startup.append(self._on_startup)
        app.on_shutdown.append(self._on_shutdown)
        return app

    async def _on_startup(self, app):
        self.fw_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300, sock_read=120),
        )
        logger.info(f"Pool Proxy starting on :{self.port}")
        logger.info(f"  Fireworks base: {self.fireworks_base}")
        logger.info(f"  Pool API: {self.pool_client.pool_api_url}")

    async def _on_shutdown(self, app):
        if self.cache.primary:
            await self.pool_client.return_key(
                self.cache.primary.get("key_id", ""),
                self.cache.primary.get("lease_id"),
            )
            logger.info("Returned primary key on shutdown")
        if self.cache.backup:
            await self.pool_client.return_key(
                self.cache.backup.get("key_id", ""),
                self.cache.backup.get("lease_id"),
            )
            logger.info("Returned backup key on shutdown")
        await self.pool_client.close()
        if self.fw_session:
            await self.fw_session.close()

    async def _ensure_key(self) -> Optional[dict]:
        primary = self.cache.get_primary()
        if primary:
            return primary
        if not NO_BACKUP:
            promoted = self.cache.promote_backup()
            if promoted:
                asyncio.create_task(self._fetch_backup())
                return promoted
        lease_result = await self.pool_client.lease(leased_to=self.proxy_id)
        if not lease_result:
            return None
        key_info = self._lease_to_key_info(lease_result)
        self.cache.set_primary(key_info)
        if not NO_BACKUP:
            if lease_result.get("backup"):
                self.cache.set_backup(self._lease_to_key_info(lease_result["backup"]))
            else:
                asyncio.create_task(self._fetch_backup())
        return key_info

    @staticmethod
    def _lease_to_key_info(lease: dict) -> dict:
        return {
            "api_key": lease["api_key"],
            "key_id": lease["key_id"],
            "lease_id": lease.get("lease_id", ""),
            "expires_at": lease.get("expires_at", 0),
            "alias_email": lease.get("alias_email", ""),
            "key_name": lease.get("key_name", ""),
        }

    async def _fetch_backup(self):
        try:
            lease_result = await self.pool_client.lease(leased_to=f"{self.proxy_id}-backup")
            if lease_result:
                self.cache.set_backup(self._lease_to_key_info(lease_result))
        except Exception as e:
            logger.warning(f"Backup lease failed: {e}")

    async def _swap_key(self, reason: str) -> Optional[dict]:
        old = self.cache.primary
        if old:
            report_result = await self.pool_client.report(
                key_id=old.get("key_id"),
                api_key=old.get("api_key"),
                reason=reason,
                leased_to=self.proxy_id,
            )
            self.cache.clear_primary()
            # Use the replacement key returned by report() (already leased atomically)
            if report_result and report_result.get("new_key"):
                key_info = {
                    "api_key": report_result["new_key"],
                    "key_id": report_result.get("new_key_id", ""),
                    "lease_id": report_result.get("lease_id", ""),
                    "expires_at": report_result.get("expires_at", 0),
                    "alias_email": report_result.get("new_alias", ""),
                    "key_name": report_result.get("new_key_name", ""),
                }
                self.cache.set_primary(key_info)
                logger.info(f"Key swapped ({reason}): new key {key_info.get('key_id','?')[:8]}... (from report+lease)")
                return key_info

        # Fallback: report didn't return a replacement → lease one
        if not NO_BACKUP:
            promoted = self.cache.promote_backup()
            if promoted:
                asyncio.create_task(self._fetch_backup())
                return promoted
        lease_result = await self.pool_client.lease(leased_to=self.proxy_id)
        if not lease_result:
            logger.error("No replacement key available!")
            return None
        key_info = self._lease_to_key_info(lease_result)
        self.cache.set_primary(key_info)
        if not NO_BACKUP:
            if lease_result.get("backup"):
                self.cache.set_backup(self._lease_to_key_info(lease_result["backup"]))
            else:
                asyncio.create_task(self._fetch_backup())
        logger.info(f"Key swapped ({reason}): new key {key_info.get('key_id','?')[:8]}...")
        return key_info

    MAX_CONSECUTIVE_SWAPS = 2

    async def _verify_key_dead(self, api_key: str) -> bool:
        """Verify key via lightweight chat request — more accurate than /models."""
        try:
            body = {
                "model": "accounts/fireworks/models/llama-v3p1-8b-instruct",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
                "stream": False,
            }
            async with self.fw_session.post(
                f"{self.fireworks_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status == 200:
                    return False
                text = await r.text()
                is_dead = any(kw in text.lower() for kw in PERMANENT_ERROR_KEYWORDS)
                logger.debug(f"Key verification: HTTP {r.status}, dead={is_dead}, body={text[:120]}")
                return is_dead
        except Exception:
            return False

    async def _handle_proxy(self, request: web.Request) -> web.Response:
        path = request.match_info.get("path", "")
        fw_url = f"{self.fireworks_base}/{path}"
        return await self._do_proxy(request, fw_url)

    async def _handle_proxy_v1(self, request: web.Request) -> web.Response:
        path = request.match_info.get("path", "")
        fw_url = f"{self.fireworks_base}/{path}"
        return await self._do_proxy(request, fw_url)

    async def _handle_v1_models(self, request: web.Request) -> web.Response:
        """Return all Fireworks models from the models.dev cache.

        Reads the community-maintained models.dev registry on disk
        (``~/.hermes/models_dev_cache.json``) to list ALL Fireworks
        models and routers — not just the subset the current pool key
        can access.

        Falls back to a curated subset if the cache is unavailable.
        """
        cache_path = Path.home() / ".hermes" / "models_dev_cache.json"
        try:
            raw = cache_path.read_text()
            registry = json.loads(raw)
            fw_provider = registry.get("fireworks-ai", {})
            model_ids = list(fw_provider.get("models", {}).keys())
        except Exception:
            model_ids = [
                "accounts/fireworks/models/deepseek-v4-flash",
                "accounts/fireworks/models/deepseek-v4-pro",
                "accounts/fireworks/models/gpt-oss-120b",
                "accounts/fireworks/models/gpt-oss-20b",
                "accounts/fireworks/models/kimi-k2p5",
                "accounts/fireworks/models/kimi-k2p6",
                "accounts/fireworks/models/minimax-m2p5",
                "accounts/fireworks/models/minimax-m2p7",
                "accounts/fireworks/models/qwen3p6-plus",
                "accounts/fireworks/models/glm-5p1",
                "accounts/fireworks/routers/kimi-k2p6-turbo",
                "accounts/fireworks/routers/glm-5p1-fast",
            ]

        now = int(time.time())
        data = [
            {"id": m, "object": "model", "created": now, "owned_by": "fireworks"}
            for m in sorted(model_ids)
        ]
        return web.json_response({"object": "list", "data": data})

    async def _do_proxy(self, request: web.Request, fw_url: str) -> web.Response:
        key_info = await self._ensure_key()
        if not key_info:
            return web.json_response(
                {"error": "no_api_key", "message": "No API key available in pool"},
                status=503,
            )

        headers = self._build_forward_headers(request, key_info)
        is_sse = self._is_streaming_request(request, fw_url)
        consecutive_swaps = 0

        for attempt in range(self.max_retries):
            try:
                req_body = await request.read() if request.method in ("POST", "PUT", "PATCH") else None

                async with self._make_fw_request(request.method, fw_url, headers, req_body, request.query) as fw_resp:
                    status = fw_resp.status

                    if status in DEAD_KEY_CODES:
                        error_body_bytes = await fw_resp.read()
                        error_text = error_body_bytes.decode(errors="replace").lower()

                        consecutive_swaps += 1
                        if consecutive_swaps > self.MAX_CONSECUTIVE_SWAPS:
                            logger.error(f"Cascade stop: {consecutive_swaps} swaps, returning error")
                            return web.Response(body=error_body_bytes, status=status,
                                                content_type=fw_resp.headers.get("Content-Type", "application/json"))
                        reason = SWAP_REASONS.get(status, "unknown")
                        if status in MAYBE_DEAD_CODES:
                            # Prüfe Response-Body auf echte Dead-Keywords
                            is_confirmed_dead = any(kw in error_text for kw in PERMANENT_ERROR_KEYWORDS)
                            # Verifiziere zusätzlich via /models
                            models_dead = await self._verify_key_dead(key_info['api_key'])
                            if not is_confirmed_dead and not models_dead:
                                logger.warning(f"Key got {status} but error body + /models don't confirm dead — retrying same key")
                                await asyncio.sleep(2)
                                continue
                            if is_confirmed_dead:
                                logger.info(f"Confirmed dead via error body: {status} ({reason}) — matched keyword in response")
                        logger.warning(f"Dead key: {status} ({reason}), swapping (attempt {attempt+1})...")
                        new_key = await self._swap_key(reason)
                        if new_key and attempt < self.max_retries - 1:
                            headers["Authorization"] = f"Bearer {new_key['api_key']}"
                            # Key wurde intern getauscht — sag dem Client er soll retryen
                            return web.Response(
                                body=b'{"error":"key_swapped","message":"Pool key rotated, please retry","retry_after":1}',
                                status=503,
                                content_type="application/json",
                                headers={"Retry-After": "1"},
                            )
                        return web.Response(body=error_body_bytes, status=status,
                                            content_type=fw_resp.headers.get("Content-Type", "application/json"))

                    if status == 429:
                        error_text = await fw_resp.text()
                        is_permanent = any(kw in error_text.lower() for kw in PERMANENT_429_KEYWORDS)
                        if is_permanent:
                            consecutive_swaps += 1
                            if consecutive_swaps > self.MAX_CONSECUTIVE_SWAPS:
                                logger.error(f"Cascade stop: {consecutive_swaps} swaps for permanent 429")
                                return web.Response(body=error_text.encode(), status=429,
                                                    content_type="application/json")
                            logger.warning(f"Permanent 429 (spending limit matched: {[kw for kw in PERMANENT_429_KEYWORDS if kw in error_text.lower()]}), swapping...")
                            new_key = await self._swap_key("rate_limited_permanent")
                            if new_key and attempt < self.max_retries - 1:
                                headers["Authorization"] = f"Bearer {new_key['api_key']}"
                                # Intern getauscht — Client retryen
                                return web.Response(
                                    body=b'{"error":"key_rotated","message":"Rate limit reached, key rotated. Retry now.","retry_after":1}',
                                    status=503,
                                    content_type="application/json",
                                    headers={"Retry-After": "1"},
                                )
                            return web.Response(body=error_text.encode(), status=429,
                                                content_type="application/json")
                        # Transientes 429 — SOFORT an Client zurückgeben mit Retry-After
                        # (nicht intern warten — verhindert Client-Timeouts + InvalidHTTPResponse)
                        retry_after = fw_resp.headers.get("Retry-After", "5")
                        try:
                            wait = min(int(retry_after), 30)
                        except ValueError:
                            wait = 5
                        logger.info(f"Temporary 429, returning to client with Retry-After: {wait}s")
                        return web.Response(
                            body=error_text.encode(),
                            status=429,
                            content_type=fw_resp.headers.get("Content-Type", "application/json"),
                            headers={"Retry-After": str(wait)},
                        )

                    if status >= 500:
                        logger.warning(f"Fireworks server error: {status}, retrying (attempt {attempt+1})...")
                        await asyncio.sleep(2)
                        continue

                    if is_sse and status == 200:
                        return await self._stream_sse(request, fw_resp)

                    body = await fw_resp.read()
                    resp = web.Response(body=body, status=status)
                    for k, v in fw_resp.headers.items():
                        kl = k.lower()
                        if kl not in ("transfer-encoding", "content-encoding", "connection"):
                            resp.headers[k] = v
                    return resp

            except asyncio.TimeoutError:
                logger.warning(f"Fireworks timeout (attempt {attempt+1})")
                continue
            except aiohttp.ClientError as e:
                logger.warning(f"Fireworks connection error: {e}")
                await asyncio.sleep(2)
                continue

        return web.json_response(
            {"error": "max_retries_exceeded", "message": f"Failed after {self.max_retries} attempts"},
            status=502,
        )

    @staticmethod
    def _build_forward_headers(request: web.Request, key_info: dict) -> dict:
        headers = {}
        for k, v in request.headers.items():
            kl = k.lower()
            if kl in ("host", "authorization", "content-length", "transfer-encoding", "x-api-key"):
                continue
            headers[k] = v
        headers["Authorization"] = f"Bearer {key_info['api_key']}"
        headers["Host"] = "api.fireworks.ai"
        return headers

    def _make_fw_request(self, method: str, url: str, headers: dict,
                         body: Optional[bytes], query: dict):
        if method == "GET":
            return self.fw_session.get(url, headers=headers, params=query)
        elif method == "POST":
            return self.fw_session.post(url, headers=headers, data=body)
        elif method == "PUT":
            return self.fw_session.put(url, headers=headers, data=body)
        elif method == "PATCH":
            return self.fw_session.patch(url, headers=headers, data=body)
        elif method == "DELETE":
            return self.fw_session.delete(url, headers=headers)
        return self.fw_session.get(url, headers=headers)

    @staticmethod
    def _is_streaming_request(request: web.Request, path: str) -> bool:
        accept = request.headers.get("Accept", "")
        if "text/event-stream" in accept:
            return True
        if "/chat/completions" in path or "/completions" in path:
            return True
        return False

    async def _stream_sse(self, request: web.Request, fw_resp) -> web.Response:
        resp = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": fw_resp.headers.get("Content-Type", "text/event-stream"),
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        await resp.prepare(request)
        try:
            async for chunk in fw_resp.content.iter_chunked(4096):
                await resp.write(chunk)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        await resp.write_eof()
        return resp

    async def _health(self, request: web.Request) -> web.Response:
        key = self.cache.get_primary()
        return web.json_response({
            "status": "ok" if key else "no_key",
            "proxy_id": self.proxy_id,
            "primary_key": key.get("key_id", "")[:8] + "..." if key else None,
            "primary_alias": key.get("alias_email") if key else None,
            "backup_key": self.cache.backup.get("key_id", "")[:8] + "..." if self.cache.backup else None,
            "request_count": self.cache.request_count,
        })

    async def _lease_key(self, request: web.Request) -> web.Response:
        """Lease a single API key from the pool."""
        try:
            leased_to = request.query.get("leased_to", f"app-{time.time():.0f}")
            result = await self.pool_client.lease(leased_to=leased_to)
            if not result:
                return web.json_response(
                    {"error": "no_keys", "message": "No API keys available"},
                    status=503,
                )
            return web.json_response({
                "api_key": result["api_key"],
                "key_name": result.get("key_name", ""),
                "alias_email": result.get("alias_email", ""),
                "key_id": result.get("key_id", ""),
            })
        except Exception as e:
            logger.error(f"Lease key error: {e}")
            return web.json_response(
                {"error": "lease_failed", "message": str(e)},
                status=500,
            )

    async def _pool_status(self, request: web.Request) -> web.Response:
        stats = await self.pool_client.stats()
        cache_status = self.cache.status()
        return web.json_response({
            "pool": stats,
            "cache": cache_status,
            "proxy_id": self.proxy_id,
        })


def main():
    import urllib.request
    backend_wait = int(os.environ.get("SIN_BACKEND_WAIT", "5"))
    for i in range(backend_wait):
        try:
            urllib.request.urlopen("http://localhost:8000/health", timeout=2)
            logger.info(f"✅ Backend ready (waited {i}s)")
            break
        except Exception:
            if i == 0:
                logger.info(f"⏳ Waiting for backend on :8000 (max {backend_wait*sleep}s)...")
            time.sleep(1)
    else:
        logger.warning("⚠️ Backend not ready — proxy will start anyway")

    proxy = PoolProxy()
    app = proxy.create_app()
    web.run_app(app, host="0.0.0.0", port=proxy.port, print=logger.info)


if __name__ == "__main__":
    main()
