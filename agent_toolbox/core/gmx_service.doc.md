# GMX Service (`gmx_service.py`)

Playwright-native GMX Service für Alias-Rotation und OTP-Extraktion im SINator Fireworks AI Rotator.

## Dependencies

- **Imported by:** `agent_toolbox/api/routes/gmx.py`, `tools/rotate.py`, `tools/gmx_open_email.py`
- **Imports:** `agent_toolbox/core/cdp_client.py` (CDP fallback), Playwright async API
- **Depends on:** User Chrome Profile 73 (simoneschulze) via Playwright connect_over_cdp

## Key Methods

| Section | Method | Purpose |
|---|---|---|
| **Multi-Tab** | `initialize_architecture()` | Creates `work_tab` + `inbox_tab` in same browser context |
| **Multi-Tab** | `navigate_inbox()` | Keeps inbox_tab pinned at GMX Posteingang |
| **Connection** | `_pw_connect()` | Playwright-Page aus CDP, SID-Tab-Priorisierung |
| **Login** | `_login()` | GMX Login via Form (email+password) + post-consent redirect (V20.0 FIX) |
| **Navigation** | `_navigate_to_all_email_addresses()` | Zum E-Mail-Adressen-Settings-Bereich |
| **Alias Delete** | `_delete_alias()` | Löscht existierenden Alias via Playwright native mouse + kleinste-BBox row (V19.3 FIX, V20.0 portiert) |
| **Alias Create** | `_create_alias()` | Erstellt neuen Alias via Playwright iframe |
| **Rotation** | `rotate_alias()` | Kombiniert delete + create + verify |
| **Legacy OTP** | `read_otp_cdp_axtree()` | CDP-basierte OTP-Suche (deprecated) |
| **Playwright OTP** | `read_otp_via_playwright()` | Playwright-native OTP-Suche (V14, falls V2 versagt) |
| **V2 OTP** | `read_otp_v2()` | Browser_scan_frames + browser_eval_in_frame (V18.2, bevorzugt) |
| **Session** | `check_session()` | Prüft ob GMX Session noch aktiv |
| **Helpers** | `open_email_addresses()` | Navigiert zu E-Mail Settings |
| **Legacy** | `_inject_cookies()` | Cookie-Injection via CDP (deprecated, nicht mehr verwendet) |
| **Singleton** | `get_gmx_service()` | Module-level Singleton |

## V20.0 Fixes (10.06.2026)

### `_delete_alias` — V19.3 Port (Commit ce2f64f)
**Vorher:** Playwright `row.hover()` triggert Wicket `:hover` nicht zuverlässig → Delete-Icon wird nicht gefunden.
**Jetzt:** 
- Row-Detection: kleinste BBox (GMX nutzt `<div class="table_body-row table_row">`, nicht `<tr>/<li>`)
- Hover: `page.mouse.move(0,0)` → `page.mouse.move(cx,cy)` Pattern mit 3x retry
- Delete-Icon: `a.table-hover_icon[title*="löschen"]` mit Fallback-Suche
- Klick + OK-Confirm: Playwright native mouse (kein CDP)

### `_login` — Post-Consent Redirect (Commit c34466e)
**Vorher:** Nach Cookie-Consent-Accept blieb URL auf `consent-management`.
**Jetzt:** Expliziter `page.goto("https://www.gmx.net/")` nach Consent-Klick.

## ⚠️ V19.3 — `_delete_alias` Selektor repariert (IMMORTAL TAG: `v19.3-gmx-delete-fixed`)

**DO NOT TOUCH** ohne diesen Tag zu reverten und mit ausführlicher Diagnose.

### Was war kaputt
Der Delete-Link sitzt in einem **`<div class="js-template is-hidden" data-template-name="hoverMenu">`** Block AUSSERHALB der Row. Bei Hover wird das Template **unhidden** (`is-hidden` Klasse weg).

**Vorher suchte der Code INNERHALB der Row** (`rows[i].querySelector('[title*="lösch"]')`) — die Row enthält NUR `<div class="table_field">` mit Email-Text, **keine `<a>` Tags**. Resultat: null.

**Globaler Fallback** iterierte ALLE `<a>` Tags und prüfte `title.includes('lösch')` — matchte entweder falsche Elemente (Sidebar) oder das hidden Template (w=0, h=0).

