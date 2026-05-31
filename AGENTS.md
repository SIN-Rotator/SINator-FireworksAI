# AGENTS.md — SINator Fireworks AI Rotator V15.4 (2026-05-31)

## ✅ COMPLETE E2E FLOW — VERIFIED 2026-05-29

```bash
python tools/rotate.py
# → GMX Login (Step 0) → Alias Rotation (~37s) → Fireworks Signup
# → OTP (25×8s poll) → Verify → Login → Onboarding → API Key → Pool
```

**Pool:** 235 Keys (235 verfügbar, 0 used, 0 suspended)
**Cycle Time:** ~37s GMX + ~60s Fireworks signup + ~30s API Key = ~130s total
**Pool-Router:** `sinatorpool-router.delqhi.com` (:9998, single endpoint, auto-failover)
**Pool Proxies:** 10 Instanzen (:8888-:8897) hinter Pool-Router
**API Key (alle Macs gleich):** `<DEIN_API_KEY>`
**Services:** com.sinator.backend (:8000), com.sinator.pool-router (:9998), 10× pool-proxy (:8888-:8897), Pages (:8040)
**Config Repos:**
  • **OpenCode →** [SIN-Code-FireworksAI-OpenCode-Config](https://github.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config)
  • **Hermes  →** [SIN-Hermes-Provider-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle)

---

## 🔧 V14 CHANGES (2026-05-29) — Playwright-native Migration

### fireworks_service.py — V6 Restored (Playwright+CUA Hybrid)
**Vorher:** 3103 Zeilen CDP-only (V5), dann 216 Zeilen CDP-only (V7), dann broken
**Jetzt:** 655 Zeilen — bewährter V6 Code (Playwright + CUA Hybrid)

**Funktionen:**
- `signup_fireworks(email, password)` — Signup + OTP + Verify
- `login_fireworks(email, password)` — Login + Onboarding (CUA + Playwright Fallback)
- `create_api_key(key_name)` — API Key erstellen via Playwright
- `verify_account(verify_url)` — Verify URL öffnen
- `_fireworks_playwright_onboarding(page)` — Playwright-Onboarding-Fallback
- `_generate_and_poll_key(pg, key_name)` — Generate-Button + Key-Polling

**OTP Polling:** 25 Versuche × 8s = 200s max. Fallback: `partial` status wenn OTP nicht kommt (Account ist unverified aber oft loginbar).

### rotate.py — V7 Playwright-native (108 Zeilen)
**Vorher:** 157 Zeilen mit CDP-Login, Onboarding, API Key (alles CDP)
**Jetzt:** 108 Zeilen — nutzt nur `fireworks_service.py` Funktionen

```python
# rotate.py flow:
1. GmxService.login() → Playwright
2. GmxService.rotate_alias() → Playwright
3. signup_fireworks(alias, password) → Playwright
4. login_fireworks(alias, password) → Playwright + CUA
5. create_api_key(key_name) → Playwright
6. PoolManager.add_key() → JSON
```

**Kein CDP mehr im rotate.py!** Alles über Playwright-API-Calls.

### gmx_service.py — Playwright-native (1286 Zeilen)
**Vorher:** Mix aus CDP + CUA + Playwright
**Jetzt:** Playwright-native für alle Operationen

- `initialize_architecture(browser)` — Multi-Tab-Setup (work_tab + dedizierter inbox_tab)
- `navigate_inbox()` — hält den Inbox-Tab dauerhaft im Posteingang
- `_navigate_to_all_email_addresses()` — Playwright shadow DOM traversal
- `_login()` — Playwright form fill
- `_delete_alias()` — Playwright iframe interaction
- `_create_alias()` — Playwright iframe interaction
- `read_otp()` — CDP-basiert (MailCheck Extension + OOPIF), Legacy-Fallback — bewährt
- `read_otp_via_playwright(browser)` — **frame-aware**: scannt ALLE Frames (auch OOPIF `bap.navigator.gmx.net`), klickt im matchenden Frame
- `read_otp_axtree_and_frames()` — bevorzugt Fireworks Confirm-URL, 6-stelliger Code nur mit Verifizierungs-Kontext

> ⚠️ Diese 8 Methoden gehören ALLE zur Klasse `GmxService` (4-Space-Indent). Ein
> früherer Bug hatte vier davon versehentlich auf Modul-Ebene (Spalte 0) verschoben
> → `AttributeError` bei jedem Aufruf. Siehe V15.5 FIXES.

---

## 🔧 V15.5 FIXES (2026-05-31) — OTP-Extraktion repariert

### Struktur-Bug: Methoden aus der Klasse gefallen
- `generate_alias_name`, `initialize_architecture`, `navigate_inbox`,
  `read_otp_axtree_and_frames` standen auf Modul-Ebene (Spalte 0) statt in `GmxService`
- Folge: `self.generate_alias_name()`, `gmx.initialize_architecture()`,
  `gmx.navigate_inbox()`, `gmx.read_otp_axtree_and_frames()` → `AttributeError`
- Fix: zurück in die Klasse eingerückt (per AST verifiziert, alle 22 Methoden vorhanden)

### Frame-aware OTP
- `read_otp_via_playwright` durchsucht jetzt `page.frames` (alle Frames), nicht nur den Hauptframe
- Klick erfolgt im matchenden Frame (`matched_frame.evaluate`), Text- ODER ID-basiert
- `read_otp_axtree_and_frames` erkennt zuerst die eindeutige Fireworks **Confirm-URL** und
  akzeptiert 6-stellige Codes nur aus Text mit Verifizierungs-Kontext (vermeidet `[A-Z0-9]{6}`-False-Positives)

---

## 🔧 V13 CHANGES (2026-05-29) — Fireworks Model Discovery

### Pool-Proxy `/v1/models` Handler
- `proxy/server.py` — `_handle_v1_models()` liest `~/.hermes/models_dev_cache.json`
- Gibt ALLE Fireworks Modelle + Router zurück (12 aktuell)
- Routen: `/v1/models` + `/inference/v1/models` (vor Catch-All registriert)
- `PUBLIC_PROXY_PATHS` um `/v1/models` erweitert

### Hermes `custom:*` Provider Support
- `patches/` (now in SIN-Rotator repo) — `provider_model_ids()` behandelt `custom:` prefix
- Probt `/v1/models` live über Pool-Proxy
- Model-Picker zeigt Fireworks-Modelle (vorher: 0, jetzt: 12)

---

## 🔧 V12 CHANGES (2026-05-26)

### Config Manager — GMX + Fireworks Credentials
- `agent_toolbox/core/config_manager.py` — speichert in `data/config.json`
- API: `GET /api/v1/config` + `POST /api/v1/config` (public, kein Auth)
- `rotate.py` liest Config → übergibt `--gmx-email` + `--gmx-password` + `--password`

### Setup-Seite (Dashboard)
- `/setup` — Formular für GMX Email, GMX Passwort, Fireworks Passwort
- Show/Hide Toggle auf Passwort-Feldern

### Pool-Stats: `leased` entfernt
- `available = total - used - suspended`
- `leased` Feld entfernt aus Schema, Route, Pool Manager

### Chat-Assistent (Dashboard /hilfe)
- Rust-Command `chat_send` → Pool-Router (`localhost:9998`)
- Modell: `accounts/fireworks/models/gpt-oss-120b` ($0.15/M input)
- System-Prompt in `src-tauri/chat-system-prompt.txt`
- Live-Pool-Stats + Backend-Health im System-Prompt

### CORS + Auth
- `/api/v1/config` zu `public_prefixes` hinzugefügt
- CORS Origins: `https://tauri.localhost`, `tauri://localhost`, `http://localhost:3000`, `http://localhost:8000`

### Tauri Build
- Neue Dependencies: `reqwest`, `tokio`, `futures-util`
- `chat_send` Command registriert

---

## 🔧 V12 FIXES (2026-05-26)

### Pool-Router + 10 Proxys
- EIN Pool-Router (:9998) verteilt auf 10 Proxy-Instanzen (:8888-:8897)
- Auto-Failover bei 413/429/412/5xx
- Cooldown nach 3 Fehlern (60s Pause)
- Start: `proxy/start-multi.sh`

### GMX Navigation — Playwright Shadow DOM
- Reiner Playwright-Ansatz — kein CUA für Navigation
- `ACCOUNT-AVATAR-NAVIGATOR` Custom Element → JS `.click()` + `dispatchEvent(mouseenter)`
- Shadow DOM traversal → "E-Mail Einstellungen" → settings iframe → "E-Mail-Adressen"
- `3c.gmx.net` (HTTPS, direkt) funktioniert für direkte Navigation

### Double-Key-Waste Fix (Atomic Report+Lease)
- `pool_manager.report_key()` leaset Ersatz-Key atomar (im gleichen Lock wie suspend)
- Proxy `_swap_key()` nutzt `report()`-Result direkt — kein extra `lease()`

### 429 Handling — Client Return
- Transientes 429 → SOFORT an Client zurück mit `Retry-After` Header
- Kein internes Warten mehr

### Chrome Tab Cleanup
- `rotate.py` schließt ALLE non-essential Tabs nach jeder Rotation
- Nur Dashboard + 1 GMX-Inbox bleiben

### CDP Target Selection — Inbox bevorzugen
- `get_page_target()` priorisiert `navigator.gmx.net` über `www.gmx.net`

---

## 🐛 BEKANNTE PROBLEME (2026-05-29)

### Fireworks Account Suspension (Spending Limit)
```
Account golden-cobra-560-66c is suspended, possibly due to reaching the monthly
spending limit or failure to pay past invoices.
```
- Jeder FW Account hat $5 Credits — sobald aufgebraucht = Suspension
- Betroffene Keys müssen als `used` markiert werden
- Workaround: `POST /pool/report` oder `POST /pool/use` für suspended Keys

### OTP-Email Verzögerung
- Fireworks Verify-Email kann bis zu 180s brauchen
- Fix: 25×8s = 200s Polling in `signup_fireworks()`
- Fallback: `partial` status — Account ist unverified aber oft loginbar

### OTP-Extraktion — ✅ GEFIXT (V15.5)
- **War:** `read_otp_via_playwright` scannte nur den Hauptframe → Mail in OOPIF/iframe
  (`bap.navigator.gmx.net`) wurde nie gefunden; zusätzlich waren 4 GmxService-Methoden
  durch fehlerhafte Einrückung aus der Klasse gefallen (`AttributeError`).
- **Jetzt:** Frame-übergreifender Scan + Confirm-URL-Erkennung + Kontext-validierter Code.

### Unverified Account = API Key Blocked
- Account erstellt, aber unverified → API Key Seite redirected zu `/login`
- Fix: Verify-URL muss geöffnet werden (oder Account ist verified)
- Workaround: Nach `partial` signup → `login_fireworks()` versucht trotzdem

---

## 🔑 CRITICAL PATTERNS (MANDATORY)

### Playwright Form Interaction
```python
# Email/Password
page.locator('input[name="email"]').first.fill(email)
page.locator('input[name="password"]').first.fill(password)

# Button matching via text content
for btn in await page.locator('button[type="submit"]').all():
    if 'Next' in (await btn.text_content() or ''):
        await btn.click(force=True); break

# API Key (Playwright) — disabled-Wait + DOM-Polling
for _ in range(15):
    for btn in await page.locator('button').all():
        txt = (await btn.text_content() or '').strip()
        if 'Generate' == txt and not await btn.is_disabled():
            await btn.click(force=True); break
```

### GMX Alias Delete (Playwright iframe)
```python
frame = [f for f in page.frames if 'allEmailAddresses' in f.url][0]
frame.locator(f'text={alias_email}').first.hover()
frame.locator('[title*="löschen"]').first.click(force=True)
```

### GMX Alias Create (Playwright iframe)
```python
inp = frame.locator('input[type="text"]').first
await inp.fill("name-123")
btn = frame.locator('button:has-text("Hinzufügen")').first
await btn.click(force=True)
# verify: inp.input_value() == '' = success
```

### CUA Onboarding (Fallback)
```python
# Names: "First" + "Last" suchen, NICHT "Name"
el = _find_element("First", "AXTextField")  # richtig
# el = _find_element("Name", "AXTextField")  # FALSCH!

# Use-cases
for uc_text in ["Prototype", "Flexible", "Conversational", "Search"]:
    el = _find_element(uc_text, "AXCheckBox")
    if el: _cua_click(el)
```

### OTP Polling (read_otp)
```python
# 25 attempts × 8s = 200s max
for attempt in range(25):
    await asyncio.sleep(8)
    otp_result = await svc.read_otp(sender_filter="fireworks", max_retries=1, retry_delay=3)
    if otp_result.get("status") == "success":
        verify_url = otp_result.get("url") or otp_result.get("otp_url")
        if verify_url: break
```

---

## 📁 ARCHITECTURE

```
agent_toolbox/
├── core/
│   ├── fireworks_service.py    V6: Playwright+CUA Hybrid + launch()
│   ├── gmx_service.py          Playwright-native, launch() statt connect_over_cdp
│   ├── pool_manager.py         Pool-Stats + Key-Management
│   ├── keychain_store.py       macOS Keychain-Store
│   ├── config_manager.py       GMX+FW Credentials
│   ├── cua_helper.py           CUA Window Detection (nur für Onboarding)
│   └── cdp_client.py           Raw CDP WebSocket (OOPIF fallback)
├── api/
│   └── routes/
│       ├── gmx.py              GMX API
│       ├── fireworks.py        Fireworks API
│       ├── pool.py             Pool-CRUD + Stats
│       ├── rotation.py         Full Rotation Orchestrator
│       ├── config.py           GET/POST /api/v1/config
│       └── schemas.py          Pydantic Models
├── static/dashboard.html       Dashboard SPA
└── start_toolbox.py            FastAPI entry point

proxy/
├── server.py                   Pool-Proxy (aiohttp SSE) + /v1/models Handler
├── pool_client.py              Backend API Client
├── key_cache.py                Key Pre-fetch Cache
├── config.py                   Proxy Configuration
└── start-multi.sh              Startet Pool-Router + 10 Proxys

scripts/
├── pool-router.py              Pool-Router (ThreadingMixIn)
└── pool-router.plist           LaunchAgent

tools/
├── rotate.py                   V8.1: TRUE ONE Browser (page-native, no CDP)
├── batch_rotate.py             Batch N Rotations
├── gmx_alias_tool.py          GMX Alias CLI
├── open_gmx_email.py          GMX Email Opener
├── swap_key.py                Key Swap CLI
├── install.sh                 Service Installer
└── manage_services.sh         Service Management

---

## 🔗 CROSS-REFERENCES — SINator Ecosystem

| Repo | Port | Was |
|------|------|-----|
| **SINator-fireworksai** (dieses) | `:8000` | Fireworks Key Pool + Proxy |
| **SINator-heypiggy** | `:8002` | HeyPiggy Account Generator |
| **SINator-dashboard** | `:3000` | Tauri App, Provider-Switcher |

Start: `cd ~/dev/SINator-dashboard && ./start.sh` → :8000 + :8002 + :3000 + Tauri App
Build: `cd ~/dev/SINator-dashboard && ./build.sh` → /Applications/SINator.app

⚠️ Tauri Release App ist **statisch** — jedes Code-Update erfordert `./build.sh`.

---

*Last Updated: 2026-05-31 (V15.5 — OTP frame-aware Fix, GmxService Struktur-Fix)*
*All learnings propagated to AGENTS.md, knowledge-base.md, and banned.md.*

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **SINator-FireworksAI** (3253 symbols, 5007 relationships, 133 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/SINator-FireworksAI/context` | Codebase overview, check index freshness |
| `gitnexus://repo/SINator-FireworksAI/clusters` | All functional areas |
| `gitnexus://repo/SINator-FireworksAI/processes` | All execution flows |
| `gitnexus://repo/SINator-FireworksAI/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

---

## 🧠 Simone MCP — Code Intelligence & Automation

Simone MCP bietet zusätzliche Code-Analyse-Tools via MCP:

**Verfügbare Tools:**
- `sin_simone_mcp_symbol_search` — Symbol-Suche im gesamten Workspace
- `sin_simone_mcp_find_references` — Alle Referenzen zu einem Symbol finden
- `sin_simone_mcp_project_overview` — Workspace-Footprint + Dateitypen
- `sin_simone_mcp_structural_edit` — Strukturelle Code-Edits (LSP-grade)
- `sin_simone_mcp_memory_query` — Cloud Semantic Memory (Kontext + Analysen)
- `sin_simone_mcp_health` — Server-Status und Capabilities

**IMMER verwenden für:**
- `sin_simone_mcp_symbol_search` statt grep für Symbol-Suche
- `sin_simone_mcp_find_references` vor Refactoring
- `sin_simone_mcp_project_overview` für schnellen Codebase-Überblick
- `sin_simone_mcp_structural_edit` für sichere, strukturierte Edits
