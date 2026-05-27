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
Er leitet Requests an `sinatorpool1 -> pool2 -> pool3` weiter.

**Auto-Failover:** Bei 429 (Rate Limit), 412 (Suspended), oder 5xx (Server Error)
springt der Router automatisch zum naechsten Pool.

| Pool | Base URL | Prioritaet |
|------|----------|------------|
| **Pool 1** | `https://sinatorpool1.delqhi.com/inference/v1` | 1 (bevorzugt) |
| **Pool 2** | `https://sinatorpool2.delqhi.com/inference/v1` | 2 (Fallback) |
| **Pool 3** | `https://sinatorpool3.delqhi.com/inference/v1` | 3 (letzter Fallback) |

## Was der Installer macht

1. **Pool Router Config** — `~/.hermes/config.yaml` mit `localhost:9998`
2. **Pool Router Daemon** — `pool-router.py` im Hintergrund starten
3. **412 Retry Patch** — `error_classifier.py`: 412 + "suspended" -> `billing` + retryable
4. **UA-Spoof Patch** — `_ua_patch.py` + `import _ua_patch` in `run_agent.py`
5. **Unlimited max_turns** — `999999` (kein Iterations-Limit)

## Management

```bash
# Router laeuft?
pgrep -f pool-router.py

# Router stoppen
pkill -f pool-router.py

# Router Logs
tail -f ~/.hermes/logs/pool-router.log

# Router manuell starten
python3 ~/.hermes/scripts/pool-router.py &
```

## Inhalt

| Komponente | Zweck |
|-----------|-------|
| `config/fireworks-router.yaml` | Hermes Config fuer lokalen Pool-Router |
| `config/fireworks-pool{1,2,3}.yaml` | Einzelne Pool-Configs (Referenz, nicht fuer Installation) |
| `scripts/pool-router.py` | Lokaler Proxy mit Auto-Failover |
| `patches/error_classifier_412.patch` | 412-Retry-Fix |
| `_ua_patch.py` | User-Agent Spoof fuer OpenAI SDK |
| `docs/` | 412-Fix, UA-Spoof, Pool-Wechsel, Troubleshooting, Router |

## Struktur

```
├── config/
│   ├── fireworks-router.yaml           # localhost:9998 -> auto-failover
│   ├── fireworks-pool1.yaml            # Referenz: sinatorpool1
│   ├── fireworks-pool2.yaml            # Referenz: sinatorpool2
│   └── fireworks-pool3.yaml            # Referenz: sinatorpool3
├── patches/
│   └── error_classifier_412.patch      # 412 + "suspended" -> retryable
├── scripts/
│   └── pool-router.py                  # Lokaler Proxy
├── docs/
│   ├── 412-retry-fix.md                # 412 Fix Doku
│   ├── ua-spoof.md                     # UA-Spoof Doku
│   ├── pool-switching.md                 # Pool-Wechsel Anleitung
│   ├── troubleshooting.md                # Fehlerbehebung
│   └── router.md                       # Pool-Router Doku
├── _ua_patch.py                        # UA-Spoof
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
