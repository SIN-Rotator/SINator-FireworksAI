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

DEAD_KEY_CODES = {401, 402, 403, 412}
SWAP_REASONS = {
    401: "unauthorized",
    402: "credits_exhausted",
    403: "suspended",
    412: "suspended",
    429: "rate_limited",
}

PERMANENT_429_KEYWORDS = ("spending limit", "monthly", "quota exceeded", "suspended")


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
        app.router.add_get("/health", self._health)
        app.router.add_get("/pool-status", self._pool_status)
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
        promoted = self.cache.promote_backup()
        if promoted:
            asyncio.create_task(self._fetch_backup())
            return promoted
        lease_result = await self.pool_client.lease(leased_to=self.proxy_id)
        if not lease_result:
            return None
        key_info = self._lease_to_key_info(lease_result)
        self.cache.set_primary(key_info)
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
            await self.pool_client.report(
                key_id=old.get("key_id"),
                api_key=old.get("api_key"),
                reason=reason,
            )
            self.cache.clear_primary()
        promoted = self.cache.promote_backup()
        if promoted:
            logger.info(f"Key swapped ({reason}): promoted backup {promoted.get('key_id','?')[:8]}...")
            asyncio.create_task(self._fetch_backup())
            return promoted
        lease_result = await self.pool_client.lease(leased_to=self.proxy_id)
        if not lease_result:
            logger.error("No replacement key available!")
            return None
        key_info = self._lease_to_key_info(lease_result)
        self.cache.set_primary(key_info)
        if lease_result.get("backup"):
            self.cache.set_backup(self._lease_to_key_info(lease_result["backup"]))
        else:
            asyncio.create_task(self._fetch_backup())
        logger.info(f"Key swapped ({reason}): new key {key_info.get('key_id','?')[:8]}...")
        return key_info

    async def _handle_proxy(self, request: web.Request) -> web.Response:
        path = request.match_info.get("path", "")
        fw_url = f"{self.fireworks_base}/{path}"
        return await self._do_proxy(request, fw_url)

    async def _handle_proxy_v1(self, request: web.Request) -> web.Response:
        path = request.match_info.get("path", "")
        fw_url = f"{self.fireworks_base}/{path}"
        return await self._do_proxy(request, fw_url)

    async def _do_proxy(self, request: web.Request, fw_url: str) -> web.Response:
        key_info = await self._ensure_key()
        if not key_info:
            return web.json_response(
                {"error": "no_api_key", "message": "No API key available in pool"},
                status=503,
            )

        headers = self._build_forward_headers(request, key_info)
        is_sse = self._is_streaming_request(request, fw_url)

        for attempt in range(self.max_retries):
            try:
                req_body = await request.read() if request.method in ("POST", "PUT", "PATCH") else None

                async with self._make_fw_request(request.method, fw_url, headers, req_body, request.query) as fw_resp:
                    status = fw_resp.status

                    if status in DEAD_KEY_CODES:
                        reason = SWAP_REASONS.get(status, "unknown")
                        logger.warning(f"Dead key: {status} ({reason}), swapping (attempt {attempt+1})...")
                        new_key = await self._swap_key(reason)
                        if new_key and attempt < self.max_retries - 1:
                            headers["Authorization"] = f"Bearer {new_key['api_key']}"
                            continue
                        error_body = await fw_resp.read()
                        return web.Response(body=error_body, status=status,
                                            content_type=fw_resp.headers.get("Content-Type", "application/json"))

                    if status == 429:
                        error_text = await fw_resp.text()
                        is_permanent = any(kw in error_text.lower() for kw in PERMANENT_429_KEYWORDS)
                        if is_permanent:
                            logger.warning(f"Permanent 429 (spending limit), swapping...")
                            new_key = await self._swap_key("rate_limited_permanent")
                            if new_key and attempt < self.max_retries - 1:
                                headers["Authorization"] = f"Bearer {new_key['api_key']}"
                                continue
                            return web.Response(body=error_text.encode(), status=429,
                                                content_type="application/json")
                        retry_after = fw_resp.headers.get("Retry-After", "5")
                        try:
                            wait = min(int(retry_after), 30)
                        except ValueError:
                            wait = 5
                        logger.info(f"Temporary 429, waiting {wait}s then retrying same key...")
                        await asyncio.sleep(wait)
                        continue

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
            if kl in ("host", "authorization", "content-length", "transfer-encoding"):
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

    async def _pool_status(self, request: web.Request) -> web.Response:
        stats = await self.pool_client.stats()
        cache_status = self.cache.status()
        return web.json_response({
            "pool": stats,
            "cache": cache_status,
            "proxy_id": self.proxy_id,
        })


def main():
    proxy = PoolProxy()
    app = proxy.create_app()
    web.run_app(app, host="0.0.0.0", port=proxy.port, print=logger.info)


if __name__ == "__main__":
    main()
