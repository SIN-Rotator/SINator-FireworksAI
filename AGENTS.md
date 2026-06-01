# AGENTS.md — SINator Fireworks AI Rotator V19.2 (2026-06-02) — **ONBOARDING FIXED**

## ✅ COMPLETE E2E FLOW — VERIFIED 2026-06-02

```bash
python tools/rotate.py
# → GMX Login (Step 0) → Alias Rotation (~37s) → Fireworks Signup
# → OTP (25×8s poll) → Verify → Login → Onboarding → API Key → Pool
```

**Pool:** 243 Keys (7 available, 0 leased, 10 used, 226 suspended) — **+1 NEUER KEY nach Onboarding-Fix**
**Cycle Time:** ~37s GMX + ~60s Fireworks signup + ~30s API Key = ~130s total
**Pool-Router:** `sinatorpool-router.delqhi.com` (:9998, single endpoint, auto-failover)
**CF Tunnel:** `sinator` — `cloudflared tunnel run sinator --config config-sinator.yml`
**Pool Proxies:** 10 Instanzen (:8888-:8897) hinter Pool-Router
**API Key (alle Macs gleich):** `7avN1KkfInNqcOMn2CtwLTvx`
**Services:** com.sinator.backend (:8000), com.sinator.pool-router (:9998), 10× pool-proxy (:8888-:8897), Pages (:8040)
**Config Repos:**
  • **OpenCode →** [SIN-Code-FireworksAI-OpenCode-Config](https://github.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config)
  • **Hermes  →** [SIN-Hermes-Provider-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle)

---

## ⚠️ IMMORTAL COMMIT PROTOCOL — ACTIVE ⚠️

> **Diese Rotation funktioniert. NICHTS ZERSTÖREN. Alle zukünftigen Commits MÜSSEN:**
> 1. Conventional Commit Message (fix:/feat:/refactor:/docs:/chore:/perf:/test:)
> 2. Immer auf Branch committen (kein detached HEAD)
> 3. Annotated Tag `v<major>.<minor>-<suffix>` für wichtige Fixes
> 4. Push zu `origin` (force-with-lease nur bei amend)
>
> **Tag `v19.2-onboarding-fixed` markiert den letzten bekannten funktionierenden Stand.**
> **Vor JEDER Änderung an Code-Dateien: `git diff v19.2-onboarding-fixed` und verifizieren dass der Fix erhalten bleibt.**

### Warum diese Vorsicht?

Diese Rotation hat **5 separate Bugs** gehabt die ALLE gleichzeitig gefixt werden mussten:
1. **Account ID Überschreiben** → Validation Error → Continue disabled
2. **Carousel "Next slide" wurde geklickt** statt Continue
3. **Cookie-Banner blockierte Form** (hunderte cky-Elemente)
4. **Wait-Zeit zu kurz** (15s statt 45s)
5. **os-Import fehlte** in Onboarding-Funktion

Diese Bugs sind NICHT unabhängig — alle 5 zusammen ergeben erst den funktionierenden Flow.

---

## 🔧 V19.2 ONBOARDING-FIX (2026-06-02) — 5 BUGS IN EINEM COMMIT GEFIXT

### Was war kaputt (deine Hinweise + meine Diagnose)

#### 1. Account ID Feld wurde ÜBERSCHRIEBEN
- **Symptom:** Account ID = `sinjtrrubqpfrost-lynx-612-jkh0y` (28 chars), Error "String must contain at most 20 character(s)", Continue-Button disabled
- **Ursache:** Mein Code hat `browser_type('input[name="accountId"]', "sin" + 8_random)` aufgerufen — aber das Feld war von Fireworks VORAB GEFÜLLT. `browser_type` HÄNGT an, statt zu ersetzen. Resultat: 22 (pre-fill) + 9 (mein Code) = 31 chars → Validation Error
- **Fix:** Account ID nicht mehr anfassen wenn pre-filled:
  ```python
  if current_aid:
      logger.info(f"Account ID pre-filled by Fireworks: '{current_aid}' (using as-is, NOT overwriting)")
  else:
      # Field is empty — fill with a safe 11-char value
  ```

#### 2. Carousel "Next slide" wurde geklickt statt Continue
- **Symptom:** DIAG `Continue button state: {'text': 'Next slide', 'disabled': False}` — Code klickte CAROUSEL-BUTTON!
- **Ursache:** JS-Query hatte `t.indexOf('Continue') !== -1 || t.indexOf('Next') !== -1` — der Carousel-Button "Next slide" matched "Next" UND kam im DOM vor echtem Continue
- **Fix:** "Next" komplett aus Suche entfernt, nur exakt "Continue":
  ```python
  if (t === 'Continue' || t.indexOf('Continue') !== -1) { ... }  # KEIN "Next" mehr!
  ```

#### 3. Cookie-Banner blockierte die Form
- **Symptom:** DIAG zeigte hunderte cky-Checkboxen (Cookie-Banner), aber KEINE Fireworks-Onboarding-Checkboxes
- **Ursache:** Cookie-Banner wurde nur über "Reject All" weggeklickt, aber wenn das in einem Iframe war oder verdeckt → Form nicht klickbar
- **Fix:** AGGRESSIVE Cookie-Banner-Entfernung:
  1. Scroll to top
  2. Click "Reject All" (sichtbarer Button oben)
  3. JS-Force-Remove aller `cky-*` Elemente
  4. Body-Style-Overflow wieder auf `visible`
  5. Verifizieren: 0 cky-Elemente übrig

#### 4. Wait-Zeit nach Submit war zu kurz (15s)
- **Symptom (dein Hinweis):** "dauert es nämlich paar sekunden länger" — Server braucht länger zum Verarbeiten
- **Fix:**
  - Wait-Loop von 15×1s auf **45×1s** erweitert
  - Enter-Fallback `asyncio.sleep` von 3s auf **5s** erhöht
  - requestSubmit `asyncio.sleep` von 2s auf **5s** erhöht
  - Force-navigate hat jetzt **zusätzliche 15s** Wartezeit

#### 5. os-Import fehlte in Onboarding-Funktion
- **Symptom:** "DIAG verify shot failed: name 'os' is not defined" → Screenshots wurden nicht gemacht
- **Fix:** `import os` am Anfang der Funktion

---

## Vollständiger Working Flow (NICHT ÄNDERN)

1. Cookie-Banner AGGRESSIV entfernen (Reject All + JS-strip)
2. Account ID NICHT überschreiben wenn pre-filled (nur füllen wenn leer)
3. First/Last Name via browser_type (mit delay=30ms triggert React)
4. Terms-Checkbox via browser_click_checkbox_by_text (sin_browser_tools sophisticated walker)
5. Continue: exakte Suche ohne "Next" Fallback
6. Use-cases: 4-Strategie checkbox clicker
7. Submit: button click → form.requestSubmit() → Enter (5s sleeps)
8. Wait-Loop: 45×1s (statt 15s) auf redirect zu /home
9. Force-navigate als Fallback mit extra 15s wait

---

## Stats

| Metrik | Vorher | Nachher |
|--------|--------|---------|
| Pool total | 242 | **243** |
| Pool available | 0 | **7** |
| Onboarding redirect | ❌ (timeout 15s) | ✅ `/account/home` |
| Account ID | ❌ (überschrieben, invalid) | ✅ pre-filled, valid |
| Continue button | ❌ (Carousel geklickt) | ✅ echter Continue |
| Wait time | 15s | 45s |

---

## 🔧 V19.2 CHANGES (2026-06-01) — Security: Auth Enforcement + Tunnel

### Security Hardening
| Change | Before | After |
|--------|--------|-------|
| Pool-Router Auth | ❌ no validation | Bearer via `SINATOR_AUTH_TOKEN` (401 on bad/missing) |
| Proxy Bind | `0.0.0.0` (all interfaces) | `127.0.0.1` (localhost only) |
| opencode.json apiKey | `fw_HJknMPsmyKfGAAqqBNGGkJ` (dummy) | `7avN1KkfInNqcOMn2CtwLTvx` (real) |
| CF Tunnel | nicht aktiv | `sinator` tunnel → `sinatorpool-router.delqhi.com` → :9998 |
| Plists | `~/.sin-pool/` + `~/.hermes/` | Repo paths (`proxy/server.py`, `scripts/pool-router.py`) |

### Auth Flow
```
Client → CF Tunnel → pool-router (auth check ✓) → proxy (localhost bypass) → Fireworks API
```
- `/health` is public (no auth)
- `/v1/models`, `/v1/chat/completions` require Bearer token
- Proxy localhost bypass means pool-router-validated requests pass freely to proxy

### Tunnel Command
```bash
cloudflared tunnel --config ~/.cloudflared/config-sinator.yml run sinator &
```
Config: `~/.cloudflared/config-sinator.yml` — ingress routes `sinatorpool-router.delqhi.com` → `localhost:9998`

### Pool Stats (2026-06-02)
- **243 total, 7 available, 0 leased, 10 used, 226 suspended**
- +1 neuer Key nach Onboarding-Fix (2026-06-02)
- Rotation ist wieder voll funktional

### Core Change: Zero Raw Playwright Calls
`fireworks_service.py` now uses **100% SIN-Browser-Tools** — no `page.evaluate()`, no `page.locator()`, no `page.goto()`. All operations go through:
- `browser_navigate()`, `browser_fill()`, `browser_click_by_text()`
- `browser_click_checkbox_by_text()`, `browser_console()`, `browser_get_text()`
- `browser_get_url()`, `browser_press()`

### Bug Fixes
| Problem | Fix | Impact |
|---------|-----|--------|
| Account ID > 20 chars | `sin` + 8 random = 11 chars | Form validation passes |
| `browser_fill()` doesn't clear React inputs | Native React value setter via `browser_console()` | Fields fill correctly |
| "Next" clicks carousel button | `browser_press("Enter")` after password | Login submits properly |
| Onboarding stuck on page 1 | Terms checkbox via `browser_click_checkbox_by_text()` | Page 2 loads |
| Continue doesn't advance | Native React setter for Account/First/Last | Form validates |
| Submit button disabled (React pending) | JS dispatchEvent fallback + `browser_press("Enter")` | Submit geht immer durch |
| `browser_click_by_text("Submit")` matched nicht | `indexOf('Submit') !== -1` statt `===` | Button mit beliebigem Text suffix |

### `_BrowserHandle` Duck-Type
Replaces `BrowserManager` (which hardcodes `--start-maximized`). Provides `_page`, `_context`, `_browser`, `_playwright` for SIN-Browser-Tools compatibility. Window size: 1200×800.

### Immortal Tags
- `v19.1-e2e-sin-tools` — Full E2E flow working
- `v19.1-fix-signup-enter` — Enter key fix for signup (proven working baseline)
- `v19.1-working-revert` — HEAD (3485aa4) nach Revert auf v19.1-fix-signup-enter
- `v19.1-fix-onboarding-enter` — Enter key fallback für onboarding Submit

---

## ⚠️ LEARNINGS 2026-06-01 — Was schiefging und wie es richtig geht

### 1. `browser_press("Enter")` NIEMALS durch `browser_click_by_text("Next")` ersetzen

**Symptom:** Nach Email-Fill in Signup/Login → Enter sendet Formular → Password-Felder erscheinen nicht → Page zeigt "Build. Tune. Scale" (Homepage).

**Warum:** Fireworks hat carousel "Next slide" Button (disabled) VOR dem echten "Next"-Button im DOM. `browser_click_by_text("Next", role="button")` matched den carousel Button (disabled) → kein Submit.

**Richtig:** `browser_press("Enter")` — immer, in Signup UND Login. Form-Submit per Enter ist der einzig reliable Weg.

**Tag:** `v19.1-fix-signup-enter` ist der proven working baseline.

### 2. Button-Text Matching: `includes()` statt `===`

**Symptom:** Onboarding Submit-Button wird nicht gefunden → kein Redirect → /onboarding bleibt → API Key fails.

**Warum:** `browser_click_by_text("Submit", role="button")"` matched exakten Text "Submit". Fireworks Button heißt aber "Submit to get $5 Credits". Strict equality schlägt fehl. Auch der Fallback `browser_click_by_text("Get $5", role="button")"` matched nicht weil "Submit to get $5 Credits" !== "Get $5".

**Richtig:** JS dispatchEvent mit `.indexOf('Submit') !== -1` (partial match) — wie der alte pre-v19.1 Code mit `'Submit' in txt`. Genutzt für Continue UND Submit in `_playwright_onboarding`.

### 3. Onboarding Submit: Enter-Key als Fallback für disabled Button

**Symptom:** Submit-Button ist disabled (React validation pending) → `browser_click_by_text` wirft Exception → Fallback-Texte matchen nicht → kein Submit.

**Richtig:** Nach erfolglosem `browser_click_by_text` + Fallback-Texte → Enter-Key (`browser_press("Enter")`) — bypassed disabled state, triggert Form-Submit native.

### 4. JS dispatchEvent nur für disabled-Button-Fallback, NICHT für Signup/Login

**Symptom:** `dispatchEvent(new MouseEvent('click', ...))` für Signup "Next" → Password-Felder erscheinen nicht.

**Warum:** React SPA erwartet native Form-Submit (Enter-Key) für Email-Validierung. JS dispatchEvent dispatht nur click, kein form submit → Validierung läuft nicht.

**Richtig:**
- Signup/Login Email → `browser_press("Enter")`
- Onboarding Continue/Submit → `browser_click_by_text` + JS dispatchEvent Fallback (disabled bypass) + Enter als letzter Fallback

### 5. Kein Code ändern ohne Vergleich mit proven Tag

**Regel:** Jeder Commit/Eingriff muss gegen `v19.1-fix-signup-enter` validiert werden. Wenn der Tag funktioniert, meine Änderungen aber nicht → Fehler liegt bei mir.

**Check:**
```bash
git diff v19.1-fix-signup-enter -- agent_toolbox/core/fireworks_service.py
# Sollte 0 sein (keine Änderungen zum working state)
```

---

## 🔧 V18.0 CHANGES (2026-06-01) — Frame-Tools for GMX Shadow DOM

### ✅ Issue #11 — Gelöst (SIN-Browser-Tools, Commit c77ae56)

**3 Frame-Tools in `sin_browser_tools/tools/frames.py`:**

1. **`browser_list_frames()`** — alle Frames auflisten
2. **`browser_eval_in_frame(expression, frame_name=None, frame_url=None)`** — JS in bestimmtem Frame
3. **`browser_snapshot_in_frame(frame_name=None, frame_url=None, selector=None, ...)`** — Frame-DOM mit Shadow Root traversal

### GMX Shadow DOM Struktur
```
page → iframe#mail (webmailer.gmx.net)
  → mail-list-container → shadowRoot → list-mail-list → shadowRoot → list-mail-item
  → detail-body → iframe.detail-body--full-height (EMAIL BODY)
```

### Immortal Tag
- `v18.0-gmx-email-lesbar` — Frame-Tools fix in SIN-Browser-Tools

---

## 🔧 V16.0 FIXES (2026-05-31) — GMX Navigation + Session

### KERNFIX: "Zum Postfach" klicken
**NIEMALS** `page.goto("https://navigator.gmx.net/mail")` — redirected ohne SID. Stattdessen:
1. `page.goto("https://www.gmx.net/")` → "Zum Postfach" klicken → `navigator.gmx.net/mail?sid=...`

### _pw_connect: SID-Tab-Priorisierung
Tabs mit `sid=` + `navigator.gmx.net` werden bevorzugt. `status=inactive` URLs übersprungen.

---

## 🔧 V15.5 FIXES (2026-05-31) — OTP-Extraktion repariert

### Struktur-Bug: Methoden aus Klasse gefallen
`generate_alias_name`, `initialize_architecture`, `navigate_inbox`, `read_otp_axtree_and_frames` standen auf Modul-Ebene → `AttributeError`. Fix: zurück in Klasse.

### Frame-aware OTP
`read_otp_via_playwright` durchsucht ALLE Frames (inkl. OOPIF). `read_otp_axtree_and_frames` erkennt Confirm-URL + 6-stellige Codes nur mit Verifizierungs-Kontext.

---

## 🔧 V12 CHANGES (2026-05-26)

### Config Manager
- `agent_toolbox/core/config_manager.py` — `data/config.json`
- API: `GET/POST /api/v1/config` (public)

### Pool-Router + 10 Proxys
- EIN Pool-Router (:9998) → 10 Proxy-Instanzen (:8888-:8897)
- Auto-Failover bei 413/429/412/5xx
- **CF-Fallback (Issue #24):** alle Pools tot/Cooldown → Cloudflare Worker (D1-Key-Rotation), falls `CF_WORKER_URL` gesetzt. Siehe `cloudflare/`

### Double-Key-Waste Fix (Atomic Report+Lease)
- `pool_manager.report_key()` leaset Ersatz-Key atomar

---

## 🐛 BEKANNTE PROBLEME

### Fireworks Account Suspension
- Jeder FW Account hat $5 Credits — aufgebraucht = Suspension
- Betroffene Keys als `used` markieren via `POST /pool/report`

### OTP-Email Verzögerung
- Fireworks Verify-Email bis 180s → 25×8s = 200s Polling

### Browser Window Size
- `BrowserManager` hardcodes `--start-maximized` (1920px)
- Fireworks Detects → Blockiert
- Fix: `_BrowserHandle` mit `--window-size=1200,800`

### Fireworks Model Lineup (V19.1 — 2026-06-01)
- **ALLE alten Llama-Models entfernt** (llama-v3p1-*, llama-v3p3-*)
- Verifizierung in `proxy/server.py:254` nutzte `llama-v3p1-8b-instruct` → 404
- Fix: `deepseek-v4-flash` (v19.1-fix-proxy-verify-model)
- **Aktuelle Models:** deepseek-v4-flash/pro, gpt-oss-120b/20b, kimi-k2p5/k2p6, glm-5p1, minimax-m2p5/m2p7, qwen3p6-plus
- Alle Model-Namen in opencode Config (`~/.config/opencode/opencode.json`) sind korrekt

### Pool Status (2026-06-01)
- **224/240 Keys suspended** — nur 6 tatsächlich verfügbar
- Ursache: Fireworks $5 Credits pro Account — aufgebraucht = Suspension
- Pool-Eintrag `$(uuidgen)` Fix: shell-Template literal statt UUID (v19.1-fix-pool-entry)
- **NIEMALS suspended Keys löschen** — in separate Archive-DB verschieben
- Oft fehlerhaft als suspended markiert vom System

### ~/.sin-pool/ Deployment Problem
- Laufende Proxys starten von `~/.sin-pool/server.py` (AELTERE Version)
- Repo-Fixes in `proxy/server.py` greifen NUR nach Neustart aus Repo
- `start-multi.sh` startet korrekt aus Repo, aber alte Proxys müssen zuerst sterben
- **Cloudflare/deployment muss PROXY aus Repo starten, nicht aus ~/.sin-pool/**

### Cloudflare Deployment (Issue #24 — umgesetzt, Deploy ausstehend)
- **Problem:** Mac muss aus sein → Serving muss ohne Mac weiterlaufen
- **Lösung:** Cloudflare Worker + D1 als Fallback (`cloudflare/worker.js`, `cloudflare/schema.sql`).
  Mac bleibt primär; CF DNS Health Check → Mac tot = Worker übernimmt.
- **Key-Sync:** `scripts/sync_to_cf.py` pusht den Pool nach jeder Rotation nach D1 (Mac = Source of Truth)
- **GMX-Problem bleibt:** Chrome Profile 73 ist lokal — neue Keys werden weiterhin nur am Mac erzeugt; der Worker serviert nur den zuletzt gesyncten Pool
- **Free Tier:** 100k req/Tag (~10 User)
- **Ausstehend:** `wrangler deploy` + D1-Migration mit echten CF-Credentials (siehe `cloudflare/README.md`)

---

## 🔑 CRITICAL PATTERNS (MANDATORY)

### SIN-Browser-Tools Form Interaction
```python
from sin_browser_tools.tools.navigation import browser_navigate, browser_press
from sin_browser_tools.tools.interaction import browser_click_by_text, browser_fill
from sin_browser_tools.tools.extraction import browser_console

# Fill email (React controlled input — native setter)
await browser_console("""(() => {
    var inp = document.querySelector('input[name="email"]');
    var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(inp, 'user@example.com');
    inp.dispatchEvent(new Event('input', {bubbles: true}));
    inp.dispatchEvent(new Event('change', {bubbles: true}));
})()""")

# Click button by text
await browser_click_by_text("Next", role="button")

# Submit form (avoids carousel button conflict)
await browser_press("Enter")
```

### React Native Value Setter (MANDATORY for React SPAs)
```python
# browser_fill() uses page.type() which doesn't clear React state
# Use this pattern instead:
await browser_console(f"""(() => {{
    var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(document.querySelector('input[name="fieldName"]'), '{value}');
    document.querySelector('input[name="fieldName"]').dispatchEvent(new Event('input', {{bubbles: true}}));
    document.querySelector('input[name="fieldName"]').dispatchEvent(new Event('change', {{bubbles: true}}));
}})()""")
```

### OTP Polling (rotate.py)
```python
otp_result = await gmx.read_otp_main_frame_only(sender_keyword="fireworks", timeout=80)
otp_url = otp_result.get("otp_url")
if otp_url:
    verify_ok = await verify_account(otp_url)
```

### GMX Alias Delete (Playwright iframe)
```python
frame = [f for f in page.frames if 'allEmailAddresses' in f.url][0]
frame.locator(f'text={alias_email}').first.hover()
frame.locator('[title*="löschen"]').first.click(force=True)
```

---

## 📁 ARCHITECTURE

```
agent_toolbox/
├── core/
│   ├── fireworks_service.py    V19.1: 100% SIN-Browser-Tools + _BrowserHandle
│   ├── gmx_service.py          Playwright-native, launch() statt connect_over_cdp
│   ├── pool_manager.py         Pool-Stats + Key-Management + Keychain
│   ├── keychain_store.py       macOS Keychain-Store
│   ├── config_manager.py       GMX+FW Credentials
│   ├── browser_utils.py        Legacy utilities (DEPRECATED — use SIN-Tools)
│   ├── cua_helper.py           CUA Window Detection (nur für Onboarding)
│   └── cdp_client.py           Raw CDP WebSocket (OOPIF fallback)
├── api/
│   └── routes/
│       ├── gmx.py              GMX API
│       ├── fireworks.py        Fireworks API
│       ├── pool.py             Pool-CRUD + Stats + Lease
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
├── pool-router.py              Pool-Router (ThreadingMixIn) + CF-Fallback
├── pool-router.plist           LaunchAgent
└── sync_to_cf.py               Mac → Cloudflare D1 Pool-Sync (Issue #24)

cloudflare/                     Worker-Fallback (Issue #24)
├── worker.js                   1 Worker statt 10 Proxys, Key-Rotation in D1
├── schema.sql                  D1 pool_keys Tabelle (ersetzt pool.json)
├── wrangler.toml               Worker-Config (D1/KV Bindings)
└── README.md                   Deploy + 5 offene Fragen

tools/
├── rotate.py                   V19.1: Full E2E flow (GMX + Fireworks)
├── batch_rotate.py             Batch N Rotations
├── gmx_alias_tool.py          GMX Alias CLI
├── open_gmx_email.py          GMX Email Opener
├── swap_key.py                Key Swap CLI
├── install.sh                 Service Installer
└── manage_services.sh         Service Management
```

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

*Last Updated: 2026-06-01 (V19.1 — 100% SIN-Browser-Tools, E2E Flow Fixed)*

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
