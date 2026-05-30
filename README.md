# SINator — Fireworks AI Key Pool

[![GitNexus](https://img.shields.io/badge/GitNexus-knowledge%20graph-8B5CF6)](.gitnexus/)

> **⚠️ GitNexus-Pflicht:** Bevor du Code in diesem Repo änderst, MUSST du `gitnexus_impact()` (Blast Radius) und `gitnexus_detect_changes()` (vor Commit) ausführen. Siehe [GitNexus Guide](.gitnexus/).

Automated GMX alias rotation → Fireworks AI account → API key pool.
OpenAI-compatible proxy with automatic key rotation on rate-limits.

**Backend Port:** `8000` | **Dashboard Repo:** [SINator-dashboard](https://github.com/SIN-Rotator/SINator-dashboard) | **HeyPiggy Repo:** [SINator-heypiggy](https://github.com/SIN-Rotator/SINator-heypiggy)

## EINE Base-URL — Pool-Router mit Auto-Failover

**Es gibt nur EINEN Endpunkt.** Der Pool-Router verteilt Requests automatisch auf 10 lokale Proxys (8888-8897), jeder mit eigenem API-Key aus dem Pool. Bei 413/429/412/5xx springt der Router zum nächsten Proxy.

| Zugriff | Base URL |
|---------|----------|
| **Lokal (dieser Mac)** | `http://localhost:9998/inference/v1` |
| **Remote (andere Macs / Clients)** | `https://sinatorpool-router.delqhi.com/inference/v1` |

**Kein manuelles Pool-Wechseln mehr.** Der Router macht alles automatisch.

### Auto-Failover

| Status | Reaktion |
|--------|----------|
| 413 Payload Too Large | Nächster Proxy |
| 429 Rate Limit | Nächster Proxy |
| 412 Account Suspended | Nächster Proxy |
| 500/502/503/504 Server Error | Nächster Proxy |
| Alle Pools gleicher Fehler | Status-Code durchreichen (pass-through) |
| Proxy 3 Fehler in 60s | Cooldown — 60s Pause |

### Backend: 10 Proxys (lokal, 8888-8897)

Jeder Proxy ist eine eigene aiohttp-Instanz mit charset-Fix, eigenem API-Key aus dem Pool (218 Keys), und launchd-Autostart.

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
Pool-Router (:9998, ThreadingMixIn)
  ↓ Auto-Failover über 10 Proxys
Pool Proxys (:8888-:8897, aiohttp SSE)
  ↓ Key rotation + silent swap
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
| `com.sinator.pool-router` | :9998 | Pool-Router mit Auto-Failover |
| `com.sinator.pool-proxy-{8888..8897}` | :8888-:8897 | 10× OpenAI-compatible proxies with silent swap |
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
```

---

## Client Konfiguration

### Lokal (auf Mac mit Backend)

**OpenCode (`~/.config/opencode/opencode.json`):**
```json
{
  "provider": {
    "fireworks-ai": {
      "options": {
        "baseURL": "http://localhost:9998/inference/v1",
        "apiKey": "<DEIN_API_KEY>"
      }
    }
  }
}
```

**Umgebungsvariable:**
```bash
export FIREWORKS_API_KEY="<DEIN_API_KEY>"
```

**Python:**
```python
from openai import OpenAI
client = OpenAI(
    base_url="http://localhost:9998/inference/v1",
    api_key="<DEIN_API_KEY>",
)
```

### Remote (andere Macs)

**OpenCode:**
```json
{
  "provider": {
    "fireworks-ai": {
      "options": {
        "baseURL": "https://sinatorpool-router.delqhi.com/inference/v1",
        "apiKey": "<DEIN_API_KEY>"
      }
    }
  }
}
```

**curl:**
```bash
curl https://sinatorpool-router.delqhi.com/inference/v1/models \
  -H "Authorization: Bearer <DEIN_API_KEY>"
```

---

## Was der Installer macht

1. **Pool Router Config** — `~/.hermes/config.yaml` mit `localhost:9998`
2. **Pool Router Daemon** — `pool-router.py` via launchd `com.sinator.pool-router`
3. **10 Proxy Daemons** — `com.sinator.pool-proxy-{8888..8897}` via launchd
4. **412 Retry Patch** — `error_classifier.py`: 412 + "suspended" -> `billing` + retryable
5. **UA-Spoof Patch** — `_ua_patch.py` + `import _ua_patch` in `run_agent.py`
6. **Unlimited max_turns** — `999999` (kein Iterations-Limit)

## Management

```bash
# Router läuft?
pgrep -f pool-router.py

# Router stoppen
launchctl unload ~/Library/LaunchAgents/com.sinator.pool-router.plist

# Router starten
launchctl load ~/Library/LaunchAgents/com.sinator.pool-router.plist

# Proxys (alle 10)
launchctl list | grep pool-proxy

# Pool-Router Logs
tail -f /tmp/pool-router-launchd.log
```

## Struktur

```
├── agent_toolbox/
│   └── core/
│       ├── gmx_service.py              # GMX Session + Alias-Rotation + OTP
│       ├── fireworks_service.py        # Fireworks Registration + API-Key
│       ├── cdp_client.py               # Chrome DevTools Protocol Client
│       └── pool_manager.py             # API-Key Pool-Manager (Lease/Return)
├── proxy/
│   ├── __init__.py                     # Spiegel von ~/.sin-pool/
│   ├── config.py
│   ├── key_cache.py
│   ├── pool_client.py
│   ├── server.py                       # silent swap Fix (412/429)
│   ├── setup.sh
│   └── start-multi.sh                  # 10 Proxys starten
├── tools/
│   ├── install.sh
│   ├── rotate.py
│   ├── sinator-cli.py
│   └── manage_services.sh
├── docs/
├── tests/
└── README.md
```

## API Key Lifecycle

| Status | Reaktion im Proxy |
|--------|-------------------|
| 401/402/403 (Key tot) | `_swap_key("suspended")` — meldet Key als suspended an Pool-API |
| 412 (Precondition Failed) | `_swap_key_silent("precondition_failed")` — Key bleibt verfügbar |
| 429 (Rate Limited) | `_swap_key_silent("rate_limited")` — Key bleibt verfügbar |
| 5xx (Server Error) | Nächster Proxy versuchen |

---

*Stand: 2026-05-28 | 218 Keys | 10 Proxys + Pool-Router | silent swap Fix*
