# Fehleranalyse: SIN-Browser-Tools + GMX Email-Lesen

## Datum: 2026-05-31

---

## 1. SIN-Browser-Tools OOPIF-Fix funktioniert nicht für GMX

### Was erwartet wurde
`browser_snapshot_full_oopif()` sollte alle OOPIFs scannen via `new_cdp_session(frame)`.

### Was passiert
```
(frame scan failed: https://lps.navigator.gmx.net -- 
 BrowserContext.new_cdp_session: This frame does not have a separate CDP session, 
 it is a part of the parent frame's session)
```

### Ursache
Die GMX iframes (`lps.navigator.gmx.net`, `mail`, etc.) sind **same-process iframes**, nicht OOPIFs. Chrome DevTools zeigt sie als `iframe` mit `parentId`, nicht als eigene `page` targets.

### Unterscheidung
| Frame-Typ | `new_cdp_session(frame)` | `pierce=True` |
|-----------|-------------------------|---------------|
| **OOPIF** (separate process) | ✅ Eigenständige Session | ❌ Blockiert |
| **Same-process iframe** | ❌ "part of parent session" | ✅ pierce durchsucht |

### Erkenntnis
`browser_snapshot_full_oopif()` nutzt `new_cdp_session(frame)` für cross-origin frames. Bei GMX sind die iframes aber **same-origin** (alle `navigator.gmx.net`) - nur verschiedene Subdomains. Chrome's Site-Isolation behandelt Subdomains als same-process, nicht als OOPIF.

---

## 2. SID-Problem

### Was passiert
Die GMX-Session im Browser Tab ist aktiv mit SID `496970b9954896064bc2a9b3a45a8a38fa754011859f9`.

Die alte SID (`c8216ce7...`) die wir hatten ist **expired** → leitet zu `logoutlounge?status=session` weiter.

### Beweis
```
Existing tab URL: https://navigator.gmx.net/mail?sid=496970b9954896064bc2a9b3a45a8a38fa754011859f9
Still logged in.
```

---

## 3. Email-Liste ist in einer SPA (Dynamic Render)

### Was passiert
Auch mit frischem Page-Reload und 8s Wartezeit: Die Email-Liste erscheint **nicht** im Accessibility Tree.

### Vermutung
Die Email-Liste in `lps.navigator.gmx.net` ist ein **Web Component mit Shadow DOM** das erst nach User-Interaktion (z.B. Click auf "E-Mail" Button) gemountet wird. Das `iframe[name="lps"]` ist ein Empty-Shell der erst bei Navigation befüllt wird.

---

## 4. Falscher Test-Ansatz

### Problem
Ich habe versucht:
- `goto()` auf eine abgelaufene SID → `logoutlounge`
- Eine neue Page im gleichen Context erstellen → Cookies werden nicht korrekt übertragen
- Blindes Warten ohne Verifikation

---

## 5. Registry Bug (GEFIXT 2026-06-01)

### Problem
`browser_snapshot_full_oopif` crashte mit:
```
AttributeError: '_RegistryStub' object has no attribute 'counter'
```

### Ursache
`_RegistryStub` hat `__len__()` aber kein `counter` property. `accessibility.py:154` nutzte `manager.registry.counter`.

### Fix
```python
# Alt:
ref_count = manager.registry.counter
# Neu:
ref_count = len(manager.registry)
```
Commit: `a034958` im SIN-Browser-Tools Repo (GEFIXT + GEPUSHT)

### Issue
https://github.com/OpenSIN-Code/SIN-Browser-Tools/issues/3

---

## Zusammenfassung der Probleme

| # | Problem | Ursache | Status |
|---|---------|---------|--------|
| 1 | OOPIF-Fix scannt GMX iframes nicht | Same-process iframes, kein eigener CDP target | Offen |
| 2 | Email-Liste nicht im AXTree | SPA mounted erst bei User-Interaction | Offen |
| 3 | SID confusion | Alte vs neue SID, Session Recovery nötig | Offen |
| 4 | Tool-Einsatz ohne Verstehen | Ich wusste nicht dass OOPIF != same-process iframe | Fix nötig |

---

## Nächste Schritte (für Issue)

1. **Test mit frischer Navigation**: `goto("E-Mail")` button click statt reload
2. **SPA-Wartezeit erhöhen**: GMX Email-UI braucht 10-15s nach Navigation
3. **Shadow DOM traversal**: `pierce=True` sollte Shadow DOM können, aber GMX nutzt möglicherweise `attachShadow({mode: 'closed'})`
4. **Alternative**: GMX MailCheck Extension nutzen (hat Zugriff auf OOPIFs)

---

## Relevant Files
- `GMX_OOPIF_PROBLEM.md` - Vorherige Analyse
- Chrome Profile 73: `/Users/simoneschulze/Library/Application Support/Google Chrome`
- Aktiver GMX Tab: ID `43FB2DCED5E0F74BC0A331D9D9729142`
- Aktiver SID: `496970b9954896064bc2a9b3a45a8a38fa754011859f9`