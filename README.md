# SIN-Hermes-Provider-Bundle

**Hermes-native Provider-Konfiguration für Survey Automation.**

Fireworks-AI-Setup, 412-Retry-Fix, UA-Spoof-Patch, und Config für dedizierte sinator Pool-Proxies.

Für Browser-Skills siehe [SIN-Hermes-Browser-Skills-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Browser-Skills-Bundle).

## Quick Start

### Einzelner Pool (wähle deinen Proxy)

```bash
# Mac 1 → sinatorpool1.delqhi.com
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-pool1.sh | bash

# Mac 2 → sinatorpool2.delqhi.com
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-pool2.sh | bash

# Mac 3 → sinatorpool3.delqhi.com
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-pool3.sh | bash
```

### Alle Pools (Complete)

```bash
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install.sh | bash
```

## Pool-Übersicht

| Pool | Base URL | Mac | Installer |
|------|----------|-----|-----------|
| **Pool 1** | `https://sinatorpool1.delqhi.com/inference/v1` | Mac 1 | `install-pool1.sh` |
| **Pool 2** | `https://sinatorpool2.delqhi.com/inference/v1` | Mac 2 | `install-pool2.sh` |
| **Pool 3** | `https://sinatorpool3.delqhi.com/inference/v1` | Mac 3 | `install-pool3.sh` |

Alle Pools teilen denselben API-Key: `FIREWORKS_AI_API_KEY` (setze als Umgebungsvariable)

## Was der Installer macht

1. **Fireworks Config** — `~/.hermes/config.yaml` mit dedizierter Pool-URL
2. **412 Retry Patch** — `error_classifier.py`: 412 + "suspended" → `billing` + retryable
3. **UA-Spoof Patch** — `_ua_patch.py` + `import _ua_patch` in `run_agent.py`
4. **Unlimited max_turns** — `999999` (kein Iterations-Limit)

## UA-Spoof Patch

**Warum:** Das OpenAI Python SDK sendet default `User-Agent: OpenAI/Python 1.x.x`. Unsere sinator-Proxy-Loadbalancer können damit "Bot/Script" erkennen und blocken/drosseln. Der Patch injiziert einen echten Chrome-on-Mac User-Agent in jeden HTTP-Request.

**Was gepatched wird:** `openai.OpenAI.__init__` — greift für **alle** LLM-Calls (Chat, Vision, Tools), nicht nur Browser.

## Inhalt

| Komponente | Zweck |
|-----------|-------|
| `config/fireworks-pool{1,2,3}.yaml` | Hermes Config pro dediziertem Pool-Proxy |
| `patches/error_classifier_412.patch` | 412-Retry-Fix für Hermes error_classifier.py |
| `_ua_patch.py` | User-Agent Spoof für OpenAI SDK |
| `docs/` | 412-Fix-Doku, UA-Spoof, Pool-Wechsel, Troubleshooting |

## Struktur

```
├── config/
│   ├── fireworks-pool1.yaml          # Mac 1 → sinatorpool1
│   ├── fireworks-pool2.yaml          # Mac 2 → sinatorpool2
│   └── fireworks-pool3.yaml          # Mac 3 → sinatorpool3
├── patches/
│   └── error_classifier_412.patch      # 412 + "suspended" → retryable
├── docs/
│   ├── 412-retry-fix.md                # Warum und wie der Fix funktioniert
│   ├── ua-spoof.md                     # User-Agent Spoof Doku
│   ├── pool-switching.md                 # Pool-Wechsel Anleitung
│   └── troubleshooting.md                # Fehlerbehebung
├── _ua_patch.py                        # UA-Spoof (OpenAI SDK Monkey-Patch)
├── install.sh                          # Complete Installer (alle 3 Pools)
├── install-pool1.sh                    # Pool 1 Installer
├── install-pool2.sh                    # Pool 2 Installer
├── install-pool3.sh                    # Pool 3 Installer
└── README.md                           # Diese Datei
```

## Warum getrennt?

| Bundle | Inhalt | Update-Frequenz |
|--------|--------|-----------------|
| **Provider-Bundle** | Config, Patches, Auth, UA-Spoof | Selten (nur bei Provider-Änderungen) |
| **Browser-Skills-Bundle** | 22+ Skills, SOP | Oft (nach jeder Umfrage neuer Skill) |

Trennung erlaubt unabhängige Releases. Skills können täglich wachsen ohne Provider-Config zu berühren.
