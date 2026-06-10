# SINator — Fireworks AI Key Pool

[![GitNexus](https://img.shields.io/badge/GitNexus-knowledge%20graph-8B5CF6)](.gitnexus/)

Automated GMX alias rotation → Fireworks AI account registration → API key pool.
OpenAI-compatible proxy with automatic key rotation on rate-limits and silent key swap.

**Backend:** :8000 | **Pool:** ~245 Keys | **Proxy:** 10 Instances (:8888-:8897) | **Router:** :9998

**Dashboard:** [SINator-dashboard](https://github.com/SIN-Rotator/SINator-dashboard) |
**Config:** [OpenSIN-Code](https://github.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config) |
**Hermes:** [SIN-Hermes-Bundles](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle)

> **V20.0 Update (10.06.2026):** 2 chirurgische Fixes aus v19.3-gmx-delete-fixed portiert (siehe `AGENTS.md`):
> - `_delete_alias`: kleinste-BBox Row + Playwright native mouse hover
> - `_login`: post-consent redirect zu www.gmx.net
>
> **Tag `v20.0-fireworks-working`** markiert den verifizierten funktionierenden Stand.

## Quick Start

```bash
# Dashboard (empfohlen):
cd ~/dev/SINator-dashboard && ./start.sh
# → Backend (:8000) + Dashboard (:3000) + Tauri App

# Oder standalone:
python agent_toolbox/start_toolbox.py
# → http://localhost:8000/docs
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

### Key-Status

| Status | Bedeutung |
|--------|-----------|
| `available` | Nutzbar, nicht belegt |
| `leased` | Von Proxy reserviert (Primary + Backup) |
| `used` | Manuell verbraucht |
| `suspended` | Von Fireworks gesperrt |

`available = total - used - suspended - leased`

## Setup

```bash
# Dependencies installieren
pip install -e .                    # Produktion
pip install -e ".[dev]"             # mit Test-Deps
playwright install chromium

# Oder via requirements.txt
pip install -r requirements.txt && playwright install chromium
```

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
Backend (:8000, FastAPI)
  ↓ PoolManager + Keychain + Rotation-Orchestrator
Chrome (Playwright V15.4 ONE Browser)
  ↓ GMX + Fireworks Automation
Alias-Rotation → Signup → OTP → API Key → Pool
```

## Pool-API

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/v1/pool/stats` | GET | `total/used/suspended/leased/available` |
| `/api/v1/pool/keys` | GET | Alle Keys |
| `/api/v1/pool/lease` | POST | Key reservieren |
| `/api/v1/pool/return` | POST | Key freigeben |
| `/api/v1/pool/report` | POST | Key melden + Ersatz leasen |
| `/api/v1/pool/add` | POST | Key hinzufügen |

## Repository-Landschaft

| Repo | GitHub | Funktion |
|------|--------|----------|
| **SINator-FireworksAI** (dieses) | [SIN-Rotator/SINator-FireworksAI](https://github.com/SIN-Rotator/SINator-FireworksAI) | Key Pool + Proxy + Automation |
| **SINator-dashboard** | [SIN-Rotator/SINator-dashboard](https://github.com/SIN-Rotator/SINator-dashboard) | Tauri Dashboard + Setup |
| **SINator-heypiggy** | [SIN-Rotator/SINator-heypiggy](https://github.com/SIN-Rotator/SINator-heypiggy) | HeyPiggy Account Generator |
| **OpenCode Config** | [OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config](https://github.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config) | opencode.json mit 12 Modellen |
| **Hermes Bundle** | [SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle) | Hermes Provider Config |

---

*Stand: 2026-06-10 | pyproject.toml mit [dev]-Extras | V15.4 ONE-Browser | Proxy 1s Key-Retry*
