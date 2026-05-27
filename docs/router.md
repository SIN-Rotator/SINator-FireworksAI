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
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-router.sh | bash
```

Das macht:
1. Config auf `localhost:9998` statt direktem Pool
2. `pool-router.py` herunterladen + ausführbar machen
3. Router im Hintergrund starten (`nohup`)
4. 412-Patch + UA-Spoof wie gewohnt anwenden

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

Wenn du lieber direkt einen Pool ansprechen willst (z.B. weil Router einen Bug hat):

```bash
# Direkt Pool 2
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-pool2.sh | bash
```

Der direkte Pool-Installer überschreibt die Config mit der Pool-URL.
