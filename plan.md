# BUILDING PLAN — SINator Fireworks AI V5 ✅ / V6 🚧 (2026-05-22)

## ✅ V5 Status: COMPLETE FLOW VERIFIED

```
GMX Rotation (19.8s) → Fireworks Signup → OTP → Login → Onboarding → API Key → Pool
Latest: crystal-beetle-676 → fw_MdM6tGucgWuuc7zQyJGeTK
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
| #7 | Pool | ✅ | Auto-save (4 keys total, 3 available) |

## ✅ V5 Completed Milestones

| # | Task | Ergebnis |
|---|------|----------|
| 1 | Full-Flow Automation | `rotation.py` V5 — Playwright+CUA hybrid |
| 2 | API-Key Pool | 4 Keys (3 available), auto-save |
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

## 🔴 PRIORITÄT 3 — 3 Fragile Punkte stabilisieren

### 3a. GMX Session-Refresh

| Problem | Aktuell | Fix |
|---------|---------|-----|
| E-Mail click erwartet `www.gmx.net` | Navigiert zu aktueller Page | `page.goto("https://www.gmx.net")` forced vor click |
| SID nicht in URL | `'sid=' in _pg.url` prüft nur Substring | Regex `sid=([a-f0-9]+)` + logging |
| IAC Tab offen | Nur `page.close()` auf `iac` URLs | Auch `iac/restart` und `session-expired` schließen |

- [ ] Robust Session-Check + Recovery in `gmx_service.py`
- [ ] Timeout: 15s max für E-Mail click (nicht 5s)

### 3b. Use-Case Submit Redirect

| Problem | Aktuell | Fix |
|---------|---------|-----|
| Submit leitet zu `/account/home` statt `/settings` | Erwartet direkt API Keys | Navigate forced: `page.goto("/settings/users/api-keys")` nach Submit |
| Credits Banner manchmal langsamer | 6s wait | Polling: warte auf API Keys Button (max 30s) |

- [ ] Submit → polling auf API Key URL (statt fixed wait)
- [ ] Fallback: `page.goto("/settings/users/api-keys")` nach 10s

### 3c. API Key Dialog Generate

| Problem | Aktuell | Fix |
|---------|---------|-----|
| Generate Button disabled (Name fehlt) | `inp.fill(key_name)` + sofort Generate | Wait 1s nach fill, prüfe Button `disabled` Attribut |
| Modal schließt zu früh | `force=True` klickt trotzdem | Wait for `aria-busy="false"` |
| Key nicht im DOM bei schnellem Content-Read | `page.content()` nach 5s | Poll `body.innerText` alle 1s für 10s max |

- [ ] Wait for disabled → enabled transition
- [ ] Poll for API Key in DOM (nicht fixed 5s)
- [ ] Error handling: "Missing API Key Name!" Modal → close + retry

---

## 🔴 PRIORITÄT 4 — gmx-alias-tool API Konsolidierung

### Problem
`agent_toolbox/api/routes/rotation.py` ruft `GmxService.rotate_alias()` direkt auf (localhost). `gmx-alias-tool` (Port 8001) hat den gleichen Code. Dublette.

### Fix-Plan
- [ ] `rotation.py` → httpx-Aufruf an `http://localhost:8001/alias/rotate` statt direktem Service-Call
- [ ] `gmx-alias-tool` update: Playwright+CUA Code vollständig übernommen (teilweise noch CDP legacy)
- [ ] Fallback: wenn API offline → direkt `GmxService` nutzen

### Files
- `agent_toolbox/api/routes/rotation.py` — HTTP statt direkt
- `/Users/jeremy/dev/gmx-alias-tool/app.py` — Legacy CDP Code entfernen

---

## 🎯 V6 Nächste Tasks

| Prio | Task | Aufwand | Impact | Status |
|:----:|------|:-------:|:------:|:------:|
| 1 | Dynamische CUA Window-Erkennung | 1h | 🔴 Hoch | ✅ **DONE** |
| 2 | E2E Regressionstests | 2h | 🟡 Mittel | ✅ **16 Tests, alle pass** |
| 2b | GMX CUA-Tests in pytest | — | ❌ | ❌ **Nicht testbar** (CUA braucht echten Chrome) |
| 3 | 3 Fragile Punkte stabilisieren | 3h | 🔴 Hoch | ⏳ |
| 4 | gmx-alias-tool API Konsolidierung | 1h | 🟢 Niedrig | ⏳ |

---

## 🚀 Quick Start (V5)

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
