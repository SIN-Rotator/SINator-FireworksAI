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
| `tools/rotate.py` | Single key generation (Playwright, uses CDP port 9222) |
| `tools/rotate_sync.py` | **RECOMMENDED — automated: rotate.py + auto_sync.py in ONE command** |
| `tools/auto_sync.py` | Sync v2→v3 pool + reset used flag |
| `tools/batch_rotate.py` | DEPRECATED — has import issues. Use `rotate_sync.py` instead |
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
REQUEST ──► ASSESS POOL ──► GENERATE (rotate_sync.py) ──► AUTO-SYNCED ──► VERIFY
```

1. **Assess**: Check `GET /api/v1/pool/stats` for available/suspended counts.
2. **Generate**: Run `tools/rotate_sync.py N` — generates N keys AND auto-syncs to dashboard in ONE command.
3. **Verify (~10s after)**: Pool stats show available keys (may drop to 0 quickly as proxies lease them — this is GOOD).

### ⚠️ CRITICAL TWO-STEP ARCHITECTURE

The system uses **two repos** with **manual sync** requirement:
- **v2 repo** `~/dev/SINator-Fireworks-Rotator-v2` — `tools/rotate.py` generates keys (writes to v2 pool)
- **v3 repo** `~/dev/SIN-Rotator-SINator-FireworksAI` — Dashboard reads v3 pool

Keys generated in v2 are NOT visible in v3 dashboard until `auto_sync.py` runs.

### ⚠️ NEVER call `tools/rotate.py` alone!

`rotate.py` does NOT sync to dashboard. The keys would be generated but invisible to the app.

**ALWAYS use one of these methods instead:**

#### ▶ RECOMMENDED (one command, fully automated):

```bash
cd ~/dev/SINator-Fireworks-Rotator-v2
python3 tools/rotate_sync.py        # Generate and sync 1 key
python3 tools/rotate_sync.py 10     # Generate and sync 10 keys
```

Output shows each step: `[1/2] Generating key...` → `[2/2] Auto-syncing...` → final stats.

#### ▶ MANUAL (only if rotate_sync.py fails):

```bash
# After every rotate.py
cd ~/dev/SINator-Fireworks-Rotator-v2
python3 tools/rotate.py --debug     # Generate 1 key
python3 tools/auto_sync.py          # Sync to dashboard
```

Use when rotate_sync.py has errors. NEVER skip auto_sync.py after rotate.py.

### What Each Script Does

| Script | Purpose | Output |
|---|---|---|
| `tools/rotate.py` | Generate 1 key via GMX+Fireworks automation | Key → `data/fireworksai-pool.json` (v2 pool, `used: True`) |
| `tools/auto_sync.py` | Sync v2→v3 pool + reset `used: False` | Keys visible in dashboard |
| **`tools/rotate_sync.py`** | **Combined: rotate.py + auto_sync.py** | **Keys generated AND in dashboard** |

### How The System Becomes "Healthy"

After running rotate_sync.py, expect this sequence:
1. auto_sync makes keys available (resets `used: False`)
2. Background proxies (proxy-8888 through proxy-8897) immediately lease them
3. "available" count drops to 0 → keys are now actively in use
4. To verify: check `leased: True` + `assigned_to: proxy-XXXX` in pool stats

**DONT PANIC** when "available" drops to 0 right after rotation. This is GOOD — keys are being used.

### ⚠️ WHAT NEVER TO DO

| ❌ Dont | ✅ Do Instead |
|---|---|
| Call `rotate.py` without auto_sync.py | Always use `rotate_sync.py` |
| Wait for keys to appear via "available count" | Check `leased + assigned_to` instead |
| Try to fix "missing keys" manually | Run `python3 tools/auto_sync.py` |
| Edit `fireworksai-pool.json` by hand | Let the scripts handle JSON |

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

### Generate Batch (N keys) — AUTOMATED

**IMPORTANT:** Use the new `rotate_sync.py` script for FULLY AUTOMATED generation + sync:

```bash
cd ~/dev/SINator-Fireworks-Rotator-v2

# Generate + sync 1 key (default)
python3 tools/rotate_sync.py

# Generate + sync 10 keys at once
python3 tools/rotate_sync.py 10

