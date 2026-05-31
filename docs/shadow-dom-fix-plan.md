# Shadow DOM Fix — Plan (ETERNAL, V15.6)

**Version:** V15.6  
**Datum:** 2026-05-31  
**Status:** IMPLEMENTED — Fixes 1-4 + Debug-Tool applied (V15.6)  
**Severity:** CRITICAL — OTP-Extraktion komplett kaputt seit Monaten

---

## Bug-Symptome (bestätigt)

- `body.innerText` = **0 Zeichen** im webmailer-frame (`webmailer.gmx.net`)
- Emails existieren → in Shadow DOM → unsichtbar für normale Selectors
- Rotator findet 0 Emails → OTP-Poll läuft ins Leere → Rotation bricht ab
- **Pool zeigt falsche Zahlen**: 235 total, aber ~234 als `suspended=True` → `available = 1`

---

## Root Cause (bestätigt via Playwright CDP-Dump 2026-05-31)

1. **Shadow DOM Blockade:** GMX nutzt `<sc-webmailer-mail-list-h>` WebComponent. Emails liegen in `element.shadowRoot`. `document.querySelectorAll('*')` penetriert Shadow DOM **NICHT**.
2. **Alter Tag-Name:** Code sucht nach `<list-mail-item>` (veraltet). Neuer Container: `<sc-webmailer-mail-list-h class="sc-webmailer-mail-list-h hydrated">`, Inhalt in `#mailer_container.maillist.gmx`.
3. **Leerer body.innerText:** `frame.evaluate("document.body.innerText")` liefert `""` weil der gesamte Inhalt im Shadow DOM wohnt.
4. **Pool-Bug:** `get_stats()` berechnet `suspended` nur wenn `used=False`. Aber fast alle Keys haben `suspended=True, used=False` → werden als `suspended` gezählt → `available = 1`. **Aber:** im JSON steht `suspended: null` (Python `None`) für manuell hinzugefügte Keys — die werden mit `bool(None) = False` als `nicht suspended` gewertet. Inkonsistente Daten.

---

## Betroffene Dateien (exakte Zeilen, basierend auf Commit `b222e80`)

| Datei | Zeile(n) | Problem |
|-------|----------|---------|
| `agent_toolbox/core/gmx_service.py` | 107-128 | `read_otp_axtree_and_frames()` — `frame.evaluate` scan `document.body.childNodes` + `shadowRoot`, aber `body.innerText = 0` → keine Treffer |
| `agent_toolbox/core/gmx_service.py` | 990-1008 | `findItems()` im CDP-Pfad — `document.body.querySelectorAll('*')` ignoriert Shadow DOM komplett + sucht nach `list-mail-item` (veraltet) |
| `agent_toolbox/core/gmx_service.py` | 1117 | Playwright `scan_js` — sucht `list-mail-item`, Shadow DOM wird traversiert aber Entry-Point ist `document.body` das leer ist |
| `agent_toolbox/core/gmx_service.py` | 1139-1147 | Playwright `click_js` — gleiches Problem wie scan_js |
| `agent_toolbox/core/pool_manager.py` | 177 | `get_stats()` — `suspended` Berechnung: `bool(None)` = `False` → Keys mit `suspended: null` werden als AVAILABLE gezählt, obwohl sie es nicht sind |

---

## EXAKTER FIX — Code-Delta (copy-paste ready)

### Fix 1: `read_otp_axtree_and_frames()` — Shadow DOM Text-Extraktion (Zeile 107-128)

**ERSETZE** den `frame.evaluate("""() => { ... }""")` Block (ab Zeile 107):

```javascript
() => {
    let results = [];
    function traverse(node) {
        if (!node) return;
        // ZUERST shadowRoot behandeln — dort liegt der Inhalt
        if (node.shadowRoot) {
            const st = node.shadowRoot.body
                ? node.shadowRoot.body.innerText
                : (node.shadowRoot.documentElement
                    ? node.shadowRoot.documentElement.innerText
                    : '');
            if (st && st.trim()) results.push(st.trim());
            traverse(node.shadowRoot);
        }
        // Dann normale childNodes
        node.childNodes.forEach(child => {
            if (child.nodeType === Node.TEXT_NODE && child.textContent && child.textContent.trim()) {
                results.push(child.textContent.trim());
            } else if (child.nodeType === Node.ELEMENT_NODE) {
                const elText = (child.innerText || child.textContent || '').trim();
                if (elText) results.push(elText);
                traverse(child);
            }
        });
    }
    if (document.body) traverse(document.body);
    return results;
}
```

**WICHTIG:** Entry-Point muss `shadowRoot` VOR `childNodes` traversieren, sonst wird Shadow DOM-Inhalt nie erreicht.

### Fix 2: `findItems()` im CDP-Pfad (Zeile 986-1009)

**ERSETZE** den `items_js` String:

