# Fix GMX Alias Creation + Fireworks Flow — Plan

> **⚠️ ARCHIVED — This fix was implemented and verified 2026-05-21.**
> Current flow uses V8+ Playwright+CUA hybrid with New-Tab iframe approach.
> See AGENTS.md for the latest working flow. Kept for historical reference only.

## Problem
Raw CDP kann Cross-Origin-Iframes (`3c.gmx.net`) nicht handlen.
Alle DOM.getBoxModel Calls returnen stale NodeIDs (0).

## Lösung: Playwright + CUA Hybrid
CUA für Navigation + React-Checkbox. Playwright für Form-Interaktion.

## Resultat (2026-05-21)

### ✅ COMPLETE FLOW VERIFIED
```
GMX Rotation (19.8s) → Fireworks Signup → GMX Email Verify → Login
→ Onboarding (CUA) → Use-Case + $5 → API Key: fw_8d1PLFjvQMdgJFzjDZSTRx
```

### ✅ GMX Alias Rotation
- [x] CUA Navigation (E-Mail Link → Einstellungen → allEmailAddresses)
- [x] Delete: `.table_field:has-text()` hover(force=True) → `[title*="löschen"]` click(force=True) → CUA OK
- [x] Create: `input[type="text"]` fill → `button:has-text("Hinzufügen")` click → verify empty input
- [x] 3/3 successful, 19.8s average

### ✅ Fireworks Flow
- [x] Verify-URL aus GMX MailCheck Extension + CDP OOPIF extrahiert
- [x] Account bestätigt (server-seitig)
- [x] Login: `/login` → "Email Login" → `input[name="email"]` → onboarding
- [x] Onboarding via CUA: names (type_text) + Terms-CB (AXPress) + Continue
- [x] Use-Case + $5 Credits via CUA: checkboxes + Submit
- [x] API Key: `/settings/users/api-keys` → PopUpButton → menuitem → Generate
- [x] API Key extrahiert: `fw_8d1PLFjvQMdgJFzjDZSTRx`

### Key Learnings
- Fireworks Login-Form: `input[name="email"]` (KEIN `type`-Attribut!)
- React-Checkbox: Playwright `check()` + JS `click()` ignoriert → NUR CUA `AXPress`
- Cookie-Banner MUSS vor Form-Suche dismissed werden
- Onboarding-Reihenfolge: ALLE Felder zuerst → DANN Terms-CB → DANN Continue
- Continue redirects to login after onboarding → must login again
- API Keys URL: `/settings/users/api-keys` (nicht `/settings/workspace/api-keys`)
- `text=CREATE` matched Cookie-Banner — spezifischere Selektoren!
- IAC: Direkte Navigation zu 3c.gmx.net URLs trigger Anti-Automation
- `_re` import muss in JEDER Funktion sein (nicht nur global)
- CUA Names: "First"+"Last" suchen, NICHT "Name" (matched Company Name zuerst!)
- CUA element indices sind LABILE → immer text-based scan
- `pkill -9 -f "Google Chrome"` killt User Chrome → SIGTERM via `kill`

### Banned Approaches
- CDP `DOM.performSearch` + `getBoxModel` (nodeId=0 in cross-origin iframes)
- Playwright `check()` auf React-Checkbox ("did not change state")
- JS `.click()` auf React-Button (dispatchEvent ignoriert)
- Direct URL navigation to `3c.gmx.net` → IAC restart
- `macos-use` Agent (tool validation bug)
- Hardcodierte CUA element_index (React re-renders ändern alles)
- CUA `"Name"` statt `"First"+"Last"` (matcht Company Name zuerst)
