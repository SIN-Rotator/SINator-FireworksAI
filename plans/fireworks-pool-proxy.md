# Fireworks Pool Proxy — Detailed Build Plan (V2, 2026-05-24)

## Problem Statement

**Was NICHT funktioniert hat:**
1. `fw_proxy.py` (existierender Proxy) nutzt `http.server.BaseHTTPRequestHandler` → **KEIN Streaming** → opencode hängt bei SSE-Responses (chat/completions streamen nicht!)
2. `key_watchdog.py` pollt nur alle 60s → Key kann 60s lang "tot" sein bevor er swapped wird → in der Zwischenzeit schlägt jeder Request fehl
3. `GET /pool/key` markiert den Key NICHT als in-use → Race-Condition bei mehreren Maschinen
4. Dashboard zeigt keine Live-Updates → wenn Proxy einen Key swapped, weiß das Dashboard nichts
5. Proxy liest Key aus `auth.json` → wenn opencode den Key selbst ändert, liest der Proxy den falschen Key

**Was funktioniert hat:**
- `/pool/report` endpoint — markiert Key als used und liefert neuen
- `/pool/health` — deep check via Fireworks API
- Error detection: 401, 402, 403, 429, 412 + "suspended"/"rate limit"/"spending limit"
- `key_watchdog.py` swap-logic (wenn er läuft)

## Architecture

```
Miner MacBook                              SINator Server (macOS)
┌────────────────────────────┐            ┌─────────────────────────────┐
│  opencode / aider / ...    │            │  Pool API :8000             │
│    ↓ baseURL               │            │    /api/v1/pool/lease       │
│    localhost:8888          │            │    /api/v1/pool/use         │
│         ↓                  │            │    /api/v1/pool/report     │
│  ┌─────────────────────┐   │   HTTPS    │    /api/v1/pool/return     │
│  │  Pool Proxy :8888   │───┼──→──────── │    /api/v1/pool/stats     │
│  │                     │   │            │                             │
│  │  - SSE streaming    │   │            │  Cloudflare Tunnel          │
│  │  - lease keys       │   │            │  https://xxx.trycloudflare  │
│  │  - auto-swap 429    │   │            │                             │
│  │  - auto-retry       │   │            │  Dashboard.html             │
│  │  - WebSocket events │───┼──→──────── │    (live key status)        │
│  │  - mark used ASAP   │   │            │                             │
│  └─────────────────────┘   │            └─────────────────────────────┘
│         ↓                                                  │
│    api.fireworks.ai/inference/v1  ←─────────────────────────┘
└────────────────────────────┘
```

## CRITICAL FIXES vs. Existing Code

### Fix 1: SSE Streaming (EXISTING PROXY IS BROKEN)

**Problem:** `http.server.BaseHTTPRequestHandler` liest die GANZE Response bevor er sie weitersendet.
Fireworks chat/completions nutzt SSE (Server-Sent Events) mit `Transfer-Encoding: chunked`.
Der alte Proxy puffert alles → opencode bekommt KEIN Streaming → Timeout.

**Fix:** `aiohttp` mit `response.content.iter_chunked()` — Streamt chunks in Echtzeit.

```python
async def handle_chat_completions(request):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            FIREWORKS_BASE + "/chat/completions",
            headers={"Authorization": f"Bearer {current_key}"},
            json=await request.json(),
            timeout=aiohttp.ClientTimeout(total=300),
        ) as fw_resp:
            # Stream SSE chunks in real-time
            response = web.StreamResponse()
            response.content_type = fw_resp.content_type
            await response.prepare(request)
            
            # CHECK FIRST CHUNK for errors before streaming
            first_chunk = await fw_resp.content.read(4096)
            if fw_resp.status in (402, 429, 403):
                # Parse error, don't stream garbage
                await handle_rate_limit(first_chunk, current_key, request)
                return response
            
            # Stream first chunk + remaining chunks
            await response.write(first_chunk)
            async for chunk in fw_resp.content.iter_chunked(4096):
                await response.write(chunk)
            await response.write_eof()
            return response
```

