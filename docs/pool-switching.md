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
#   base_url: https://sinatorpool2.delqhi.com/inference/v1
# 3. Hermes neustarten (Config wird bei Start gelesen)
```
### Zurück zum Router
```bash
# 1. Config auf localhost zurücksetzen
# ~/.hermes/config.yaml:
#   base_url: http://localhost:9998/inference/v1
# 2. Router starten
launchctl load ~/Library/LaunchAgents/com.sinator.pool-router.plist
```

## Ohne Router (direkte Pools)

Wenn du keinen Router willst, nutze die Pool-Configs als Vorlage:

```bash
# Pool 1 Config als Vorlage
# Siehe: config/fireworks-pool1.yaml
# Oder: config/fireworks-pool2.yaml
# Oder: config/fireworks-pool3.yaml
```

Diese YAML-Dateien zeigen wie eine direkte Pool-Config aussieht. Kopieren und `base_url` anpassen.

## Verifizierung

```bash
# Aktuelle Config
grep "base_url" ~/.hermes/config.yaml

# Router läuft?
pgrep -f pool-router.py

# Sollte zeigen:
#   base_url: http://localhost:9998/inference/v1  (Router-Modus)
# ODER:
#   base_url: https://sinatorpoolX.delqhi.com/inference/v1  (Direkt)
```