### Der Fix
```python
# Suche 1: Spezifischer Selektor .table-hover_icon
delLinks = document.querySelectorAll('a.table-hover_icon[title*="löschen"]')
# Nur sichtbare (r.width > 5 && r.height > 5) matchen

# Suche 2: Breite Suche als Fallback (z.B. wenn class-Name sich ändert)
document.querySelectorAll('a[title*="lösch" i]')
```

**Selektor-Logik:**
- `a.table-hover_icon[title*="löschen"]` — eindeutige CSS-Klasse (nur Hover-Menu-Links) + exakter Title-Filter
- Sichtbarkeits-Check `r.width > 5 && r.height > 5` filtert das hidden Template raus
- Nach Hover ist `<a>` sichtbar (20×20) — liefert sofort die korrekte Position

### Bug-Marker (NICHT ÄNDERN ohne Diagnose)
- `gmx_service.py:816-855` — Delete-Icon-Selektion
- `gmx_service.py:785-800` — Row-Finding (Hover-Position) — bleibt wie es war
- `gmx_service.py:806-814` — CDP-Hover via `Input.dispatchMouseEvent` — bleibt wie es war

### Verifikation
```bash
python3 debug/test_delete_fix.py
# Erwartet: "DELETION SUCCESS" für einen Test-Alias
```

## GMX Shadow DOM Structure

```
page → iframe#mail (webmailer.gmx.net)
  → mail-list-container > shadowRoot
    → list-mail-list > shadowRoot
      → list-mail-item (50 Stück) ← EMAIL LISTE
    → webmailer-mail-detail > shadowRoot
      → detail-body > iframe.detail-body--full-height ← separate Playwright Frame
```

## GMX allEmailAddresses DOM Structure (V19.3)

```
page (3c.gmx.net/mail/client/settings/allEmailAddresses)
  → div.splitpanel-settings-content_wrapper
    → div.table_body
      → div.table_body-row.table_row[data-row-id="..."] ← ROW (enthält NUR Email-Text)
        → div.table_field
          → text: silver-cobra-874@gmx.de
  → div.js-template.is-hidden[data-template-name="hoverMenu"] ← HIDDEN TEMPLATE
    → div.table-hover_menu
      → a.table-hover_icon[title="Bearbeiten"]    ← EDIT (wird sichtbar bei Hover)
      → a.table-hover_icon[title="E-Mail-Adresse löschen"]  ← DELETE (wird sichtbar bei Hover)
```

**KRITISCH:** Delete-Icon ist im TEMPLATE (SIBLING des table_body), NICHT IN der Row. Suche INNERHALB der Row findet NICHTS.

## OTP Extraction Strategy (V18.2 — `read_otp_v2()`)

1. **Check inbox_tab** for existing GMX mail list
2. **`browser_eval_in_frame(frame_name="mail")`** — shadow-piercing JS scan for Fireworks emails
3. **`mail_frame.locator('list-mail-item').nth(N).click(force=True)`** — click via Playwright locator
4. **`browser_scan_frames(regex=...)`** — scan ALL unnamed about:blank frames for verify URL
5. Return `{"status":"success", "otp_url": "..."}`

Fallback: `read_otp_via_playwright()` (legacy, falls CDP nicht verfügbar)

## Important Constants

- `GMX_HOME_URL = "https://www.gmx.net/"` — **NIEMALS direkt `navigator.gmx.net/mail` navigieren** (verliert SID)
- Alias-Format: `{adjektiv}-{substantiv}-{NNN}` (32×32 Adj/Noun Pool)
- OTP Polling: max 25×8s = 200s für read_otp_cdp_axtree, 15×6s für read_otp_via_playwright
- Delete-Selektor: `a.table-hover_icon[title*="löschen"]` (V19.3, NICHT ÄNDERN)

## Known Caveats

- `force=True` required for `locator().click()` — webmailer-mail-detail overlay intercepts pointer events
- Email body lives in **separate unnamed Playwright frame** (about:blank) — NOT in the mail frame
- `goto(navigator.gmx.net/mail)` redirects to `www.gmx.net` without SID — use "Zum Postfach" strategy
- GMX FreeMail: only ONE alias at a time (delete before create)
- **Delete-Icon ist im `js-template is-hidden` Block** — innerhalb der Row suchen findet NICHTS (V19.3 Bug-Fix)
- **Hover-Timing:** Nach `mouseMoved` CDP-Event mindestens 1.5s sleep für Template-Unhide
