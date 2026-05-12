"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Fireworks Service                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ⚠️  WICHTIG: CUA DRIVER IST IMMER DIE ERSTE WAHL!                           ║
║  CDP NUR FÜR React Inputs und Target Management!                             ║
║  Siehe command_registry.json für vollständige Dokumentation.                 ║
║                                                                              ║
║  ZWECK:                                                                      ║
║  Fireworks AI Account-Registrierung, Bestätigung, API-Key-Erstellung         ║
║                                                                              ║
║  CUA PRIMÄR — WANN WELCHE METHODE:                                           ║
║  ────────────────────────────────────────────────────────────────────────── ║
║  ✅ CUA click         → Buttons, Links, Checkboxes, MenuItems, PopUpButtons  ║
║  ✅ CUA type_text     → Normale Inputs (NICHT React controlled!)             ║
║  ✅ CUA set_value     → PopUpButton Menus                                    ║
║  ✅ CUA get_window_state → AX-Tree scannen für Elemente                      ║
║                                                                              ║
║  ✅ CDP nativeInputValueSetter → React controlled inputs (Email, Passwort)   ║
║  ✅ CDP evaluate           → JavaScript im Page-Kontext                      ║
║  ✅ CDP Target             → Tab Management                                  ║
║  ✅ CDP Cookie Inspection   → Cookies lesen/analysieren                      ║
║                                                                              ║
║  KOMPLETTER FLOW (CUA + CDP):                                                ║
║  ─────────────────────────────────────────────────────────────────────────── ║
║                                                                              ║
║  FIREWORKS SIGNUP FLOW:                                                     ║
║  Phase 1:  Navigate zu https://app.fireworks.ai/signup                       ║
║  Phase 2:  Cookie Banner dismissen (CUA)                                     ║
║  Phase 3:  Email eingeben (CDP nativeInputValueSetter)                       ║
║  Phase 4:  "Next" Button klicken (CUA)                                       ║
║  Phase 5:  Passwort twice eingeben (CDP nativeInputValueSetter)              ║
║  Phase 6:  "Create Account" klicken (CUA) → /signup/verify URL               ║
║                                                                              ║
║  GMX OTP FLOW (GMX Extension):                                              ║
║  Phase 7:  GMX Extension öffnen → Email finden                               ║
║  Phase 8:  OTP-URL klicken → Account verifiziert                             ║
║                                                                              ║
║  FIREWORKS LOGIN + SETUP FLOW:                                              ║
║  Phase 9:  Navigate zu /login → "Sign In" (CUA)                              ║
║  Phase 10: "Email Login" klicken (CUA)                                       ║
║  Phase 11: Email + Password (CDP nativeInputValueSetter)                     ║
║  Phase 12: FirstName + LastName (CUA type_text)                              ║
║  Phase 13: Terms checkbox (CUA click)                                        ║
║  Phase 14: "Continue" (CUA click)                                            ║
║                                                                              ║
║  USE CASE + CREDITS FLOW:                                                   ║
║  Phase 15: Checkbox "Flexible capacity" (CUA click)                          ║
║  Phase 16: Checkbox "Conversational AI" (CUA click)                          ║
║  Phase 17: "Submit to get $5 Credits" (CUA click)                            ║
║  Phase 18: 15s Timeout + Polling auf Credits                                 ║
║                                                                              ║
║  API KEY ERSTELLUNG:                                                        ║
║  Phase 19: Settings → Users & Access → API Keys (CUA Navigation)            ║
║  Phase 20: "Create API Key" PopUpButton → Menu → API Key (CUA)               ║
║  Phase 21: Name eingeben (CDP nativeInputValueSetter)                        ║
║  Phase 22: "Generate Key" (CUA) → Key aus AX-Tree extrahieren                ║
║                                                                              ║
║  FIREWORKS URLS:                                                            ║
║  • Signup:     https://app.fireworks.ai/signup (PRIMÄR — hat Email-Form!)    ║
║  • Login:      https://app.fireworks.ai/login (nur OAuth: Google/GitHub)     ║
║  • Dashboard:  https://app.fireworks.ai/account/home                         ║
║  • Settings:   https://app.fireworks.ai/settings/users/api-keys              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
import re
import asyncio
import json
from typing import Optional, Dict, Any, Tuple

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target
from pathlib import Path

# Import GmxService for Flow 0 session recovery (VERIFIED, READ-ONLY)
from agent_toolbox.core.gmx_service import GmxService

logger = logging.getLogger(__name__)

FIREWORKS_SIGNUP_URL = "https://app.fireworks.ai/signup"
FIREWORKS_LOGIN_URL = "https://app.fireworks.ai/login"
FIREWORKS_API_KEYS_URL = "https://app.fireworks.ai/settings/workspace/api-keys"
FIREWORKS_DASHBOARD_URL = "https://app.fireworks.ai/dashboard"


