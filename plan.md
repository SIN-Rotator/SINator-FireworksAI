# BUILDING PLAN — SINator Fireworks AI V5 ✅ / V6 🚧 (2026-05-22)

## ✅ V5 Status: COMPLETE FLOW VERIFIED

```
GMX Login → Rotation (19.8s) → Fireworks Signup → OTP → Verify → Login → Onboarding → API Key → Pool
Latest: omega-condor-654 → fw_GEB2TRxTFzcFNweZwMuq5b
```

| Flow | Name | Status | Tool |
|------|------|:---:|------|
| #0 | GMX Session | ✅ | Playwright "E-Mail" click → SID |
| #1 | GMX Alias Delete | ✅ | Playwright iframe hover+click + CUA OK |
| #1 | GMX Alias Create | ✅ | Playwright iframe fill+click, verify empty |
| #2 | Fireworks Signup | ✅ | Playwright + CUA: email→pw→Create→OTP→Verify |
| #3 | Fireworks Login | ✅ | Playwright form `a:has-text("Email Login")` + CUA onboarding |
| #4 | Onboarding | ✅ | CUA: "First"+"Last" type_text + Terms AXPress |
| #5 | Use-Case + $5 | ✅ | CUA dynamic scan text-based checkboxes |
| #6 | API Key | ✅ | PopUpButton force-click + menuitem + Generate |
| #7 | Pool | ✅ | Auto-save (5 keys total, 4 available) |

## ✅ V5 Completed Milestones

| # | Task | Ergebnis |
|---|------|----------|
| 1 | Full-Flow Automation | `rotation.py` V5 — Playwright+CUA hybrid |
| 2 | API-Key Pool | 5 Keys (4 available), auto-save |
| 3 | fireworks_service.py | 3103→114 Zeilen (-96%), V5 Playwright+CUA |
| 4 | Cleanup | Obsolete files gelöscht (preflight.py, command_registry.json, etc.) |
| 5 | Single Command | `python tools/rotate.py` — E2E in einem Befehl |
| 6 | Dynamic CUA Scanning | Text-based `_find_element()` — keine Hardcoded-Indizes |
| 7 | Chrome Config | NON-accessibility mode: `--profile-directory="Profile 901"`, Port 9222 |

---

## 🚧 V6: Stabilisierung & Robustheit

## ✅ PRIORITÄT 1 — Dynamische CUA Window-Erkennung (COMPLETE)

### Was wurde gemacht
Neue `agent_toolbox/core/cua_helper.py` mit shared `find_cua_window()` — ersetzt 4x duplizierte `list_windows` + hardcodierte `pid`/`wid`:

| Datei | Call Site | Vorher | Nachher |
|-------|-----------|--------|---------|
| `fireworks_service.py:160` | `login_fireworks()` onboarding | 10 Zeilen inline list_windows | 1 Zeile `find_cua_window(["fireworks"])` |
| `gmx_service.py:434` | `_navigate_to_all_email_addresses()` | 12 Zeilen inline | 1 Zeile `find_cua_window(["GMX","gmx","freemail"])` |
| `gmx_service.py:760` | `delete_existing_alias()` dialog OK | 13 Zeilen inline | 1 Zeile `find_cua_window(["GMX","E-Mail"])` |
| `gmx_service.py:951` | `_delete_alias_via_playwright()` dialog OK | 12 Zeilen inline | 1 Zeile `find_cua_window(["GMX","Einstell"])` |

### Features
- ✅ Case-insensitive `app_name` + `title` matching
- ✅ `include_minimized_fallback` — on-screen zuerst, dann alle Window-States
- ✅ Kein Crash bei Timeout/JSON-Fehler/fehlendem `cua-driver`
- ✅ In **beiden Repos** deployed (SINator-fireworksai + gmx-alias-tool)

### Helper API
```python
from cua_helper import find_cua_window, cua_click, cua_type_text, cua_get_window_state

result = find_cua_window(title_keywords=["fireworks"])
if result:
    pid, wid = result
    cua_click(pid, wid, element_index=42)
    cua_type_text(pid, text="Hallo")
    tree = cua_get_window_state(pid, wid)
```

---

## ✅ PRIORITÄT 2 — E2E Regressionstests (COMPLETE)

### Was wurde gemacht (2026-05-22)
| File | Tests | Status |
|------|-------|:------:|
| `tests/conftest.py` | Shared fixtures: `browser`, `gmx_page`, `fireworks_page`, `cua_window` | ✅ |
| `tests/test_cua_helper.py` | 7 sync — `find_cua_window` + `get_window_state` | ✅ 7/7 |
| `tests/test_gmx_session.py` | 3 async — E-Mail click → Session → Alias page | ✅ 3/3 |
| `tests/test_e2e_fresh.py` | 6 async — 4 non-destructive + 2 `@destructive` (Fireworks only) | ✅ 16/16 |

