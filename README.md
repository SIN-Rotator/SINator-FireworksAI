# SINator — Fireworks AI Key Pool

Automated GMX alias rotation → Fireworks AI account → API key pool.  
OpenAI-compatible proxy with automatic key rotation on rate-limits.

**Endpoint:**
```
baseURL: https://sinator.delqhi.com/inference/v1
apiKey:  7avN1KkfInNqcOMn2CtwLTvx
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
| `com.sinator.pool-proxy` | :8888 | OpenAI-compatible proxy with auto-swap |
| `com.sinator.tunnel` | — | Cloudflare tunnel → `sinator.delqhi.com` |
| `com.sinator.pages` | :8040 | Landing page |
| `com.sinator.chrome` | — | Chrome lifecycle |
| `com.sinator.cua-driver` | — | macOS AX automation |

---

## Quick Start

```bash
# Full Rotation (Single Command)
python tools/rotate.py

# API Server starten
python agent_toolbox/start_toolbox.py
# → http://localhost:8000/docs
```

---

## E2E Flow (V10 — ~210s)

```
Step 0:  GMX Login via Playwright                      → frische Cookies
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

```bash
# Direct proxy usage
curl -H "Authorization: Bearer 7avN1KkfInNqcOMn2CtwLTvx" \
  https://sinator.delqhi.com/inference/v1/models
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
│   │   ├── gmx_service.py         GMX: Session, Alias, OTP
│   │   ├── fireworks_service.py   Fireworks: E2E 12-Phase
│   │   ├── cdp_client.py         Raw CDP Websocket
│   │   └── browser_manager.py    Chrome Lifecycle
│   └── api/routes/
│       ├── pool.py                Pool + Reveal + Migrate
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

*V10 — 2026-05-25 | 112 Keys | macOS Keychain | Pool Proxy + Tunnel*
