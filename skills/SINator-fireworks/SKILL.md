---
name: SINator-fireworks
description: "Fireworks AI API key pool rotation, management, and proxy infrastructure. Generates new Fireworks API keys via GMX alias + automated Playwright browser signup, manages a key pool with cooldown/suspend logic, exposes an OpenAI-compatible proxy through a Cloudflare tunnel, and configures opencode model providers. Triggers on 'fireworks key', 'generate fireworks keys', 'pool stats', 'key rotation', 'sinator pool', 'fireworks pool', 'add fireworks key', 'rotate fireworks', 'sinator backend', 'pool proxy', or any task involving the SINator Fireworks AI key pool."
license: MIT
compatibility:
  - opencode
  - sin-code
metadata:
  author: SIN-Rotator
  version: 1.0.0
---

# SINator-fireworks

## Overview

Manages the full lifecycle of Fireworks AI API keys: automated generation via GMX alias rotation + Playwright-driven Fireworks signup, pool storage with 429-cooldown / 401-suspend logic, load-balancing proxy, and OpenCode provider configuration.

## Architecture

```
OpenCode CLI / Cursor / OpenAI Clients
    ↓ OpenAI Responses API (/v1/responses, /v1/chat/completions)
Pool Router (:9998, aiohttp)         ← com.sinator.pool-router
    ↓ Auto-Failover über 10 Proxys
Pool Proxys (:8888-8897, aiohttp)    ← com.sinator.pool-proxy-{port}
    ↓ Key-Rotation + State-Mapping (chatId→Key)
Backend (:8000/:8100, FastAPI)       ← com.sinator.backend
    ↓ PoolManager + JSON-Storage
Fireworks AI API (https://api.fireworks.ai)
    ↑ Public via Cloudflare Tunnel
    ↓ https://sinatorpool-router.delqhi.com/inference/v1
```

### Two Repos

| Repo | Path | GitHub | Role |
|---|---|---|---|
| **v2 (working)** | `~/dev/SINator-Fireworks-Rotator-v2` | `SIN-Rotator/SINator-Fireworks-Rotator-v2` | Primary rotator — `tools/rotate.py` works |
| **v3 (production pool)** | `~/dev/SIN-Rotator-SINator-FireworksAI` | `SIN-Rotator/SINator-FireworksAI` | Backend, pool storage, proxy — `tools/rotate.py` broken (EPIPE) |

**Key insight:** Use v2 repo for key generation (rotate.py), v3 repo for pool/backend/proxy management.

### Services & Ports

| Service | Port | LaunchAgent | Log |
|---|---|---|---|
| Backend | :8000 or :8100 | `com.sinator.backend` | `/tmp/sinator-backend.log` |
| Pool Router | :9998 | `com.sinator.pool-router` | `/tmp/sinator-pool-router.log` |
| Pool Proxys | :8888-8897 | `com.sinator.pool-proxy-{port}` | `/tmp/sinator-pool-proxy-{port}.log` |
| Cloudflare Tunnel | — | `com.cloudflared.sinator` | `/tmp/cloudflared-sinator.log` |

### Key Files

| File | Purpose |
|---|---|
| `data/config.json` | GMX email/password + Fireworks password |
| `data/fireworksai-pool.json` | Pool storage (all keys + status) |
| `agent_toolbox/core/config_manager.py` | Config loader (env + JSON) |
| `agent_toolbox/core/pool_manager.py` | Pool CRUD, cooldown, suspend |
| `tools/rotate.py` | Single key generation (Playwright) |
| `tools/batch_rotate.py` | Batch generation loop |
| `tools/manage_services.sh` | Start/stop/restart all services |
| `proxy/server.py` | Proxy server (per-port) |
| `scripts/pool-router.py` | Load balancer + failover |

## When to Use

- User asks to generate new Fireworks API keys
- User needs pool stats, key status, or pool health check
- User wants to add/remove keys from the pool
- User needs to restart the backend, router, or proxy services
- User needs to configure or fix the OpenCode Fireworks provider
- User reports 429 rate-limit storms or pool exhaustion
- User wants to check/fix the Cloudflare tunnel for the public pool

## How It Works

```
REQUEST ──► ASSESS POOL ──► GENERATE (if needed) ──► SYNC POOLS ──► VERIFY
```

1. **Assess**: Check `GET /api/v1/pool/stats` for available/suspended counts.
2. **Generate**: Run `tools/rotate.py` (v2 repo) via Playwright browser automation.
3. **Add to pool**: `POST /api/v1/pool/add` or direct `PoolManager.add_key()`.
4. **Sync**: v2 pool → v3 pool if needed.
5. **Verify**: Pool stats show new available keys; E2E test through proxy.

