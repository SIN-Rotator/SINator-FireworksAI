# AGENTS.md — SINator Fireworks AI Rotator V19.14 (2026-06-02) — **SOTA + E2E PROVEN + SOFT-OWNERSHIP + MULTI-AGENT**

## ✅ COMPLETE E2E FLOW — VERIFIED 2026-06-02 07:25

```bash
python tools/rotate.py
# → GMX Login (Step 0) → Alias Rotation (~37s) → Fireworks Signup
# → OTP (25×8s poll) → Verify → Login → Onboarding → API Key → Pool
```

**Pool:** 256 Keys — **+1 NEUER KEY** (elron-wolf-580@gmx.de → `fw_G3yw1hoAVAwe2HmiHNqPwG`)
**Cycle Time:** 158s total (V19.6 OK-confirm fix path) — see commit fff8983
**sin-browser-tools:** v2.0.1 (Issue #41 logging fix merged, PR #42 → main @ 64c9abcc)
**Pool-Router:** `sinatorpool-router.delqhi.com` (:9998, single endpoint, auto-failover)
**CF Tunnel:** `sinator` — `cloudflared tunnel run sinator --config config-sinator.yml`
**Pool Proxies:** 10 Instanzen (:8888-:8897) hinter Pool-Router
**API Key (alle Macs gleich):** `7avN1KkfInNqcOMn2CtwLTvx`
**Services:** com.sinator.backend (:8000), com.sinator.pool-router (:9998), 10× pool-proxy (:8888-:8897), Pages (:8040)
**Config Repos:**
  • **OpenCode →** [SIN-Code-FireworksAI-OpenCode-Config](https://github.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config)
  • **Hermes  →** [SIN-Hermes-Provider-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle)

## V19.7 Highlights (this commit)

| Component | Status |
|-----------|--------|
| GMX delete (icon + OK confirm) | ✅ V19.3 + V19.6 (both merged to main) |
| sin-browser-tools v2.0.1 | ✅ Issue #41 fixed, host log handlers preserved |
| E2E rotation @ 07:25 UTC | ✅ 158s, key `fw_G3yw1hoAVAwe2HmiHNqPwG` |
| Proxy `/v1/models` | ✅ 12 models (deepseek-v4-flash, glm-5p1, gpt-oss-120b/20b...) |
| Proxy `/v1/chat/completions` | ✅ Real Fireworks response (test: 20 token limit) |
| `toolbox.log` wächst | ✅ 9.5MB+ (war 0 vor #41 Fix) |

## 🔧 V19.10 FIXES (2026-06-02) — Ghost-Lease Bug Behoben

### Symptom
Dashboard zeigte "71 leased" + "12 verfügbar" bei nur 1 Proxy-Request. Pool war quasi unnutzbar.

### Root Cause: Zwei Bugs zusammen
1. **20 Proxy-Prozesse** statt 10 — alte Ghost-Proxies (ports 27191-27200, 27399-27401) aus 6:39 liefen noch neben den 10 aktuellen (8888-8897) aus 7:21
2. **`proxy_id` Kollision** — `proxy_id = f"proxy-{int(time.time())}"` gab allen 10 Proxies die GLEICHE ID (alle starteten in derselben Sekunde). Dadurch landeten ALLE Leases unter `leased_to=proxy-1780377674` und 52+20 Keys waren für eine einzige "Instanz" reserviert
3. **Kein periodisches Lease-Cleanup** — `expire_leases()` lief nur bei `get_stats()`/`lease_key()`, nicht automatisch

### Fixes
1. **10 Ghost-Proxies gekillt** (ports 27191-27200, 27399-27401) — nicht mehr in `lsof`
2. **124 Geister-Leases returned** (alle mit `leased_to` startend mit `proxy-1780377674`) → `available: 5 → 77` (+72 Keys zurück)
3. **`proxy_id` unique** — `f"proxy-{self.port}-{random.randint(1000,9999)}"` statt `int(time.time())`
4. **V19.10 Background Lease-Cleanup** — FastAPI `lifespan` startet asyncio task: `expire_leases()` alle 60s, räumt stale Leases automatisch auf

### Vorher / Nachher
| Metrik | Vorher (V19.9) | Nachher (V19.10) |
|--------|----------------|------------------|
| Proxy-Prozesse | 20 (10 ghost + 10 aktiv) | 10 (sauber) |
| Pool "leased" | 71 (alle unter 1 ID!) | 4 (3 setup + 1 dashboard) |
| Pool "available" | 12 | **77** (+65) |
| Unique proxy_ids | 1 (alle gleich!) | 10 (proxy-8888-8813, proxy-8889-8068, …) |
| Lease cleanup | nur on-demand | automatisch alle 60s |

### Immortal Tag
- `v19.10-ghost-lease-fixed` — verhindert 71-Lease-Pileup für immer
**Pool-Router:** `sinatorpool-router.delqhi.com` (:9998, single endpoint, auto-failover)
**CF Tunnel:** `sinator` — `cloudflared tunnel run sinator --config config-sinator.yml`
**Pool Proxies:** 10 Instanzen (:8888-:8897) hinter Pool-Router
**API Key (alle Macs gleich):** `7avN1KkfInNqcOMn2CtwLTvx`
**Services:** com.sinator.backend (:8000), com.sinator.pool-router (:9998), 10× pool-proxy (:8888-:8897), Pages (:8040)
**Config Repos:**
  • **OpenCode →** [SIN-Code-FireworksAI-OpenCode-Config](https://github.com/OpenSIN-Code/SIN-Code-FireworksAI-OpenCode-Config)
  • **Hermes  →** [SIN-Hermes-Provider-Bundle](https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle)

## 🔧 V19.12 FIXES (2026-06-02) — Lease-Hydration + 401-Cascade end-to-end

### Symptom
Chat-Requests an `https://sinatorpool-router.delqhi.com/inference/v1/chat/completions` lieferten permanent `401 UNAUTHORIZED`. Symptomatisch sah der Proxy gesund aus, `/v1/models` lieferte die 12 Modelle korrekt, aber `chat/completions` schlug durchgehend fehl. `opencode` zeigte „no answer". Pool meldete 24 verfügbar / 234 suspended, aber alle 24 verfügbaren Keys waren effektiv tot.

### Root Cause: 4 zusammenwirkende Bugs
1. **Lease-Endpoint hydratisierte nie aus dem Keychain.** Nach V19.8 wurde `api_key` in `data/fireworksai-pool.json` durch den Sentinel `"STORED_IN_KEYCHAIN"` ersetzt. `POST /pool/lease` und `GET /pool-lease` haben den Sentinel-String **direkt** an den Client zurückgegeben, ohne `hydrate_single()` aus `keychain_store` aufzurufen. → Der Proxy schickte `"Bearer STORED_IN_KEYCHAIN"` an Fireworks → 401.
2. **Proxy `main()` health-checkte `:8000` statt `:8100`.** Backend wurde auf 8100 migriert, `proxy/server.py:619` checkte aber weiterhin `http://localhost:8000/health`. Der `else`-Branch der for-Loop benutzte `sleep` statt `time.sleep` → `NameError` killte den Proxy beim Start (`exit code 1`).
3. **`proxy/pool_client.py` sendete keinen `Authorization`-Header.** Backend verlangt `Bearer $SINATOR_AUTH_TOKEN` für `/pool/lease` etc., Proxy tat nichts dazu → 401 auch bei korrekt hydratierten Keys.
4. **LaunchAgents `com.sinator.pool-proxy-*.plist` zeigten `SIN_POOL_API_URL=http://localhost:8000/api/v1`.** `proxy/config.py` fiel bei fehlender `~/.sin-pool/config.json` auf `localhost:8000` zurück, und die plists gaben das explizit so weiter.

### Fixes
1. **`agent_toolbox/api/routes/pool.py`:** `hydrate_single` in `POST /pool/lease` und `GET /pool-lease`. Wenn `result["api_key"]` leer ist, hole aus Keychain. Gleiches für `backup` bei `lease_backup=True`.
2. **`proxy/server.py:main()`:** `SIN_BACKEND_HEALTH_URL` env-var mit Default `http://localhost:8100/health`. `time.sleep(1)` statt `sleep`. Saubere Log-Strings.
3. **`proxy/pool_client.py`:** `self.auth_token = os.environ.get("SINATOR_AUTH_TOKEN", "").strip()`, `_headers()` baut `{"Authorization": f"Bearer {self.auth_token}"}`. Wird in `lease`/`return_key`/`report`/`stats` mitgesendet. **Außerdem:** leere `api_key` aus Lease → sofort `report(reason="empty_api_key")` + retry, damit kaputte IDs nicht immer wieder gezogen werden.
4. **`proxy/config.py` + `~/Library/LaunchAgents/com.sinator.pool-proxy-{8888..8897}.plist`:** `pool_api_url` und `SIN_POOL_API_URL` auf `http://localhost:8100/api/v1`.

### Verifikation
- `curl http://localhost:8888/inference/v1/chat/completions -d '{"model":"accounts/fireworks/models/deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":4}'` → echte Fireworks-Antwort
- `opencode chat` (nach Restart) → Antworten kommen
- 17 von 24 verfügbaren Keys sind wieder hydratable (7 IDs kaputt, werden in V19.13 repariert)
- `git log` auf main: `a22b4b3 fix(pool): V19.12 lease-hydration + 401-cascade end-to-end`
- `git push origin v19.12-lease-hydration-fix` ✅

### Immortal Tag
- `v19.12-lease-hydration-fix` — markiert den letzten bekannten funktionierenden Stand. Vor JEDER Änderung an `proxy/server.py`, `proxy/pool_client.py`, `proxy/config.py` oder `agent_toolbox/api/routes/pool.py`: `git diff v19.12-lease-hydration-fix -- <datei>` und sicherstellen dass die 4 Fixes erhalten bleiben.

---

## 🔧 V19.11 FIXES (2026-06-02) — Return-Old-Key + Lease-Field-Cleanup

### Symptom
Nach V19.10 Fix waren 77 Keys verfügbar, aber jeder Cache-Expiry (30min) würde den alten Key NICHT zurückgeben — nur neuen leasen. Verschwendung + potenzielle Geister-Leases.

### Fixes
1. **Proxy gibt alten Key vor neuem Lease zurück** (`proxy/server.py:_ensure_key`)
   - `KeyCache.get_primary()` speichert expired Key in `previous` statt nur zu clearen
   - `KeyCache.pop_previous()` holt und löscht den previous Key
   - `_ensure_key()` ruft `pool_client.return_key()` für den expired Key bevor neu geleased wird
   - Persistiert in `~/.sin-pool/previous-key.json` für Crash-Recovery
2. **`mark_suspended` löscht Lease-Felder** (`pool_manager.py:mark_suspended`)
   - Setzt `leased_until`, `leased_to`, `lease_id`, `leased_at` auf `None`
   - Verhindert dass suspended Keys noch als "leased" im JSON stehen

### Impact
- **Vorher:** Cache-Expiry → alter Key bleibt 30min "leased" bis expire_leases()
- **Nachher:** Cache-Expiry → sofort `/pool/return` → Key ist SOFORT verfügbar
- **Bonus:** Bei Proxy-Crash wird `previous-key.json` beim nächsten Start geladen und `pop_previous()` gibt den Key zurück

### Immortal Tag
- `v19.11-return-old-key` — Key-Return bei Cache-Expiry

---

## 🔧 V19.14 SOFT-OWNERSHIP (2026-06-02) — Multi-Agent Key Distribution

### Konzept
Ersetzt exklusives Leasing (`leased_until`) durch `assigned_to` + `active_consumers`.
Jeder Agent bekommt seinen eigenen Stamm-Key. Wenn alle assigned → least-shared
Key als Fallback. **Niemals blockieren, niemals warten.**

### Neue Pool-Felder
| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `assigned_to` | str\|null | Permanenter Sticky-Owner (agent_id) |
| `active_consumers` | list[str] | Agenten die diesen Key aktuell nutzen |
| `shared_count` | int | Wie oft wurde dieser Key geteilt |
| `last_heartbeat` | float | Für Stale-Consumer-Cleanup (300s timeout) |

### Neue Endpoints
| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/pool/agent-key` | POST | Soft-Ownership Key-Zuweisung (4 Prioritäten) |
| `/pool/agent-release` | POST | Agent gibt Key frei |
| `/pool/agent-heartbeat` | POST | Agent-Heartbeat (hält consumer alive) |

### Proxy-Änderungen
- `AgentKeyCache` ersetzt `KeyCache` — pro-Agent, kein TTL-Expiry, sticky `preferred_key_id`
- `_ensure_key()` kein Retry-Loop mehr (von 300×1s auf sofort)
- `agent_id` via `SIN_AGENT_ID` env-var (default: `proxy-{port}`)
- `_on_shutdown` nutzt `release_agent_key()` statt `return_key()`

### Test-Ergebnisse (2026-06-02)
| Test | Status |
|------|--------|
| 3 Agenten → 3 verschiedene Keys | ✅ |
| Sticky: gleicher Agent = gleicher Key | ✅ |
| Release: Agent gibt Key frei | ✅ |
| Proxy E2E: echte Fireworks Chat-Responses | ✅ |
| Cache: 2. Request braucht keinen Backend-Call | ✅ |
| Backward-Compat: /pool/lease funktioniert weiter | ✅ |
| Router (:9998) → alle 10 Proxies erreichbar | ✅ |

### Immortal Tag
- `v19.14-soft-ownership` — markiert den funktionierenden Soft-Ownership-Stand

---

## 🛑 SUBAGENT ROTATION GUARD (2026-06-02 V19.14)

**Subagents DÜRFEN NIEMALS Chrome killen. NIEMALS `pkill -9 -f "Google Chrome"`.**

Der AGENTS.md Chrome-Start-Command (`pkill -9 -f "Google Chrome"` → `nohup Chrome ...`) ist NUR für den MAIN-AGENT wenn Chrome tot ist.

### Warum
- Chrome auf Port 9222 mit Profile 73 ist die EINZIGE lebende GMX-Session. Killen = Rotation kaputt.
- Eine laufende `rotate.py` nutzt diese Session. Killen = Abbruch + Orphan-Account ohne Key.
- Danach startet der Subagent Chrome neu, GMX-Cookies laden, ABER die Fireworks-Onboarding-Session innerhalb der Rotation ist unterbrochen → Subagent denkt "Code kaputt" obwohl Code 100% sauber ist.

### Pflicht-Check VOR jeder Rotation im Subagent

```bash
# 1. Chrome schon da?
curl -s http://127.0.0.1:9222/json/version > /dev/null 2>&1 || {
    echo "❌ Chrome NICHT auf 9222 — Main-Agent informieren, NICHT selbst starten!"
    exit 1
}

# 2. Läuft schon eine Rotation?
pgrep -f "rotate.py" > /dev/null 2>&1 && {
    echo "❌ rotate.py LÄUFT BEREITS — warten oder Main-Agent fragen!"
    exit 1
}

# 3. Beides OK → Rotation starten
python3 tools/rotate.py
```

Siehe auch: `banned.md` → Subagent Rotation Rules

---

## ⚠️ IMMORTAL COMMIT PROTOCOL — ACTIVE ⚠️

> **Diese Rotation funktioniert. NICHTS ZERSTÖREN. Alle zukünftigen Commits MÜSSEN:**
> 1. Conventional Commit Message (fix:/feat:/refactor:/docs:/chore:/perf:/test:)
> 2. Immer auf Branch committen (kein detached HEAD)
> 3. Annotated Tag `v<major>.<minor>-<suffix>` für wichtige Fixes
> 4. Push zu `origin` (force-with-lease nur bei amend)
>
> **Tag `v19.14-soft-ownership` markiert den letzten bekannten funktionierenden Stand.**
> **Vor JEDER Änderung an Code-Dateien: `git diff v19.14-soft-ownership` und verifizieren dass der Fix erhalten bleibt.**

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

## 🔧 V19.3 GMX DELETE FIX (2026-06-02) — `_delete_alias` Selektor repariert

### Symptom
`gmx_service._delete_alias()` fand Delete-Icon nicht:
- `"Delete icon not found in alias row — global search as fallback"`
- `"Delete icon not found globally either"` → return False → rotation failed

### Root Cause
GMX rendert den Delete-Link in einem **`js-template is-hidden` Block außerhalb der Row** (HTML Zeile 401-419):
```html
<div class="js-template is-hidden" data-template-name="hoverMenu">
  <a class="table-hover_icon icon-link" title="E-Mail-Adresse löschen">...</a>
</div>
```

Bei Hover über die Row wird das Template **unhidden** (`is-hidden` Klasse weg), die `<a>` wird sichtbar.

**Der Bug:** Der Code suchte `rows[i].querySelector('[title*="lösch"]')` INNERHALB der Row. Die Row enthält NUR `<div class="table_field">` mit Email-Text — keine `<a>` Tags. Der Fallback `rows[i].querySelector('a, button, span, ...')` fand entsprechend auch nichts.

**Globaler Fallback (Zeile 838)**: Iteriert ALLE `<a>` Tags, prüft `title.includes('lösch')`. Theoretisch korrekt, ABER:
- Erstes hidden-Element hat `w=0 h=0` → `r.width > 5` schlägt fehl
- Nach Hover ist `<a>` sichtbar (`w=20 h=20`) — **sollte matchen**
- **Realität:** Manchmal matchte der Fallback das falsche Element (Sidebar-Links), oder die Position war stale (Mouse weg von Row → Template wieder hidden)

### Der Fix (`gmx_service.py:816-855`)

**Vorher (2 Suchen, beide falsch):**
```python
# Suche 1: INNERHALB der Row — findet NICHTS
delEl = rows[i].querySelector('[title*="lösch"]')
delEl = rows[i].querySelector('a, button, span, ...')  # fallback auch INNERHALB

# Suche 2: Global über alle <a> — falsche Reihenfolge/Position
title.includes('lösch') || title.includes('delete')  # matched Sidebar-Links
```

**Nachher (1 direkte Suche + 1 breite Suche):**
```python
# Suche 1: Spezifischer Selektor .table-hover_icon (nur Hover-Menu-Links)
delLinks = document.querySelectorAll('a.table-hover_icon[title*="löschen"]')
# → findet das ELEMENT IM TEMPLATE, prüft visibility

# Suche 2: Fallback über alle <a> mit "lösch" im title (korrekt)
title.indexOf('lösch') !== -1  # lowercase substring
```

**Warum das funktioniert:**
1. **`a.table-hover_icon`** ist eine eindeutige CSS-Klasse — nur Hover-Menu-Links nutzen sie
2. **Selektor `[title*="löschen"]`** matcht nur das Delete-Icon (`Bearbeiten` hat anderen Title)
3. **Visibility-Check** `r.width > 5 && r.height > 5` filtert das hidden Template raus
4. **Nach Hover** ist `<a>` sichtbar (20×20), Selektor liefert sofort die korrekte Position

### Verifikation
Test-Script: `debug/test_delete_fix.py`
```
[3] Will try to delete: test-1779947387@alphafrau.de
[4] Calling _delete_alias() with the fix...
  Hover row via CDP at (593, 464)
  Delete 'E-Mail-Adresse löschen' at (930, 463)
  OK confirm at (815, 417)
  Alias deleted successfully
  DELETION SUCCESS
```

### Impact Analysis
- **Risk:** LOW
- **Callers:** 2 (`gmx_service.py:1078` intern in `rotate_alias` + `gmx/delete_alias.py:45` CLI)
- **Signatur unverändert:** `async def _delete_alias(self, page, alias_email) -> bool`
- **Kein Breaking Change:** Return values identisch

### Immortal Tag
- `v19.3-gmx-delete-fixed` — Delete-Selektor repariert, end-to-end getestet

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

*Last Updated: 2026-06-02 (V19.14 — Soft-Ownership Multi-Agent Key Distribution)*

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