### Fix 2: Mark Key as Used IMMEDIATELY (Not on Error)

**Problem:** Keys werden erst als `used` markiert wenn der Rate-Limit kommt.
In der Zwischenzeit nutzen andere Maschinen den gleichen Key.

**Fix: LEASE pattern** — Key wird SOFORT als `leased` markiert wenn er vergeben wird.
Erst bei Suspension/Rate-Limit wird er `used`. Bei normalem Betrieb bleibt er `leased`.

```
available → leased (sofort bei GET /pool/lease) → used (bei 429/suspended)
                                          ↑
                                     leased → available (bei /pool/return, wenn Proxy stoppt)
```

### Fix 3: Dashboard Live Updates

**Problem:** Dashboard zeigt keine Änderungen wenn Proxy einen Key swapped.
User muss manuell "Refresh" klicken.

**Fix:** Server-Sent Events (SSE) vom SINator Backend → Dashboard.
Oder einfacher: Dashboard pollt `/pool/stats` alle 5s wenn Rotation läuft.

### Fix 4: Auth.json Race Condition

**Problem:** Alter Proxy liest Key aus `auth.json`. Wenn opencode den Key selbst überschreibt
(z.B. durch `/connect`), liest der Proxy einen anderen Key als opencode.

**Fix:** Proxy verwaltet den Key SELBST. Opencode bekommt `apiKey: "pool"` als Dummy-Wert.
Der Proxy injected den echten Key IMMER auf Request-Ebene.

## Request Flow (Revised)

```
1. CLI sends: POST http://localhost:8888/inference/v1/chat/completions
   Headers: Authorization: Bearer pool  (DUMMY — proxy replaces it)

2. Proxy:
   a. Check local cache → has a leased key? → use it
   b. No key → POST https://<tunnel>/api/v1/pool/lease → get fw_xxx + lease_id
      (LEASE marks key as "in-use" IMMEDIATELY — no other proxy can grab it)
   c. Replace Authorization: Bearer fw_xxx
   d. Forward to https://api.fireworks.ai/inference/v1/chat/completions

3. Fireworks responds:
   a. 200 OK + SSE → STREAM chunks to CLI in real-time → done
   b. 200 OK + JSON → forward body → done
   c. 401 "UNAUTHORIZED" → Key is invalid/revoked:
      - POST /pool/report {api_key, reason: "unauthorized"} → marks used + gets new
      - Retry with new key (max 3)
   d. 402 "Payment Required" → Credits exhausted:
      - POST /pool/report {api_key, reason: "credits_exhausted"} → marks used + gets new
      - Retry with new key
   e. 429 + "rate_limit" → Temporary rate limit:
      - Check Retry-After header → wait + retry SAME key
      - If no Retry-After → permanent quota exceeded → swap key + report
   f. 403 + "suspended" → Account dead:
      - POST /pool/report {api_key, reason: "suspended"} → marks used + gets new
      - Retry with new key
   g. 412 "Precondition Failed" → Another suspension variant:
      - Same as 403 suspended
   h. 5xx → Server error → retry same key (not a key issue)

4. Dashboard: Poll /pool/stats every 5s during active sessions
   Show: active key (last 4 chars), lease status, swap events
```

## Fireworks API Error Codes (VERIFIED)

| Status | Error Code | Body Pattern | Meaning | Action |
|--------|-----------|--------------|---------|--------|
| 401 | UNAUTHORIZED | "API key you provided is invalid" | Key invalid/revoked | Swap + report |
| 402 | PAYMENT_REQUIRED | "credits", "spending" | Credits exhausted | Swap + report |
| 403 | FORBIDDEN | "suspended", "rate limit", "spending limit" | Account suspended | Swap + report |
| 412 | PRECONDITION_FAILED | "precondition_failed" | Another suspension form | Swap + report |
| 429 | RATE_LIMITED | "rate limit", "quota" | Rate limited | Check Retry-After → wait or swap |
| 500 | INTERNAL | — | Fireworks server error | Retry same key |

