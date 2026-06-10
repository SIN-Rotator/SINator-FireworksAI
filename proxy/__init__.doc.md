# Package Entry (`__init__.py`)

Empty package marker for the `proxy` module. All functionality lives in the sub-modules (`config.py`, `key_cache.py`, `pool_client.py`, `server.py`).

## Dependencies

- **Imported by:** `proxy.config`, `proxy.key_cache`, `proxy.pool_client`, `proxy.server`

## Structure

| Module | Purpose |
|--------|---------|
| `config.py` | Configuration loading (env vars, file, defaults) |
| `key_cache.py` | Primary/backup key caching with file persistence |
| `pool_client.py` | HTTP client to backend pool API |
| `server.py` | aiohttp-based Pool Proxy with SSE streaming |
