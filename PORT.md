# SINator-FireworksAI — Port-Zuordnung (OFFIZIELL)

**Diese Datei ist die Single Source of Truth für alle Ports. Bei Abweichungen im Code: CODE FIXEN, nicht Port ändern.**

---

## 🔴 FESTER ROTATIONS-PORT: 59230

**Der SINator-FireworksAI Rotation Bot Chrome nutzt IMMER Port 59230.**  
Definiert als Konstante `SINATOR_ROTATION_CDP_PORT = 59230` in `tools/rotate.py`.  
**NIEMALS ändern, NIEMALS dynamisch suchen, NIEMALS `--cdp-port` überschreiben.**

---

## 🔴 EIN Chrome: Bot-Chrome auf Port 59230

| Chrome-Typ | Port | Zweck | Wer startet |
|------------|------|-------|-------------|
| **Bot-Chrome (Rotation)** | **59230** | ALLES: GMX Login, Alias, Fireworks Signup, OTP lesen, API Key | Playwright `chromium.launch()` |

**Kein User-Chrome für OTP nötig!**  
OTP wird **Playwright-native** gelesen (Shadow-DOM + Multi-Frame Scan im Bot-Chrome).
MailCheck Extension / CDP / User-Chrome = **VERALTET, ENTFERNT**.

---

## Überblick

| Port | Service | Prozess | Start-Methode | Wichtig |
|------|---------|---------|---------------|---------|
| **8100** | Backend API (Pool, Keys, Rotation) | FastAPI/Uvicorn | `python3 agent_toolbox/start_toolbox.py` | **Backend-Hauptport** |
| **9998** | Pool-Router (Failover über 10 Proxys) | Python ThreadingMixIn | `bash proxy/start-multi.sh` | **Client-Entry-Point** |
| **8888-8897** | 10 Pool-Proxys (aiohttp SSE) | Python | `proxy/start-multi.sh` | Router verteilt hier drauf |
| **9222** | **User-Chrome CDP** (nur OTP lesen!) | Chrome mit `--remote-debugging-port=9222` | User startet manuell / Dashboard | **NUR für OTP via CDP** |
| **59230** | **Bot-Chrome CDP** (Playwright `chromium.launch()`) | **FEST: 59230** (Hardcoded in rotate.py) | Playwright startet selbst | **Rotation läuft HIER - NIEMALS ÄNDERN** |

---

## Flow & Port-Logik (KORREKT — Stand V19.23+)

```
Rotation (tools/rotate.py)
    │
    ├─ Playwright: chromium.launch(headless=False, args=['--remote-debugging-port=59230'])
    │   └─ FIXED CDP Port 59230 → DIESEN Port an ALLE Services weitergeben!
    │
    ├─ GMX Alias Rotation (Playwright auf 59230)
    │   └─ _navigate_to_all_email_addresses() nutzt page (Playwright)
    │
    ├─ Fireworks Signup (fireworks_service.signup_fireworks)
    │   └─ MUSS cdp_port=59230 nutzen (connect_over_cdp)
    │
    ├─ OTP lesen (gmx.read_otp_via_playwright) 
    │   └─ PLAYWRIGHT-NATIVE: Shadow-DOM + Multi-Frame Scan
    │       • KEIN CDP, KEINE MailCheck Extension, KEIN User-Chrome!
    │       • Nutzt Bot-Chrome (59230) — der ist bereits bei GMX eingeloggt!
    │       • Scannt ALLE Frames (OOPIF: bap.navigator.gmx.net) nach list-mail-item
    │
    └─ Fireworks Login + API Key (fireworks_service.login_fireworks/create_api_key)
        └─ MUSS cdp_port=59230 nutzen (connect_over_cdp)
```

---

## Häufige Fehler & Fixes

| Fehler | Ursache | Fix |
|--------|---------|-----|
| `Connection refused` in Fireworks | `cdp_port` default war 9222, Bot läuft auf 59230 | Im Code: `cdp_port=59230` an ALLE Services übergeben |
| `read_otp` findet keine Mails | Alte CDP-Methode (MailCheck) statt Playwright | `read_otp_via_playwright(browser, existing_page=page)` nutzen |
| Rotate.py läuft ewig | `signup_fireworks` wartet auf OTP, alter Code | Playwright-native OTP implementiert |

---

## Rotation aufrufen (KORREKT — V19.23+)

```bash
# NUR Rotation starten (Playwright-Chrome auf FESTEM PORT 59230)
cd /Users/jeremy/dev/SIN-Rotator-SINator-FireworksAI
python3 tools/rotate.py \
  --gmx-email delqhi@gmx.de \
  --gmx-password ZOE.jerry2024 \
  --password ZOE.jerry2024!

# Im Code: rotate.py nutzt FESTEN cdp_port=59230 (SINATOR_ROTATION_CDP_PORT)
#          fireworks_service.* bekommen cdp_port=59230 übergeben
#          read_otp_via_playwright(browser, existing_page=page) — KEIN CDP!
```

---

## Config-Datei

```json
// data/config.json
{
  "gmx_email": "delqhi@gmx.de",
  "gmx_password": "ZOE.jerry2024",
  "fireworks_password": "ZOE.jerry2024!"
}
```

Wird von `config_manager.py` geladen und an rotate.py übergeben.

---

## WICHTIG für Devs

**NIE `pkill -9 -f "Google Chrome"` nutzen!**  
→ Killt ALLE Chrome-Instanzen.  
Rotation nutzt **eigenen Playwright-Chrome** (temp Profile, Port 59230). User-Chrome bleibt unberührt.

**Code-Änderung bei Port-Problemen:**
- `rotate.py`: `cdp_port = SINATOR_ROTATION_CDP_PORT (59230)` — **FEST, nicht dynamisch!** An ALLE Service-Calls übergeben
- `fireworks_service.py`: Default `cdp_port: Optional[int] = None` → aber `connect_over_cdp` NUR wenn gesetzt (immer 59230)
- `gmx_service.py`: `read_otp_via_playwright(browser, existing_page=page)` — **Playwright-native, KEIN CDP!**

---

*Stand: 2026-06-10 | Erstellt nach mehrfachen Port-Confusion-Vorfällen*