**Key insight from testing:** 401 is the MOST COMMON error for invalid keys (not just 429).
The old proxy missed 401, 412 which are also key-death signals.

## Components

### 1. Proxy Server (`proxy/server.py`) — REWRITE of fw_proxy.py

```python
# aiohttp-based async proxy with SSE streaming
# - Single-port HTTP server on 8888
# - SSE streaming for chat/completions (CRITICAL FIX)
# - Error detection on FIRST chunk before streaming
# - Auto-swap + retry on 401/402/403/429/412
# - Key managed internally (NOT from auth.json)
# - Health endpoint: GET /health
# - Pool status: GET /pool-status
# - SSE event stream for dashboard: GET /events
```

### 2. Pool Client (`proxy/pool_client.py`)

```python
# Talks to SINator server via Cloudflare tunnel
# - POST /pool/lease → lease key (atomically marks as in-use)
# - POST /pool/report → report bad key + get replacement
# - POST /pool/return → return key when proxy stops
# - GET /pool/stats → pool statistics
# - Local file cache at ~/.sin-pool/current-key.json
# - Fallback: direct pool.json read if tunnel unreachable
```

### 3. Key Cache (`proxy/key_cache.py`)

```python
# Local cache to avoid pool API round-trip on EVERY request
# - Stores: api_key, key_id, lease_id, cached_at, request_count
# - TTL: 30 minutes (key stays valid as long as proxy is running)
# - Invalidation: on 401/402/403/429/412 detection
# - Persists to ~/.sin-pool/current-key.json
# - Pre-fetch backup key: after lease, also lease a 2nd key as backup
```

### 4. Pool Manager Updates (`agent_toolbox/core/pool_manager.py`)

```python
# ADD: lease_key(ttl_seconds=1800) → atomically marks key as leased
# ADD: return_key(key_id) → removes lease, makes available again
# ADD: get_leased_key() → returns currently leased key (for dashboard)
# MODIFY: get_available_key() → skips leased keys
```

### 5. Pool Route Updates (`agent_toolbox/api/routes/pool.py`)

```python
# ADD: POST /pool/lease → lease a key (with TTL)
# ADD: POST /pool/return → return a leased key
# MODIFY: GET /pool/key → now also marks as leased (backward compat)
```

### 6. Dashboard Updates (`agent_toolbox/static/dashboard.html`)

```javascript
// ADD: Auto-refresh every 5s when proxy is active
// ADD: Show "Active Key" card with last 4 chars + lease status
// ADD: Show swap events in real-time (EventSource /api/v1/pool/events)
// ADD: Visual indicator: 🟢 = key active, 🟡 = swapping, 🔴 = suspended
// PRESERVE: existing layout, buttons, styles — DON'T BREAK
```

### 7. LaunchAgent (`proxy/com.sin.pool-proxy.plist`)

```xml
<!-- Auto-starts proxy on boot, restarts on crash -->
<!-- Lives in ~/Library/LaunchAgents/ -->
<!-- Logs to ~/.sin-pool/proxy.log -->
```

### 8. Setup Script (`proxy/setup.sh`)

```bash
# Installs proxy on Miner MacBook:
# 1. Copy proxy files to ~/.sin-pool/
# 2. Ask for tunnel URL
# 3. Create config.json
# 4. Install LaunchAgent
# 5. Patch opencode.json baseURL
# 6. Start proxy
```

## Config Changes for CLI Tools

### opencode

```json
{
  "provider": {
    "fireworks-ai": {
      "npm": "@ai-sdk/fireworks",
      "name": "Fireworks AI (Pool)",
      "options": {
        "baseURL": "http://localhost:8888/inference/v1"
      },
      "models": { ... }
    }
  }
}
```

Note: `baseURL` path must be `/inference/v1` (Fireworks path prefix), proxy strips and forwards to `api.fireworks.ai/inference/v1`.
Auth key can be anything (e.g. "pool") — proxy replaces it with leased key.

