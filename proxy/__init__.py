"""
Proxy package — Pool Proxy for Fireworks AI inference API.

Sub-modules:
    config      — Environment-driven configuration loader
    key_cache   — On-disk primary/backup key cache
    pool_client — HTTP client for the backend pool API
    server      — aiohttp-based proxy with SSE streaming + auto key rotation

Docs: __init__.doc.md
"""