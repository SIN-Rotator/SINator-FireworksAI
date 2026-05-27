# SINator — Fireworks AI Key Pool

Automated GMX alias rotation → Fireworks AI account → API key pool.  
OpenAI-compatible proxy with automatic key rotation on rate-limits.

**Backend Port:** `8000` | **Dashboard Repo:** [SINator-dashboard](https://github.com/SIN-Rotator/SINator-dashboard) | **HeyPiggy Repo:** [SINator-heypiggy](https://github.com/SIN-Rotator/SINator-heypiggy)

## 3 Pool-Proxies — je Mac ein dedizierter

Drei Cloudflare-Tunnel-Subdomains, drei Proxy-Instanzen (`:8888`–`:8890`).  
Jeder Mac bekommt seinen eigenen Proxy mit eigenem API-Key aus dem Pool.

```bash
cd ~/dev/SINator-fireworksai && proxy/start-multi.sh
```

| Mac | Subdomain | baseURL |
|-----|-----------|---------|
| Mac 1 | `sinatorpool1.delqhi.com` | `https://sinatorpool1.delqhi.com/inference/v1` |
| Mac 2 | `sinatorpool2.delqhi.com` | `https://sinatorpool2.delqhi.com/inference/v1` |
| Mac 3 | `sinatorpool3.delqhi.com` | `https://sinatorpool3.delqhi.com/inference/v1` |

Lokal (auf Mac 1): `http://localhost:{8888,8889,8890}/inference/v1` — kein Auth nötig.  
**apiKey (remote):** `7avN1KkfInNqcOMn2CtwLTvx` (für alle Subdomains gleich)

## Quick Start

```bash
# Mit dem Dashboard-Launcher (empfohlen):
cd ~/dev/SINator-dashboard
./start.sh
# → Startet Fireworks (:8000) + HeyPiggy (:8002) + Dashboard (:3000) + Tauri App

# Oder standalone:
python agent_toolbox/start_toolbox.py
# → http://localhost:8000/docs
```

---

## Architecture

```
Clients (opencode, Cursor, etc.)
  ↓ OpenAI-compatible API
Pool Proxy (:8888, aiohttp SSE)
  ↓ Key rotation + lease management
Backend (:8000, FastAPI)
  ↓ PoolManager + Keychain
Chrome + CUA Driver
  ↓ Browser automation
GMX → Fireworks AI → API Key
```

**Services (macOS LaunchAgents):**

| Service | Port | Purpose |
|---------|------|---------|
| `com.sinator.backend` | :8000 | FastAPI Backend |
| `com.sinator.pool-proxy` | :8888-:8890 | 3× OpenAI-compatible proxies with auto-swap |
| `com.sinator.tunnel` | — | Cloudflare tunnel → `sinator.delqhi.com` |
| `com.sinator.pages` | :8040 | Landing page |
| `com.sinator.chrome` | — | Chrome lifecycle |
| `com.sinator.cua-driver` | — | macOS AX automation |

---

## Dashboard + HeyPiggy Integration

Dieses Repo ist der Fireworks-Backend. Das vollständige System besteht aus drei Repos:

| Repo | Port | Funktion |
|------|------|----------|
| **SINator-fireworksai** (dieses) | `:8000` | Fireworks Key Pool + Pool-Proxy |
| [SINator-heypiggy](https://github.com/SIN-Rotator/SINator-heypiggy) | `:8002` | HeyPiggy Account Generator |
| [SINator-dashboard](https://github.com/SIN-Rotator/SINator-dashboard) | `:3000` | Tauri App (Provider-Switcher) |

```bash
# Alles starten (from dashboard repo):
cd ~/dev/SINator-dashboard && ./start.sh
# → Fireworks :8000 + HeyPiggy :8002 + Dashboard :3000 + Tauri App
```

Nach Dashboard-Code-Änderungen: `cd ~/dev/SINator-dashboard && ./build.sh` (Tauri Release App ist statisch).

## Lease Backup Fix (2026-05-26)

`lease_backup`-Default war `True` → jeder Swap konsumierte 2 Keys (einen verschwendet als "backup-backup"). Gefixt in `proxy/config.py`, `proxy/pool_client.py`, `proxy/setup.sh`. Jetzt `False` — nur 1 Key pro Lease.

---

## E2E Flow (V12 — ~180s)

```
Step 0:  GMX Login via Playwright (credentials from /api/v1/config)  → frische Cookies
Step 1:  GMX Alias Rotation (CUA+Playwright)            → new-alias@gmx.de
Step 2:  Fireworks Signup (Playwright + CDP)            → Account created
Step 3:  OTP Polling (GMX MailCheck Extension + CDP)    → Verify URL extracted
Step 4:  Verify + Login + Onboarding (CUA+Playwright)   → Dashboard reached
Step 5:  API Key Creation (Playwright PopUpButton)      → fw_xxx
Step 6:  Save to Pool (macOS Keychain)                  → Key encrypted
```

---

## Pool Proxy

OpenAI-compatible proxy with automatic key management:

- **Auto-Swap:** 401/402 → instant swap, 403/412 → verify then swap
- **SSE Streaming:** Full support for chat/completions
- **Backup Key:** Pre-fetched for 0ms swap
- **Cascade Stop:** Max 2 consecutive swaps per request
- **Key Verification:** `_verify_key_dead()` tests against `/models` before marking dead

```
baseURL: https://sinatorpool1.delqhi.com/inference/v1  (Mac 1)
baseURL: https://sinatorpool2.delqhi.com/inference/v1  (Mac 2)
baseURL: https://sinatorpool3.delqhi.com/inference/v1  (Mac 3)
apiKey:  7avN1KkfInNqcOMn2CtwLTvx  (alle Macs gleich)
```

Rate-limit handling is automatic: 401/402/403/412 → key swapped, 429 → retry or swap (permanent vs temporary).

---

## Setup: opencode

1. Create `~/.config/opencode/opencode.json` (or merge into existing):

```json
{
  "provider": {
    "fireworks-ai": {
      "npm": "@ai-sdk/fireworks",
      "name": "Fireworks AI",
      "models": {
        "deepseek-v4-pro": {
          "id": "fireworks/deepseek-v4-pro",
          "name": "DeepSeek V4 Pro",
          "options": { "thinking": { "type": "enabled", "budgetTokens": 64000 } },
          "limit": { "context": 1048576, "output": 65536 }
        },
        "glm-5p1": {
          "id": "fireworks/glm-5p1",
          "name": "GLM 5.1",
          "options": { "thinking": { "type": "enabled", "budgetTokens": 32000 } },
          "limit": { "context": 202752, "output": 32768 }
        },
        "kimi-k2p6": {
          "id": "fireworks/kimi-k2p6",
          "name": "Kimi K2.6",
          "options": { "thinking": { "type": "enabled", "budgetTokens": 32000 } },
          "limit": { "context": 262144, "output": 32768 }
        }
      },
      "options": {
        "baseURL": "https://sinatorpool1.delqhi.com/inference/v1"
      }
    }
  }
}
```

2. Set API key as environment variable (in `~/.zshrc` or `~/.bashrc`):

```bash
export FIREWORKS_API_KEY="7avN1KkfInNqcOMn2CtwLTvx"
```

The `@ai-sdk/fireworks` SDK reads `FIREWORKS_API_KEY` automatically as `Authorization: Bearer` header.

> **Local users** (localhost) don't need the API key — the proxy skips auth for `127.0.0.1`/`::1`. Remote users **must** set it or they get 401.

---

## Setup: Cursor / Continue / other OpenAI clients

Any OpenAI-compatible client works:

```
baseURL = https://sinatorpool1.delqhi.com/inference/v1  (Mac 1)
baseURL = https://sinatorpool2.delqhi.com/inference/v1  (Mac 2)
baseURL = https://sinatorpool3.delqhi.com/inference/v1  (Mac 3)
apiKey  = 7avN1KkfInNqcOMn2CtwLTvx  (alle Macs gleich)
```

```bash
# Test it (Mac 1)
curl -H "Authorization: Bearer 7avN1KkfInNqcOMn2CtwLTvx" \
  https://sinatorpool1.delqhi.com/inference/v1/models
```

---

## API Key Security

API keys are stored in **macOS Keychain** (service: `com.sinator.pool`).

- Pool JSON contains `STORED_IN_KEYCHAIN` sentinel instead of plaintext keys
- `GET /pool/reveal/{key_id}` retrieves real key from Keychain (for dashboard copy)
- `POST /pool/migrate-to-keychain` migrates existing plaintext keys
- `GET /pool/stats` returns `api_key: ""` — never leaks secrets

---

## API Reference

All endpoints prefixed with `/api/v1`.

### Pool

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/pool/stats` | Pool statistics (no api_key leaked) |
| GET | `/pool/key` | Next available key (hydrated from Keychain) |
| GET | `/pool/reveal/{key_id}` | Reveal real API key from Keychain |
| POST | `/pool/lease` | Lease key with TTL |
| POST | `/pool/return` | Return leased key |
| POST | `/pool/report` | Report bad key + get replacement |
| POST | `/pool/add` | Add key to pool (→ Keychain) |
| POST | `/pool/use` | Mark key as manually used |
| DELETE | `/pool/{key_id}` | Delete key from pool + Keychain |
| GET | `/pool/health` | Validate all keys via Fireworks API |
| POST | `/pool/migrate-to-keychain` | Migrate plaintext → Keychain |
| GET | `/pool/events` | SSE stream for live updates |

### Config

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Get GMX email + passwords |
| POST | `/config` | Save GMX + Fireworks credentials |

### Rotation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/rotation/full` | Complete: GMX → Fireworks → API Key |

### Browser / GMX / Fireworks / Cookies

See AGENTS.md for full documentation.

---

## Key Status

| Status | Meaning |
|--------|---------|
| verfügbar | Key is active and ready |
| verbraucht | Manually marked as used by user |
| gesperrt | Auto-detected as suspended by Fireworks (403/412) |

---

## Chrome Configuration

```
Chrome Binary:     /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
User Data Dir:     /Users/jeremy/Library/Application Support/Google Chrome
Profile:           Profile 901
CDP Port:          9222
```

**NIEMALS** `--force-renderer-accessibility` (zerstört GMX Inbox)  
**NIEMALS** `pkill -9 -f "Google Chrome"` (killt Session)

---

## Project Structure

```
SINator-fireworksai/
├── agent_toolbox/
│   ├── start_toolbox.py           FastAPI Entrypoint
│   ├── core/
│   │   ├── keychain_store.py      macOS Keychain CRUD
│   │   ├── pool_manager.py        Pool: add/lease/report/stats
│   │   ├── config_manager.py      GMX + Fireworks credentials
│   │   ├── gmx_service.py         GMX: Session, Alias, OTP
│   │   ├── fireworks_service.py   Fireworks: E2E 12-Phase
│   │   ├── cdp_client.py         Raw CDP Websocket
│   │   └── browser_manager.py    Chrome Lifecycle
│   └── api/routes/
│       ├── pool.py                Pool + Reveal + Migrate
│       ├── config.py               GMX + Fireworks Config
│       ├── rotation.py            POST /rotation/full
│       ├── gmx.py / fireworks.py / browser.py / cookies.py
├── proxy/
│   ├── server.py                  Pool Proxy (aiohttp SSE)
│   ├── pool_client.py            Backend API client
│   ├── key_cache.py              Primary + backup cache
│   └── config.py                 Proxy config
├── tools/
│   └── rotate.py                 Single-command E2E
├── data/
│   └── fireworksai-pool.json     Pool metadata (keys in Keychain)
│   └── config.json                GMX + Fireworks credentials
└── AGENTS.md                     Full technical documentation
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SINATOR_AUTH_TOKEN` | — | Auth token for proxy + backend |
| `SIN_PROXY_PORT` | 8888 | Proxy port |
| `SIN_LEASE_TTL` | 1800 | Key lease duration (seconds) |

---

*V12 — 2026-05-26 | 146 Keys | macOS Keychain | 3 Pool Proxies + Tunnel | Config Manager*
