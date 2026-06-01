# Troubleshooting

## Proxys laufen mit veralteter Version (Issue #26)

**Symptom:** Repo-Fixes (normalizeBody, FALLBACK_MODELS, etc.) werden nicht aktiv.

```bash
# Pruefen welche Version laeuft:
ps aux | grep -E "sin-pool|pool-router" | grep -v grep
# FALSCH: .../Python /Users/jeremy/.sin-pool/server.py
# RICHTIG: .../Python /Users/jeremy/dev/SINator-fireworksai/proxy/server.py

# Installierte Version pruefen:
cat ~/.sin-pool/.version
```

**Ursache:** LaunchAgents mit `KeepAlive: true` starten von `~/.sin-pool/` (nicht vom Repo).

**Loesung:**
```bash
# Option 1: Development (laeuft direkt aus Repo)
./proxy/start-multi.sh

# Option 2: Production (synct installierte Version)
./proxy/update-installed.sh
launchctl load ~/Library/LaunchAgents/com.sin.pool-proxy.plist
```

## Installer-Fehler

### "Patch may already be applied"

**Normal** — 412-Patch oder UA-Spoof waren schon drauf. Ignorieren.

### `sed` fehlschlägt (kein GNU sed auf macOS)

macOS hat BSD-sed. Unsere Installer nutzen `sed -i ''` — das funktioniert auf macOS. Auf Linux wäre es `sed -i` ohne `''`.

Falls `sed` trotzdem fehlschlägt:

```bash
# Manuell mit Python
python3 -c "
import re
with open('$HOME/.hermes/hermes-agent/run_agent.py', 'r') as f:
    content = f.read()
if 'import _ua_patch' not in content:
    content = content.replace('import os\n', 'import os\nimport _ua_patch  # noqa\n')
    with open('$HOME/.hermes/hermes-agent/run_agent.py', 'w') as f:
        f.write(content)
    print('Patched')
else:
    print('Already patched')
"
```

### `git apply` fehlschlägt (412 Patch)

```bash
# Prüfen ob Patch schon drauf
grep -n "status_code == 412" ~/.hermes/hermes-agent/agent/error_classifier.py

# Zeile 789 sollte zeigen:
# if status_code == 412:
#     if "suspended" in error_msg:
```

Wenn nicht: Patch manuell anwenden siehe `docs/412-retry-fix.md`.

### `curl` 404 auf GitHub

Raw-URLs brauchen das `main` Branch-Suffix korrekt:

```
https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install.sh
                                                                     ^^^^^^
```

Nicht `master`, nicht `HEAD`. Unsere Repos nutzen `main`.

## Post-Install Checks

```bash
# 1. Config da?
ls ~/.hermes/config.yaml

# 2. Pool-URL korrekt?
grep base_url ~/.hermes/config.yaml

# 3. 412 Patch da?
grep "status_code == 412" ~/.hermes/hermes-agent/agent/error_classifier.py

# 4. UA-Spoof da?
ls ~/.hermes/hermes-agent/_ua_patch.py
grep "import _ua_patch" ~/.hermes/hermes-agent/run_agent.py

# 6. Router Service?
launchctl list | grep com.sinator.pool-router
pgrep -f pool-router.py

# 7. Proxy charset? (optional, nur bei charset-Fehlern)
# Symptom: "ValueError: Content-Type contains parameter charset=utf-8"
# Fix: ~/.sin-pool/server.py strippt charset vor aiohttp-Response
# Status: Alle 10 Proxies (8888-8897) haben den Fix
```

Alle 7 Checks müssen grün sein.

## Cloudflare-Fallback greift nicht (Issue #24)

**Symptom:** Mac ist offline, aber Requests laufen weiter in „All pools exhausted" / 503 statt zum Worker zu gehen.

```bash
# 1. Ist CF_WORKER_URL im Router-Prozess gesetzt?
ps eww $(pgrep -f pool-router.py) | tr ' ' '\n' | grep CF_WORKER_URL

# 2. Worker erreichbar?
curl -s "$CF_WORKER_URL/health"          # erwartet: {"status":"ok",...}

# 3. Client-Auth ok? (401 = Token fehlt/falsch)
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $SINATOR_AUTH_TOKEN" \
  "$CF_WORKER_URL/v1/models"

# 4. Pool in D1 vorhanden? (leerer Pool = Worker hat keine Keys)
curl -s -H "Authorization: Bearer $SINATOR_AUTH_TOKEN" "$CF_WORKER_URL/pool/stats"
```

- **Fallback ist nur Notnagel:** er greift erst, wenn *alle* lokalen Pools tot/in Cooldown sind. Solange ein lokaler Pool lebt, geht nichts zum Worker — das ist gewollt.
- **Worker liefert 502 / leere Antwort:** D1 ist leer oder alle Keys `suspended`. Erst syncen: `CF_WORKER_URL=... CF_SYNC_TOKEN=... python3 scripts/sync_to_cf.py`.
- **`/pool/push` gibt 401:** `CF_SYNC_TOKEN` (lokal) ≠ `SYNC_TOKEN` (im Worker als Secret gesetzt).
- **Mac kommt zurück:** nichts zu tun — sobald ein lokaler Pool wieder lebt, übernimmt der Router automatisch wieder; nächster `sync_to_cf.py`-Lauf bringt D1 auf Stand.

## Auth-Fehler

```bash
# Provider registriert?
hermes auth list

# Key gesetzt?
echo $FIREWORKS_AI_API_KEY

# Registrieren (einmalig)
hermes auth add custom:fireworks --type api-key --api-key "$FIREWORKS_AI_API_KEY"
```

## GMX OTP / Verify-Email wird nicht gefunden

**Symptom:** Signup bei Fireworks klappt, aber `read_otp_via_playwright()` findet die
Verify-Mail nicht; Rotation endet in `partial`.

### 1. Methoden in der Klasse? (häufigste Ursache)
Alle OTP-/Tab-Methoden MÜSSEN Teil von `GmxService` sein (4-Space-Indent). War in V15.5 gebrochen.

```bash
python3 -c "
import ast
t=ast.parse(open('agent_toolbox/core/gmx_service.py').read())
cls=[n for n in t.body if isinstance(n,ast.ClassDef) and n.name=='GmxService'][0]
m=[n.name for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
for x in ['initialize_architecture','navigate_inbox','read_otp_via_playwright','read_otp_axtree_and_frames']:
    print(('OK  ' if x in m else 'FEHLT ')+x)
"
```
Alle vier müssen `OK` sein. Wenn `FEHLT`: Methode ist auf Modul-Ebene gerutscht → wieder einrücken.

### 2. Mail in einem iframe/OOPIF?
GMX liefert die Mail teilweise unter `bap.navigator.gmx.net` in einem Sub-Frame.
`read_otp_via_playwright` scannt seit V15.5 **alle** `page.frames` — nicht nur den Hauptframe.

```bash
# Frame-Scan-Logik prüfen
grep -n "page.frames" agent_toolbox/core/gmx_service.py
```

### 3. Falscher Code extrahiert (False-Positive)?
Das alte `[A-Z0-9]{6}`-Pattern matchte zufällige IDs. Seit V15.5 wird zuerst die
Fireworks **Confirm-URL** bevorzugt und ein 6-stelliger Code nur mit Verifizierungs-Kontext
(`code`/`verify`/`confirm`) akzeptiert, rein numerisch (`\d{6}`).

### 4. Inbox-Tab navigiert weg?
Der dedizierte Inbox-Tab (`navigate_inbox()`) muss IMMER im Posteingang bleiben.
Alias-Operationen laufen im separaten `work_tab` (`initialize_architecture()`).
