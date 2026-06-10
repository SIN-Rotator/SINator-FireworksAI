# Pool Router

## Was ist das?

Ein lokaler Mini-Proxy (`pool-router.py`) der auf `localhost:9998` lauscht und Requests an 10 lokale Proxys (`localhost:8888-8897`) weiterleitet.

**Killer-Feature:** Bei 413 (Payload Too Large), 429 (Rate Limit), 412 (Suspended), oder 5xx (Server Error) springt der Router **automatisch** zum nächsten Pool.

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

## POOLS-Liste

Der Router leitet an diese 10 lokalen Proxys weiter:

```python
POOLS = [
    "http://localhost:8888",
    "http://localhost:8889",
    "http://localhost:8890",
    "http://localhost:8891",
    "http://localhost:8892",
    "http://localhost:8893",
    "http://localhost:8894",
    "http://localhost:8895",
    "http://localhost:8896",
    "http://localhost:8897",
]
```

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

1. `localhost:8888` (Pool 1)
2. `localhost:8889` (Pool 2)
3. `localhost:8890` (Pool 3)
4. `localhost:8891` (Pool 4)
5. `localhost:8892` (Pool 5)
6. `localhost:8893` (Pool 6)
7. `localhost:8894` (Pool 7)
8. `localhost:8895` (Pool 8)
9. `localhost:8896` (Pool 9)
10. `localhost:8897` (Pool 10)

### Retry-Trigger (Status Codes)

- `413` — Payload Too Large (API-Limit, alle Pools probieren)
- `429` — Too Many Requests
- `412` — Precondition Failed (suspended key)
- `500`, `502`, `503`, `504` — Server Errors

### Failure-Tracking

Jeder Pool hat einen Counter. Bei Retry-Trigger: +1. Bei Erfolg: -1. Bei `MAX_FAILURES` (default 3) wird der Pool mit 60s Cooldown belegt statt dauerhaft zu sterben.

### Gleicher Fehler von allen Pools (v2.1)

Wenn ALLE Pools denselben Fehler zurückgeben (z.B. 413, 500), wird der Status-Code + Body **durchgereicht** statt in "All pools exhausted" (500) gewrappt. Das ermöglicht dem Client (z.B. OpenCode SDK) eigene Retry- oder Fallback-Logik.

### 413 pass-through (v3 — 2026-05-28)

413 wurde vorher sofort mit `raise` abgefangen → `except Exception` → 500. Jetzt: 413 in der Retry-Liste → alle Pools probieren → 413 durchreichen falls alle denselben Fehler haben.

### Cloudflare-Fallback (v3 — Issue #24)

Wenn **alle** lokalen Pools tot oder in Cooldown sind (z.B. Mac offline), leitet der Router den Request an einen Cloudflare Worker weiter — sofern `CF_WORKER_URL` gesetzt ist. Der Worker rotiert Keys gegen eine D1-Datenbank (statt `pool.json`) und gibt die Antwort 1:1 zurück.

```bash
export CF_WORKER_URL="https://sinator-fallback.<account>.workers.dev"
export SINATOR_AUTH_TOKEN="<client-bearer-token>"   # wird gesetzt falls Client keinen schickt
```

Ist `CF_WORKER_URL` leer, ist der Fallback deaktiviert und das Verhalten bleibt unverändert. Setup + die 5 offenen Fragen (Auth, Rate Limiting, Key-Sync, DNS, Mac-Wiederkehr) sind in [`cloudflare/README.md`](../cloudflare/README.md) dokumentiert.

### Bugfix: Server-Start beim Import (v3 — Issue #24)

`ThreadedPoolServer` + `serve_forever()` standen außerhalb des `if __name__ == "__main__"`-Guards → schon der **Import** startete einen Server und band Port 9998. Jetzt in `main()` gekapselt; Import ist nebenwirkungsfrei.

### Proxy charset bug fix

Der Pool-Proxy (`~/.sin-pool/server.py`) crashte bei `Content-Type: application/json; charset=utf-8` von Fireworks mit `ValueError`. Fix: charset-Parameter vor aiohttp-Response-Konstruktion strippen. Betrifft alle 10 Proxy-Instanzen (8888-8897).

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
launchctl unload ~/Library/LaunchAgents/com.sinator.pool-router.plist

# Router starten
launchctl load ~/Library/LaunchAgents/com.sinator.pool-router.plist

# Logs
tail -f ~/.hermes/logs/pool-router.log
```

## Einschränkungen

- **Kein Load-Balancing** — Es gibt keinen Round-Robin. Pool 1 ist bevorzugt solange er geht.
- **Kein Health-Check** — Der Router weiß nicht ob ein Pool "langsam" ist, nur ob er Fehler wirft.
- **Ein Prozess pro Maschine** — Der Router bindet Port 9998. Auf derselben Maschine kann nur einer laufen (launchd managed).

## Alternative: Direkter Pool (kein Router)

Wenn du lieber direkt einen lokalen Proxy ansprechen willst (z.B. weil Router einen Bug hat):

```bash
# Config direkt auf Pool 1
# ~/.hermes/config.yaml editieren:
#   base_url: http://localhost:8888/inference/v1
# Dann Router stoppen (falls läuft):
pkill -f pool-router.py
```

Oder `config/fireworks-pool1.yaml` als Vorlage nutzen.
