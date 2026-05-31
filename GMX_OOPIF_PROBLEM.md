# GMX Email-Lesen: Probleme & Lösungsansätze

## Status: OFFEN (2026-05-31)

---

## Kernproblem

**GMX Emails können nicht gelesen werden** - die Email-Liste ist in einem **OOPIF (Out-of-Process iframe)** das alle Zugriffsversuche blockiert.

---

## Architektur-Analyse

### GMX Page-Struktur

```
Hauptseite: https://bap.navigator.gmx.net/mail (Profile 73, User Chrome)
├── iframe[name="lps"]           → https://lps.navigator.gmx.net/ (Email-UI?)
├── iframe[name="mail"]          → https://navigator.gmx.net/mail/mail (Cross-origin)
├── iframe[name="trackbar"]      → https://trackbar.navigator.gmx.net/
├── iframe[name="mail_settings"] → https://3c.gmx.net/mail/client/settings/allEmailAddresses
├── iframe[name="id81"]          → https://3c.gmx.net/mail/client/blank
└── 20+ Ad-Tracker iframes       → Various cross-origin

Alternativ-URL: https://navigator.gmx.net/mail/mail?sid=<SID>
```

### Das OOPIF-Problem

| Zugriffsmethode | Ergebnis |
|-----------------|----------|
| `page.evaluate()` (JS) | ❌ Cross-Origin blockiert |
| `Accessibility.getFullAXTree(pierce=True)` | ❌ Nur 24 Nodes (Navigation chrome), keine Email-Liste |
| `page.locator()` (Playwright) | ❌ OOPIF ist fremder Prozess |
| `iframe.contentDocument` | ❌ Blockiert |
| `fetch()` im Page-Kontext | ❌ CORS-Block |

**`pierce=True` durchdringt Shadow DOM aber NICHT cross-origin iframes.**

---

## Versuchte Lösungswege

### 1. SIN-Browser-Tools (`browser_snapshot_full_oopif`)

```python
await manager.connect_cdp('http://127.0.0.1:9222')
result = await browser_snapshot_full_oopif(pierce=True)
# Ergebnis: 24 Nodes (nur Navigation, keine Emails)
```

**Problem:** CDP `Accessibility.getFullAXTree` mit `pierce=True` liest NUR den main frame + Shadow DOM. Cross-origin iframes (OOPIFs) werden nicht gelesen.

### 2. Direkte CDP-Session zum `mail` iframe

```python
# Tab-Liste abfragen
rtk curl -s http://127.0.0.1:9222/json/list
```

**Problem:** Der `mail` iframe hat keinen eigenen CDP-Target-Eintrag. Er existiert nur als `iframe` child des `bap.navigator.gmx.net` page targets.

### 3. Frame-URL direkt navigieren

```python
# Email-URL direkt ansteuern
await gmx_page.goto(f'https://navigator.gmx.net/mail/mail?sid={sid}')
```

**Problem:** URL wird zu `https://navigator.gmx.net/mail?sid=<SID>` (mit Redirect), zeigt aber immer noch OOPIF.

### 4. JavaScript im Page-Kontext

```python
result = await gmx_page.evaluate('''async () => {
    // Cross-origin iframe - Blocked
    const iframe = document.querySelector('iframe[name="mail"]');
    const doc = iframe.contentDocument; // Error
}''')
```

**Problem:** `Blocked a frame with origin "https://bap.navigator.gmx.net" from accessing a cross-origin frame.`

### 5. GMX API direkt