### aider

```bash
export OPENAI_API_BASE=http://localhost:8888/inference/v1
export OPENAI_API_KEY=pool
```

## Pool API Endpoints — Current + New

| Endpoint | Method | Status | Purpose |
|----------|--------|--------|---------|
| `/api/v1/pool/stats` | GET | ✅ EXISTS | Pool statistics (auth-free) |
| `/api/v1/pool/key` | GET | ✅ EXISTS (fix) | Get next available key — ADD lease logic |
| `/api/v1/pool/use` | POST | ✅ EXISTS | Mark key as used permanently |
| `/api/v1/pool/report` | POST | ✅ EXISTS | Report bad key + get replacement |
| `/api/v1/pool/health` | GET | ✅ EXISTS | Deep health check |
| `/api/v1/pool/add` | POST | ✅ EXISTS | Add key to pool |
| `/api/v1/pool/{key_id}` | DELETE | ✅ EXISTS | Delete key |
| `/api/v1/pool/lease` | POST | **NEW** | Lease key with TTL (atomic) |
| `/api/v1/pool/return` | POST | **NEW** | Return leased key |
| `/api/v1/pool/events` | GET | **NEW** | SSE stream for dashboard live updates |

## LEASE Pattern (Detailed)

**Why lease instead of just mark_used?**
- `mark_used` is PERMANENT — key can never be used again
- A key might be temporarily rate-limited but still have credits
- Lease = "I'm using this key right now, nobody else should take it"
- If proxy crashes without returning → lease auto-expires after TTL

**Lease states:**
```
available (used=false, leased_until=null)     ← can be leased
leased    (used=false, leased_until=<future>)  ← in use by a proxy
used      (used=true)                          ← permanently dead
```

**Lease flow:**
```
1. POST /pool/lease {ttl_seconds: 1800}
   → Find first key where used=false AND (leased_until is null OR leased_until < now)
   → Set leased_until = now + 1800s
   → Set leased_to = "proxy-macbook-1"
   → Return {api_key, key_id, lease_id, expires_at}

2. Proxy uses key for 30 minutes...

3a. Key works fine → lease expires → key becomes available again (organic rotation)
3b. Key gets 429/suspended → POST /pool/report → marks used=true → gets new key
3c. Proxy shuts down → POST /pool/return → removes lease → key becomes available
3d. Proxy crashes → no /pool/return → lease auto-expires after TTL → key becomes available
```

**Pre-fetch optimization:**
```
After leasing primary key, also lease a BACKUP key.
If primary dies, swap to backup immediately (0ms delay).
Then lease another backup in the background.
```

## Dashboard Live Updates

**Approach: SSE (Server-Sent Events) from Pool API**

```
GET /api/v1/pool/events → SSE stream:
  event: key_leased
  data: {"key_id": "...", "leased_to": "proxy-1", "expires_at": "..."}

  event: key_swapped
  data: {"old_key_id": "...", "new_key_id": "...", "reason": "suspended"}

  event: key_returned
  data: {"key_id": "...", "from": "proxy-1"}

  event: stats
  data: {"total": 56, "available": 42, "used": 14, "leased": 2}
```

**Dashboard JavaScript:**
```javascript
// Add EventSource listener
const evtSource = new EventSource('/api/v1/pool/events');
evtSource.addEventListener('key_swapped', (e) => {
    const data = JSON.parse(e.data);
    log(`🔄 Key swapped: ${data.old_key_id?.slice(0,8)}... → ${data.new_key_id?.slice(0,8)}... (${data.reason})`, 'success');
    loadDashboard(); // refresh stats
});
evtSource.addEventListener('stats', (e) => {
    const data = JSON.parse(e.data);
    document.getElementById('stat-total').textContent = data.total;
    document.getElementById('stat-available').textContent = data.available;
    document.getElementById('stat-used').textContent = data.used;
});
```

