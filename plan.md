# PLAN.md — V14→V15.4 Code-Migration (SINator-fireworksai)

**CEO: Jeremy | Datum: 2026-05-31 | Status: INIT**

---

## ZIEL

Docs sind V15.4, Code ist V14. Migration: `connect_over_cdp` → `chromium.launch()`, gelöschte Module wirklich löschen, `Profile 901` → `Profile 73`, `SIN-Hermes-Bundles` → `SIN-Rotator`.

## PRINZIPIEN

- **Jede Phase = 1 Commit** — bei Erfolg sofort `git commit && git push`
- **Nach JEDEM Schritt testen** — kein Blindflug
- **Keine Batch-Löschungen** — jede Datei einzeln prüfen
- **Test-Strategie:** `python -c "import agent_toolbox.start_toolbox"` als Smoke-Test, dann spezifische Tests

---

## PHASE 1: Safe Deletions (leaf dependencies)

### 1.1 DELETE `cookie_manager.py` + `routes/cookies.py`
- **Dependency:** cookie_manager ← routes/cookies.py (ONLY CALLER)
- **routes/cookies.py** ← start_toolbox.py (ONLY CALLER)
- **Aktion:** Lösche beide Dateien. Entferne `cookies_router` import + registration aus start_toolbox.py
- **Test:** `python -c "from agent_toolbox.start_toolbox import app; print('OK')"`
- ~~~bash
  git rm agent_toolbox/core/cookie_manager.py agent_toolbox/api/routes/cookies.py
  ~~~

### 1.2 DELETE `routes/browser.py`
- **Dependency:** routes/browser.py ← start_toolbox.py (ONLY CALLER)
- **browser_manager.py bleibt VORERST** (wird von routes/gmx.py + routes/fireworks.py importiert)
- **Aktion:** Nur routes/browser.py löschen. browser_router aus start_toolbox.py entfernen.
- **Test:** `python -c "from agent_toolbox.start_toolbox import app; print('OK')"`
- ~~~bash
  git rm agent_toolbox/api/routes/browser.py
  ~~~

---

## PHASE 2: browser_manager Refactor (HARD — careful)

### 2.1 Check caller usage in routes/gmx.py und routes/fireworks.py
- Was genau brauchen die routes von `browser_manager`? Nur `cdp_port`?
- **Aktion:** Ersetze `browser_manager`-Import durch direkten 9222-Constant
- **Test:** `python -c "from agent_toolbox.api.routes.gmx import router; print('GMX OK')"` + `python -c "from agent_toolbox.api.routes.fireworks import router; print('FW OK')"`

### 2.2 DELETE `browser_manager.py`
- **Aktion:** Nach routes/gmx.py + routes/fireworks.py entkoppelt → browser_manager.py löschen
- **start_toolbox.py** /health endpoint: `browser_mgr.is_running` → immer True (Playwright läuft)
- **start_toolbox.py** lifespan: `browser_mgr.stop()` → no-op (chromium.launch() braucht kein cleanup)
- **Test:** `python -c "from agent_toolbox.start_toolbox import app; print('OK')"`

---

## PHASE 3: connect_over_cdp → chromium.launch()

### 3.1 fireworks_service.py (4 calls: L34, L140, L504, L624)
- **Aktion:** `connect_over_cdp("http://127.0.0.1:9222")` → `chromium.launch(headless=False)` + dynamischen Port via `_find_free_port()`
- **Test:** Skript das `signup_fireworks()` aufruft (non-destructive read-only mode)

### 3.2 gmx_service.py (L71: parameterized)
- **Aktion:** `_pw_connect(cdp_port)` → `_pw_launch()` (kein cdp_port mehr nötig)
- **Test:** `python tools/rotate.py --dry-run` (falls existiert) oder Unit-Test

### 3.3 billing_tracker.py (L94)
- **Aktion:** `connect_over_cdp("http://127.0.0.1:9222")` → `chromium.launch(headless=False)`
- **Test:** Import-Test

---

## PHASE 4: cdp_port entfernen aus gmx_service API

### 4.1 `_pw_connect()` → `_pw_launch()`
- Kein cdp_port Parameter mehr. Intern `chromium.launch()`

### 4.2 Alle public-Methoden: `cdp_port` → entfernen
- `create_alias(page=..., playwright=..., browser=...)` — page reicht
- `rotate_alias(page=..., playwright=..., browser=...)` — page reicht
- `read_otp(page=..., playwright=...)` — page reicht
- `check_session(page=...)` — page reicht
- **Test:** `python tools/rotate.py` (echte Rotation)

---

## PHASE 5: Schemas & Profile-Fixes

### 5.1 schemas.py: cdp_port + profile_name entfernen
- **Aktion:** `BrowserConfigRequest.cdp_port` + `BrowserConfigRequest.profile_name` raus
- **GMXSessionRequest.cdp_port** raus
- **Test:** Schema-Import

### 5.2 Profile 901 → Profile 73 in browser_manager.py
- Falls browser_manager noch existiert, Konstante ändern
- Falls gelöscht: Kommentare in billing_tracker.py, __init__.py fixen

---

## PHASE 6: SIN-Hermes-Bundles References

### 6.1 install.sh URL fixen
### 6.2 docs/router.md, docs/ua-spoof.md, docs/troubleshooting.md fixen  
### 6.3 skills/sin-hermes-provider-setup/SKILL.md fixen
- **Test:** grep `SIN-Hermes-Bundles` → sollte 0 hits

---

## PHASE 7: Git Cleanup

### 7.1 data/fireworksai-pool.json aus Tracking entfernen
### 7.2 __pycache__ aus Tracking entfernen
### 7.3 debug/, deprecated/, plans/ aufräumen
- **Test:** `git ls-files | wc -l` → target ~80 files (aktuell ?)

---

## PHASE 8: Docs & Final Cleanup

### 8.1 sinrules.md → auf V15.4 updaten oder als "HISTORICAL" markieren
### 8.2 plan.md → auf HISTORICAL flaggen
### 8.3 CONFIGURATION.md → Chrome-Lines updaten (chromium.launch())
### 8.4 AGENTS.md Header: V14 → V15.4
### 8.5 README.md Footer updaten

---

## RISK-MAP

| Phase | Risk | Was bricht? |
|-------|------|-------------|
| 1 | 🟢 LOW | Nichts — cookie/browser routes ungenutzt |
| 2 | 🟡 MEDIUM | API routes verlieren browser_manager → ersetzen mit Konstante |
| 3 | 🔴 HIGH | production services (fireworks_service, gmx_service) |
| 4 | 🔴 HIGH | gmx_service API-Änderung — rotate.py muss funktionieren |
| 5 | 🟢 LOW | Schemas + Konstanten |
| 6 | 🟢 LOW | Nur Docs |
| 7 | 🟢 LOW | Git Tracking |
| 8 | 🟢 LOW | Nur Docs |

---

*Start: sofort. Jede Phase → Test → Commit → Push.*
