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
GMX Login (built-in) → Alias Rotation (~50s) → FW Signup → OTP → Login → Onboarding → API Key → Pool
Latest: cosmic-raven-683 → fw_G93EigYuyQnbeCfNiSCZwy (8 Keys total, ~213s)
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
- GMX Alias-Creation: Direkte Navigation zu `/mail_settings/email_addresses?sid=...` statt `/mail_settings` (Settings-Landingpage hatte "E-Mail-Adressen" nicht im AX-Tree)
- CUA Navigation: Debug-Logging + `8s` sleep nach Navigation für zuverlässigeren AX-Tree
- Playwright Alias Creation: Error-Message-Parsing mit `.count()` + `timeout=5000` statt `text_content()` (30s Timeout)
- Input-Selector fallback Chain: `name="localPart"` → `placeholder="ihr-name"` → `input[type="text"]`
- `Hinzufügen` Button: `force=True` für gecoverte Elemente (Form-Submit in Wicket-Iframe)

---

## 🚧 V8 — Docs & API Reference (IM DURCHLAUF 2026-05-22)

### Fokus: README + API Reference aufpolieren

| Task | Aufwand | Status |
|------|:-------:|:------:|
| README.md neu strukturiert (Quick Start, API Reference, Usage Examples) | 1h | ✅ **DONE** |
| API Endpoints vollständig dokumentiert (health, browser, gmx, fireworks, cookies, pool, rotation) | - | ✅ |
| curl-Beispiele für jeden Endpoint | - | ✅ |
| Chrome/CUA/Pool/Env-Dokumentation konsolidiert | - | ✅ |

### Verbleibend (V8.1)
| Task | Priorität |
|------|:---------:|
| OpenAPI Spec Review + ggf. fehlende Schemas ergänzen | 🟡 Mittel |
| CLI-Wrapper (`sinator-cli`) bauen | 🟢 Niedrig |
| Python SDK bauen | 🟢 Niedrig |

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