**Dashboard Visual Changes (PRESERVE EXISTING LAYOUT!):**
- ADD: "Active Key" stat card (shows last 4 chars + status emoji)
- ADD: Color coding in key table: 🟢 leased, 🟡 available, 🔴 used/suspended
- MODIFY: renderKeys() to show lease status
- PRESERVE: All existing buttons, layout, styles — NO BREAKING CHANGES

## Existing Infrastructure (DO NOT TOUCH)

| Component | Status | Action |
|-----------|--------|--------|
| `tools/fw_proxy.py` | ❌ BROKEN (no streaming) | DEPRECATE — replace with proxy/server.py |
| `tools/key_watchdog.py` | ⚠️ Works but 60s delay | KEEP as backup — proxy does real-time detection now |
| `tools/start_tunnel.sh` | ✅ Working | KEEP as-is |
| `tools/manage_services.sh` | ✅ Working | ADD pool-proxy service |
| `agent_toolbox/core/pool_manager.py` | ✅ Working | ADD lease/return methods |
| `agent_toolbox/api/routes/pool.py` | ✅ Working | ADD lease/return/events endpoints |
| `agent_toolbox/static/dashboard.html` | ✅ Working | ADD live updates (NO breaking changes) |
| `agent_toolbox/start_toolbox.py` | ✅ Working | ADD SSE endpoint |
| Cloudflare Tunnel | ✅ Running | KEEP as-is |
| Auth middleware | ✅ Pool is public | KEEP as-is |

## Tunnel URL

**Current:** `https://til-returning-luis-residential.trycloudflare.com`
**Type:** Quick tunnel (changes on every restart!)
**Stable alternative:** `cloudflared tunnel create sinator` → named tunnel with fixed subdomain

## Build Order

| Step | Time | Description | Dependencies |
|------|------|-------------|--------------|
| 1 | 15min | `pool_manager.py` — add lease_key(), return_key(), expire_leases() | None |
| 2 | 15min | `pool.py` routes — add /lease, /return, /events endpoints | Step 1 |
| 3 | 20min | `dashboard.html` — add live updates (EventSource) + Active Key card | Step 2 |
| 4 | 20min | `proxy/config.py` + `proxy/key_cache.py` — config + cache | None |
| 5 | 20min | `proxy/pool_client.py` — pool API client (lease/report/return) | Step 4 |
| 6 | 45min | `proxy/server.py` — aiohttp proxy with SSE streaming + auto-swap | Steps 4+5 |
| 7 | 15min | Test: curl through proxy → Fireworks API (verify streaming) | Step 6 |
| 8 | 15min | Test: simulate 401/429 → auto-rotate (verify retry) | Step 6 |
| 9 | 15min | `proxy/setup.sh` + LaunchAgent — installer for Miner MacBooks | Step 6 |
| 10 | 15min | Test: opencode E2E with pool rotation | Steps 6+9 |
| **Total** | **~3h** | | |

## File Structure

```
SINator-fireworksai/
├── proxy/
│   ├── server.py              ← aiohttp proxy (REPLACES fw_proxy.py)
│   ├── pool_client.py         ← Pool API client (lease/report/return)
│   ├── key_cache.py           ← Local key cache + persistence
│   ├── config.py              ← Configuration (ports, tunnel URL)
│   ├── setup.sh               ← Installer for Miner MacBooks
│   ├── uninstall.sh           ← Remove proxy + restore config
│   └── com.sin.pool-proxy.plist  ← macOS LaunchAgent template
├── agent_toolbox/
│   ├── core/
│   │   └── pool_manager.py    ← ADD: lease_key(), return_key(), expire_leases()
│   ├── api/routes/
│   │   └── pool.py            ← ADD: /lease, /return, /events endpoints
│   └── static/
│       └── dashboard.html     ← ADD: live updates (NO breaking changes)
└── tools/
    ├── fw_proxy.py            ← DEPRECATE (broken, no streaming)
    └── key_watchdog.py        ← KEEP (backup, runs independently)
```