### Ergebnis
```bash
rtk test pytest tests/ -v
# 16 passed, 0 failed, 0 skipped in <5min
```

### Learnings
- **GMX CUA-Tests funktionieren nicht in pytest-Chromium** — CUA benötigt macOS AX auf dem echten Chrome-Fenster. Playwrights `Google Chrome for Testing` hat keine sichtbaren AX-Titles.
- GMX Alias-Operationen werden nur via `tools/rotate.py` getestet (echter Chrome, CUA verfügbar).
- Fireworks Form-Tests (Signup/Login) laufen via Playwright ohne CUA → ✅.
- `_logout_fireworks` muss CDP `Network.deleteCookies` domain-scoped nutzen, nicht `ctx.clear_cookies()` (killt GMX-Cookies).

---

## ✅ PRIORITÄT 3 — 3 Fragile Punkte stabilisiert (2026-05-22)

### 3a. GMX Session-Refresh — DONE

| Änderung | File | Beschreibung |
|----------|------|-------------|
| IAC/Antibot-Tabs schließen | `gmx_service.py:204` | Neue `_close_iac_tabs()` — schließt `iac/restart` und `session-expired` Tabs vor Cookie-Injektion |
| Immer zu Homepage navigieren | `gmx_service.py:229-239` | `_ensure_mail_session()` navigiert IMMER zu `www.gmx.net`, nicht conditional |
| 15s Polling statt 5s fixed sleep | `gmx_service.py:291-301` | Pollt URL alle 2s max 8 Versuche (16s) auf SID |
| Direkt zu mail_settings navigieren | `gmx_service.py:464-478` | Wenn SID vorhanden: direkt `bap.navigator.gmx.net/mail_settings?sid=...` statt `www.gmx.net/?sid=...` |
| Cookie-Injektion bei fehlender GMX Page | `gmx_service.py:438-456` | `_navigate_to_all_email_addresses` injiziert Cookies + navigiert wenn keine GMX Page gefunden |
| GMX Login in rotate.py Step 0 | `rotate.py:35-71` | Automatischer Playwright-Login bei frischem Chrome-Start |

### 3b. Use-Case Submit Redirect — DONE

| Änderung | File | Beschreibung |
|----------|------|-------------|
| Polling statt fixed 6s wait | `fireworks_service.py:211-222` | Checkt URL alle 2s max 15s auf Redirect |
| Fallback `page.goto()` | `fireworks_service.py:219-221` | Bei Timeout: force navigate zu API Keys |
| Playwright-Onboarding-Fallback | `fireworks_service.py:248-301` | Neue `_fireworks_playwright_onboarding()` — falls CUA nicht funktioniert, füllt Playwright die Formularfelder |
| Erweiterter URL-Check | `fireworks_service.py:227` | `'home' or 'account' or 'settings'` statt nur `home/account` |

### 3c. API Key Dialog Generate — DONE

| Änderung | File | Beschreibung |
|----------|------|-------------|
| Wait nach fill | `fireworks_service.py:262` | `await asyncio.sleep(1)` vor Generate |
| Wait for enabled | `fireworks_service.py:265-279` | Prüft `disabled` Attribut, wartet bis enabled |
| Poll für Key im DOM | `fireworks_service.py:282-290` | `body.innerText` alle 1s max 10s |
| Error-Handling "Missing Name" | `fireworks_service.py:296-304` | Erkennt Fehler-Modal, schließt es

---

## ✅ PRIORITÄT 4 — gmx-alias-tool API Konsolidierung (DONE)

### Was wurde gemacht (2026-05-22)

| Änderung | Repo | Beschreibung |
|----------|------|-------------|
| `rotation.py` → httpx API + Fallback | SINator | `_gmx_rotate_via_api()` ruft `localhost:8001/alias/rotate`, `_gmx_rotate_fallback()` direkt via GmxService |
| `_fireworks_login` delegiert | SINator | Ruft `fireworks_service.login_fireworks()` statt CUA-hardcoded Indizes |
| `_fireworks_api_key` delegiert | SINator | Ruft `fireworks_service.create_api_key()` (V6 disabled-wait + polling) |
| `cdp_client.py` gelöscht | gmx-alias-tool | 900 Zeilen CDP Legacy entfernt (unused von gmx_service) |
| `server.py` vereinfacht | gmx-alias-tool | `_get_fresh_gmx_tab()` → `_get_svc()`, health via urllib |
| sys.path setup | gmx-alias-tool | SINator-Pfad für `agent_toolbox.core` imports |
| Version | gmx-alias-tool | bumped to 2.0.0 |