# Generate + sync 100 keys at once
python3 tools/rotate_sync.py 100
```

The script handles the complete workflow:
1. Runs `rotate.py` for each key (generates key via GMX + Fireworks)
2. Runs `auto_sync.py` after each successful generation (syncs to dashboard)
3. Reports final stats: `DONE: N/10 keys generated + auto-synced`

**WARNING:** Each key takes ~3-5 minutes. 10 keys = ~30-50 minutes total.

**`batch_rotate.py` is DEPRECATED.** It has import issues with `agent_toolbox`. Use `rotate_sync.py` instead.

### Add Key to Pool

**AUTO METHOD (recommended):** Use `tools/rotate_sync.py` — generates keys AND auto-syncs:

```bash
cd ~/dev/SINator-Fireworks-Rotator-v2
python3 tools/rotate_sync.py        # 1 key
python3 tools/rotate_sync.py 10     # 10 keys
```

**MANUAL SYNC (only if you already have unsynced keys):** Use `tools/auto_sync.py`:

```bash
cd ~/dev/SINator-Fireworks-Rotator-v2
python3 tools/auto_sync.py
```

This will:
1. Find all keys in v2 pool that aren't in v3 pool
2. Sync them to v3 pool
3. Reset `used: False` for all non-suspended keys
4. Make them available in the dashboard

**NEVER call `rotate.py` alone!** It does NOT sync to dashboard. Always use `rotate_sync.py` or pair with `auto_sync.py`.

```python
# Add to v3 pool (REQUIRED for dashboard to see the key)
cd ~/dev/SIN-Rotator-SINator-FireworksAI
python3 -c "
from agent_toolbox.core.pool_manager import PoolManager
pm = PoolManager()
pm.add_key(api_key='fw_XXX', alias_email='alias@gmx.de', key_name='fw-XXX')

# Reset used flag for all non-suspended keys
import json
v3_keys = json.load(open('data/fireworksai-pool.json'))
for k in v3_keys:
    if isinstance(k, dict) and not k.get('suspended', True):
        k['used'] = False
        k['used_at'] = None
json.dump(v3_keys, open('data/fireworksai-pool.json', 'w'), indent=2)

print('Key added to v3 pool and available')
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

## Cookie Consent Banner Fix (2026-06-18)

### Problem
Fireworks uses CookieYes consent banner (`cky-consent-container cky-banner-bottom`). The banner **re-injects itself on every SPA navigation** — reactive DOM removal was insufficient. The banner intercepted pointer events on "Create Account", "Continue", and other buttons, causing 3 consecutive failures and stopping `rotate_sync.py`.

### Root Cause
CookieYes checks `localStorage` on init. If consent is already set, it skips the banner. The old code only removed DOM elements reactively — CookieYes re-injected them on every navigation.

### Fix — 3-Layer Defense (commit `941fb4b`)

**Layer 1: PREVENT (launch `add_init_script`)** — runs BEFORE any page JS:
1. Set CookieYes consent in `localStorage` (`cookieyes-consent` + `cky-consent`) → CookieYes sees consent and skips banner
2. Inject CSS that permanently hides all `cky-*`, `onetrust-*`, `consent-*` selectors (`display: none !important; pointer-events: none`)
3. `MutationObserver` auto-removes any consent elements that slip through

**Layer 2: REACT (`_dismiss_cookie_consent()` helper)** — called after EVERY Fireworks navigation:
1. Click "Reject All" button (sets CookieYes consent properly via their API)
2. Remove all known consent DOM elements via JS (cky-*, onetrust-*, generic consent-*)
3. Restore body scroll

**Layer 3: FALLBACK (JS click)** — if consent banner still intercepts pointer events:
- `browser_click_by_text("Create Account")` fails → fall back to `document.querySelector('button[type="submit"]').click()` via JS

### Central Helper
All 6 navigation points in `fireworks_service.py` now call `_dismiss_cookie_consent()`:
- `signup_fireworks` — after navigate to /signup
- `signup_fireworks` — before "Create Account" click (SPA may re-inject)
- `verify_account` — after navigate to verify URL
- `login_fireworks` — after navigate to /login
- `_playwright_onboarding` — at start of onboarding
- `create_api_key` — after navigate to /settings/users/api-keys

