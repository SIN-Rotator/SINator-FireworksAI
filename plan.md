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

## 🔴 PRIORITÄT 1 — Dynamische CUA Window-Erkennung (CURRENT TASK)

### Problem
`fireworks_service.py` hardcodiert `pid`/`wid` für CUA `click`/`type_text` in `login_fireworks()`:
```python
for w in json.loads(res.stdout).get('windows', []):
    if 'Google Chrome' == w.get('app_name', '') and ...
        pid, wid = w['pid'], w['window_id']
```
Nach Chrome-Neustart ändern sich beide → CUA findet kein Fenster → onboarding fails.

### Fix-Plan
- [ ] `_cua_find_window()` helper: durch alle `list_windows` iterieren, case-insensitive `app_name == 'Google Chrome'` + `title.lower()` contains `'fireworks'`
- [ ] `_cua_find_window()` auch für `gmx_service.py` GMX-Navigation (title `'gmx'` + `'freemail'` oder `'mail'`)
- [ ] Fallback: wenn kein Fenster → `list_windows(include_minimized=True)` + ersten Treffer nehmen
- [ ] Unit-Test: simulierte `list_windows` Outputs parsen

### Files
- `agent_toolbox/core/fireworks_service.py` — `login_fireworks()`: PID/WID dynamic
- `agent_toolbox/core/gmx_service.py` — `_delete_alias_via_playwright()`: CUA OK dialog PID/WID

### Verification
```bash
python tools/rotate.py --dry-run  # CUA scan + match ohne tatsächlichen Klick
```

---

## 🔴 PRIORITÄT 2 — E2E Regressionstest mit frischem Chrome

### Problem
Alle Tests mit bestehender Chrome-Session durchgeführt. Kein Test mit:
- Chrome Neustart (keine Pages)
- Abgelaufene GMX Session
- Fireworks schon eingeloggt (anderer Alias)

### Fix-Plan
- [ ] `tests/test_e2e_fresh.py`: Chrome beenden → neu starten → `rotate.py` ausführen
- [ ] `tests/test_e2e_session_expired.py`: GMX Cookies löschen (nur gmx domain) → session recovery testen
- [ ] `tests/test_e2e_already_logged_in.py`: Fireworks Login mit existierendem Account
- [ ] Automatisierter Test-Runner: `python -m pytest tests/ -v`

### Files
- `tests/test_e2e_fresh.py` (NEU)
- `tests/test_e2e_session_expired.py` (NEU)
- `tests/test_e2e_already_logged_in.py` (NEU)
- `conftest.py` (NEU) — pytest fixtures für Chrome/CUA

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

## 📊 V6 Prioritäten-Matrix

| Prio | Task | Aufwand | Impact | Risk |
|:----:|------|:-------:|:------:|:----:|
| 1 | Dynamische CUA Window-Erkennung | 1h | 🔴 Hoch | Niedrig |
| 2 | E2E Regressionstests | 2h | 🟡 Mittel | Mittel |
| 3 | 3 Fragile Punkte stabilisieren | 3h | 🔴 Hoch | Mittel |
| 4 | gmx-alias-tool API Konsolidierung | 1h | 🟢 Niedrig | Niedrig |

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