```javascript
(function() {
    function snip(txt, n) { return (txt || '').trim().slice(0, n); }
    function scan(root) {
        let out = [];
        const q = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const el of q) {
            const tag = (el.tagName || '').toLowerCase();
            const txt = (el.textContent || '').trim();
            const hasShadow = !!el.shadowRoot;
            // Match: Text enthält Filter-Keyword
            if (txt && txt.toLowerCase().includes(arguments[0])) {
                const mid = (el.getAttribute('id') || '').replace(/^id/, '') || null;
                out.push({mailId: mid, text: snip(txt, 400), el: tag, hasShadow: hasShadow});
            }
            if (hasShadow) {
                out = out.concat(scan(el.shadowRoot));
            }
        }
        return out;
    }
    return scan(document.body);
})()
```

**ÄNDERUNG:** Sucht nicht mehr nach `list-mail-item` sondern nach ALLEN Elementen mit passendem Text + penetriert Shadow DOM.

### Fix 3: Playwright `scan_js` + `click_js` (Zeile 1109-1152)

**ERSETZE** `scan_js`:

```javascript
(() => {
    const SENDER = arguments[0].toLowerCase();
    let out = [];
    function scan(root) {
        const q = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const el of q) {
            const txt = (el.textContent || '').trim().toLowerCase();
            const mid = (el.getAttribute('id') || '').replace(/^id/, '') || null;
            if (txt.includes(SENDER)) {
                out.push({mailId: mid, text: (el.textContent || '').trim().slice(0, 400)});
            }
            if (el.shadowRoot) scan(el.shadowRoot);
        }
    }
    if (document.body) scan(document.body);
    return out;
})()
```

**ERSETZE** `click_js`:

```javascript
(() => {
    const a = arguments[0] || [];
    const targetId = a[0];
    const targetText = (a[1] || '').trim();
    function scan(root) {
        const q = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
        for (const el of q) {
            const eid = (el.getAttribute('id') || '').replace(/^id/, '');
            const txt = (el.textContent || '').trim();
            if ((targetId && eid === targetId) || (!targetId && txt === targetText)) {
                el.click(); return true;
            }
            if (el.shadowRoot && scan(el.shadowRoot)) return true;
        }
        return false;
    }
    return scan(document.body);
})()
```

### Fix 4 (Optional): Pool `get_stats()` — `suspended: null` behandeln

In `pool_manager.py` Zeile 177:

```python
suspended = sum(1 for k in self.keys
                if k.get("suspended") is True  # statt: k.get("suspended", False)
                and not k.get("used", False))
```

Damit werden Keys mit `suspended: null` korrekt als `nicht suspended` gewertet.

---

## Zusätzliches Tool: `tools/gmx_open_email.py`

Separates Tool um GMX Email-Seite zu öffnen, Shadow DOM zu penetrieren und eine Email anzuklicken + Inhalt zu scannen. NICHT in den Rotator integriert — nur für Debug/Manuellen Betrieb.

**Funktion:**
1. Chrome via CDP verbinden (Port 9222)
2. `navigator.gmx.net/mail` laden
3. `webmailer.gmx.net` iframe finden
4. Shadow DOM (`sc-webmailer-mail-list-h`) penetrieren
5. Erste Email mit "fireworks" im Text suchen
6. Email anklicken → OOPIF mailbody öffnen
7. Inhalt scannen + URL extrahieren

---

## Implementation Order

1. **Fix 1** — `read_otp_axtree_and_frames()` Shadow DOM penetrieren (primäre OTP-Methode)
2. **Fix 2** — CDP `findItems()` anpassen (Fallback-Pfad)
3. **Fix 3** — Playwright `scan_js` + `click_js` anpassen (Backup)
4. **Fix 4** — Pool Stats korrigieren
5. **Tool** — `gmx_open_email.py` für Debug

---

## Test-Checkliste

- [ ] `python3 tools/gmx_open_email.py` → findet + klickt Fireworks Email
- [ ] `python3 tools/rotate.py` → OTP-Poll findet Verify-URL im Shadow DOM
- [ ] Pool Stats: `available` zeigt korrekte Anzahl an
- [ ] Full Rotation: Signup → Verify → Login → API Key → Pool = Erfolg

---

## Warum dieser Plan nie verloren gehen darf

Dieser Bug existiert seit V14. Mehrere Agenten haben versucht ihn zu fixen, sind aber immer wieder an derselben Stelle gescheitert:
- Shadow DOM nicht penetriert
- Alter Tag-Name `list-mail-item` statt `sc-webmailer-mail-list-h`
- `body.innerText = 0` ignoriert

Dieser Plan dokumentiert:
- Root Cause (bestätigt via CDP)
- EXAKTE Code-Deltas (copy-paste ready)
- Betroffene Zeilen mit Commit-Referenz (`b222e80`)
- Separates Debug-Tool (`gmx_open_email.py`)

**Tag:** `v15.5-eternal-shadow-dom-plan`  
**Branch:** `main`  
**Datei:** `docs/shadow-dom-fix-plan.md`