### Key Files Changed
| File | Change |
|---|---|
| `agent_toolbox/core/fireworks_service.py` | `launch()`: preventive `add_init_script` + CSS + MutationObserver. New `_dismiss_cookie_consent()` helper. All 6 nav points call helper. JS click fallback on Create Account. |
| `tools/rotate_sync.py` | Parse `proc.stderr` (logging module output) for API Key detection. Was only parsing stdout. |

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
| Cookie consent banner blocks Fireworks clicks | Fixed (2026-06-18): 3-layer defense — see Cookie Consent Banner Fix above |
| `rotate_sync.py` reports "Generation FAILED" but key was generated | Fixed (2026-06-18): was parsing stdout only, now parses stderr too (logging module writes to stderr) |

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

- [ ] Pool stats show >0 available keys (or all immediately leased by proxies)
- [ ] Keys show `leased: True` + `assigned_to: proxy-XXXX` after auto_sync
- [ ] E2E test through proxy returns valid response
- [ ] Cloudflare tunnel reachable (HTTP 200/401 from public URL)
- [ ] OpenCode provider config has `thinking` not `reasoning_effort`
- [ ] All LaunchAgents loaded and running

### Complete Workflow Example (CRITICAL — Read This First)

**NEW AUTOMATED WORKFLOW (june 2026):** Use `rotate_sync.py` — ONE COMMAND handles everything:

```bash
# 1. ASSESS POOL (optional, just to see current state)
curl -s http://localhost:8100/api/v1/pool/stats | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'{d[\"available\"]}/{d[\"total\"]} available')
"

# 2. ⚡ GENERATE + AUTO-SYNC (one command! keys go straight to dashboard)
cd ~/dev/SINator-Fireworks-Rotator-v2
python3 tools/rotate_sync.py 10     # generate + sync 10 keys
# Output for each key:
#   [1/2] Generating key (rotate.py)...
#      ✓ API Key: fw_XXXXXXXX...
#   [2/2] Auto-syncing to dashboard...
#      ✓ Synced to dashboard

# 3. VERIFY IN DASHBOARD (wait 10s for proxies to lease new keys)
sleep 10
curl -s http://localhost:8100/api/v1/pool/stats | python3 -c "
import sys, json
d = json.load(sys.stdin)
not_suspended = [k for k in d['keys'] if not k.get('suspended', True)]
leased = [k for k in not_suspended if k.get('leased', False)]
print(f'{len(not_suspended)} not-suspended, {len(leased)} leased to proxies')
"

# 4. E2E TEST
curl -s -X POST https://sinatorpool-router.delqhi.com/inference/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 7avN1KkfInNqcOMn2CtwLTvx" \
  -d '{"model":"accounts/fireworks/models/deepseek-v4-pro","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

**OLD MANUAL WORKFLOW (only if rotate_sync.py has errors):**

```bash
# 1. ASSESS + 2. GENERATE + 3. SYNC (3 separate commands)
curl -s http://localhost:8100/api/v1/pool/stats
cd ~/dev/SINator-Fireworks-Rotator-v2
python3 tools/rotate.py --debug     # generates 1 key
python3 tools/auto_sync.py          # syncs to dashboard
```

### Files Created/Modified (2026-06-18)

| File | Purpose |
|---|---|
| `~/dev/SINator-Fireworks-Rotator-v2/tools/auto_sync.py` | Auto-sync v2→v3 pool + reset used flag |
| `~/dev/SINator-Fireworks-Rotator-v2/tools/rotate_sync.py` | **NEW (v2.6.18-2) — AUTOMATED orchestrator: rotate.py + auto_sync.py in ONE command.** Use this for ALL key generation tasks. |
| `~/dev/SINator-Fireworks-Rotator-v2/tools/batch_rotate.py` | DEPRECATED — has import issues. Use `rotate_sync.py` instead. |

### What Can Go Wrong

| Symptom | Cause | Fix |
|---|---|---|
| Keys generated but not in dashboard | Used `rotate.py` instead of `rotate_sync.py` | ALWAYS use `python3 tools/rotate_sync.py` |
| Available count drops to 0 after rotation | Proxies leased all available keys (EXPECTED!) | Verify keys have `assigned_to: proxy-XXXX` |
| Dashboard shows 0 available always | All keys suspended or leased | Generate new keys with `rotate_sync.py` |
| auto_sync.py says "Found 0 new keys" | Pool already synced | Still resets used flags — safe to run anytime |
| Pool stats API shows "available: N" but app shows different | API has 5s cache or app reads different source | Wait 5s + refresh app |
| Used `rotate.py` manually and keys not in dashboard | Missed auto_sync.py | Run `python3 tools/auto_sync.py` immediately |
