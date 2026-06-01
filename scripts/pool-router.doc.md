# Pool Router (`pool-router.py`)

Multi-proxy request router that distributes API calls across 10 local pool proxies
(`:8888`–`:8897`) with automatic failover and cooldown-based circuit breaking.

## Dependencies

- **Imports:** `http.server`, `socketserver`, `urllib.request`, `urllib.error`, `json`, `sys`, `os`, `time`, `threading`

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `_get_recent_failures(idx)` | Count failures within the sliding cooldown window |
| `_record_failure(idx)` / `_record_success(idx)` | Thread-safe failure/success tracking |
| `_is_pool_available(idx)` | Check if a pool is below `MAX_FAILURES` in the window |
| `_pool_status()` | Build health-report dict for all pools |
| `PoolHandler` | `BaseHTTPRequestHandler` — proxies GET/POST/OPTIONS to pools |
| `PoolHandler._try_pools(method, path, body, headers)` | Iterates pools in priority order; skips cooldown pools; passes through uniform errors; falls back to Cloudflare when local pool is exhausted |
| `PoolHandler._try_cf_fallback(method, path, body, headers)` | **Issue #24** — relays the request 1:1 to the Cloudflare Worker (`CF_WORKER_URL`) when no local pool is live |
| `PoolHandler._proxy(method)` | Reads request body/headers, calls `_try_pools`, streams response |
| `ThreadedPoolServer` | `ThreadingMixIn` + `TCPServer` for concurrent requests |
| `main()` | Prints banner and runs `serve_forever()` — only invoked under `if __name__ == "__main__"` |

## Routing Logic

1. Request arrives on port `9998`.
2. `_try_pools` iterates pools `:8888` → `:8889` → ... → `:8897`.
3. Pools with ≥3 failures in the last 60s are **skipped** (cooldown).
4. On success → `_record_success` (decays oldest failure).
5. On HTTP 413/429/412/500/502/503/504 → `_record_failure`, try next pool.
6. On other HTTP errors → immediately raise (not retryable).
7. **Uniform error detection:** if all pools return the same error body+status, pass it through instead of raising "All pools exhausted".
8. **Cloudflare fallback (Issue #24):** if every pool is dead/in-cooldown (or all attempts failed) and `CF_WORKER_URL` is set, relay the request to the CF Worker. The Worker does its own D1 key rotation, so the request is forwarded 1:1 (a `Bearer` token from `SINATOR_AUTH_TOKEN` is added if the client sent none). Worker error responses are passed through unchanged.

## Important Config/Limits

| Env Var | Default | Purpose |
|---------|---------|---------|
| `POOL_ROUTER_PORT` | `9998` | Listen port |
| `POOL_ROUTER_TIMEOUT` | `30` | Per-pool request timeout (s) |
| `POOL_ROUTER_COOLDOWN` | `60` | Cooldown window (s) |
| `POOL_ROUTER_MAX_FAILURES` | `3` | Failures before cooldown |
| `CF_WORKER_URL` | _(empty)_ | Cloudflare Worker base URL; empty disables fallback |
| `SINATOR_AUTH_TOKEN` | _(empty)_ | Bearer token added to fallback requests if client sent none |

## Known Caveats

- No `Transfer-Encoding: chunked` support — response headers are stripped and replaced with `Content-Length`.
- ThreadingMixIn but no thread-limit — high concurrency may cause resource exhaustion.
- `urllib` only (not `aiohttp`) — synchronous per-request, thread pool handles concurrency.
- Server startup lives in `main()` behind `if __name__ == "__main__"` — importing this module no longer starts a server or binds the port (fixed in v3, Issue #24).
