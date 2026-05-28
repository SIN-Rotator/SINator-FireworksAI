# SIN-Hermes-Provider-Bundle

**Hermes-native Provider-Konfiguration fuer Survey Automation.**

Fireworks-AI-Setup, 412-Retry-Fix, UA-Spoof-Patch, und Pool-Router mit Auto-Failover.

Fuer Browser-Skills siehe [SIN-Hermes-Browser-Skills-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Browser-Skills-Bundle).

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install.sh | bash
```

Das installiert alles: Pool-Router, Config, 412-Patch, UA-Spoof, unlimited max_turns.

## Pool-Router

Statt einen einzelnen Proxy auszuwaehlen, laeuft ein lokaler Router auf `localhost:9998`.
Er leitet Requests an `sinatorpool-router -> pool2 -> pool3` weiter.

**Auto-Failover:** Bei 413 (Payload Too Large), 429 (Rate Limit), 412 (Suspended), oder 5xx (Server Error)
springt der Router automatisch zum naechsten Pool.

**413 pass-through (v3 — 2026-05-28):** Wenn ALLE Pools denselben Fehler (z.B. 413)
zurückgeben, wird der Status-Code durchgereicht statt in 500 gewrappt. Fix: 413 zur
Retry-Liste hinzugefügt (vorher: sofortiger `raise` → `except Exception` → 500).

**Proxy charset bug fix:** Der aiohttp-Proxy (`~/.sin-pool/server.py`) crashte bei
`Content-Type: application/json; charset=utf-8` von Fireworks mit `ValueError`.
Fix: charset-Parameter vor Response-Konstruktion strippen. 3 Proxy-Instanzen
(8888/8889/8890) per launchd.

| Pool | Base URL | Prioritaet |
|------|----------|------------|
| **Pool 1** | `https://sinatorpool-router.delqhi.com/inference/v1` | 1 (bevorzugt) |
| **Pool 2** | `https://sinatorpool-router.delqhi.com/inference/v1` | 2 (Fallback) |
| **Pool 3** | `https://sinatorpool-router.delqhi.com/inference/v1` | 3 (letzter Fallback) |

## Was der Installer macht

1. **Pool Router Config** — `~/.hermes/config.yaml` mit `localhost:9998`
2. **Pool Router Daemon** — `pool-router.py` via launchd (auto-start on login, restart on crash)
3. **412 Retry Patch** — `error_classifier.py`: 412 + "suspended" -> `billing` + retryable
4. **UA-Spoof Patch** — `_ua_patch.py` + `import _ua_patch` in `run_agent.py`
5. **Unlimited max_turns** — `999999` (kein Iterations-Limit)

## Management

```bash
# Router läuft?
pgrep -f pool-router.py

# Router stoppen
launchctl unload ~/Library/LaunchAgents/com.sinhermes.poolrouter.plist

# Router starten
launchctl load ~/Library/LaunchAgents/com.sinhermes.poolrouter.plist

# Logs
tail -f ~/.hermes/logs/pool-router.log
```

## Inhalt

| Komponente | Zweck |
|-----------|-------|
| `config/fireworks-router.yaml` | Hermes Config fuer lokalen Pool-Router |
| `config/fireworks-pool{1,2,3}.yaml` | Einzelne Pool-Configs (Referenz, nicht fuer Installation) |
| `scripts/pool-router.py` | Lokaler Proxy mit Auto-Failover (v3: 413 pass-through) |
| `scripts/pool-router.plist` | macOS launchd Service (auto-start, restart on crash) |
| `patches/error_classifier_412.patch` | 412-Retry-Fix |
| `skills/sin-hermes-provider-setup/` | Hermes Skill — Installation auf neuem Mac |
| `agent_toolbox/core/gmx_service.py` | GMX Session + Alias-Rotation + OTP-Read |
| `agent_toolbox/core/fireworks_service.py` | Fireworks Registration + API-Key-Management |
| `agent_toolbox/core/cdp_client.py` | Chrome DevTools Protocol Client |
| `agent_toolbox/core/pool_manager.py` | API-Key Pool-Manager (Lease/Return) |
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
│   ├── fireworks-pool1.yaml            # Referenz: sinatorpool-router
│   ├── fireworks-pool2.yaml            # Referenz: sinatorpool-router
│   └── fireworks-pool3.yaml            # Referenz: sinatorpool-router
├── patches/
│   └── error_classifier_412.patch      # 412 + "suspended" -> retryable
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
