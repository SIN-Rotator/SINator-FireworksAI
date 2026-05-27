# Pool Router

## Was ist das?

Ein lokaler Mini-Proxy (`pool-router.py`) der auf `localhost:9998` lauscht und Requests an `sinatorpool1/2/3.delqhi.com` weiterleitet.

**Killer-Feature:** Bei 429 (Rate Limit), 412 (Suspended), oder 5xx (Server Error) springt der Router **automatisch** zum nächsten Pool.

## Warum?

| Problem | Ohne Router | Mit Router |
|---------|------------|-----------|
| Pool 1 gibt 429 | Request failed → Nutzer muss manuell Config ändern | Automatisch Pool 2 probieren |
| Pool 2 gibt 412 (suspended) | Request failed | Automatisch Pool 3 probieren |
| Pool 3 gibt 503 | Request failed | Wartet und probiert Pool 1 erneut (failure-counter reset) |

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install.sh | bash
```

Das macht:
1. Config auf `localhost:9998` statt direktem Pool
2. `pool-router.py` herunterladen + ausführbar machen
3. Router im Hintergrund starten (`nohup`)
4. 412-Patch + UA-Spoof wie gewohnt anwenden

## Neue Proxies hinzufügen

Der Router nutzt eine einfache Python-Liste. Um einen 4. Pool hinzuzufügen:

```bash
# 1. Edit pool-router.py
nano ~/.hermes/scripts/pool-router.py

# 2. POOLS-Liste erweitern:
# Vorher:
POOLS = [
    "https://sinatorpool1.delqhi.com",
    "https://sinatorpool2.delqhi.com",
    "https://sinatorpool3.delqhi.com",
]
# Nachher:
POOLS = [
    "https://sinatorpool1.delqhi.com",
    "https://sinatorpool2.delqhi.com",
    "https://sinatorpool3.delqhi.com",
    "https://sinatorpool4.delqhi.com",  # NEU
]

# 3. Router neustarten
pkill -f pool-router.py
python3 ~/.hermes/scripts/pool-router.py &
```

Kein Hermes-Restart nötig. Kein Config-Edit nötig. Nur `POOLS`-Liste erweitern und Router neustarten.

## Hermes Config (nach Installation)

```yaml
custom_providers:
- name: fireworks
  base_url: http://localhost:9998/inference/v1
  key_env: FIREWORKS_AI_API_KEY
```

Hermes denkt es redet mit einem Provider. Tatsächlich redet es mit dem lokalen Router.

## Router-Verhalten

### Reihenfolge (Priorität)

1. `sinatorpool1.delqhi.com`
2. `sinatorpool2.delqhi.com`
3. `sinatorpool3.delqhi.com`

### Retry-Trigger (Status Codes)

- `429` — Too Many Requests
- `412` — Precondition Failed (suspended key)
- `500`, `502`, `503`, `504` — Server Errors

### Failure-Tracking

Jeder Pool hat einen Counter. Bei Retry-Trigger: +1. Bei Erfolg: -1. Bei `MAX_FAILURES` (default 3) wird der Pool übersprungen bis er wieder erfolgreich antwortet.

### Logs

```bash
tail -f ~/.hermes/logs/pool-router.log
```

Beispiel:
```
[PoolRouter] Pool 1 returned 429 (failures: 1)
[PoolRouter] Pool 2 returned 200 (failures: 0)
[PoolRouter] "POST /inference/v1/chat/completions" 200 -
```

## Management

```bash
# Läuft der Router?
pgrep -f pool-router.py

# Router stoppen
pkill -f pool-router.py

# Router manuell starten (z.B. nach Reboot)
python3 ~/.hermes/scripts/pool-router.py &

# Logs
ls -la ~/.hermes/logs/pool-router.log
```

## Einschränkungen

- **Kein Load-Balancing** — Es gibt keinen Round-Robin. Pool 1 ist bevorzugt solange er geht.
- **Kein Health-Check** — Der Router weiß nicht ob ein Pool "langsam" ist, nur ob er Fehler wirft.
- **Ein Prozess pro Maschine** — Der Router bindet Port 9998. Auf derselben Maschine kann nur einer laufen.

## Alternative: Direkte Pools (kein Router)

Wenn du lieber direkt einen Pool ansprechen willst (z.B. weil Router einen Bug hat oder du nur einen Pool hast):

```bash
# Config direkt auf Pool 2
# ~/.hermes/config.yaml editieren:
#   base_url: https://sinatorpool2.delqhi.com/inference/v1
# Dann Router stoppen (falls läuft):
pkill -f pool-router.py
```

Oder `config/fireworks-pool2.yaml` als Vorlage nutzen.

Der direkte Pool-Installer überschreibt die Config mit der Pool-URL.
