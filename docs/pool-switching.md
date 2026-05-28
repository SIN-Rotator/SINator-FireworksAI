# Pool-Wechsel

## Warum wechseln?

Mit dem Pool-Router ist manuelles Wechseln meist nicht nötig — der Router wechselt automatisch bei Fehlern (413, 429, 412, 5xx).

Aber manchmal willst du manuell eingreifen:
- Pool 1 ist langsam (kein Fehler, nur hohe Latenz)
- Du willst testen ob ein bestimmter Pool schneller ist
- Router hat einen Bug und du willst direkt

## Mit Router (empfohlen)

### Router stoppen + Config auf direkten Pool

```bash
# 1. Router stoppen
launchctl unload ~/Library/LaunchAgents/com.sinator.pool-router.plist
# 2. Config auf direkten Pool ändern
# ~/.hermes/config.yaml:
#   base_url: http://localhost:9998/inference/v1
#   # ODER remote:
#   #   base_url: https://sinatorpool-router.delqhi.com/inference/v1
# 3. Hermes neustarten (Config wird bei Start gelesen)
```
### Zurück zum Router
```bash
# 1. Config auf Router setzen (EINE Base-URL für alle)
# ~/.hermes/config.yaml:
#   base_url: http://localhost:9998/inference/v1   # lokal
#   # ODER: https://sinatorpool-router.delqhi.com/inference/v1  # remote
# 2. Router starten
launchctl load ~/Library/LaunchAgents/com.sinator.pool-router.plist
```

## Ohne Router (direkte Pools — nicht empfohlen)

Lokal am Mac geht auch direkt (ohne Router):

```bash
# base_url: http://localhost:8888/inference/v1   # Pool 1 direkt
```

Aber Router empfehlenswert — sonst kein Auto-Failover bei 413/429.

## Verifizierung

```bash
# Aktuelle Config
grep "base_url" ~/.hermes/config.yaml

# Router läuft?
pgrep -f pool-router.py

# Sollte zeigen:
#   base_url: http://localhost:9998/inference/v1  (Router-Modus, lokal)
#   base_url: https://sinatorpool-router.delqhi.com/inference/v1  (Router-Modus, remote)
```