```python
# Innerhalb des Page-Kontexts
const resp = await fetch(`https://navigator.gmx.net/mail/api/v1/emails?sid=${sid}`)
```

**Problem:** `Failed to fetch` - API antwortet nicht oder ist cross-origin.

---

## Mögliche Lösungen

### Option A: `Target.attachToFrame` (ungetestet)

Chrome CDP kann mit `Target.attachToFrame` ein iframe als eigenen Target ansprechen. Dadurch könnte eine eigene CDP-Session zum OOPIF aufgebaut werden.

```python
# Pseudo-Code
await cdp.send('Target.attachToFrame', {
    'frameId': iframe_frame_id  # Aus Page.getFrameTree
})
```

### Option B: Page.evaluate in Same-Origin Subdomain

`bap.navigator.gmx.net` und `navigator.gmx.net` haben unterschiedliche Origins. Aber `lps.navigator.gmx.net` und `navigator.gmx.net` teilen sich `navigator.gmx.net` als Parent-Domain.

### Option C: MailCheck Extension

GMX MailCheck Extension läuft mit erhöhten Rechten und kann auf OOPIFs zugreifen. Die Extension `camnampocfohlcgbajligmemmabnljcm` ist im Chrome installiert.

### Option D: Cookie-Injection in Fresh Context

1. Cookies aus Profile 73 extrahieren
2. Fresh Bot-Chrome Context mit diesen Cookies erstellen
3. Direkt zu `https://navigator.gmx.net/mail/mail?sid=<SID>` navigieren
4. Hoffen dass der Server-Side-Rendering liefert (kein OOPIF)

### Option E: Headless Browser mit voller Rendering-Unterstützung

`puppeteer` mit `headless: false` oder spezielle Flags:
```python
browser = await p.chromium.launch(
    args=['--disable-web-security', '--disable-features=IsolateOrigins']
)
```

---

## SIN-Browser-Tools Status

### Install-Problem (Issue erstellt)

```bash
$ rtk pip install -e .
error: No virtual environment found; run `uv venv` to create an environment, or pass `--system` to install into a non-virtual environment
```

**Workaround:**
```bash
cd ~/dev/SIN-Browser-Tools
python3 -m pip install -e . --break-system-packages
```

**Issue:** https://github.com/OpenSIN-Code/SIN-Browser-Tools/issues/1

### CDP-Implementation (Commit 94f8668)

Die SIN-Browser-Tools haben CDP-basierte Implementierung:
- `browser_snapshot_full_oopif(pierce=True)` → nutzt `Accessibility.getFullAXTree`
- `browser_click_cdp()` → nutzt `DOM.getContentQuads` + `Input.dispatchMouseEvent`
- `ElementRegistry.register()` → gibt `@e1`, `@e2` refs zurück

**Problem:** CDP `pierce=True`穿透OOPIFs nicht.

---

## Rotator-Flow Zustand

### Funktioniert ✅
- GMX Login (Profile 73, User Chrome)
- Alias Rotation (`allEmailAddresses` via `3c.gmx.net`)
- Fireworks Signup
- OTP Email wird gesendet

### Funktioniert NICHT ❌
- Email öffnen (OOPIF blockiert alle Zugriffe)
- OTP Code lesen (Email nicht zugreifbar)
- Full E2E Rotation

---

## Nächste Schritte

1. **Target.attachToFrame testen** - könnte OOPIF als eigenen Target aufmachen
2. **Cookie-Injection + fresh context** - umgeht Session-Mischung
3. **MailCheck Extension nutzen** - hat erhöhte Rechte
4. **Neuinstallation GMX FreeMail** - Alternative zu FreeMail mit besserer API

---

## Relevant Files

- `tools/rotate.py` - Rotator Entry Point
- `agent_toolbox/core/gmx_service.py` - GMX Service mit Playwright+CDP
- `~/dev/SIN-Browser-Tools/` - Lokale SIN-Browser-Tools Installation
- Chrome Profile 73: `/Users/simoneschulze/Library/Application Support/Google Chrome`
- GMX Inbox Tab ID: `43FB2DCED5E0F74BC0A331D9D9729142`
- GMX SID: `c8216ce7c6ef68a7ee73a2c0594236ecaf3d3e35d7cf35d56433ef7792a864d4e76fd1d0bd3fa6cdacf0cfa5e1698392`