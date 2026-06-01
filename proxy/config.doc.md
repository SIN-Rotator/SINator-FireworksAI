# Proxy Configuration (`config.py`)

Configuration loading for the Pool Proxy — reads from environment variables with sensible defaults, then persists to a JSON file in `~/.sin-pool/config.json`.

## Dependencies

- **Imported by:** `proxy.key_cache`, `proxy.pool_client`, `proxy.server`
- **Imports:** `os`, `json`, `pathlib.Path`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `load_config()` | Read config from file or build from env defaults |
| `save_config(cfg)` | Persist config dict to JSON file |

## Constants / Env Vars

| Variable | Env | Default |
|----------|-----|---------|
| `DEFAULT_PROXY_PORT` | `SIN_PROXY_PORT` | `8888` |
| `FIREWORKS_BASE` | — | `https://api.fireworks.ai/inference/v1` |
| `LEASE_TTL_SECONDS` | `SIN_LEASE_TTL` | `1800` |
| `LEASE_BACKUP` | `SIN_LEASE_BACKUP` | `false` |
| `MAX_RETRIES` | `SIN_MAX_RETRIES` | `3` |
| `CACHE_DIR` | `SIN_CACHE_DIR` | `~/.sin-pool` |
| `CF_WORKER_URL` | `CF_WORKER_URL` | _(empty)_ — Cloudflare Worker fallback base URL (Issue #24) |
| `CF_SYNC_TOKEN` | `CF_SYNC_TOKEN` | _(empty)_ — token for Mac→D1 push via `scripts/sync_to_cf.py` |

## Pool API URL Resolution

1. `SIN_POOL_API_URL` env var
2. `~/.sin-pool/tunnel-url.txt` file content
3. parent project `.sin-pool/tunnel-url.txt`
4. fallback: `http://localhost:8000/api/v1`

## File Locations

| File | Purpose |
|------|---------|
| `CACHE_DIR / config.json` | Serialized config |
| `CACHE_DIR / tunnel-url.txt` | Tunnel/ngrok URL override |
| `SHARED_TUNNEL_URL_FILE` | Shared location in parent project tree |
