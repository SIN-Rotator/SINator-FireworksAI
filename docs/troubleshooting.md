# Troubleshooting

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
