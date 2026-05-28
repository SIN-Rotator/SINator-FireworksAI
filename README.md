# SIN-Hermes-Provider-Bundle

**Hermes-native Provider-Konfiguration fuer Survey Automation.**

Fireworks-AI-Setup, 412-Retry-Fix, UA-Spoof-Patch, und Pool-Router mit Auto-Failover.

Fuer Browser-Skills siehe [SIN-Hermes-Browser-Skills-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Browser-Skills-Bundle).

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install.sh | bash
```

Das installiert alles: Pool-Router, Config, 412-Patch, UA-Spoof, unlimited max_turns.

## Pool-Router — EINE Base-URL, 10 Proxys, Auto-Failover

**NUR EINE einzige URL** — kein manuelles Pool-Wechseln mehr.

Clients nutzen den Pool-Router als Base-URL. Der Router verteilt Requests automatisch auf 10 lokale Proxys (8888-8897), jeder mit eigenem API-Key aus dem Pool. Bei 413/429/412/5xx springt der Router zum nächsten Proxy — kein gegenseitiges Blockieren, kein Single-Point-of-Failure.

| Zugriff | Base URL |
|---------|----------|
| **Lokal (dieser Mac)** | `http://localhost:9998/inference/v1` |
| **Remote (andere Macs / Clients)** | `https://sinatorpool-router.delqhi.com/inference/v1` |

### Backend: 10 Proxys (lokal, 8888-8897)

Jeder Proxy ist eine eigene aiohttp-Instanz mit charset-Fix, eigenem API-Key aus dem Pool (218 Keys), und launchd-Autostart.

### Auto-Failover

| Status | Reaktion |
|--------|----------|
| 413 Payload Too Large | Nächster Proxy |
| 429 Rate Limit | Nächster Proxy |
| 412 Account Suspended | Nächster Proxy |
| 500/502/503/504 Server Error | Nächster Proxy |
| Alle Pools gleicher Fehler | Status-Code durchreichen (pass-through) |
| Proxy 3 Fehler in 60s | Cooldown — 60s Pause |

### Threading Fix (2026-05-28)

`socketserver.TCPServer` → `ThreadingMixIn + TCPServer`. Vorher blockierte eine offene Verbindung alle anderen Requests.

### 413 pass-through (v3)

Wenn ALLE Pools denselben Fehler zurückgeben, wird der Status-Code durchgereicht statt in 500 gewrappt.

### Proxy charset bug fix

Der aiohttp-Proxy crashte bei `Content-Type: application/json; charset=utf-8` mit `ValueError`. Fix: charset-Parameter vor Response-Konstruktion strippen. 10 Proxy-Instanzen (8888-8897) per launchd.

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

## Inhalt

| Komponente | Zweck |
|-----------|-------|
| `config/fireworks-router.yaml` | Hermes Config fuer Pool-Router (`localhost:9998`) |
| `config/fireworks-pool{1,2,3}.yaml` | Direkte Pool-Configs (Referenz, localhost:8888-8890) |
| `scripts/pool-router.py` | Pool-Router v3 mit Threading + 413/Cooldown/pass-through |
| `scripts/pool-router.plist` | macOS launchd Service (auto-start, restart on crash) |
| `patches/error_classifier_412.patch` | 412-Retry-Fix |
| `skills/sin-hermes-provider-setup/` | Hermes Skill — Installation auf neuem Mac |
| `agent_toolbox/core/gmx_service.py` | GMX Session + Alias-Rotation + OTP-Read |
| `agent_toolbox/core/fireworks_service.py` | Fireworks Registration + API-Key-Management |
| `agent_toolbox/core/cdp_client.py` | Chrome DevTools Protocol Client |
| `agent_toolbox/core/pool_manager.py` | API-Key Pool-Manager (Lease/Return) |
| `proxy/` | Pool-Proxy-Source (Spiegel von `~/.sin-pool/`) — server.py mit silent swap |
| `_ua_patch.py` | User-Agent Spoof + max_retries=0 fuer OpenAI SDK |
| `docs/` | 412-Fix, UA-Spoof, Pool-Wechsel, Troubleshooting, Router |

## Struktur

```
├── agent_toolbox/
│   └── core/
│       ├── gmx_service.py              # GMX Session + Alias-Rotation + OTP
│       ├── fireworks_service.py        # Fireworks Registration + API-Key
│       ├── cdp_client.py               # Chrome DevTools Protocol Client
│       └── pool_manager.py             # API-Key Pool-Manager
├── config/
│   ├── fireworks-router.yaml           # localhost:9998 -> auto-failover
│   ├── fireworks-pool1.yaml            # Referenz: localhost:8888
│   ├── fireworks-pool2.yaml            # Referenz: localhost:8889
│   └── fireworks-pool3.yaml            # Referenz: localhost:8890
├── patches/
│   └── error_classifier_412.patch      # 412 + "suspended" -> retryable
├── proxy/
│   ├── __init__.py                     # Spiegel von ~/.sin-pool/
│   ├── config.py
│   ├── key_cache.py
│   ├── pool_client.py
│   └── server.py                       # silent swap Fix (412/429)
├── scripts/
│   ├── pool-router.py                  # Lokaler Proxy (v3: 413 pass-through)
│   └── pool-router.plist               # macOS launchd Service (auto-start)
├── docs/
│   ├── 412-retry-fix.md                # 412 Fix Doku
│   ├── ua-spoof.md                     # UA-Spoof Doku
│   ├── pool-switching.md               # Pool-Wechsel Anleitung
│   ├── troubleshooting.md              # Fehlerbehebung
│   └── router.md                       # Pool-Router Doku
├── skills/
│   └── sin-hermes-provider-setup/      # Hermes Skill fuer Installation
│       └── SKILL.md
├── _ua_patch.py                        # UA-Spoof + max_retries=0
├── install.sh                          # Einziger Installer (Router + alles)
└── README.md                           # Diese Datei
```

## Warum getrennt?

| Bundle | Inhalt | Update-Frequenz |
|--------|--------|-----------------|
| **Provider-Bundle** | Config, Patches, Router, UA-Spoof | Selten |
| **Browser-Skills-Bundle** | 22+ Skills, SOP | Oft (nach jeder Umfrage) |

## Auth

```bash
hermes auth add custom:fireworks --type api-key --api-key "$FIREWORKS_AI_API_KEY"
```