## Key Rotation Flow (rotate.py)

```
1. User Chrome (GMX)
   ├── Login to GMX (nemotronv3@gmx.de)
   ├── Rotate alias → new@gmx.de alias
   └── Poll inbox for Fireworks OTP email

2. Bot Chrome (Playwright, headless=False)
   ├── Fireworks signup with alias email
   ├── Fill password (ZOE.jerry2024!)
   ├── Click "Create Account"
   ├── OTP verify (URL from GMX inbox)
   ├── Login with credentials
   ├── Onboarding Page 1:
   │   ├── Account ID (pre-filled by Fireworks, keep as-is)
   │   ├── First Name → "Super" (4-strategy selector)
   │   ├── Last Name → "Cheetah" (4-strategy selector)
   │   ├── Terms checkbox → click
   │   └── Continue button (EXACT match, no "Next")
   ├── Onboarding Page 2:
   │   └── Click "Skip" (bypasses use case selection)
   └── Create API key → fw_XXXXXXXX

3. Save
   ├── PoolManager.add_key(api_key, alias_email, key_name) [v2 repo]
   └── PoolManager.add_key(api_key, alias_email, key_name) [v3 repo — REQUIRED for dashboard]
```

### Onboarding Details (2026-06-17 Fix)

**First/Last Name — 4-strategy selector chain:**
1. `input[name="firstName"]` / `input[name="lastName"]`
2. `input[name="first"]` / `input[name="last"]`
3. `input[placeholder*="First"]` / `input[placeholder*="Last"]`
4. Label text lookup: find `<label>` with text "First Name"/"Last Name", set input value via JS + `dispatchEvent`

**Page 2 — Skip button:**
Page 2 shows use case checkboxes + two buttons: "Submit to get $5 Credits" and "Skip".
Click **"Skip"** first (bypasses use case selection entirely). If Skip fails, try "Submit to get $5 Credits".

**Page 1 — Continue button:**
CRITICAL: Only match buttons with text EXACTLY "Continue". There is a carousel "Next slide" button that will steal the click if "Next" is used as fallback.

## Pool Logic

| Event | Action | Cooldown |
|---|---|---|
| New request (create) | Next free key from pool | — |
| Existing chat/project | Always creation key (state-mapping) | — |
| 429 (rate limit) | Key cooldown + retry with new key | 60s |
| 401/403 (auth fail) | Key marked "suspended" | permanent |
| No key available | Return 503 | — |

## Commands

### Pool Stats
```bash
curl -s http://localhost:8100/api/v1/pool/stats | python3 -m json.tool
```

### Generate Single Key
```bash
cd ~/dev/SINator-Fireworks-Rotator-v2
python3 tools/rotate.py --debug
```

### Generate Batch (N keys)
```bash
cd ~/dev/SINator-Fireworks-Rotator-v2
# Edit TARGET in tools/batch_rotate.py or use custom script:
for i in $(seq 1 N); do
  python3 tools/rotate.py --debug 2>&1 | tee -a /tmp/sinator-batch.log
done
```

### Add Key to Pool

**Important:** Keys must be added to the **v3 repo's** PoolManager (the dashboard reads from v3's pool file). The v2 PoolManager writes to a different file.

```python
# Add to v3 pool (REQUIRED for dashboard to see the key)
cd ~/dev/SIN-Rotator-SINator-FireworksAI
python3 -c "
from agent_toolbox.core.pool_manager import PoolManager
pm = PoolManager()
pm.add_key(api_key='fw_XXX', alias_email='alias@gmx.de', key_name='fw-XXX')
print('Key added to v3 pool')
"
```

API keys are stored in macOS Keychain (not in the JSON file). The JSON file only contains a sentinel value.

### Service Management
```bash
cd ~/dev/SINator-Fireworks-Rotator-v2
./tools/manage_services.sh start    # Start all
./tools/manage_services.sh stop     # Stop all
./tools/manage_services.sh status   # Status
./tools/manage_services.sh restart  # Restart all
```

### Cloudflare Tunnel
```bash
# Check tunnel
curl -s -o /dev/null -w "%{http_code}" https://sinatorpool-router.delqhi.com/inference/v1/models

# Restart tunnel
launchctl unload ~/Library/LaunchAgents/com.cloudflared.sinator.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.cloudflared.sinator.plist
```

