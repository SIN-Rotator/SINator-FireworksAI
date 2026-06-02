# SINator Fireworks AI — Installation

*GMX Alias Rotation → Fireworks AI Account → API Key Pool. Prozedurale Schritt-für-Schritt-Anleitung.*

---

## 1. Voraussetzungen

### 1.1 Python 3.11+

```bash
python3 --version
# ✅ "Python 3.11.x" oder höher
# ❌ "command not found" → `brew install python3`
```

### 1.2 Google Chrome

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --version
# ✅ "Google Chrome xxx"
# ❌ → Chrome installieren
```

### 1.3 Chrome Profil (Profile 73 — simoneschulze)

```bash
ls "/Users/simoneschulze/Library/Application Support/Google Chrome/Profile 73"
# ✅ Verzeichnis existiert
# ❌ → Chrome mit Profile 73 einrichten, einmal manuell bei GMX einloggen
```

---

## 2. Repository klonen

```bash
cd ~/dev
git clone git@github.com:SIN-Rotator/SINator-FireworksAI.git
cd SINator-fireworksai

# ✅ Du bist jetzt im Ordner ~/dev/SINator-fireworksai
```

---

## 3. Dependencies installieren

```bash
pip3 install fastapi uvicorn pydantic httpx websockets playwright aiohttp
# ✅ Keine Fehlermeldung
# ❌ "externally-managed-environment" → venv verwenden:
#    python3 -m venv .venv && source .venv/bin/activate && pip install ...
```

```bash
python3 -m playwright install chromium
# ✅ "Chromium downloaded to ..."
```

---

## 4. Chrome starten (mit CDP)

```bash
pkill -9 -f "Google Chrome" 2>/dev/null; sleep 2

nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/simoneschulze/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 73" \
  --remote-debugging-port=9222 \
  --no-first-run \
  --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &

sleep 5
curl -s http://127.0.0.1:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'✅ Chrome {d[\"Browser\"]}')"
# ✅ "Chrome xxx"
# ❌ "Connection refused" → Chrome nicht gestartet
```

---

## 5. Backend starten (`:8100`)

```bash
python3 agent_toolbox/start_toolbox.py
# → Uvicorn auf http://0.0.0.0:8100
```

**In einem zweiten Terminal — Verifikation:**

```bash
curl http://localhost:8100/health
# ✅ {"server":"ok","pool":{"total":218,...}}
# ❌ "Connection refused" → Backend läuft nicht
```

---

## 6. E2E Rotation testen

```bash
python3 tools/rotate.py
# ✅ "✅ Rotation complete — API key added to pool"
# ❌ "GMX session dead" → Chrome CDP prüfen (Schritt 4)
# ❌ "CAPTCHA" → Session inkorrekt
```

```bash
# Pool-Status prüfen:
curl http://localhost:8100/api/v1/pool/stats
# ✅ {"status":"success","total":219,"available":95,...}
```

---

## 7. (Optional) Über SINator-Dashboard starten

```bash
cd ~/dev/SINator-dashboard
./start.sh
# → Startet Fireworks (:8100) + HeyPiggy (:8002) + Dashboard (:3000)
```

---

## 8. Pool-Proxy starten

```bash
# Nur wenn du eine lokale Proxy-Instanz brauchst (z.B. für Pool-Router):
cd ~/dev/SIN-Rotator-SINator-FireworksAI
python3 proxy/server.py --port 8888
# → http://localhost:8888/inference/v1

# Alle 10 Proxys + Router starten:
bash proxy/start-multi.sh
# → Pool-Router auf :9998, Proxys auf :8888-:8897
```

---

## 9. Verifikation — alles läuft?

```bash
python3 -c "
import urllib.request, json

ok, fail = [], []

try:
    r = urllib.request.urlopen('http://localhost:8100/health', timeout=5)
    data = json.loads(r.read())
    ok.append(f'Backend :8100 — {data.get(\"status\") or data.get(\"server\",\"?\")}')
except Exception as e:
    fail.append(f'Backend :8100 — {e}')

try:
    r = urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=5)
    ok.append('Chrome CDP :9222 — ok')
except Exception as e:
    fail.append(f'Chrome CDP :9222 — {e}')

try:
    r = urllib.request.urlopen('http://localhost:8100/api/v1/pool/stats', timeout=5)
    data = json.loads(r.read())
    ok.append(f'Pool — {data.get(\"available\", \"?\")} Keys verfügbar')
except Exception as e:
    fail.append(f'Pool — {e}')

print('✅ Alles OK' if not fail else '❌ Fehler:')
for m in ok: print(f'  ✅ {m}')
for m in fail: print(f'  ❌ {m}')
"

# ✅ Alles OK
#   ✅ Backend :8100 — ok
#   ✅ Chrome CDP :9222 — ok
#   ✅ Pool — 94 Keys verfügbar
```

---

## 10. Fehlerbehebung

| Problem | Ursache | Lösung |
|---------|---------|--------|
| `Connection refused` auf `:8100` | Backend läuft nicht | `tail -20 /tmp/sinator-backend.log` |
| `Connection refused` auf `:9222` | Chrome ohne CDP | Schritt 4 wiederholen |
| GMX Session tot | Cookie abgelaufen | Session Recovery Protocol ausführen (siehe AGENTS.md) |
| `409 Conflict` bei Alias | Alias existiert | `rotate.py` löscht vorher — automatisch |
| Account Suspended | Spending Limit erreicht | Key als `used` markieren via `POST /pool/report` |
| OTP kommt nicht | Email-Verzögerung | `signup_fireworks()` pollt 25×8s = 200s |
| Unverified Account | Verify-URL nicht geöffnet | `verify_account()` in login flow integriert |
| `playwright install chromium` fehlt | Deps nicht vollständig | Schritt 3 wiederholen |

---

*Stand: 2026-06-02 | FastAPI | Playwright-native | Chrome Profile 73 (simoneschulze)*
