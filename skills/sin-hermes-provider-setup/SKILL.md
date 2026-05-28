---
description: Installiert das SIN-Hermes-Provider-Bundle auf einem neuen Mac. Hermes Config, Pool-Router, 412-Patch, UA-Spoof, Fireworks Auth. Einmalig pro Maschine.
trigger:
  - installiere provider bundle
  - provider installieren
  - installiere fireworks provider
  - setup hermes provider
  - installiere pool router
  - router installieren
  - 412 patch installieren
  - ua spoof installieren
  - sin hermes provider setup
---

# sin-hermes-provider-setup

Installiert das [SIN-Hermes-Provider-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle) auf einem neuen Mac.

Enthaelt:
- Pool-Router (localhost:9998) mit Auto-Failover ueber 10 Proxys
- 412 PRECONDITION_FAILED Retry-Patch
- User-Agent Spoof-Patch (max_retries=0 fuer Router-Retry)
- Hermes Config mit `max_turns=999999`
- launchd Auto-Start Service (Login + Crash-Restart)

## Preconditions

- `FIREWORKS_AI_API_KEY` als Umgebungsvariable gesetzt
- Hermes Agent installiert (`.hermes/` existiert)

## Steps

### 1. API-Key pruefen

```bash
echo "FIREWORKS_AI_API_KEY ist ${FIREWORKS_AI_API_KEY:-NICHT GESETZT}"
```

Wenn nicht gesetzt: Benutzer nach Key fragen oder abbrechen.

### 2. Installer ausfuehren

```bash
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install.sh | bash
```

### 3. Auth einrichten

```bash
hermes auth add custom:fireworks --type api-key --api-key "$FIREWORKS_AI_API_KEY"
```

### 4. Verifizierung (6 Checks)

```bash
echo "=== Verifizierung ===" && \
pgrep -f pool-router.py >/dev/null && echo "[OK] Router laeuft" || echo "[FAIL] Router nicht laeuft" && \
launchctl list | grep -q pool-router && echo "[OK] launchd geladen" || echo "[FAIL] launchd nicht geladen" && \
grep -q "base_url.*localhost:9998" ~/.hermes/config.yaml && echo "[OK] Config auf localhost:9998" || echo "[FAIL] Config falsch" && \
grep -q "silent swap" ~/.sin-pool/server.py && echo "[OK] 412/429 silent swap" || echo "[FAIL] 412/429 silent swap fehlt" && \
grep -q "status_code == 412" ~/.hermes/hermes-agent/agent/error_classifier.py && echo "[OK] 412 Patch" || echo "[FAIL] 412 Patch fehlt" && \
ls ~/.hermes/hermes-agent/_ua_patch.py >/dev/null 2>&1 && echo "[OK] UA-Spoof" || echo "[FAIL] UA-Spoof fehlt" && \
grep -q "max_turns: 999999" ~/.hermes/config.yaml && echo "[OK] Unlimited max_turns" || echo "[FAIL] max_turns nicht gesetzt"
```

Alle Checks muessen `[OK]` sein.

### 5. Test-Request (optional)

```bash
curl -s http://localhost:9998/v1/models 2>&1 | head -5 || echo "Router nicht erreichbar (normal wenn noch kein Auth)"
```

## Troubleshooting

| Fehler | Loesung |
|--------|---------|
| "Patch may already be applied" | Ignorieren -- Patch war schon drauf |
| Router startet nicht | `launchctl load ~/Library/LaunchAgents/com.sinator.pool-router.plist` |
| 412 Patch fehlt | Siehe `docs/412-retry-fix.md` im Bundle |
| UA-Spoof fehlt | Siehe `docs/ua-spoof.md` im Bundle |
| SDK macht 429-Retries trotz Router | UA-Spoof-Patch setzt `max_retries=0` -- pruefen ob Patch geladen |

## Management

```bash
# Router laeuft?
pgrep -f pool-router.py

# Stoppen
launchctl unload ~/Library/LaunchAgents/com.sinator.pool-router.plist

# Starten
launchctl load ~/Library/LaunchAgents/com.sinator.pool-router.plist

# Logs
tail -f ~/.hermes/logs/pool-router.log
```

## Links

- [SIN-Hermes-Provider-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle)
- [SIN-Hermes-Complete (Meta-Installer)](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Complete)