### E2E Test Through Pool
```bash
curl -s -X POST https://sinatorpool-router.delqhi.com/inference/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 7avN1KkfInNqcOMn2CtwLTvx" \
  -d '{"model":"accounts/fireworks/models/deepseek-v4-pro","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

## OpenCode Provider Config

In `~/.config/opencode/opencode.json` under `provider.fireworks-ai`:

```json
"fireworks-ai": {
  "npm": "@ai-sdk/fireworks",
  "name": "Fireworks AI",
  "options": {
    "baseURL": "https://sinatorpool-router.delqhi.com/inference/v1",
    "apiKey": "7avN1KkfInNqcOMn2CtwLTvx"
  },
  "models": { ... }
}
```

**Critical:** `@ai-sdk/fireworks` v2.x only supports `thinking: {type: "enabled"|"disabled"}`.
Do NOT use `reasoning_effort` — it causes `ProviderInitError`.

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| `ProviderInitError` in opencode | Model config uses `reasoning_effort` → replace with `thinking: {type: "enabled"}` |
| Playwright "Executable doesn't exist" | Run `python3 -m playwright install chromium` |
| 0 available keys | Run key generation (see above) |
| Cloudflare Error 1033 | Tunnel down → restart `com.cloudflared.sinator` |
| Onboarding name fields not filled | Use 4-strategy selector: `input[name]` → `input[placeholder]` → label text lookup (see Onboarding Details above) |
| Onboarding Page 2 stuck | Click "Skip" button first (bypasses use case selection). Fallback: "Submit to get $5 Credits" |
| Keys generated but not in dashboard | Add key to v3 pool via `PoolManager.add_key()` from v3 repo (not v2, not curl) |
| GMX login fails (Playwright Chromium) | GMX blocks "Chrome for Testing" fingerprint → use real Chrome via CDP |
| GMX login fails (real Chrome CDP) | Check consent iframe fix (see below) |
| `prompt=none` blocks password field | DO NOT navigate to `prompt=login` — SPA shows password after Weiter, just wait |
| GMX consent page blocks login | Consent button is in cross-origin iframe (`dl.gmx.net/permission/...`) — must click in iframe, not main frame |
| v3 rotate.py EPIPE | Use v2 repo's rotate.py instead |
| 403 RestrictedModelsError | Model not available on free tier — use a different model |
| Pool backend not responding | `launchctl load ~/Library/LaunchAgents/com.sinator.backend.plist` |
| Keys in v2 pool not showing in dashboard | Sync v2→v3: compare `data/fireworksai-pool.json` by `id`/`alias_email`, copy missing entries |

## GMX Login Fix (2026-06-17)

### Problem 1: Consent Page
GMX redirects to `consent-management` page. The "Akzeptieren und weiter" button is in a **cross-origin iframe** (`dl.gmx.net/permission/...`), NOT in the main frame. Must iterate `page.frames` and click within the iframe.

### Problem 2: `prompt=none` in URL
After clicking Login on homepage, GMX uses `auth.gmx.net/login?prompt=none`. The old code tried to replace `prompt=none` with `prompt=login` via JS `replaceState` or `page.goto()` — **both break the SPA session state**.

**Fix:** Do NOT touch the URL. After filling email and clicking Weiter, the SPA dynamically shows the password field (wait ~4s). Just fill password and click Login.

### Problem 3: Playwright Chromium blocked
GMX blocks "Chrome for Testing" (Playwright's bundled Chromium) by redirecting `auth.gmx.net/login` → `hilfe.gmx.net`. Use real Chrome via CDP instead:

```bash
# Start separate Chrome instance (does NOT kill user's Chrome)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir=/tmp/sinator-chrome-profile \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/sinator-chrome.log 2>&1 &

# Run rotation with CDP
cd ~/dev/SINator-Fireworks-Rotator-v2
python3 tools/rotate.py --cdp-port 9222 --debug
```

### v2→v3 Pool Sync
New keys are saved to v2's `data/fireworksai-pool.json` but the dashboard reads v3's file. Sync missing entries:

```python
import json
from pathlib import Path
v2 = Path.home()/"dev/SINator-Fireworks-Rotator-v2/data/fireworksai-pool.json"
v3 = Path.home()/"dev/SIN-Rotator-SINator-FireworksAI/data/fireworksai-pool.json"
v2_keys = json.load(open(v2)); v3_keys = json.load(open(v3))
v3_ids = {k.get("id","") for k in v3_keys if isinstance(k,dict)}
for k in v2_keys:
    if isinstance(k,dict) and k.get("id","") not in v3_ids:
        v3_keys.append(k)
json.dump(v3_keys, open(v3,'w'), indent=2)
```

## Verification

- [ ] Pool stats show >0 available keys
- [ ] E2E test through proxy returns valid response
- [ ] Cloudflare tunnel reachable (HTTP 200/401 from public URL)
- [ ] OpenCode provider config has `thinking` not `reasoning_effort`
- [ ] All LaunchAgents loaded and running
