# Pool Proxy Server (`server.py`)

aiohttp-based async proxy that fronts Fireworks AI inference endpoints. Manages a pool of API keys with automatic rotation on 401/402/403/412/429 errors, SSE streaming, and backup key pre-fetching for zero-downtime swaps.

## Dependencies

- **Imported by:** run directly (`python -m proxy.server`)
- **Imports:** `aiohttp`, `aiohttp.web`, `proxy.config`, `proxy.pool_client`, `proxy.key_cache`

## Key Class

| Symbol | Purpose |
|--------|---------|
| `PoolProxy` | Main proxy: key management, request forwarding, SSE streaming, error handling |

### Methods

| Method | Purpose |
|--------|---------|
| `create_app()` | Build aiohttp `web.Application` with routes + middleware |
| `_ensure_key()` | Get primary (or promote backup, or lease new) |
| `_swap_key(reason)` | Report dead key, atomically get replacement |
| `_verify_key_dead(api_key)` | Verify key is dead via lightweight `/chat/completions` probe |
| `_do_proxy(request, fw_url)` | Forward request to Fireworks, handle errors/retries/SSE |
| `_stream_sse(request, fw_resp)` | Stream SSE response chunked to client |
| `_handle_v1_models(request)` | Return all Fireworks models from `~/.hermes/models_dev_cache.json` |

## HTTP Endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | Health check — key status, request count, proxy_id |
| `/pool-status` | GET | Pool stats + cache status |
| `/pool-lease` | GET | Lease a single key (query: `?leased_to=...`) |
| `/v1/models` | GET | All Fireworks models from models cache |
| `/inference/v1/models` | GET | Same as `/v1/models` |
| `/inference/v1/{path}` | ANY | Proxy to `api.fireworks.ai/inference/v1/{path}` |
| `/v1/{path}` | ANY | Proxy to `api.fireworks.ai/inference/v1/{path}` |

## Middleware

| Middleware | Purpose |
|-----------|---------|
| `_cors_middleware` | CORS headers for all origins |
| `_pool_auth_middleware` | Bearer token auth on `/inference/` and `/v1/` paths (optional, controlled by `SINATOR_AUTH_TOKEN`) |

## Key Rotation Logic

- **Dead codes** (401, 402, 403, 412): Verify via body keyword check + `/chat/completions` probe before swapping
- **Permanent 429** (spending limit matched): swap immediately
- **Transient 429**: return to client with `Retry-After` header
- **5xx**: retry up to `max_retries` times
- **Cascade stop**: max 2 consecutive swaps before returning error to client

## Config

| Env Var | Default | Purpose |
|---------|---------|---------|
| `SINATOR_AUTH_TOKEN` | `""` (disabled) | Bearer token for proxy auth |
| `SIN_NO_BACKUP` | `false` | Disable backup key pre-fetching |
| `SIN_BACKEND_WAIT` | `5` | Seconds to wait for backend on startup |
| `SIN_PROXY_PORT` | `8888` | Proxy listen port |