### Files geändert
- `agent_toolbox/api/routes/rotation.py` — 57 insertions, 132 deletions
- `server.py` (gmx-alias-tool) — `cdp_client.py` removed + routes vereinfacht

---

## ✅ V7 — Self-Healing & Robustheit (DONE 2026-05-22)

| Prio | Task | Aufwand | Impact | Status |
|:----:|------|:-------:|:------:|:------:|
| 1 | Rate-Limit Circuit Breaker verbessert | 2h | 🔴 Hoch | ✅ **DONE** |
| 2 | OOPIF Polling Fix (statt Timeout-Recovery) | 2h | 🔴 Hoch | ✅ **DONE** |
| 3 | API Key "Missing Name" Auto-Retry | 1h | 🟡 Mittel | ✅ **DONE** |

### Current E2E Status (2026-05-22)
```
GMX Login (5s) → Alias Rotation (55s) → FW Signup (30s+OTP) → Login → Onboarding → API Key → Pool
Latest: cosmic-phoenix-268 → (6 Keys total, ~204s)
```

### V7.1 — Rate-Limit Circuit Breaker (DONE)
- Exponential Backoff: 30s → 60s → 120s → 300s statt fixem 120s
- HTTP Status-Code Parsing via `_check_http_status_codes()` (CDP Network Events)
- Warm-up Phase nach Cooloff: readonly zuerst, dann delete+create
- `_BACKOFF_STAGES = [30, 60, 120, 300]`
- Reset nach 10min ohne Rate-Limit

### V7.2 — OOPIF Polling statt Timeout-Recovery (DONE)
- **Problem gelöst:** `read_fireworks_verification_email()` suchte mailbody-ui.de OOPIF nur 1× nach 5s — bei langsamer GMX-Tab-Ladung wurde es verpasst
- **Fix:** Pollt alle 2s für max 20s (10 Versuche) statt 1× 5s
- **Entscheidung:** 3-Level Recovery (Session-Refresh/CDP-Reconnect) entfernt — OOPIF-Polling adressiert die Root Cause
- OTP-Polling von 30×6s auf 18×6s reduziert (keine Recovery nötig da OOPIF zuverlässiger gefunden wird)

### V7.3 — API Key "Missing Name" Auto-Retry (DONE)
- `_generate_and_poll_key()` mit 3 Retries implementiert
- Retry 0: Normaler Generate-Versuch
- Retry 1-2: Modal Close → Input neu füllen (mit Suffix) → Generate
- Wait von disabled→enabled vor jedem Generate-Klick
- DOM-Polling max 10s für Key-Extraktion

### V7 Extra Fixes
- `login_fireworks()`: 3× Retry-Wrapper für "Email Login" Klick (stale frame / navigation)
- `create_api_key()`: Robusteres Page-Matching (jede fireworks-Seite, nicht nur home/account) + Fallback mit neuer Page
- `signup_fireworks()`: Redirect-Verifikation nach "Create Account" (10s Polling)
- `_generate_and_poll_key()`: Fehlendes `import asyncio` ergänzt
- `rotate.py`: GMX-Login-Detection für bereits eingeloggte Sessions

---

## 🚀 V7.1 — Rate-Limiting Circuit Breaker (EXISTIERT, WIRD ERWEITERT)

### Status: ⏳ Bereits implementiert in V6, aber verbesserungswürdig

### Problem
GMX blockiert bei zu vielen Anfragen mit IAC/restart, `ERR_BLOCKED_BY_RESPONSE`, oder Session-Expired. Aktuell nur Text-basierte Erkennung in URL + Body.

### Bereits implementiert (V6)

| # | Komponente | File | Beschreibung |
|---|-----------|------|-------------|
| 1 | `_is_rate_limited()` | `gmx_service.py:76` | Prüft URL + Body auf IAC/Restart/429/Blocked-Signale |
| 2 | `_track_rate_limit()` | `gmx_service.py:86` | Circuit Breaker: 3 Hits in 5min → 120s Cooloff |
| 3 | `_purge_gmx_cookies()` | `gmx_service.py:104` | Löscht stale Cookies von Disk + Chrome vor Recovery |
| 4 | `_gmx_throttle()` | `gmx_service.py:97` | Proaktive 3s-Verzögerung + Jitter zwischen GMX-Ops |
| 5 | `_rate_limit_safe_call()` | `gmx_service.py:117` | Retry-Wrapper: erkennt Rate-Limit, purgt, retryt (max 2×) |

