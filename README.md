# SINator — Fireworks AI Key Pool

[![GitNexus](https://img.shields.io/badge/GitNexus-knowledge%20graph-8B5CF6)](.gitnexus/)

Automated GMX alias rotation → Fireworks AI account registration → API key pool.
OpenAI-compatible proxy with automatic key rotation on rate-limits and silent key swap.

**Backend:** :8100 | **Pool:** 261 Keys | **Proxy:** 10 Instances (:8888-:8897) | **Router:** :9998

**Dashboard:** [SINator-dashboard](https://github.com/SIN-Rotator/SINator-dashboard) |
**Config:** [OpenSIN-Code](https://github.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config) |
**Hermes:** [SIN-Hermes-Bundles](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle)

## Quick Start

```bash
# Dashboard (empfohlen):
cd ~/dev/SINator-dashboard && ./start.sh
# → Backend (:8100) + Dashboard (:3000) + Tauri App

# Oder standalone:
python agent_toolbox/start_toolbox.py
# → http://localhost:8100/docs
```

## Eine Base-URL — Pool-Router mit Auto-Failover

Der Router (:9998) verteilt auf 10 Proxys (:8888-:8897), jeder mit eigenem API-Key. Bei Fehlern wird zum nächsten Proxy gesprungen.

| Zugriff | URL |
|---------|-----|
| **Lokal** | `http://localhost:9998/inference/v1` |
| **Remote** | `https://sinatorpool-router.delqhi.com/inference/v1` |

### Auto-Failover

| Status | Aktion |
|--------|--------|
| 401/403 (Key suspended) | **suspended** → Key aus Pool, Ersatz geleast |
| 412 (Precondition Failed) | Nächster Proxy |
| 429 transient | Retry-After an Client |
| 429 permanent (Spending-Limit) | Key swap → suspended |
| 5xx | Nächster Proxy |
| Kein Key verfügbar | **1s interne Retry** (max 300× = 5 Min), kein sofortiger 503 |
| Alle Pools tot (Mac offline) | **Cloudflare Worker Fallback** (D1-Key-Rotation) — falls `CF_WORKER_URL` gesetzt |

### Key-Status

| Status | Bedeutung |
|--------|-----------|
| `available` | Nutzbar, nicht belegt |
| `assigned` | Soft-Ownership — fest einem Agent zugewiesen |
| `shared` | Wird von mehreren Agenten gleichzeitig genutzt |
| `leased` | Von Proxy reserviert (Primary + Backup) |
| `used` | Manuell verbraucht |
| `suspended` | Von Fireworks gesperrt |

`available = total - used - suspended - assigned`

## Cloudflare-Fallback (Issue #24)

Der Mac bleibt primär. Geht er offline (CF DNS Health Check schlägt fehl), übernimmt **ein** Cloudflare Worker mit einer D1-Datenbank statt der 10 lokalen Proxys — Key-Rotation läuft im Worker.

| Aspekt | Lösung |
|--------|--------|
| Smart Router | CF DNS prüft Mac → Mac tot = Worker übernimmt |
| Proxys | 1 Worker statt 10 (Key-Rotation in D1) |
| Storage | D1 Database statt `pool.json` |
| Sync | Mac → CF nach jeder Rotation (`scripts/sync_to_cf.py`) |
| Free Tier | 100k req/Tag (~10 User) |

```bash
# Router mit Fallback starten
export CF_WORKER_URL="https://sinator-fallback.<account>.workers.dev"
export SINATOR_AUTH_TOKEN="<client-bearer>"
python3 scripts/pool-router.py

# Pool nach Rotation nach D1 syncen
CF_WORKER_URL=... CF_SYNC_TOKEN=... python3 scripts/sync_to_cf.py
```

Deploy-Schritte, D1-Schema und die Antworten auf die 5 offenen Fragen (Auth, Rate Limiting, Key-Sync, DNS, Mac-Wiederkehr): siehe [`cloudflare/README.md`](cloudflare/README.md).

## Setup

1. **GMX-Zugangsdaten** über `/setup` im Dashboard konfigurieren
2. Oder direkt `data/config.json`:
```json
{
  "gmx_email": "deinname@gmx.de",
  "gmx_password": "DEIN_GMX_PASSWORT",
  "fireworks_password": "DEIN_FIREWORKS_PASSWORT"
}
```
3. **Rotation** über Dashboard `/rotation` oder `python tools/rotate.py`

## Client-Konfiguration

### OpenCode

```bash
mkdir -p ~/.config/opencode
curl -fsSL https://raw.githubusercontent.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config/main/opencode.json \
  -o ~/.config/opencode/opencode.json
```

12 Modelle: DeepSeek V4 Pro/Flash, GLM 5.1/Fast, Kimi K2.5/2.6/Turbo, Qwen 3.6 Plus, MiniMax M2.5/2.7, GPT-OSS 120B/20B.

### Hermes

```bash
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/config/fireworks-router.yaml \
  -o ~/.hermes/config.yaml
hermes auth add custom:fireworks --type api-key --api-key "$FIREWORKS_AI_API_KEY"
```

### Python / curl

```python
from openai import OpenAI
client = OpenAI(
    base_url="https://sinatorpool-router.delqhi.com/inference/v1",
    api_key="<DEIN_API_KEY>",
)
```

```bash
curl https://sinatorpool-router.delqhi.com/inference/v1/chat/completions \
  -H "Authorization: Bearer <DEIN_API_KEY>" \
  -d '{"model":"accounts/fireworks/models/gpt-oss-120b","messages":[{"role":"user","content":"Hi"}]}'
```

## Architecture

```
Clients (opencode, Cursor, Continue, Python)
  ↓ OpenAI-compatible API (EINE URL)
Pool-Router (:9998, ThreadingMixIn)
  ↓ Auto-Failover über 10 Proxys
Pool Proxys (:8888-:8897, aiohttp SSE, silent key swap)
  ↓ Key rotation on 412/429/401, 1s Key-Retry
Backend (:8100, FastAPI)
  ↓ PoolManager + Keychain + Rotation-Orchestrator
Chrome (Playwright V15.4 ONE Browser)
  ↓ GMX + Fireworks Automation
Alias-Rotation → Signup → OTP → API Key → Pool
```

## Pool-API

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/v1/pool/stats` | GET | `total/used/suspended/assigned/shared/available` |
| `/api/v1/pool/keys` | GET | Alle Keys |
| `/api/v1/pool/lease` | POST | Key reservieren (Legacy) |
| `/api/v1/pool/return` | POST | Key freigeben |
| `/api/v1/pool/report` | POST | Key melden + Ersatz leasen |
| `/api/v1/pool/add` | POST | Key hinzufügen |
| `/api/v1/pool/agent-key` | POST | V19.14 — Soft-Ownership Key-Zuweisung |
| `/api/v1/pool/agent-release` | POST | V19.14 — Agent gibt Key frei |
| `/api/v1/pool/agent-heartbeat` | POST | V19.14 — Agent-Heartbeat |

## Repository-Landschaft

| Repo | GitHub | Funktion |
|------|--------|----------|
| **SINator-FireworksAI** (dieses) | [SIN-Rotator/SINator-FireworksAI](https://github.com/SIN-Rotator/SINator-FireworksAI) | Key Pool + Proxy + Automation |
| **SINator-dashboard** | [SIN-Rotator/SINator-dashboard](https://github.com/SIN-Rotator/SINator-dashboard) | Tauri Dashboard + Setup |
| **SINator-heypiggy** | [SIN-Rotator/SINator-heypiggy](https://github.com/SIN-Rotator/SINator-heypiggy) | HeyPiggy Account Generator |
| **OpenCode Config** | [OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config](https://github.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config) | opencode.json mit 12 Modellen |
| **Hermes Bundle** | [SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle) | Hermes Provider Config |

---

*Stand: 2026-06-02 | 261 Keys (~5 available, ~250 suspended) | 10 Proxys + Pool-Router | V19.14 Soft-Ownership | Frame-aware OTP | Proxy 1s Key-Retry*
