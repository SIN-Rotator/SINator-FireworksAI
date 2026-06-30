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

Docs: server.doc.md
"""
import os
import sys
import asyncio
import logging
import time
import json
from pathlib import Path
from typing import Any, Dict, Optional

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

try:
    from proxy.config import AGENT_ID
except ImportError:
    from config import AGENT_ID

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
        self.fw_session: Optional[aiohttp.ClientSession] = None
        # V19.10: Unique proxy ID — port + random suffix.
        # Before: f"proxy-{int(time.time())}" — all 10 proxies in start-multi.sh
        # started within the same second, so they ALL got the same ID.
        # This caused 52+20 leases to pile up under one leased_to and
        # made the pool unusable (only 12 available of 256 total).
        import random as _random
        self.proxy_id = f"proxy-{self.port}-{_random.randint(1000, 9999)}"
        self.agent_id = getattr(load_config(), 'agent_id', AGENT_ID)  # V19.14
        try:
            from proxy.key_cache import AgentKeyCache
        except ImportError:
            from key_cache import AgentKeyCache
        self.cache = AgentKeyCache(agent_id=self.agent_id)
        # V19.14 Phase 2: Per-session AgentKeyCaches, keyed by x-agent-id header
        self._session_caches: Dict[str, Any] = {}
        self._session_caches[self.agent_id] = self.cache  # default proxy cache

    def _get_session_cache(self, agent_id: str):
        """V19.14 Phase 2: Get or create AgentKeyCache for a session agent_id."""
        if agent_id not in self._session_caches:
            try:
                from proxy.key_cache import AgentKeyCache
            except ImportError:
                from key_cache import AgentKeyCache
            self._session_caches[agent_id] = AgentKeyCache(agent_id=agent_id)
            logger.info(f"V19.14: New session cache for {agent_id} (total sessions: {len(self._session_caches)})")
        return self._session_caches[agent_id]

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
        """V19.14: Release ALL session keys on shutdown."""
        for agent_id, cache in list(self._session_caches.items()):
            if cache.primary:
                await self.pool_client.release_agent_key(
                    agent_id,
                    cache.primary.get("key_id", ""),
                )
                logger.info(f"Released session key for {agent_id}")
        await self.pool_client.close()
        if self.fw_session:
            await self.fw_session.close()

    async def _ensure_key(self, agent_id: str = None):
        """V19.14: Soft-ownership — never blocks, never retries.
        
        Uses per-session AgentKeyCache if x-agent-id header is present.
        Falls back to proxy's default agent_id.
        """
        if agent_id is None:
            agent_id = self.agent_id
        
        # Get the right cache for this session
        cache = self._get_session_cache(agent_id)
        
        # 1. Cache hit
        key = cache.get_primary()
        if key:
            return key
        
        # 2. Get from backend (no retry loop!)
        result = await self.pool_client.get_agent_key(
            agent_id=agent_id,
            preferred_key_id=cache.preferred_key_id,
        )
        
        if result and result.get("api_key"):
            cache.set_primary(result)
            return result
        
        # 3. FAIL-SAFE: Pool empty for this agent_id → share any cached key
        # from another agent. This handles the case where e.g. 5 keys are
        # available but 10 agents are working — agents 6-10 share keys 1-5.
        for cached_agent_id, cached_cache in self._session_caches.items():
            if cached_agent_id == agent_id:
                continue
            cached_key = cached_cache.get_primary()
            if cached_key:
                logger.info(f"Pool empty for {agent_id}, sharing key from {cached_agent_id} (graceful degradation)")
                cache.set_primary(cached_key)
                return cached_key
        
        return None

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
        """V19.14: No backup keys needed — sharing is the fallback."""
        pass

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
            if report_result and report_result.get("new_api_key"):
                key_info = {
                    "api_key": report_result["new_api_key"],
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
        """Verify key via lightweight chat request — 2 attempts, generous timeout.
        
        V23: Fail-open on transient errors (timeout/connection). Only mark dead
        on definitive Fireworks error with permanent keywords. Burning a working
        key is WORSE than occasionally serving a dead key (which auto-swaps on
        the real request anyway)."""
        body = {
            "model": "accounts/fireworks/models/deepseek-v4-flash",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        for attempt in range(2):
            try:
                async with self.fw_session.post(
                    f"{self.fireworks_base}/chat/completions",
                    headers=headers,
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r:
                    if r.status == 200:
                        logger.debug(f"Key verify attempt {attempt+1}: ALIVE (200)")
                        return False
                    text = await r.text()
                    is_dead = any(kw in text.lower() for kw in PERMANENT_ERROR_KEYWORDS)
                    logger.info(f"Key verify attempt {attempt+1}: HTTP {r.status}, dead={is_dead}, body={text[:120]}")
                    if is_dead:
                        return True  # Definitive: "suspended", "revoked", etc.
                    if r.status in (502, 503, 504):
                        # Transient Fireworks error — NOT dead, retry
                        if attempt == 0:
                            await asyncio.sleep(2)
                            continue
                    return False  # Non-permanent error → assume alive
            except (asyncio.TimeoutError, aiohttp.ClientError, OSError) as e:
                logger.warning(f"Key verify attempt {attempt+1}: {type(e).__name__} — {'retrying' if attempt == 0 else 'assuming alive'}")
                if attempt == 0:
                    await asyncio.sleep(2)
                    continue
                return False  # Transient failure → do NOT burn the key
        return False  # Both attempts failed transiently → assume alive

    async def _handle_proxy(self, request: web.Request) -> web.Response:
        path = request.match_info.get("path", "")
        fw_url = f"{self.fireworks_base}/{path}"
        return await self._do_proxy(request, fw_url)

    async def _handle_proxy_v1(self, request: web.Request) -> web.Response:
        path = request.match_info.get("path", "")
        fw_url = f"{self.fireworks_base}/{path}"
        return await self._do_proxy(request, fw_url)

    MODEL_CACHE_PATH = Path.home() / ".hermes" / "models_dev_cache.json"

    @staticmethod
    def _load_all_model_ids() -> list[str]:
        """Load all Fireworks model IDs from the models.dev cache (or fallback)."""
        try:
            raw = PoolProxy.MODEL_CACHE_PATH.read_text()
            registry = json.loads(raw)
            fw = registry.get("fireworks-ai", {})
            return list(fw.get("models", {}).keys())
        except Exception:
            return [
                "accounts/fireworks/models/deepseek-v4-flash",
                "accounts/fireworks/models/deepseek-v4-pro",
                "accounts/fireworks/models/glm-5p1",
                "accounts/fireworks/models/glm-5p2",
                "accounts/fireworks/models/gpt-oss-120b",
                "accounts/fireworks/models/gpt-oss-20b",
                "accounts/fireworks/models/kimi-k2p7-code",
                "accounts/fireworks/models/minimax-m2p5",
                "accounts/fireworks/models/minimax-m2p7",
                "accounts/fireworks/models/qwen3p6-plus",
                "accounts/fireworks/routers/glm-5p1-fast",
                "accounts/fireworks/routers/kimi-k2p7-code-fast",
            ]

    @staticmethod
    def _build_model_alias_map(model_ids: list[str]) -> dict[str, str]:
        """Build short_name → full_path lookup for all model IDs."""
        m = {}
        for mid in model_ids:
            parts = mid.split("/")
            short = parts[-1]  # e.g. "glm-5p1-fast", "deepseek-v4-flash"
            m[short] = mid
        return m

    VISION_FALLBACK_MODEL = "accounts/fireworks/models/kimi-k2p7-code"
    VISION_CAPABLE_MODELS = None  # None = all Fireworks serverless models support vision

    @staticmethod
    def _has_image_content(parsed: dict) -> bool:
        """Check if any message in the request has image_url content."""
        messages = parsed.get("messages", [])
        if not isinstance(messages, list):
            return False
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return True
        return False

    async def _normalize_request_body(self, body: Optional[bytes]) -> Optional[bytes]:
        """Normalize model name in request body — expand short names and route vision requests."""
        if not body:
            return body
        try:
            parsed = json.loads(body)
        except Exception:
            return body

        model = parsed.get("model", "")
        if model and "/" not in model:
            model_ids = self._load_all_model_ids()
            alias_map = self._build_model_alias_map(model_ids)
            full = alias_map.get(model)
            if full and full != model:
                parsed["model"] = full
                logger.debug(f"Normalized model: {model} → {full}")

        if self._has_image_content(parsed):
            current_model = parsed.get("model", "")
            if current_model not in self.VISION_CAPABLE_MODELS:
                logger.info(f"Vision request detected, routing {current_model} → {self.VISION_FALLBACK_MODEL}")
                parsed["model"] = self.VISION_FALLBACK_MODEL

        return json.dumps(parsed).encode()

    async def _handle_v1_models(self, request: web.Request) -> web.Response:
        """Return all Fireworks models from the models.dev cache.

        Reads the community-maintained models.dev registry on disk
        (``~/.hermes/models_dev_cache.json``) to list ALL Fireworks
        models and routers — not just the subset the current pool key
        can access.

        Falls back to a curated subset if the cache is unavailable.
        """
        model_ids = self._load_all_model_ids()
        now = int(time.time())
        data = [
            {"id": m, "object": "model", "created": now, "owned_by": "fireworks"}
            for m in sorted(model_ids)
        ]
        return web.json_response({"object": "list", "data": data})

    async def _ensure_key_with_retry(self, agent_id: str = None, max_attempts: int = 5, delay: float = 2.0) -> Optional[Dict[str, Any]]:
        """V19.14: Short retry for transient empty-pool resets (max 5 attempts, 2s each).
        
        Down from 300 attempts (5min) in V19.12. Soft-ownership means keys
        are never permanently blocked by leases.
        """
        for attempt in range(max_attempts):
            key_info = await self._ensure_key(agent_id=agent_id)
            if key_info:
                return key_info
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
        return None

    async def _do_proxy(self, request: web.Request, fw_url: str) -> web.Response:
        # V19.14 Phase 2: Per-session key assignment via x-agent-id header
        session_agent_id = request.headers.get("x-agent-id", self.agent_id)
        key_info = await self._ensure_key_with_retry(agent_id=session_agent_id)
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
                req_body = await self._normalize_request_body(req_body)

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
                            keyword_match = any(kw in error_text for kw in PERMANENT_ERROR_KEYWORDS)
                            if keyword_match:
                                if status == 412:
                                    # V22: 412 + "suspended" = definitive Fireworks account suspension.
                                    # NOT transient like 401/403 during maintenance windows.
                                    # Skip verify — it would also get 412, wasting time.
                                    logger.info(f"412 + keyword match = definitive suspension: {status} ({reason}) — swapping immediately")
                                else:
                                    # V20: 401/403 with keyword — VERIFY before suspending.
                                    # Fireworks returns transient 401/403 with "suspended" in the
                                    # body during maintenance windows.
                                    verified_dead = await self._verify_key_dead(key_info['api_key'])
                                    if not verified_dead:
                                        logger.warning(f"Key got {status} with keyword in body but /chat verify says ALIVE — transient error, retrying same key")
                                        await asyncio.sleep(2)
                                        continue
                                    logger.info(f"Confirmed dead via error body + verify: {status} ({reason}) — swapping")
                            else:
                                # Body-Keywords matchten nicht — zusätzlich via /chat verifizieren
                                models_dead = await self._verify_key_dead(key_info['api_key'])
                                if not models_dead:
                                    logger.warning(f"Key got {status} but error body + /chat don't confirm dead — retrying same key")
                                    await asyncio.sleep(2)
                                    continue
                        logger.warning(f"Dead key: {status} ({reason}), swapping (attempt {attempt+1})...")
                        new_key = await self._swap_key(reason)
                        if new_key and attempt < self.max_retries - 1:
                            headers["Authorization"] = f"Bearer {new_key['api_key']}"
                            logger.info(f"Silently retrying with new key: {new_key['key_name']}...")
                            continue
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
                                logger.info(f"Silently retrying with new key after 429: {new_key['key_name']}...")
                                continue
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
    backend_url = os.environ.get("SIN_BACKEND_HEALTH_URL", "http://localhost:8100/health")
    for i in range(backend_wait):
        try:
            urllib.request.urlopen(backend_url, timeout=2)
            logger.info(f"✅ Backend ready (waited {i}s) at {backend_url}")
            break
        except Exception:
            if i == 0:
                logger.info(f"⏳ Waiting for backend at {backend_url} (max {backend_wait}s)...")
            time.sleep(1)
    else:
        logger.warning(f"⚠️ Backend not ready at {backend_url} — proxy will start anyway")

    proxy = PoolProxy()
    app = proxy.create_app()
    web.run_app(app, host="127.0.0.1", port=proxy.port, print=logger.info)


if __name__ == "__main__":
    main()