### Geplante Verbesserungen

#### 1a. HTTP Status-Code Parsing (`gmx_service.py`)
**Aktuell:** Nur Text-Scan von URL + Body (z.B. sucht nach `"429"` im Text).  
**Ziel:** CDP `Network.responseReceived` Events abhören für echte HTTP-Status-Codes:
```python
# Neue Methode: _check_http_status_codes(client, session_id)
# Parst Network.responseReceived Events aus CDP-Log
# Erkennt 429/413/503 direkt aus HTTP-Response-Headern
async def _check_http_status_codes(client, session_id):
    events = await client.send_to_session(session_id, "Network.getResponseBody", ...)
    # Prüfe responses auf 429/413/503/502
    for response in events:
        if response['status'] in (429, 413, 503, 502):
            _track_rate_limit(True)
            return True
    return False
```

#### 1b. Exponentielles Backoff (`gmx_service.py`)
**Aktuell:** Fester 120s Cooloff nach 3 Hits.  
**Ziel:** Dynamisches Backoff: 30s → 60s → 120s → 300s:
```python
# _BACKOFF_STAGES = [30, 60, 120, 300]
# Nach jedem Cooloff-Ablauf ohne Erfolg → nächste Stufe
# Reset nach erfolgreicher Operation (kein Rate-Limit für >10min)
```

#### 1c. Warm-up nach Cooloff (`gmx_service.py`)
**Aktuell:** Nach Cooloff direkt wieder volle Operation (delete+create).  
**Ziel:** Readonly-Operation zuerst (Session-Check), dann erst delete+create:
```python
# Nach Cooloff:
# 1. _ensure_mail_session() — nur readonly
# 2. Wenn OK → _navigate_to_all_email_addresses() — readonly
# 3. Wenn OK → delete + create
# Bei erneutem Rate-Limit in Step 1/2 → erneuter Cooloff + höhere Stufe
```

### Integration
| Funktion | Neu | Beschreibung |
|----------|-----|-------------|
| `rotate_alias()` | HTTP-Status-Check nach jeder Navigation | Zusätzlich zu Text-basiertem Check |
| `_ensure_mail_session()` | Exponential-Backoff-Logik | Statt fixem 120s Cooloff |
| `rotate_alias()` | Warm-up-Phase nach Cooloff | Readonly vor Mutation |

### Files
- `agent_toolbox/core/gmx_service.py` — Erweiterung der Rate-Limit-Logik

---

## 🚀 V7.2 — OTP Timeout Recovery (GEPLANT)

### Status: 📝 Noch nicht implementiert

### Problem
Fireworks Verification-Email kann 2-5 Minuten brauchen. Aktuell nur 12×6s = 72s Polling — zu knapp. Bei Timeout wird `"otp_not_found"` returned, aber:
- GMX Session könnte abgelaufen sein (SID stale)
- MailCheck Extension-Popup könnte geschlossen/stale sein
- CDP-Targets könnten veraltet sein

### Lösung: 3-Ebenen Recovery-System

```python
async def _otp_with_recovery(svc, max_attempts=30):
    """OTP Polling mit 3-Ebenen Recovery. Max 30×6s = 180s."""
    for attempt in range(max_attempts):
        url = await svc.read_fireworks_verification_email()
        if url:
            return url

        # Recovery-Ebenen — alle 6 Versuche (36s)
        if attempt > 0 and attempt % 6 == 0:
            level = attempt // 6  # 1, 2, 3, 4, 5

            # Level 1: GMX Session auffrischen
            if level >= 1:
                logger.warning(f"OTP-Level-1: Session Refresh (attempt {attempt})")
                await svc.ensure_gmx_session(...)
                # Navigate to inbox with fresh SID

            # Level 2: Extension-Popup neu öffnen
            if level >= 2:
                logger.warning(f"OTP-Level-2: Extension neu öffnen (attempt {attempt})")
                # CDP: Target.createTarget für mail-panel.html
                # Falls schon offen: schließen + neu öffnen
                await svc._reopen_mailcheck_extension(...)

            # Level 3: CDP Reconnect
            if level >= 3:
                logger.warning(f"OTP-Level-3: CDP Reconnect (attempt {attempt})")
                # CDP disconnect + reconnect
                # Targets neu scannen
                # Extension neu attachen
                await svc._reconnect_cdp(...)

        await asyncio.sleep(6)

    # Nach 180s: letzter Recovery-Versuch
    return None
```

