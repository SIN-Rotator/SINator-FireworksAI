# ISSUES.md — GitHub Issues Tracking

> **Alle Issues hier dokumentieren. Fixen, Kommentieren, Schließen, Erstellen.**

---

## 📋 OFFENE ISSUES

### #15: Erster erfolgreicher API-Key (2026-05-11)
**Status:** ✅ GELÖST
**Title:** Erster erfolgreicher API-Key: blaze-scorpion-746

**Ergebnis:**
- GMX Alias: `blaze-scorpion-746@gmx.de`
- Fireworks Account: `blaze-scorpion-746@gmx.de`
- API Key: `fw_4SyZoeCFsyn5L4hpT63LGV`
- Credits: $6.00

**Learnings:**
- CUA Driver primär, CDP nur für React Inputs
- Pre-Flight Check vor jedem Klick
- GMX Extension für Email (NICHT lightmailer)

**Commit:** `feat: Komplette Dokumentation überarbeitet + Command Registry erstellt`

---

### #14: MD Dateien vollständig korrigiert (2026-05-11)
**Status:** ✅ GELÖST
**Title:** MD Dateien vollständig korrigiert

**Geändert:**
- README.md: CUA primär, GMX Extension, API Endpoints
- banned.md: Chrome Start mit Original-Profil 901

**Commit:** `docs: MD Dateien vollständig korrigiert`

---

### #13: Pool Format korrigiert (2026-05-11)
**Status:** ✅ GELÖST
**Title:** fireworksai-pool.json Format korrigiert

**Problem:** Pool wurde von dict zu list konvertiert beim Hinzufügen von Test-Key.

**Lösung:** Pool manuell auf Plain List Format zurückgesetzt.

---

## 📋 GESCHLOSSENE ISSUES

### #12: Flow 0 Session Recovery (2026-05-10)
**Status:** ✅ GELÖST
**Title:** GMX Login Flow hat sich geändert — Shadow DOM

**Problem:** ACCOUNT-AVATAR ist jetzt Custom Element mit Shadow DOM.

**Lösung:** JS `.click()` + `.dispatchEvent()` auf Custom Element.

**Files:**
- `agent_toolbox/core/gmx_service.py` — `_click_profile_icon_and_action()`

---

### #11: Flow #1 Breakdown Recovery (2026-05-10)
**Status:** ✅ GELÖST
**Title:** Flow #1 komplett gebrochen

**Problem:** Agent versuchte "DOM exploration" → rewrite `_navigate_to_all_email_addresses`

**Recovery:** 11 Dateien reverted auf commit `cf146a6`

**Learn:** ONCE VERIFIED = READ-ONLY

---

### #10: GMX OTP URL Discovery (2026-05-10)
**Status:** ✅ GELÖST
**Title:** GMX nutzt zwei URL-Formate für Mail

**Problem:** SPA hash URL zeigt PUBLIC content, nicht LOGGED-IN inbox.

**Lösung:** Navigate zu `navigator.gmx.net/mail?sid=<SID>` direkt.

---

## 📋 NEUE ISSUES ERSTELLEN

Template:
```markdown
### #XX: [Titel] ([Datum])
**Status:** 🆕 OFFEN
**Title:** 

**Problem:**


**Lösung (wenn bekannt):**


**Files betroffen:**


---
```

---

## 📋 AKTUELLE PRIORITÄTEN

1. **Pool erweitern** — Mehr API Keys generieren
2. **Rotation automatisieren** — POST /rotation/full testen
3. **Command Registry Auto-Update** — Nach jedem Erfolg/Fehler

---

## 📋 BEKANNTE PROBLEME (NOCH NICHT GELÖST)

- Keine weiteren bekannten Probleme

---

*Letzte Aktualisierung: 2026-05-11*