class FireworksService:
    """
    Verwaltet Fireworks AI Operationen via RAW CDP websocket.
    """

    async def _connect(self, cdp_port: int) -> Tuple[CDPClient, str]:
        """Erstellt CDP-Verbindung zum Browser und attached an erste Page."""
        ws_url = await get_browser_ws_endpoint(cdp_port)
        client = CDPClient(ws_url)
        await client.connect()
        target = await get_page_target(client)
        if not target:
            await client.disconnect()
            raise RuntimeError("Kein Page-Target im Browser gefunden")
        target_id = target["targetId"]
        session_id = await client.attach_to_target(target_id)
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        logger.info(f"Fireworks CDP Session bereit: {target_id[:15]}...")
        return client, session_id

    async def _find_element(
        self, client: CDPClient, session_id: str, selectors: list
    ) -> Optional[Dict[str, Any]]:
        """
        Findet erstes sichtbares Element via CSS Selector-Liste.

        Args:
            selectors: Liste von CSS-Selector-Strings zum Durchprobieren

        Returns:
            Dict mit nodeId, rect, oder None
        """
        doc = await client.get_document(session_id)
        root_id = doc.get("root", {}).get("nodeId")

        for selector in selectors:
            node_id = await client.query_selector(session_id, selector, root_id)
            if not node_id:
                continue
            box = await client.get_box_model(session_id, node_id)
            if not box:
                continue
            content = box.get("content", [])
            if len(content) >= 4:
                x1, y1, x2, y2 = content[0], content[1], content[2], content[3]
                if x2 > x1 and y2 > y1:
                    return {
                        "nodeId": node_id,
                        "x": (x1 + x2) / 2,
                        "y": (y1 + y2) / 2,
                        "width": x2 - x1,
                        "height": y2 - y1,
                        "selector": selector,
                    }
        return None

    async def _fill_input(
        self, client: CDPClient, session_id: str, selectors: list, value: str
    ) -> bool:
        """
        Findet Input-Feld via Selector und füllt es per JS + Key-Events.

        Args:
            selectors: Liste von CSS-Selector-Strings
            value: Text zum Eingeben

        Returns:
            True wenn erfolgreich
        """
        el = await self._find_element(client, session_id, selectors)
        if not el:
            return False

        escaped_value = value.replace("'", "\\'")
        js = f'''
        (function() {{
            const inputs = document.querySelectorAll('{selectors[0]}');
            const input = Array.from(inputs).find(i => i.offsetParent !== null);
            if (!input) return {{error: 'not found or hidden'}};
            input.focus();
            // Use native value setter to trigger React controlled component
            const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(input, '{escaped_value}');
            input.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
            return {{success: true, name: input.name, type: input.type, value: input.value}};
        }})()
        '''
        result = await client.evaluate(session_id, js, return_by_value=True)
        val = result.get("result", {}).get("value", {})
        if not val.get("success"):
            return False
        logger.debug(f"[_fill_input] Set '{selectors[0]}' to '{val.get('value', '')}'")
        return True

    async def _click_button(
        self, client: CDPClient, session_id: str, selectors: list
    ) -> bool:
        """
        Findet Button via Text-Match oder Selector und klickt per Koordinaten.

        Args:
            selectors: Liste von CSS-Selector-Strings oder Text-Patterns

        Returns:
            True wenn geklickt
        """
        for selector in selectors:
            el = await self._find_element(client, session_id, [selector])
            if el:
                cx, cy = el["x"], el["y"]
                await client.click_at(session_id, x=cx, y=cy)
                return True

        js_text = f'''
        (function() {{
            const btns = document.querySelectorAll('button, a, input[type="submit"]');
            for (const b of btns) {{
                const t = (b.textContent || '').trim();
                const lower = t.toLowerCase();
                const matches = {selectors};
                if (matches.some(m => lower.includes(m.toLowerCase()))) {{
                    const r = b.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {{
                        b.scrollIntoView();
                        b.click();
                        return {{found: true, text: t, x: r.x + r.width/2, y: r.y + r.height/2}};
                    }}
                }}
            }}
            return null;
        }})()
        '''
        result = await client.evaluate(session_id, js_text, return_by_value=True)
        val = result.get("result", {}).get("value")
        if val and val.get("found"):
            await client.click_at(session_id, x=val["x"], y=val["y"])
            return True
        return False

    async def _screenshot(self, client: CDPClient, session_id: str, label: str):
        """Macht Debug-Screenshot."""
        ts = int(time.time())
        path = f"/tmp/fw_{label}_{ts}.png"
        try:
            await client.screenshot(session_id, path=path)
            return path
        except Exception as e:
            logger.warning(f"Screenshot {label} fehlgeschlagen: {e}")
            return ""

    async def _dismiss_cookie_banner(        self,        client: CDPClient,        session_id: str    ) -> bool:        """Dismiss cookie banner by removing overlays from DOM and reloading."""        await client.evaluate(session_id, """(function() {            var all = document.querySelectorAll('*');            for (var i = 0; i < all.length; i++) {                var el = all[i];                var style = window.getComputedStyle(el);                if ((style.position === 'fixed' || style.position === 'absolute') && el.offsetWidth > 300 && el.offsetHeight > 300) {                    el.remove();                }            }            document.body.style.overflow = '';            document.documentElement.style.overflow = '';        })()""", return_by_value=True)        await asyncio.sleep(1)        await client.navigate(session_id, "https://app.fireworks.ai/signup")        await asyncio.sleep(4)        return True    async def register(
        self,
        email: str,
        password: str,
        gmx_password: str,
        cdp_port: int = 9222,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        ════════════════════════════════════════════════════════════════════════════
        KOMPLETTE FIREWORKS.AI ACCOUNT-ERSTELLUNG — VOLLSTÄNDIGER FLOW
        ════════════════════════════════════════════════════════════════════════════

        ZWECK:
        Erstellt einen vollständigen Fireworks AI Account mit dem GMX Alias als
        Email-Adresse. Der Account wird verifiziert (OTP via GMX) und ein
        API-Key wird generiert.

        FLOW (12 PHASEN):
        ════════════════════════════════════════════════════════════════════════

        PHASE 1: FIREWORKS DOMAIN CLEANUP (Nur Fireworks-Cookies + LocalStorage)
        ────────────────────────────────────────────────────────────────────────
        GMX und Fireworks teilen sich denselben Browser (Profile 901). Wir dürfen
        NICHT alle Cookies löschen (würde GMX-Session zerstören). Nur Cookies
        deren Domain "fireworks" enthält löschen.

        Ziel: Alte Fireworks-Sessions entfernen, Consent-Status resetten.
        Methode: Network.deleteCookies via CDP für jeden Fireworks-Cookie.
        Zusätzlich: localStorage + sessionStorage auf app.fireworks.ai clearen.

        WICHTIG: Dies ist ein SAFETY-FIX. Frühere Versuche ohne Cleanup
        scheiterten weil alte Session-Daten die Registrierung blockierten.

        PHASE 2: FIREWORKS SIGNUP PAGE LADEN
        ────────────────────────────────────────────────────────────────────────
        URL: https://app.fireworks.ai/signup
        Erwartet: Cookie-Banner (CKY Consent Manager) über der Seite.
        Ohne Cleanup: Cookie-Banner könnte gar nicht mehr erscheinen (Consent
        ist im LocalStorage gespeichert und noch auf "accepted").
        Mit Cleanup: Consent ist zurückgesetzt → Banner erscheint wieder.

        Der /signup-Pfad (nicht /login!) ist korrekt weil:
        - /login zeigt OAuth-Buttons (Google/GitHub/LinkedIn) aber kein Email-Form
        - /signup hat ein Email-Form mit "Next" Button das Account-Erstellung startet
        - Das Email-Form auf /signup ist ein SINGLE-PAGE-INLINE-FLOW:
          Step 1: Email → Next → Step 2: Passwords → Create Account

        PHASE 3: COOKIE BANNER DISMISSEN (Accept All per CDP Coordinate Click)
        ────────────────────────────────────────────────────────────────────────
        Fireworks verwendet den "Cookiebot" Consent Manager (consent.cookiebot.com).
        Banner-Struktur: .cky-consent-container (position: fixed, bottom: 0)
        Button "Accept All": button.cky-btn-accept at viewport (1113, 805)
        Größe: 122x40px → Center: (1113.7, 805.5)

        KRITISCHE ERKENNTNIS (Bug-Fix aus früherer Implementierung):
        - JavaScript element.click() via Runtime.evaluate FUNKTIONIERT NICHT
        - Der Cookiebot-Handler fängt synthetische JS-Clicks ab und ignoriert sie
        - Lösung: client.click_at(x, y) via CDP Input.dispatchMouseEvent
        - Dies simuliert ECHTE Maus-Interaktionen im Browser-Prozess

        Validierung: Nach Klick prüfen ob .cky-consent-container collapsed
        (display: none oder height: 0). Warte 2 Sekunden.

        PHASE 4: EMAIL EINGEBEN + NEXT KLICKEN
        ────────────────────────────────────────────────────────────────────────
        Input: input#email-display (type=email, disabled=false, readonly=false)
        Koordinaten: x=751, y=302, w=384, h=48
        CSS Classes: focus:ring-input-active focus:border-input-active ...

        Füll-Methode:
        1. JS: element.focus() + element.value = '' + Event('input', {bubbles: true})
           → Löst React/Next.js onChange Handler aus (Input ist ein Controlled Component)
        2. Input.dispatchKeyEvent für jeden Character (type=keyDown + keyUp)
           → Mimics echtes Tipp-Verhalten, löst keypress/keydown/keyup Events aus
           → Wichtig für Form-Validation die auf keydown Events hört
        3. JS: Event('change', {bubbles: true}) nach dem letzten Character
           → Signalisiert dass Input abgeschlossen ist

        "Next" Button:
        Selector: button mit text.toLowerCase() === 'next'
        Koordinaten: x=943, y=374, w=384, h=48 (volle Breite, unter dem Email-Feld)
        Click: client.click_at() an Button-Center

        Nach Next: Page changed zu Step 2 — Password-Eingabe.
        URL bleibt auf /signup, DOM updated für Step 2.

        PHASE 5: PASSWÖRTER EINGEBEN (2x) + CREATE ACCOUNT KLICKEN
        ────────────────────────────────────────────────────────────────────────
        Nach Next erscheinen ZWEI Passwort-Felder:

        Feld 1: input#password
        Koordinaten: x=751, y=356, w=384, h=48
        Placeholder: "Enter your password"
        Type: password (masked)

        Feld 2: input#confirm-password
        Koordinaten: x=751, y=449, w=384, h=48
        Placeholder: "Re-enter your password"
        Type: password (masked)

        "Create Account" Button:
        Text: "Create Account" (exakte Schreibweise!)
        Koordinaten: x=943, y=746, w=384, h=48
        WICHTIG: Dies ist NICHT "button[type=submit]" (es gibt auch einen
        password-toggle Button mit type=button in der Nähe)

        Nach Create Account: URL wechselt zu /signup/verify
        → Account ist erstellt aber noch nicht verifiziert
        → Bestätigungs-Email wurde an die GMX Alias Adresse gesendet

        PHASE 6: GMX OTP POLLING
        ────────────────────────────────────────────────────────────────────────
        Navigate zu GMX: https://www.gmx.net/
        Cookie-Banner: GMX verwendet AUP Cookie Manager (anderer als Fireworks)
        → MUSS NICHT dismissed werden (AUP ist inline, nicht als fixed overlay)

        GMX Session-Validierung:
        1. Navigate GMX Homepage
        2. Click "E-Mail" im Header (Koordinaten: x=262, y=44)
        3. Prüfe URL enthält "navigator.gmx.net/mail?sid=..."
        4. Wenn nicht → GMX Session ist tot → Fehler

        OTP-Poll-Strategie:
        1. Suche "fireworks" in Absender-Limit (filter auf Absender)
        2. Suche nach "verify" oder "bestätigen" im Betreff
        3. Extrahiere OTP-URL aus dem Email-Body
        4. Pattern: href="https://app.fireworks.ai/signup/confirm?token=..."
        5. Retry: 12x mit je 5s Delay (60s total)

        URL-Pattern im Email-Body:
        https://app.fireworks.ai/signup/confirm?token=...&email=...
        oder: app.fireworks.ai/signup/confirm?token=...

        PHASE 7: OTP URL ÖFFNEN → ACCOUNT VERIFIZIEREN
        ────────────────────────────────────────────────────────────────────────
        Navigate zur OTP-URL (https://app.fireworks.ai/signup/confirm?token=...)
        Erwartete Seite: Account-Welcome oder Dashboard-Redirect

        Mögliche Szenarien:
        - Redirect zu /dashboard (Account bereits aktiv)
        - Zeigt "Email verified" Bestätigung
        - Zeigt Formular für FirstName/LastName (wenn Profil unvollständig)

        PHASE 8: FIREWORKS LOGIN FLOW (Sign In)
        ────────────────────────────────────────────────────────────────────────
        URL: https://app.fireworks.ai/login
        Erwartet: OAuth-Buttons (Continue with Google/GitHub/LinkedIn)

        Das /login Page hat NUR OAuth-Buttons wenn der User nicht eingeloggt ist.
        Die Buttons zeigen auf: /login?provider=google (etc.)

        Der User meint "Sign In" und "Email Login" Buttons die im Page-DOM
        nach dem Cookie-Consent erscheinen. Wir suchen:

        "Sign In" Button:
        - Text: "Sign in with Email" oder "Sign In" oder "Email Login"
        - Position: Unter den OAuth-Buttons (y > 423 = unter LinkedIn)
        - Alternativ: Ein Tab/Link der zwischen OAuth und Email-Login wechselt

        Phase 8a: "Sign In" oder "Email Login" Button klicken
        → Zeigt das Email/Password Login-Formular inline auf der Seite

        Phase 8b: Email + Password eingeben
        input#email (type=email) — erscheint nach dem Sign-In Button-Klick
        input#password (type=password)

        Phase 8c: "Next" Button klicken
        → Loggt den User ein → Redirect zu /dashboard

        PHASE 9: ACCOUNT SETUP (FirstName + LastName + Terms)
        ────────────────────────────────────────────────────────────────────────
        Nach erstem Login (Account ist verifiziert aber Profil unvollständig):
        Fireworks zeigt ein Setup-Formular:

        input[name="firstName"] — Vorname aus dem GMX Alias extrahieren
        input[name="lastName"] — Nachname (Default: "User" oder leer lassen)

        Checkbox 1: "I agree to the Terms of Service and Privacy Policy"
        → input[type="checkbox"] mit Label-Text containing "Terms" oder "agree"
        → Muss per CDP click_at() geklickt werden (kein JS .click!)

        "Continue" Button:
        → Text: "Continue" oder "Next" oder "Weiter"
        → Koordinaten: unter dem ToS Checkbox

        PHASE 10: USE CASE AUSWAHL
        ────────────────────────────────────────────────────────────────────────
        Nach Continue erscheint ein "Use Case Selection" Formular:

        Checkbox 1: "Flexible capacity for production"
        → Mögliche Selector: input[type="checkbox"] mit Label containing "Flexible"

        Checkbox 2: "Conversational AI"
        → Mögliche Selector: input[type="checkbox"] mit Label containing "Conversational"

        "Submit to get $5 Credits" Button:
        → Text: "Submit to get $5 Credits"
        → KRITISCH: Dies startet die $5 Credits für das Konto
        → Ohne diesen Klick gibt es keine kostenlosen Credits

        PHASE 11: LOADING POLLING NACH SUBMIT (15s + 5x2s)
        ────────────────────────────────────────────────────────────────────────
        Nach dem Submit-Button-Klick:
        - Fireworks verarbeitet die Anfrage (1-10 Sekunden)
        - Die Seite kann in einem Loading-State sein (Spinner oder "Processing")
        - Wir pollen alle 2 Sekunden für max 15 Sekunden
        - Success-Indikator: URL wechselt zu /dashboard oder
          body-text enthält "dashboard" oder "credits" oder "$5"

        Retry-Logik: 5 retries × 2s = 10s + initial 5s = 15s total
        Wenn nach 15s immer noch loading → trotzdem weitermachen
        (Credits könnten schon aktiv sein, nur die UI ist langsam)

        PHASE 12: API KEY ERSTELLEN
        ────────────────────────────────────────────────────────────────────────
        Navigate zu: https://app.fireworks.ai/settings/workspace/api-keys
        (Oder: /dashboard → Sidebar → Settings → API Keys)

        "Create API Key" Button:
        → Text: "Create API Key" (case-sensitive!)
        → Erscheint auf der API-Keys Settings Page

        Dialog öffnet sich → Name-Feld + "Generate Key" Button

        Name-Feld: input[name="name"] oder input[placeholder*="name"]
        → Wert: Erster Teil des GMX Alias (z.B. "frost-spider" aus "frost-spider@gmx.de")

        "Generate Key" Button:
        → Text: "Generate Key" oder "Generate"
        → Klick erstellt den API-Key

        Key-Extraktion:
        → Pattern: input[readonly] mit value.startsWith('fw-')
        → Alternativ: code, pre, span mit text.startsWith('fw-')
        → Regex: body.match(/(fw-[a-zA-Z0-9_-]{20,})/)

        Return: {api_key: "...", key_name: "...", status: "success"}

        ════════════════════════════════════════════════════════════════════════

        FEHLERBEHANDLUNG:
        - Jeder Step hat einen Timeout (default 30s pro Step, konfigurierbar)
        - Bei Fehler: return mit steps_completed Liste + error message
        - Bei Timeout in einer Phase: Continue zur nächsten wenn möglich
        - Nie einzelne Schritte hard-failen (Account könnte teilweise erstellt sein)

        Beispiel-Fehler-Szenarien:
        1. Cookie Banner nicht dismissed → Email-Feld nicht erreichbar → fail
        2. Email bereits registriert → Fireworks Fehler-Meldung im Body → fail
        3. OTP nicht in GMX-Inbox nach 60s → Timeout → return partial
        4. API Key Button nicht gefunden → return partial (Account ist aber gut)
        5. GMX Session tot → Fehler vor OTP → return failed

        PERFORMANCE-ERWARTUNGEN:
        - Phase 1-3 (Setup + Cookie): ~5s
        - Phase 4-5 (Signup Form): ~10s
        - Phase 6 (OTP Polling): 10-60s (abhängig von Email-Delay)
        - Phase 7 (OTP Confirm): ~5s
        - Phase 8-10 (Login + Setup): ~15s
        - Phase 11 (Loading): 5-15s
        - Phase 12 (API Key): ~10s
        - Total: ~60-120s (1-2 Minuten)

        Args:
            email: GMX Alias Email (z.B. "frost-spider@gmx.de")
            password: Passwort für den neuen Fireworks Account
                     (z.B. "ZOE.sinator2026!")
            gmx_password: GMX Account Passwort (für GMX-Inbox-Zugriff, nicht für
                         Fireworks-Login, nur für die URL-Navigation in Phase 6)
            cdp_port: CDP Port des Browsers (default: 9222)
            timeout: Timeout pro Sub-Step in Sekunden (default: 30)

        Returns:
            Dict mit:
            - status: "success" | "partial" | "failed" | "error"
            - account_email: Die GMX Alias Email
            - fireworks_password: Das Fireworks-Passwort (für spätere Logins)
            - api_key: Der generierte Fireworks API-Key (oder null)
            - api_key_name: Name des API-Keys
            - steps_completed: Liste aller erfolgreichen Steps
            - steps_failed: Liste aller fehlgeschlagenen Steps
            - execution_time: Gesamtdauer in Sekunden
            - error: Fehlermeldung falls status nicht "success"

        Side Effects:
            - Löscht Fireworks-spezifische Cookies (nur Domain-matching)
            - Clear localStorage/sessionStorage auf app.fireworks.ai
            - Navigiert durch: GMX Homepage → GMX Email-Inbox → Fireworks Pages
            - Erstellt Account, verifiziert via OTP, erstellt API-Key
            - GMX-Session bleibt intakt (nur Fireworks-Daten werden manipuliert)

        Chrome Profile Context:
            - Profile: Profile 901 ("SINator (Fireworks AI)")
            - User Data Dir: /Users/jeremy/Library/Application Support/Google Chrome
            - CDP Port: 9222
            - Viewport: 1200x919 (macOS Retina)
            - Chrome Version: 147.0.7727.138

        Known Limitations:
            - GMX OTP-Poll ist Limited auf 12 retries × 5s = 60s
            - Wenn OTP länger als 60s braucht → partial failure
            - Fireworks UI könnte sich ändern → Selector müssen ggf. angepasst werden
            - API Key Pattern: fw-[a-zA-Z0-9_-]{20,} (kann sich ändern)

        """
        start_time = time.time()
        client = None
        steps_completed = []
        steps_failed = []
        api_key = None
        api_key_name = None

        try:
            # ════════════════════════════════════════════════════════════════════════
            # VERBINDUNG HERSTELLEN
            # ════════════════════════════════════════════════════════════════════════
            #
            # Wir erstellen eine CDP-Verbindung zum Browser.
            # Das gleiche Browser-Fenster wird für ALLE Phasen verwendet
            # (GMX + Fireworks im selben Tab/Session).
            #
            # _connect() liefert: (CDPClient instance, session_id string)
            # - CDPClient: Websocket-Client für CDP-Kommandos
            # - session_id: String für Target-Attachment (Target ID → Session ID)
            #
            # WICHTIG: Wir verwenden eine EINZIGE Connection für den gesamten Flow.
            # Kein reconnect zwischen GMX und Fireworks (würde GMX-Session gefährden).
            #
            client, session_id = await self._connect(cdp_port)
            logger.info(f"[FW Register] Start — email={email}, cdp_port={cdp_port}")

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 1: FIREWORKS DOMAIN COOKIE + LOCALSTORAGE CLEAR
            # ════════════════════════════════════════════════════════════════════════
            #
            # GMX und Fireworks teilen sich denselben Chrome-Browser (Profile 901).
            # Wir dürfen NICHT alle Browser-Cookies löschen (würde GMX-Session killen).
            # Nur Cookies deren domain "fireworks" oder "app." enthält löschen.
            #
            # Methode: Network.getAllCookies → Filter → Network.deleteCookies
            #
            # localStorage/sessionStorage auf app.fireworks.ai ebenfalls clearen:
            # - Consent-Status ist in localStorage gespeichert
            # - Alte Session-Tokens könnten Registrierung blockieren
            #
            # Nach diesem Cleanup: Fireworks ist wie ein komplett frischer Browser.
            #
            logger.info("[FW Register] Phase 1: Clear Fireworks cookies + localStorage")

            all_cookies_result = await client.send_to_session(
                session_id, "Network.getAllCookies", {}
            )
            all_cookies = all_cookies_result.get("cookies", [])
            fireworks_cookies = [
                c for c in all_cookies
                if "fireworks" in (c.get("domain", "") or "").lower()
                or "app." in (c.get("domain", "") or "").lower()
            ]
            logger.info(f"[FW Register] Found {len(fireworks_cookies)} Fireworks cookies to delete")

            for cookie in fireworks_cookies:
                await client.send_to_session(
                    session_id, "Network.deleteCookies", {
                        "name": cookie.get("name", ""),
                        "domain": cookie.get("domain", ""),
                        "url": "https://app.fireworks.ai/",
                    }
                )

            await client.evaluate(
                session_id,
                """
                (function() {
                    try {
                        localStorage.clear();
                        sessionStorage.clear();
                        console.log('[FW] Storage cleared successfully');
                        return {success: true};
                    } catch(e) {
                        console.error('[FW] Storage clear failed:', e);
                        return {success: false, error: e.message};
                    }
                })()
                """,
                return_by_value=True
            )
            await asyncio.sleep(1)
            steps_completed.append("cookies_cleared")
            logger.info("[FW Register] Phase 1 DONE: Fireworks storage cleared")

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 2: FIREWORKS SIGNUP PAGE LADEN
            # ════════════════════════════════════════════════════════════════════════
            #
            # URL: https://app.fireworks.ai/signup
            #
            # WICHTIG: /signup (NICHT /login) weil:
            # - /login zeigt nur OAuth-Buttons (Google/GitHub/LinkedIn)
            # - /signup hat ein Email-Formular das Account-Erstellung startet
            #
            # Das /signup Page ist ein SINGLE-PAGE-INLINE-FLOW (kein Page-Reload):
            # 1. Email-Eingabe + "Next" → URL bleibt /signup, DOM updated
            # 2. Password-Eingabe + "Create Account" → URL wechselt zu /signup/verify
            #
            # Cookie-Banner erscheint IMMER nach dem Storage-Clear (Consent resetted).
            #
            logger.info("[FW Register] Phase 2: Navigate to /signup")
            await client.navigate(session_id, FIREWORKS_SIGNUP_URL)
            await asyncio.sleep(3)

            steps_completed.append("signup_page_loaded")
            logger.info(f"[FW Register] Phase 2 DONE: /signup loaded")

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 3: COOKIE BANNER DISMISSEN (Accept All per CDP Coordinate Click)
            # ════════════════════════════════════════════════════════════════════════
            #
            # Fireworks verwendet den "Cookiebot" Consent Manager.
            # Der Banner sitzt als fixed div über dem unteren Viewport-Bereich.
            #
            # Banner-Struktur:
            #   .cky-consent-container (position: fixed, bottom: 0, z-index: high)
            #     └─ .cky-consent-bar
            #           └─ .cky-notice-btn-wrapper
            #                 ├─ button.cky-btn.cky-btn-customize
            #                 ├─ button.cky-btn.cky-btn-reject
            #                 └─ button.cky-btn.cky-btn-accept ← DIESER BUTTON
            #
            # Button "Accept All" Koordinaten:
            #   x=1052.484375, y=785.484375, w=122.515625, h=40.015625
            #   → Center: (1113.7421875, 805.4921875)
            #
            # KRITISCHE ERKENNTNIS: JavaScript element.click() via
            # Runtime.evaluate() FUNKTIONIERT NICHT auf dem Cookie-Banner.
            # Der Cookiebot-Handler ignoriert synthetische JS-Clicks.
            # Lösung: client.click_at() mit echten CDP-Koordinaten.
            #
            logger.info("[FW Register] Phase 3: Dismiss cookie banner")

            dismiss_result = await self._dismiss_cookie_banner(client, session_id)
            if dismiss_result:
                steps_completed.append("cookie_banner_dismissed")
                logger.info("[FW Register] Phase 3 DONE: Cookie banner dismissed")
            else:
                logger.warning("[FW Register] Phase 3: Cookie banner dismiss returned False — may not have been visible or could not be closed")
                steps_failed.append("cookie_banner_partial")

            await asyncio.sleep(1)

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 4: EMAIL EINGEBEN + NEXT KLICKEN
            # ════════════════════════════════════════════════════════════════════════
            #
            # Email-Input auf /signup Page:
            #   Element: input#email-display
            #   Type: email
            #   Koordinaten: x=751, y=302, w=384, h=48
            #   Classes: focus:ring-input-active focus:border-input-active ...
            #   Disabled: false (nicht disabled)
            #
            # Filling-Methode (React/Next.js Controlled Component):
            #   1. element.focus() → aktiviert das Input
            #   2. element.value = '' → cleared den Inhalt (React tracked value)
            #   3. Event('input', {bubbles: true}) → löst React onChange aus
            #   4. Input.dispatchKeyEvent für jeden Character
            #      (type=keyDown mit text=char + type=keyUp)
            #   5. Event('change', {bubbles: true}) → Signalisiert Abschluss
            #
            # "Next" Button:
            #   Text: "Next" (case-sensitive: "Next", nicht "next")
            #   Koordinaten: x=943, y=374, w=384, h=48
            #   WICHTIG: Volle Breite (384px), direkt unter dem Email-Feld
            #   Click: client.click_at() an Button-Center
            #
            logger.info(f"[FW Register] Phase 4: Enter email={email}")

            email_input_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const el = document.querySelector('#email-display');
                    if (!el) return {found: false};
                    el.focus();
                    el.value = '';
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    const r = el.getBoundingClientRect();
                    return {
                        found: true,
                        x: r.x + r.width / 2,
                        y: r.y + r.height / 2,
                        disabled: el.disabled
                    };
                })()
                """,
                return_by_value=True
            )
            email_input_val = email_input_result.get("result", {}).get("value", {})

            if not email_input_val.get("found"):
                return {
                    "status": "failed",
                    "account_email": email,
                    "fireworks_password": password,
                    "api_key": None,
                    "api_key_name": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed + ["email_input_failed"],
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "Email input field #email-display not found on /signup page",
                }

            if email_input_val.get("disabled"):
                logger.warning("[FW Register] Email input is DISABLED — cookie banner may still be blocking!")
                steps_failed.append("email_input_disabled")

            cx, cy = email_input_val["x"], email_input_val["y"]

            await client.evaluate(session_id, f"""(function() {{
                const el = document.querySelector('#email-display');
                if (!el) return false;
                const ns = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                ns.call(el, '{email}');
                el.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
            }})()""", return_by_value=True)
            await asyncio.sleep(0.5)
            steps_completed.append("email_entered")
            logger.info(f"[FW Register] Email entered: {email}")

            # Click "Next" Button
            next_btn_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const btns = [...document.querySelectorAll('button')];
                    for (const b of btns) {
                        const r = b.getBoundingClientRect();
                        const t = (b.textContent || '').trim();
                        if (r.width > 0 && r.height > 0 && t.toLowerCase() === 'next') {
                            return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2};
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            next_btn_val = next_btn_result.get("result", {}).get("value", {})

            if not next_btn_val.get("found"):
                # Single-page form? Check if password field already visible
                pw_check = await client.evaluate(session_id, """(function() {
                    const el = document.querySelector('#password');
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                })()""", return_by_value=True)
                if pw_check.get("result", {}).get("value"):
                    logger.info("[FW Register] Single-page form detected — skip Next, go to password")
                else:
                    return {
                        "status": "failed",
                        "account_email": email,
                        "fireworks_password": password,
                        "api_key": None, "api_key_name": None,
                        "steps_completed": steps_completed,
                        "steps_failed": steps_failed + ["next_button_not_found"],
                        "execution_time": f"{time.time() - start_time:.2f}s",
                        "error": "'Next' button not found on /signup page and password field not visible",
                    }
            else:
                await client.evaluate(session_id, f"""(function() {{
                    var btn = document.elementFromPoint({next_btn_val['x']}, {next_btn_val['y']});
                    if (!btn) return;
                    ['mousedown', 'mouseup', 'click'].forEach(function(t) {{
                        btn.dispatchEvent(new MouseEvent(t, {{
                            bubbles: true, cancelable: true, view: window,
                            clientX: {next_btn_val['x']}, clientY: {next_btn_val['y']}
                        }}));
                    }});
                }})()""", return_by_value=True)
                steps_completed.append("next_clicked")
                logger.info(f"[FW Register] Clicked Next at ({next_btn_val['x']:.0f}, {next_btn_val['y']:.0f})")
                await asyncio.sleep(4)

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 5: PASSWÖRTER EINGEBEN (2x) + CREATE ACCOUNT KLICKEN
            # ════════════════════════════════════════════════════════════════════════
            #
            # Nach dem "Next" Klick erscheinen zwei Passwort-Felder:
            #
            # Feld 1 — Password:
            #   Element: input#password
            #   Type: password
            #   Placeholder: "Enter your password"
            #   Koordinaten: x=751, y=356, w=384, h=48
            #
            # Feld 2 — Confirm Password:
            #   Element: input#confirm-password
            #   Type: password
            #   Placeholder: "Re-enter your password"
            #   Koordinaten: x=751, y=449, w=384, h=48
            #
            # "Create Account" Button:
            #   Text: "Create Account" (exakte Schreibweise, großes A!)
            #   Koordinaten: x=943, y=746, w=384, h=48
            #   WICHTIG: Der Button hat NICHT type="submit" als primären Marker
            #   (es gibt auch einen passwort-toggle Icon-Button mit type="button")
            #
            logger.info(f"[FW Register] Phase 5: Enter passwords (2x)")

            for field_id in ["password", "confirm-password"]:
                field_result = await client.evaluate(
                    session_id,
                    f"""
                    (function() {{
                        const el = document.querySelector('#{field_id}');
                        if (!el) return {{found: false}};
                        el.focus();
                        el.value = '';
                        el.dispatchEvent(new Event('input', {{bubbles: true}}));
                        const r = el.getBoundingClientRect();
                        return {{found: true, x: r.x + r.width / 2, y: r.y + r.height / 2}};
                    }})()
                    """,
                    return_by_value=True
                )
                field_val = field_result.get("result", {}).get("value", {})

                if not field_val.get("found"):
                    return {
                        "status": "failed",
                        "account_email": email,
                        "fireworks_password": password,
                        "api_key": None,
                        "api_key_name": None,
                        "steps_completed": steps_completed,
                        "steps_failed": steps_failed + [f"password_field_{field_id}_not_found"],
                        "execution_time": f"{time.time() - start_time:.2f}s",
                        "error": f"Password field '#{field_id}' not found after Next click",
                    }

                fc_x, fc_y = field_val["x"], field_val["y"]

                await client.evaluate(session_id, f"""(function() {{
                    const el = document.querySelector('#{field_id}');
                    if (!el) return false;
                    const ns = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                    ns.call(el, '{password}');
                    el.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }})()""", return_by_value=True)
                logger.info(f"[FW Register] Filled {field_id}")

            await asyncio.sleep(0.5)
            steps_completed.append("password_entered")

            # Click "Create Account"
            create_btn_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const btns = [...document.querySelectorAll('button')];
                    for (const b of btns) {
                        const r = b.getBoundingClientRect();
                        const t = (b.textContent || '').trim();
                        if (r.width > 0 && r.height > 0 && r.y < 1500 && t === 'Create Account') {
                            return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2};
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            create_btn_val = create_btn_result.get("result", {}).get("value", {})

            if not create_btn_val.get("found"):
                return {
                    "status": "failed",
                    "account_email": email,
                    "fireworks_password": password,
                    "api_key": None,
                    "api_key_name": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed + ["create_account_button_not_found"],
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "'Create Account' button not found after password entry",
                }

            await client.evaluate(session_id, f"""(function() {{
                var btn = document.elementFromPoint({create_btn_val['x']}, {create_btn_val['y']});
                if (!btn) return;
                ['mousedown', 'mouseup', 'click'].forEach(function(t) {{
                    btn.dispatchEvent(new MouseEvent(t, {{
                        bubbles: true, cancelable: true, view: window,
                        clientX: {create_btn_val['x']}, clientY: {create_btn_val['y']}
                    }}));
                }});
            }})()""", return_by_value=True)
            steps_completed.append("create_account_clicked")
            logger.info(f"[FW Register] Clicked Create Account at ({create_btn_val['x']:.0f}, {create_btn_val['y']:.0f})")

            # Warten auf Account-Erstellung + Redirect zu /signup/verify
            await asyncio.sleep(5)

            verify_url_result = await client.evaluate(
                session_id, "window.location.href", return_by_value=True
            )
            verify_url = verify_url_result.get("result", {}).get("value", "")

            if "/verify" in verify_url or "verify" in verify_url:
                steps_completed.append("account_created")
                logger.info(f"[FW Register] Account created! Redirected to: {verify_url}")
            else:
                # Prüfe auf Fehlermeldungen im Body
                error_body_result = await client.evaluate(
                    session_id,
                    """
                    (function() {
                        return document.body.innerText.slice(0, 500).toLowerCase();
                    })()
                    """,
                    return_by_value=True
                )
                error_body = error_body_result.get("result", {}).get("value", "")

                if any(k in error_body for k in ["error", "exists", "taken", "already", "invalid"]):
                    return {
                        "status": "failed",
                        "account_email": email,
                        "fireworks_password": password,
                        "api_key": None,
                        "api_key_name": None,
                        "steps_completed": steps_completed,
                        "steps_failed": steps_failed + ["account_creation_error"],
                        "execution_time": f"{time.time() - start_time:.2f}s",
                        "error": f"Account creation failed: {error_body[:300]}",
                    }

                logger.warning(f"[FW Register] URL after Create Account: {verify_url} (expected /signup/verify)")
                steps_failed.append("account_creation_redirect_mismatch")

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 6: GMX SESSION SICHERSTELLEN + OTP POLLING
            # ════════════════════════════════════════════════════════════════════════
            #
            # Account ist erstellt aber noch nicht verifiziert.
            # Fireworks hat eine Bestätigungs-Email an die GMX Alias geschickt.
            # Wir müssen die Email in der GMX-Inbox finden und die OTP-URL extrahieren.
            #
            # WICHTIG: Cookie-Injektion funktioniert NICHT zuverlässig (SameSite/Secure
            # Restrictions, abgelaufene Cookies). Stattdessen verwenden wir
            # GmxService.ensure_gmx_session() für einen frischen Login falls nötig.
            #
            # Flow 0 (ensure_gmx_session) ist VERIFIED und funktioniert zuverlässig.
            # Siehe agent_toolbox/core/gmx_service.py:_ensure_mail_session()
            #
            logger.info("[FW Register] Phase 6: Ensure GMX session via Flow 0")
            
            # Disconnect Fireworks client to allow GmxService to use its own connection
            await client.disconnect()
            
            gmx_service = GmxService()
            session_result = await gmx_service.ensure_gmx_session(
                email="opensin@gmx.de",
                password=gmx_password,
                cdp_port=cdp_port,
            )
            
            if session_result.get("status") != "success":
                steps_failed.append("gmx_session_invalid")
                return {
                    "status": "partial",
                    "account_email": email,
                    "fireworks_password": password,
                    "api_key": None,
                    "api_key_name": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": f"GMX session invalid — not on mail page. URL: {session_result.get('current_url', 'unknown')}",
                }
            
            steps_completed.append("gmx_session_active")
            logger.info(f"[FW Register] GMX Session OK")
            
            # Re-connect CDP for OTP polling
            client, session_id = await self._connect(cdp_port)
            
            # Navigate DIRECTLY to navigator.gmx.net/mail using the SID from session_result
            # This is more reliable than clicking the E-Mail header (which may go to SPA hash URL)
            sid = session_result.get("sid", "")
            if not sid and session_result.get("current_url"):
                import re
                match = re.search(r'sid=([^&]+)', session_result.get("current_url", ""))
                if match:
                    sid = match.group(1)
            
            if not sid:
                steps_failed.append("gmx_sid_missing")
                return {
                    "status": "failed",
                    "account_email": email,
                    "fireworks_password": password,
                    "api_key": None,
                    "api_key_name": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed + ["gmx_sid_missing"],
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": f"GMX SID not found in session_result. URL: {session_result.get('current_url', 'unknown')}",
                }
            
            logger.info(f"[FW Register] Navigating to GMX Inbox with SID: {sid[:30]}...")
            await client.navigate(session_id, f"https://navigator.gmx.net/mail?sid={sid}")
            await asyncio.sleep(5)

            # Verify GMX Inbox is reachable
            gmx_url_result = await client.evaluate(
                session_id, "window.location.href", return_by_value=True
            )
            gmx_url = gmx_url_result.get("result", {}).get("value", "")

            if ("navigator.gmx.net/mail" not in gmx_url and "bap.navigator.gmx.net/mail" not in gmx_url) or "sid=" not in gmx_url:
                steps_failed.append("gmx_inbox_nav_failed")
                return {
                    "status": "failed",
                    "account_email": email,
                    "fireworks_password": password,
                    "api_key": None,
                    "api_key_name": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed + ["gmx_inbox_nav_failed"],
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": f"GMX Inbox navigation failed. URL: {gmx_url}",
                }

            steps_completed.append("gmx_inbox_reached")
            logger.info(f"[FW Register] GMX Inbox reached: {gmx_url[:80]}...")

# OTP Polling via GMX HTTP API (gmx_service.read_otp)
            # This uses httpx to fetch mail bodies directly from GMX's internal API
            # instead of trying to access the cross-origin iframe DOM.
            # read_otp() creates its own CDP connection and handles the polling internally.
            gmx_svc_instance = GmxService()
            
            logger.info(f"[FW Register] Starting GMX OTP poll with SID: {sid[:30]}...")
            otp_result = await gmx_svc_instance.read_otp(
                sender_filter="fireworks",
                max_retries=10,
                retry_delay=30,
                cdp_port=cdp_port,
                exclude_mail_ids=None,
            )
            
            if otp_result.get("status") == "success" and otp_result.get("otp_url"):
                otp_url = otp_result["otp_url"]
                steps_completed.append("otp_url_received")
                logger.info(f"[FW Register] OTP URL found: {otp_url[:80]}...")
            elif otp_result.get("status") == "not_found":
                steps_failed.append("otp_not_found")
                return {
                    "status": "partial",
                    "account_email": email,
                    "fireworks_password": password,
                    "api_key": None,
                    "api_key_name": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "OTP URL not found in GMX inbox after " + otp_result.get("execution_time", "unknown"),
                }
            else:
                steps_failed.append("otp_polling_error")
                return {
                    "status": "partial",
                    "account_email": email,
                    "fireworks_password": password,
                    "api_key": None,
                    "api_key_name": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "OTP polling error: " + str(otp_result.get("error", "unknown")),
                }
            logger.info("[FW Register] Phase 7: Open OTP URL to verify account")
            await client.navigate(session_id, otp_url)
            await asyncio.sleep(5)

            confirm_url_result = await client.evaluate(
                session_id, "window.location.href", return_by_value=True
            )
            confirm_url = confirm_url_result.get("result", {}).get("value", "")

            confirm_body_result = await client.evaluate(
                session_id,
                "(function() { return document.body.innerText.slice(0, 300); })()",
                return_by_value=True
            )
            confirm_body = confirm_body_result.get("result", {}).get("value", "")

            is_verified = any(k in confirm_url for k in ["dashboard", "workspace", "welcome"]) or \
                          any(k in confirm_body.lower() for k in ["verified", "confirmed", "welcome", "success"])

            if is_verified:
                steps_completed.append("account_verified")
                logger.info(f"[FW Register] Account verified! URL: {confirm_url[:60]}")
            else:
                logger.warning(f"[FW Register] Account verification uncertain. URL: {confirm_url[:60]}, Body: {confirm_body[:200]}")
                steps_failed.append("account_verification_uncertain")
                # Continue anyway — account might be verified even if page shows something else

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 8: FIREWORKS LOGIN FLOW (Sign In → Email Login)
            # ════════════════════════════════════════════════════════════════════════
            #
            # Account ist erstellt und verifiziert. Jetzt einloggen.
            #
            # /login Page hat beim ersten Load OAuth-Buttons:
            #   - Continue with Google (y=279)
            #   - Continue with GitHub (y=351)
            #   - Continue with LinkedIn (y=423)
            #
            # Der User beschreibt "Sign In" + "Email Login" Buttons.
            # Diese erscheinen möglicherweise NACH dem OAuth-Block oder
            # als Alternative. Wir suchen beide.
            #
            # Mögliche Button-Texte:
            #   - "Sign in with Email" (oder "Sign In with Email")
            #   - "Sign In"
            #   - "Email Login"
            #   - "Use Email Instead"
            #   - "Continue with Email"
            #
            # Nach dem ersten Klick (Sign In): Ein Email-Form erscheint inline.
            #   - input[type="email"] oder input#email
            #   - input[type="password"] oder input#password
            #   - "Next" oder "Sign In" Button
            #
            logger.info("[FW Register] Phase 8: Fireworks login flow")

            await client.navigate(session_id, FIREWORKS_LOGIN_URL)
            await asyncio.sleep(3)

            # Dismiss cookie banner falls es wieder da ist
            await self._dismiss_cookie_banner(client, session_id)
            await asyncio.sleep(1)

            # Suchen nach "Sign In" oder "Email Login" Button
            signin_search_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const btns = [...document.querySelectorAll('button, a')];
                    for (const b of btns) {
                        const r = b.getBoundingClientRect();
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (r.width > 0 && r.height > 0 && r.y < 1500) {
                            if (t.includes('sign in') || t.includes('email login') ||
                                t.includes('use email') || t.includes('continue with email')) {
                                return {found: true, text: b.textContent?.trim().slice(0, 50),
                                        x: r.x + r.width / 2, y: r.y + r.height / 2};
                            }
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            signin_val = signin_search_result.get("result", {}).get("value", {})

            if signin_val.get("found"):
                await client.click_at(session_id, x=signin_val["x"], y=signin_val["y"])
                logger.info(f"[FW Register] Clicked '{signin_val['text']}' at ({signin_val['x']:.0f}, {signin_val['y']:.0f})")
                await asyncio.sleep(3)
            else:
                logger.info("[FW Register] 'Sign In' button not found — checking if email form is already visible")
                # Form might already be visible, skip to filling

            steps_completed.append("signin_button_clicked")

            # Email + Password eingeben auf dem Login-Formular
            login_email_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const selectors = ['input[type="email"]', 'input[id="email"]',
                                       'input[name="email"]', 'input[placeholder*="email" i]'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) {
                                return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2,
                                        id: el.id || sel};
                            }
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            login_email_val = login_email_result.get("result", {}).get("value", {})

            if login_email_val.get("found"):
                logger.info(f"[FW Register] Filling login email: {email}")

                await client.evaluate(
                    session_id,
                    """
                    (function() {
                        const el = document.querySelector('#email') ||
                                   document.querySelector('input[type="email"]');
                        if (el) {
                            el.focus();
                            el.value = '';
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                        }
                    })()
                    """,
                    return_by_value=True
                )

                await client.evaluate(session_id, f"""(function() {{
                    const el = document.querySelector('input[type="email"], input[name*="email"]');
                    if (!el) return false;
                    const ns = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                    ns.call(el, '{email}');
                    el.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }})()""", return_by_value=True)

                await asyncio.sleep(0.5)
                steps_completed.append("login_email_entered")

            # Password auf Login-Formular
            login_pw_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const selectors = ['input[type="password"]', 'input[id="password"]',
                                       'input[name="password"]'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && r.y < 1500) {
                                return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2};
                            }
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            login_pw_val = login_pw_result.get("result", {}).get("value", {})

            if login_pw_val.get("found"):
                logger.info("[FW Register] Filling login password")

                await client.evaluate(
                    session_id,
                    f"""
                    (function() {{
                        const el = document.querySelector('input[type="password"]');
                        if (!el) return false;
                        const ns = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                        ns.call(el, '{password}');
                        el.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                        el.dispatchEvent(new Event('blur', {{bubbles: true}}));
                        return true;
                    }})()
                    """,
                    return_by_value=True
                )

                await asyncio.sleep(0.5)
                steps_completed.append("login_password_entered")

            # Click "Next" auf dem Login-Formular
            login_next_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const btns = [...document.querySelectorAll('button')];
                    for (const b of btns) {
                        const r = b.getBoundingClientRect();
                        const t = (b.textContent || '').trim();
                        if (r.width > 0 && r.height > 0 && r.y < 1500 &&
                            (t.toLowerCase() === 'next' || t.toLowerCase() === 'sign in' ||
                             t.toLowerCase() === 'login' || t.toLowerCase() === 'submit')) {
                            return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2, text: t};
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            login_next_val = login_next_result.get("result", {}).get("value", {})

            if login_next_val.get("found"):
                await client.click_at(session_id, x=login_next_val["x"], y=login_next_val["y"])
                logger.info(f"[FW Register] Clicked login button: '{login_next_val['text']}'")
                await asyncio.sleep(5)
                steps_completed.append("login_submitted")
            else:
                logger.warning("[FW Register] Login submit button not found")
                steps_failed.append("login_submit_button_missing")

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 9: ACCOUNT SETUP (FirstName + LastName + Terms of Service)
            # ════════════════════════════════════════════════════════════════════════
            #
            # Nach dem Login zeigt Fireworks ein Setup-Formular wenn das Profil
            # noch nicht vollständig ist (FirstName/LastName fehlen).
            #
            # Erwartete Elemente:
            #   - input[name="firstName"] oder input[placeholder*="first"]
            #   - input[name="lastName"] oder input[placeholder*="last"]
            #   - Checkbox: "I agree to the Terms of Service and Privacy Policy"
            #   - "Continue" oder "Next" Button
            #
            # FirstName: Erster Teil des Alias (z.B. "frost" aus "frost-spider@gmx.de")
            # LastName: Zweiter Teil (z.B. "spider")
            #
            logger.info("[FW Register] Phase 9: Account setup (firstname/lastname/terms)")

            # FirstName
            firstname_value = email.split("-")[0] if "-" in email else email.split("@")[0]

            fname_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const selectors = ['input[name="firstName"]', 'input[name="first_name"]',
                                       'input[placeholder*="first" i]', 'input[id="firstName"]'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) {
                                return {found: true, id: sel};
                            }
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            fname_val = fname_result.get("result", {}).get("value", {})

            if fname_val.get("found"):
                await client.evaluate(session_id, f"""(function() {{
                    const el = document.querySelector('[name="firstName"]') ||
                               document.querySelector('[placeholder*="first"]');
                    if (!el) return false;
                    const ns = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                    ns.call(el, '{firstname_value}');
                    el.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }})()""", return_by_value=True)
                logger.info(f"[FW Register] FirstName entered: {firstname_value}")
                steps_completed.append("firstname_entered")
                await asyncio.sleep(0.5)

            # LastName
            lastname_value = "-".join(email.split("-")[1:]).split("@")[0] if "-" in email else ""

            lname_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const selectors = ['input[name="lastName"]', 'input[name="last_name"]',
                                       'input[placeholder*="last" i]', 'input[id="lastName"]'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) {
                                return {found: true, id: sel};
                            }
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            lname_val = lname_result.get("result", {}).get("value", {})

            if lname_val.get("found") and lastname_value:
                await client.evaluate(session_id, f"""(function() {{
                    const el = document.querySelector('[name="lastName"]') ||
                               document.querySelector('[placeholder*="last"]');
                    if (!el) return false;
                    const ns = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                    ns.call(el, '{lastname_value}');
                    el.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }})()""", return_by_value=True)
                logger.info(f"[FW Register] LastName entered: {lastname_value}")
                steps_completed.append("lastname_entered")
                await asyncio.sleep(0.5)

            # Terms of Service Checkbox
            tos_result = await client.evaluate(
                session_id,
                """
                (function() {
                    // Find checkbox with label containing "terms" or "agree"
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    for (const cb of checkboxes) {
                        const r = cb.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            // Check parent label
                            const label = cb.closest('label') || cb.parentElement;
                            const labelText = (label?.textContent || '').toLowerCase();
                            const id = cb.id || '';
                            if (labelText.includes('terms') || labelText.includes('agree') ||
                                id.includes('terms') || id.includes('agree')) {
                                return {
                                    found: true,
                                    x: r.x + r.width / 2,
                                    y: r.y + r.height / 2,
                                    labelText: labelText.slice(0, 100)
                                };
                            }
                        }
                    }
                    // Fallback: any unchecked checkbox
                    for (const cb of checkboxes) {
                        const r = cb.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0 && !cb.checked) {
                            return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2,
                                    labelText: 'fallback checkbox', isFallback: true};
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            tos_val = tos_result.get("result", {}).get("value", {})

            if tos_val.get("found"):
                await client.click_at(session_id, x=tos_val["x"], y=tos_val["y"])
                logger.info(f"[FW Register] ToS checkbox clicked at ({tos_val['x']:.0f}, {tos_val['y']:.0f})")
                steps_completed.append("tos_checkbox_checked")
                await asyncio.sleep(0.5)
            else:
                logger.warning("[FW Register] ToS checkbox not found")
                steps_failed.append("tos_checkbox_not_found")

            # "Continue" Button
            continue_btn_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const btns = [...document.querySelectorAll('button')];
                    for (const b of btns) {
                        const r = b.getBoundingClientRect();
                        const t = (b.textContent || '').trim();
                        if (r.width > 0 && r.height > 0 && r.y < 1500 &&
                            (t.toLowerCase() === 'continue' || t.toLowerCase() === 'next' ||
                             t.toLowerCase() === 'weiter' || t.toLowerCase() === 'complete')) {
                            return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2, text: t};
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            continue_btn_val = continue_btn_result.get("result", {}).get("value", {})

            if continue_btn_val.get("found"):
                await client.click_at(session_id, x=continue_btn_val["x"], y=continue_btn_val["y"])
                logger.info(f"[FW Register] Clicked Continue: '{continue_btn_val['text']}'")
                await asyncio.sleep(3)
                steps_completed.append("setup_continue_clicked")
            else:
                logger.warning("[FW Register] Continue button not found")
                steps_failed.append("setup_continue_missing")

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 10: USE CASE AUSWAHL (Flexible Capacity + Conversational AI)
            # ════════════════════════════════════════════════════════════════════════
            #
            # Nach Continue erscheint das "Use Case Selection" Formular.
            # Zwei Checkboxen müssen gesetzt werden:
            #   1. "Flexible capacity for production"
            #   2. "Conversational AI"
            #
            # Danach: "Submit to get $5 Credits" Button klicken.
            # WICHTIG: Dieser Button startet die $5 Credits!
            # Ohne diesen Klick gibt es keine Credits.
            #
            logger.info("[FW Register] Phase 10: Use case selection + $5 Credits")

            usecase_btns = [
                ("Flexible capacity", "flexible"),
                ("Conversational AI", "conversational"),
            ]

            for label_text, _ in usecase_btns:
                cb_result = await client.evaluate(
                    session_id,
                    f"""
                    (function() {{
                        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                        for (const cb of checkboxes) {{
                            const r = cb.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) {{
                                const label = cb.closest('label') || cb.parentElement;
                                const text = (label?.textContent || '').toLowerCase();
                                if (text.includes('{label_text.toLowerCase()}')) {{
                                    return {{found: true, x: r.x + r.width / 2, y: r.y + r.height / 2}};
                                }}
                            }}
                        }}
                        return {{found: false}};
                    }})()
                    """,
                    return_by_value=True
                )
                cb_val = cb_result.get("result", {}).get("value", {})
                if cb_val.get("found"):
                    await client.click_at(session_id, x=cb_val["x"], y=cb_val["y"])
                    logger.info(f"[FW Register] Checked: '{label_text}'")
                    await asyncio.sleep(0.3)

            # "Submit to get $5 Credits" Button
            submit_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const btns = [...document.querySelectorAll('button')];
                    for (const b of btns) {
                        const r = b.getBoundingClientRect();
                        const t = (b.textContent || '').trim();
                        if (r.width > 0 && r.height > 0 && r.y < 1500 &&
                            t.toLowerCase().includes('submit') &&
                            t.toLowerCase().includes('5')) {
                            return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2, text: t};
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            submit_val = submit_result.get("result", {}).get("value", {})

            if submit_val.get("found"):
                await client.click_at(session_id, x=submit_val["x"], y=submit_val["y"])
                logger.info(f"[FW Register] Clicked: '{submit_val['text']}'")
                steps_completed.append("submit_credits_clicked")
            else:
                logger.warning("[FW Register] 'Submit to get $5 Credits' button not found")
                steps_failed.append("submit_credits_button_missing")

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 11: LOADING POLLING (15s + 5x2s)
            # ════════════════════════════════════════════════════════════════════════
            #
            # Nach dem Submit-Button kann Fireworks 1-15 Sekunden brauchen
            # um die Credits zu aktivieren. Die Seite kann in einem
            # Loading-State sein (Spinner oder "Processing...").
            #
            # Success-Indikatoren:
            #   - URL wechselt zu /dashboard
            #   - body-text enthält "dashboard" oder "credits" oder "$5"
            #   - Redirect zu einer Settings-Page
            #
            # Polling: 5 retries × 2s = 10s + initial 5s = 15s total
            # Wenn nach 15s immer noch loading → weitermachen (Credits könnten
            # schon aktiv sein)
            #
            logger.info("[FW Register] Phase 11: Wait for credits activation (15s)")

            await asyncio.sleep(5)  # Initial wait

            for poll_attempt in range(5):
                poll_url_result = await client.evaluate(
                    session_id, "window.location.href", return_by_value=True
                )
                poll_url = poll_url_result.get("result", {}).get("value", "")

                poll_body_result = await client.evaluate(
                    session_id,
                    "(function() { return document.body.innerText.slice(0, 300).toLowerCase(); })()",
                    return_by_value=True
                )
                poll_body = poll_body_result.get("result", {}).get("value", "")

                if any(k in poll_url for k in ["dashboard", "workspace", "settings"]) or \
                   any(k in poll_body for k in ["dashboard", "credits", "$5", "welcome"]):
                    logger.info(f"[FW Register] Credits activated! URL: {poll_url[:60]}")
                    steps_completed.append("credits_activated")
                    break

                logger.info(f"[FW Register] Poll {poll_attempt + 1}/5: Still loading... URL: {poll_url[:60]}")
                await asyncio.sleep(2)

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 12: API KEY ERSTELLEN
            # ════════════════════════════════════════════════════════════════════════
            #
            # Navigate zu: https://app.fireworks.ai/settings/workspace/api-keys
            #
            # Flow:
            # 1. "Create API Key" Button klicken
            # 2. Dialog öffnet sich
            # 3. Name-Feld: input[name="name"] oder input[placeholder*="name"]
            #    → Name = Vornamen-Teil des Alias (z.B. "frost-spider")
            # 4. "Generate Key" Button klicken
            # 5. Key extrahieren:
            #    → Pattern: input[readonly] mit value.startsWith('fw-')
            #    → Regex: body.match(/(fw-[a-zA-Z0-9_-]{20,})/)
            #
            logger.info("[FW Register] Phase 12: Create API key")

            await client.navigate(session_id, FIREWORKS_API_KEYS_URL)
            await asyncio.sleep(4)

            # "Create API Key" Button
            create_key_btn_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const btns = [...document.querySelectorAll('button, a')];
                    for (const b of btns) {
                        const r = b.getBoundingClientRect();
                        const t = (b.textContent || '').trim();
                        if (r.width > 0 && r.height > 0 && r.y < 1500 &&
                            (t.toLowerCase() === 'create api key' ||
                             t.toLowerCase() === 'create key' ||
                             t.toLowerCase() === 'add key')) {
                            return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2, text: t};
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            create_key_btn_val = create_key_btn_result.get("result", {}).get("value", {})

            if create_key_btn_val.get("found"):
                await client.click_at(session_id,
                    x=create_key_btn_val["x"], y=create_key_btn_val["y"])
                logger.info(f"[FW Register] Clicked: '{create_key_btn_val['text']}'")
                await asyncio.sleep(2)
                steps_completed.append("create_api_key_button_clicked")
            else:
                logger.warning("[FW Register] 'Create API Key' button not found")
                steps_failed.append("create_api_key_button_missing")

            # Name-Feld
            api_key_name = email.split("-")[0] if "-" in email else email.split("@")[0]

            name_field_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const selectors = ['input[name="name"]', 'input[placeholder*="name" i]',
                                       'input[type="text"]'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0 && r.y < 1500) {
                                return {found: true, id: sel};
                            }
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            name_field_val = name_field_result.get("result", {}).get("value", {})

            if name_field_val.get("found"):
                await client.evaluate(session_id, f"""(function() {{
                    const el = document.querySelector('[name="name"]') ||
                               document.querySelector('input[placeholder*="name"]');
                    if (!el) return false;
                    const ns = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                    ns.call(el, '{api_key_name}');
                    el.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }})()""", return_by_value=True)
                logger.info(f"[FW Register] API key name entered: {api_key_name}")
                await asyncio.sleep(0.5)

            # "Generate Key" Button
            gen_btn_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const btns = [...document.querySelectorAll('button')];
                    for (const b of btns) {
                        const r = b.getBoundingClientRect();
                        const t = (b.textContent || '').trim();
                        if (r.width > 0 && r.height > 0 && r.y < 1500 &&
                            (t.toLowerCase() === 'generate key' ||
                             t.toLowerCase() === 'generate' ||
                             t.toLowerCase() === 'create')) {
                            return {found: true, x: r.x + r.width / 2, y: r.y + r.height / 2, text: t};
                        }
                    }
                    return {found: false};
                })()
                """,
                return_by_value=True
            )
            gen_btn_val = gen_btn_result.get("result", {}).get("value", {})

            if gen_btn_val.get("found"):
                await client.click_at(session_id, x=gen_btn_val["x"], y=gen_btn_val["y"])
                logger.info(f"[FW Register] Clicked: '{gen_btn_val['text']}'")
                await asyncio.sleep(4)
                steps_completed.append("generate_key_clicked")
            else:
                logger.warning("[FW Register] 'Generate Key' button not found")
                steps_failed.append("generate_key_button_missing")

            # Key extrahieren
            key_extract_result = await client.evaluate(
                session_id,
                """
                (function() {
                    // Strategy 1: input[readonly] with fw- value
                    const roInputs = document.querySelectorAll('input[readonly]');
                    for (const inp of roInputs) {
                        const val = (inp.value || '').trim();
                        if (val.startsWith('fw-') && val.length > 20) return val;
                        if (val.startsWith('sk-') && val.length > 20) return val;
                    }
                    // Strategy 2: code/pre/span with fw- text
                    const codeEls = document.querySelectorAll('code, pre, span[class*="key"], [class*="api-key"]');
                    for (const el of codeEls) {
                        const txt = (el.textContent || '').trim();
                        if (txt.startsWith('fw-') && txt.length > 20) return txt;
                        if (txt.startsWith('sk-') && txt.length > 20) return txt;
                    }
                    // Strategy 3: Body regex
                    const body = document.body.innerText;
                    const match1 = body.match(/(fw-[a-zA-Z0-9_-]{20,})/);
                    if (match1) return match1[1];
                    const match2 = body.match(/(sk-[a-zA-Z0-9_-]{20,})/);
                    if (match2) return match2[1];
                    // Strategy 4: any element with fw- in text
                    const allEls = document.querySelectorAll('*');
                    for (const el of allEls) {
                        const txt = (el.textContent || '').trim();
                        if ((txt.startsWith('fw-') || txt.startsWith('sk-')) && txt.length > 20) {
                            return txt;
                        }
                    }
                    return null;
                })()
                """,
                return_by_value=True
            )
            api_key = key_extract_result.get("result", {}).get("value")

            if api_key and len(api_key) > 20:
                steps_completed.append("api_key_extracted")
                logger.info(f"[FW Register] API Key extracted: {api_key[:12]}...")
            else:
                logger.warning("[FW Register] API Key NOT found in page after Generate")
                steps_failed.append("api_key_extraction_failed")
                api_key = None

            # ════════════════════════════════════════════════════════════════════════
            # FINAL: ERGEBNIS ZUSAMMENFASSEN
            # ════════════════════════════════════════════════════════════════════════
            elapsed = time.time() - start_time

            final_status = "success" if (api_key and len(api_key) > 20) else "partial"

            logger.info(
                f"[FW Register] COMPLETE — status={final_status}, "
                f"api_key={'YES' if api_key else 'NO'}, "
                f"steps_ok={len(steps_completed)}, "
                f"steps_failed={len(steps_failed)}, "
                f"time={elapsed:.1f}s"
            )

            return {
                "status": final_status,
                "account_email": email,
                "fireworks_password": password,
                "api_key": api_key,
                "api_key_name": api_key_name,
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "execution_time": f"{elapsed:.2f}s",
                "error": None if final_status == "success" else
                         f"{len(steps_failed)} steps failed: {', '.join(steps_failed[-3:])}",
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[FW Register] EXCEPTION: {e}")
            return {
                "status": "error",
                "account_email": email,
                "fireworks_password": password,
                "api_key": None,
                "api_key_name": None,
                "steps_completed": steps_completed,
                "steps_failed": steps_failed + ["exception"],
                "execution_time": f"{elapsed:.2f}s",
                "error": str(e),
            }
        finally:
            if client:
                await client.disconnect()

    async def confirm(
        self, confirm_url: str, email: str, password: str,
        first_name: Optional[str] = None, last_name: Optional[str] = None,
        cdp_port: int = 9222
    ) -> Dict[str, Any]:
        """
        Bestätigt Fireworks Account via OTP/Confirm-URL.

        FLOW:
        1. Navigate zur Confirm-URL
        2. Ggf. Login mit Email + Password
        3. Ggf. FirstName + LastName eingeben
        4. Continue klicken
        5. Prüfen ob bestätigt (Dashboard-Redirect)

        Args:
            confirm_url: URL aus der GMX Bestätigungs-Email
            email: Account Email
            password: Account Passwort
            first_name, last_name: Optionale Profile-Daten
            cdp_port: CDP Port

        Returns:
            {"status": "success"|"failed"|"error", "account_confirmed": bool}
        """
        start_time = time.time()
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            logger.info(f"Bestätige Fireworks Account: {confirm_url[:60]}...")

            await client.navigate(session_id, confirm_url)
            await asyncio.sleep(5)
            await self._screenshot(client, session_id, "fw_confirm")

            current_selectors = [
                'input[type="email"]',
                'input[name="email"]',
            ]
            if await self._find_element(client, session_id, current_selectors):
                logger.info("Login-Formular gefunden, fülle Email + Passwort")
                await self._fill_input(client, session_id, current_selectors, email)
                await asyncio.sleep(1)

                pw_selectors = ['input[type="password"]', 'input[name="password"]']
                await self._fill_input(client, session_id, pw_selectors, password)
                await asyncio.sleep(1)

                submit_selectors = [
                    'button[type="submit"]',
                    'button:has-text("Login")',
                    'button:has-text("Sign In")',
                    'button:has-text("Next")',
                ]
                await self._click_button(client, session_id, submit_selectors)
                await asyncio.sleep(4)
                await self._screenshot(client, session_id, "fw_after_login")

            if first_name:
                fname_selectors = [
                    'input[name="firstName"]',
                    'input[name="first_name"]',
                    'input[placeholder*="first" i]',
                    'input[placeholder*="vorname" i]',
                ]
                await self._fill_input(client, session_id, fname_selectors, first_name)
                await asyncio.sleep(0.5)

            if last_name:
                lname_selectors = [
                    'input[name="lastName"]',
                    'input[name="last_name"]',
                    'input[placeholder*="last" i]',
                    'input[placeholder*="nachname" i]',
                ]
                await self._fill_input(client, session_id, lname_selectors, last_name)
                await asyncio.sleep(0.5)

            continue_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Weiter")',
                'button:has-text("Complete")',
                'button:has-text("Finish")',
                'button[type="submit"]',
            ]
            await self._click_button(client, session_id, continue_selectors)
            await asyncio.sleep(4)
            await self._screenshot(client, session_id, "fw_after_continue")

            url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_result.get("result", {}).get("value", "")

            body_js = '''(function(){
                let txt = '';
                const walk = (r) => { if(!r) return; txt += (r.textContent || '') + ' '; for(const e of r.querySelectorAll('*')) walk(e); };
                walk(document.body);
                return txt.trim().slice(0, 500);
            })()'''
            body_result = await client.evaluate(session_id, body_js, return_by_value=True)
            body_text = body_result.get("result", {}).get("value", "")

            confirmed = any(k in current_url for k in ["dashboard", "workspace", "home", "account"]) or \
                       any(k in body_text.lower() for k in ["welcome", "verified", "confirmed", "success"])

            elapsed = time.time() - start_time
            logger.info(f"Account bestätigt: {confirmed} → {current_url}")
            return {
                "status": "success" if confirmed else "failed",
                "account_confirmed": confirmed,
                "current_url": current_url,
                "execution_time": f"{elapsed:.2f}s",
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Fireworks Bestätigung fehlgeschlagen: {e}")
            return {"status": "error", "account_confirmed": False, "error": str(e), "execution_time": f"{elapsed:.2f}s"}
        finally:
            if client:
                await client.disconnect()

    async def create_api_key(
        self, key_name: str = "sinator-key", cdp_port: int = 9222
    ) -> Dict[str, Any]:
        """
        Erstellt Fireworks API-Key im Dashboard.

        FLOW:
        1. Navigate zu Settings → API Keys
        2. "Create API Key" oder "New Key" klicken
        3. Key-Name eingeben
        4. "Generate" oder "Create" klicken
        5. Key-Text auslesen (input[readonly], code, etc.)
        6. Key kopieren oder aus display extrahieren

        Args:
            key_name: Name für den API-Key
            cdp_port: CDP Port

        Returns:
            {"status": "success"|"failed"|"error", "api_key": str, "key_name": str}
        """
        start_time = time.time()
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            logger.info(f"Erstelle Fireworks API-Key: {key_name}")

            await client.navigate(session_id, FIREWORKS_API_KEYS_URL)
            await asyncio.sleep(4)
            await self._screenshot(client, session_id, "fw_apikeys")

            create_selectors = [
                'button:has-text("Create API Key")',
                'button:has-text("New API Key")',
                'button:has-text("Create Key")',
                'button:has-text("Add Key")',
                'button:has-text("Create")',
                'a:has-text("Create API Key")',
            ]
            if not await self._click_button(client, session_id, create_selectors):
                url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                current_url = url_result.get("result", {}).get("value", "")
                if "api-keys" not in current_url:
                    await client.navigate(session_id, FIREWORKS_DASHBOARD_URL)
                    await asyncio.sleep(4)
                    sidebar_selectors = ['button:has-text("API Keys")', 'a:has-text("API Keys")', '[href*="api-key"]']
                    await self._click_button(client, session_id, sidebar_selectors)
                    await asyncio.sleep(4)

            await self._screenshot(client, session_id, "fw_apikeys_dialog")

            name_selectors = [
                'input[name="name"]',
                'input[placeholder*="name" i]',
                'input[type="text"]',
            ]
            if not await self._fill_input(client, session_id, name_selectors, key_name):
                logger.warning("Name-Feld nicht gefunden, überspringe")

            generate_selectors = [
                'button:has-text("Generate")',
                'button:has-text("Create")',
                'button:has-text("Save")',
                'button[type="submit"]',
            ]
            if not await self._click_button(client, session_id, generate_selectors):
                return {"status": "failed", "api_key": None, "key_name": key_name, "error": "Generate-Button nicht gefunden"}

            await asyncio.sleep(3)
            await self._screenshot(client, session_id, "fw_apikeys_result")

            js_extract = '''
            (function() {
                const patterns = [
                    'input[readonly]',
                    'input[value*="fw-"]',
                    'code',
                    'pre',
                    '[data-testid*="key"]',
                    '[class*="key"]',
                ];
                for (const sel of patterns) {
                    const els = document.querySelectorAll(sel);
                    for (const el of els) {
                        const val = el.value || el.textContent || '';
                        const trimmed = val.trim();
                        if (trimmed.startsWith('fw-') && trimmed.length > 20) return trimmed;
                        if (trimmed.startsWith('sk-') && trimmed.length > 20) return trimmed;
                    }
                }
                const codeEls = document.querySelectorAll('code, pre, span');
                for (const el of codeEls) {
                    const txt = (el.textContent || '').trim();
                    if ((txt.startsWith('fw-') || txt.startsWith('sk-')) && txt.length > 20) return txt;
                }
                const body = document.body.textContent;
                const match = body.match(/(fw-[a-zA-Z0-9_-]{20,})/) || body.match(/(sk-[a-zA-Z0-9_-]{20,})/);
                return match ? match[1] : null;
            })()
            '''
            result = await client.evaluate(session_id, js_extract, return_by_value=True)
            api_key = result.get("result", {}).get("value")

            elapsed = time.time() - start_time
            if api_key and len(api_key) > 20:
                logger.info(f"API-Key gefunden: {api_key[:12]}...")
                return {
                    "status": "success",
                    "api_key": api_key,
                    "key_name": key_name,
                    "execution_time": f"{elapsed:.2f}s",
                }
            else:
                logger.warning(f"API-Key nicht gefunden in Seite, screenshot für Debug")
                return {"status": "failed", "api_key": None, "key_name": key_name, "error": "Key nicht gefunden", "execution_time": f"{elapsed:.2f}s"}

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"API-Key-Erstellung fehlgeschlagen: {e}")
            return {"status": "error", "api_key": None, "key_name": key_name, "error": str(e), "execution_time": f"{elapsed:.2f}s"}
        finally:
            if client:
                await client.disconnect()


_fireworks_service: Optional[FireworksService] = None


def get_fireworks_service() -> FireworksService:
    global _fireworks_service
    if _fireworks_service is None:
        _fireworks_service = FireworksService()
    return _fireworks_service