### Integration
| Funktion | Änderung | Beschreibung |
|----------|----------|-------------|
| `signup_fireworks()` | OTP-Poll von 12×6s → 30×6s mit Recovery-Logik | Ersetzt einfache for-Schleife |
| `gmx_service.py` | Neue `_reopen_mailcheck_extension()` | Schließt + öffnet Extension-Popup via CDP Target |
| `gmx_service.py` | Neue `_reconnect_cdp()` | CDP disconnect/reconnect + Target-Rescan |
| `gmx_service.py` | `_ensure_gmx_session()` | Wiederverwendbar für Level-1 Recovery |

### Files
- `agent_toolbox/core/fireworks_service.py` — OTP-Polling mit Recovery
- `agent_toolbox/core/gmx_service.py` — Neue Helper für Extension/CDP-Recovery

---

## 🚀 V7.3 — API Key "Missing Name" Auto-Retry (GEPLANT)

### Status: 📝 Teilweise implementiert (erkennt Modal, schließt es, gibt aber auf)

### Problem
Aktueller Code (`fireworks_service.py:401-409`):
```python
# Erkennt "Missing Name" Modal, schließt es, gibt dann auf:
if 'Missing' in body and 'Name' in body:
    for btn in await pg.locator('button').all():
        if (await btn.text_content() or '').strip() in ['Close', 'Cancel', 'OK', '×']:
            await btn.click(force=True); await asyncio.sleep(1)
            break
return {"status": "error", ...}  # ← gibt einfach auf!
```

### Lösung: Vollständiger Retry-Zyklus

```python
async def _create_api_key_with_retry(pg, key_name, max_retries=3):
    """Create API Key mit Modal-Erkennung + Auto-Retry."""
    
    for retry in range(max_retries):
        # 1. Generate klicken
        for btn in await pg.locator('button').all():
            if 'Generate' == (await btn.text_content() or '').strip():
                if not await btn.is_disabled():
                    await btn.click(force=True)
                    break

        # 2. Key pollen (10s)
        for _ in range(10):
            await asyncio.sleep(1)
            text = await pg.evaluate("() => document.body.innerText")
            keys = re.findall(r'fw_[a-zA-Z0-9]{20,}', text)
            if keys:
                return {"status": "success", "api_key": keys[0]}

        # 3. "Missing Name" Modal erkennen + schließen
        body = await pg.evaluate("() => document.body.innerText")
        if 'Missing' in body and 'Name' in body:
            logger.warning(f"Missing Name Modal — schließen (retry {retry+1})")
            for btn in await pg.locator('button').all():
                txt = (await btn.text_content() or '').strip()
                if txt in ['Close', 'Cancel', 'OK', '×']:
                    await btn.click(force=True)
                    await asyncio.sleep(1)
                    break

            # 4. Input neu füllen (mit Suffix für Eindeutigkeit)
            suffix = f"-{retry}" if retry > 0 else ""
            for inp in await pg.locator('input').all():
                if 'name' in (await inp.get_attribute('name') or '').lower():
                    await inp.fill(key_name + suffix)
                    await asyncio.sleep(1)
                    break

            # 5. Warten bis Generate enabled ist
            for _ in range(5):
                generate_btn = None
                for btn in await pg.locator('button').all():
                    if 'Generate' == (await btn.text_content() or '').strip():
                        generate_btn = btn
                        break
                if generate_btn and not await generate_btn.is_disabled():
                    break
                await asyncio.sleep(1)
        else:
            # Anderer Fehler — abbrechen
            break

    return {"status": "error", "error": "API Key not found after retry"}
```

### Retry-Strategie
| Retry | Key-Name | Aktion |
|:-----:|----------|--------|
| 0 | `sinator-key` | Normaler Generate-Versuch |
| 1 | `sinator-key-1` | Modal Close → Input neu füllen → Generate |
| 2 | `sinator-key-2` | Nochmal mit anderem Suffix |

### Integration
| Funktion | Änderung |
|----------|----------|
| `create_api_key()` | Ersetzt einfaches Polling durch `_create_api_key_with_retry()` |
| `create_api_key()` | Modal-Handling + Input-Retry inkludiert |

### Files
- `agent_toolbox/core/fireworks_service.py` — `_create_api_key_with_retry()` + `create_api_key()` Refactor

---

## 🚀 Quick Start (V7)

```bash
# Chrome mit Profile 901 (OHNE accessibility!)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &

# CUA Daemon
cua-driver serve &

# Full Rotation (Single Command)
python tools/rotate.py

# API Server
python agent_toolbox/start_toolbox.py
curl -X POST http://localhost:8000/rotation/full \
  -H 'Content-Type: application/json' \
  -d '{"fireworks_password": "ZOE.jerry2024!"}'
```
