# server.py — Pool Proxy (aiohttp)

## What
aiohttp-based async HTTP proxy that sits between the dashboard/Tauri app and the
Fireworks API. Manages API key leasing, caching, and automatic failover when a
key gets suspended.

## Why
- **Zero-downtime key swap**: Pre-fetches a backup key for instant 0ms failover
  when the primary returns 401/402/403/412/429
- **SSE streaming support**: Critical for Fireworks chat completions (old proxy
  couldn't stream)
- **Lease-based key management**: Atomic, TTL-based — prevents dashboard from
  leasing the same key twice

## Touched by
- `com.sinator.pool-proxy-8888..8897` LaunchAgents (10 instances)
- `proxy/pool_client.py` — async HTTP client for backend pool API
- `proxy/key_cache.py` — primary/backup key persistence to disk
- `proxy/config.py` — env-driven config
- `pool-router.py` (scripts/) — round-robins across the 10 proxy instances

## Key features

### V19.10: Unique proxy_id
`f"proxy-{port}-{random}"` instead of `int(time.time())`. Before the fix, all 10
proxies started within the same second got the SAME proxy_id — their leases all
landed under one `leased_to` and couldn't be told apart.

### V19.11: Return-old-key flow
`KeyCache.get_primary()` saves expired keys to `previous` (persisted as
`previous-key.json`). `_ensure_key()` calls `pop_previous()` and returns the
expired key via `/pool/return` BEFORE leasing a new one. Prevents ghost leases
from cache expiry (30 min cycle).

### V19.14: Soft-Ownership + Per-Session Keys
- **AgentKeyCache** replaces KeyCache — no TTL expiry, sticky preferred_key_id
  persists to `~/.sin-pool/agent-{id}.json`
- **Phase 2 x-agent-id**: Each request can send `x-agent-id` header → gets its own
  key via per-session AgentKeyCache (lazy creation). Falls back to proxy's
  `SIN_AGENT_ID` if no header.
- **_ensure_key(agent_id)**: Accepts optional agent_id, no retry loop (instant)
- **_on_shutdown**: Releases ALL session keys together via `/pool/agent-release`
- **_get_session_cache()**: Creates per-session AgentKeyCache on first request

## Endpoints
- `GET /health` — proxy status + cached key info
- `GET /pool-status` — pool stats from backend + cache status
- `GET /pool-lease` — lease a key (for dashboard/rotation use)
- `GET /v1/models` — Fireworks model list (cached)
- `*  /v1/{path}` — proxy → backend agent-key → Fireworks (Phase 2: x-agent-id)
- `*  /inference/v1/{path}` — proxy → backend agent-key → Fireworks (Phase 2: x-agent-id)

## Auth
- `Authorization: Bearer <SINATOR_AUTH_TOKEN>` for all `/v1/*` and `/inference/*`
- `/health`, `/pool-status`, `/v1/models` are public

## Usage
```bash
# Single instance
SIN_PROXY_PORT=8888 python3 -m proxy.server

# All 10 via LaunchAgent
launchctl load ~/Library/LaunchAgents/com.sinator.pool-proxy-8888.plist
```

## Caveats
- **Window size**: aiohttp default, not set explicitly
- **No retry on Fireworks 5xx**: only retries on dead-key codes (401/402/403/412/429)
- **Cache files in `~/.sin-pool/`**: persists across restarts but stale keys
  on disk are returned to pool on next lease via V19.11
