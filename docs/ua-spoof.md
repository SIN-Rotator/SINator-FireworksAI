# UA-Spoof Patch

## Problem

Hermes nutzt das OpenAI Python SDK für alle LLM-Requests. Das SDK sendet default:

```
User-Agent: OpenAI/Python 1.x.x
```

Unsere sinator-Pool-Router (sinatorpool-router.delqhi.com) erkennen diesen Header als "Bot/Script" und drosseln oder blocken Requests.

## Lösung

`_ua_patch.py` monkey-patched `openai.OpenAI.__init__` und injiziert einen echten Chrome-on-Mac User-Agent:

```
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...
```

## Scope

**Betroffen:** Alle LLM-Calls — Chat, Vision, Tools, alles was über OpenAI SDK läuft.

**Nicht betroffen:** Browser-Tools (die haben ihren eigenen Chrome-UA via CDP).

## Dateien

| Datei | Wo hin | Was macht der Installer |
|-------|--------|------------------------|
| `_ua_patch.py` | `~/.hermes/hermes-agent/_ua_patch.py` | `curl` von GitHub |
| `run_agent.py` Mod | `import _ua_patch` nach `import os` | `sed` insert wenn nicht vorhanden |

## Manuelle Anwendung (falls Installer versagt)

```bash
# 1. Patch-Datei holen
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/_ua_patch.py \
  -o ~/.hermes/hermes-agent/_ua_patch.py

# 2. Import in run_agent.py einfügen (nach Zeile "import os")
sed -i '' 's/^import os$/import os\nimport _ua_patch  # noqa/' ~/.hermes/hermes-agent/run_agent.py
```

## Verifizierung

```bash
# Check: Patch-Datei existiert
ls ~/.hermes/hermes-agent/_ua_patch.py

# Check: Import in run_agent.py
grep "import _ua_patch" ~/.hermes/hermes-agent/run_agent.py
```

Beides muss grün sein. Sonst: Installer nochmal laufen lassen.
