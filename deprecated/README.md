# Deprecated Tools — Replaced by proxy/

## fw_proxy.py (deprecated 2026-05-24)
- **Why deprecated:** Uses `http.server.BaseHTTPRequestHandler` → no SSE streaming.
  OpenCode chat/completions require real-time SSE chunks.
- **Replaced by:** `proxy/server.py` (aiohttp, full SSE streaming, auto-swap, lease-based)

## key_watchdog.py (deprecated 2026-05-24)
- **Why deprecated:** Polls every 60s — key can be dead for up to 60s before detection.
  No lease mechanism → race condition with multiple proxies.
- **Replaced by:** `proxy/server.py` (real-time detection on every request, auto-swap <50ms)
