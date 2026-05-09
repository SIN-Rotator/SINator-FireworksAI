"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Fireworks Service (CDP Edition)          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Fireworks AI Account-Registrierung, Bestätigung, API-Key-Erstellung         ║
║  via RAW CDP (kein Playwright Page-Objekt für Fireworks nötig).              ║
║                                                                              ║
║  ARCHITEKTUR:                                                                 ║
║  • CDP websocket für alle Fireworks-Operationen (Konsistenz mit GMX)         ║
║  • BrowserManager liefert den CDP-Port; FireworksService öffnet              ║
║    eine eigene CDP-Verbindung pro Operation                                  ║
║  • Fireworks ist eine normale Web-App (KEIN SPA mit Frame-Detach-Crashes)    ║
║    → einfache DOM-Manipulation via CDP funktioniert                         ║
║                                                                              ║
║  FLOW (komplette Account-Rotation):                                          ║
║  1. rotate_alias() auf GMX (neue Alias-Email)                               ║
║  2. register() auf Fireworks (Alias-Email + Passwort)                       ║
║  3. OTP-Poll: GMX-Inbox nach Confirm-URL durchsuchen                       ║
║  4. confirm() auf Fireworks (OTP-URL öffnen)                                ║
║  5. create_api_key() im Fireworks-Dashboard                                 ║
║  6. Pool speichern (JSON-Datei)                                             ║
║                                                                              ║
║  FIREWORKS URLS:                                                             ║
║  • Signup:     https://app.fireworks.ai/signup                              ║
║  • Login:      https://app.fireworks.ai/login                               ║
║  • Dashboard:  https://app.fireworks.ai/dashboard                           ║
║  • Settings:   https://app.fireworks.ai/settings/workspace/api-keys         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
import re
import asyncio
from typing import Optional, Dict, Any, Tuple

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

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

        js = f'''
        (function() {{
            const inputs = document.querySelectorAll('{selectors[0]}');
            const input = Array.from(inputs).find(i => i.offsetParent !== null);
            if (!input) return {{error: 'not found or hidden'}};
            input.focus();
            input.value = '';
            input.dispatchEvent(new Event('input', {{bubbles: true}}));
            return {{success: true, name: input.name, type: input.type}};
        }})()
        '''
        result = await client.evaluate(session_id, js, return_by_value=True)
        if not result.get("result", {}).get("value", {}).get("success"):
            return False

        for char in value:
            await client.send_to_session(session_id, "Input.dispatchKeyEvent", {
                "type": "keyDown", "text": char,
            })
            await client.send_to_session(session_id, "Input.dispatchKeyEvent", {
                "type": "keyUp", "text": char,
            })
            await asyncio.sleep(0.02)

        await client.evaluate(session_id, f'''
        (function() {{
            const inputs = document.querySelectorAll('{selectors[0]}');
            const input = Array.from(inputs).find(i => i.offsetParent !== null);
            if (input) input.dispatchEvent(new Event('change', {{bubbles: true}}));
        }})()
        ''', return_by_value=True)
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

    async def _dismiss_cookie_banner(
        self,
        client: CDPClient,
        session_id: str
    ) -> bool:
        """
        ════════════════════════════════════════════════════════════════════════════
        DISMISS COOKIE CONSENT BANNER — FIREWORKS.AI
        ════════════════════════════════════════════════════════════════════════════

        ZWECK:
        Fireworks.ai verwendet einen Cookie-Consent-Banner (Cookiebot/CookieFirst),
        der sich beim ersten Page-Load über den gesamten unteren Viewport legt.
        Dieser Banner blockiert ALLE Interaktionen mit den darunterliegenden
        Formular-Elementen (Email-Eingabe, Passwort-Feld, Buttons) und MUSS
        zuerst dismissed werden, bevor irgendwelche anderen Aktionen möglich sind.

        PROBLEM (HISTORISCHER KONTEXT):
        Ein früherer Implementierungsansatz verwendete JavaScript's natives
        `element.click()` über einen `Runtime.evaluate()` JS-Kontext im CDP.
        Dies FUNKTIONIERTE NICHT aus folgenden Gründen:

        1. COOKIE BANNER OVERLAY: Der Banner ist ein div mit z-index > alle anderen
           Elemente, das den gesamten Viewport ab y=656 bis y=919 abdeckt (ca. 263px).
           Er sitzt ÜBER dem Signup-Formular (das bei y=302 beginnt).

        2. JS .click() IM EVALUATE-KONTEXT: Wenn wir via
           `Runtime.evaluate()` JS-Code im Page-Kontext ausführen und darin
           `element.click()` aufrufen, passiert folgendes:
           - Das DOM-Element EXISTS und ist sichtbar (r.width > 0, r.height > 0)
           - `element.click()` löst ein mouseDown + mouseUp + click Event aus
           - ABER: Der Browser verarbeitet das Event im EVALUATE-JS-KONTEXT, nicht
             im echten User-Input-Kontext
           - Der Banner-Consent-Handler (Cookiebot-Script) erwartet eine echte
             User-Interaktion und ignoriert/verarbeitet das synthetische Event
             nicht korrekt → Banner bleibt stehen

        3. TRANSPARENT OVERLAY DIVS (VERWANDTES PROBLEM): Das gleiche Phänomen
           wurde bei GMX beobachtet. GMX verwendet transparente overlay divs,
           die JavaScript `.click()` abfangen und verwerfen. Der Fix war
           `client.click_at(x, y)` mit echten CDP-Koordinaten-Klicks.

        LÖSUNG — CDP COORDINATE-BASED CLICK:
        Die einzig zuverlässige Methode ist `client.click_at(session_id, x, y)`
        über CDP's `Input.dispatchMouseEvent(type="mousePressed")` und
        `Input.dispatchMouseEvent(type="mouseReleased")`.
        Dies simuliert ECHTE Maus-Interaktionen im Browser-Prozess und löst
        die native Event-Verarbeitung aus, die der Cookiebot-Handler erwartet.

        STRATEGIE:
        Wir verwenden einen zweistufigen Ansatz:
        1. Phase 1: JS-Locator via `Runtime.evaluate()` findet den Button und
           liefert seine (x, y) Koordinaten (Mitte des Elements)
        2. Phase 2: `client.click_at()` klickt an diesen Koordinaten mit
           echten CDP Maus-Events (mousePressed → mouseReleased)

        COOKIE BANNER STRUKTUR (Fireworks.ai Stand 2026-05-09):
        Der Banner verwendet das "Cookiebot" oder "CookieFirst" Consent Management
        System mit folgenden DOM-Elementen:

        Cookie-Consent-Container:
        - Klasse: `.cky-consent-container` (position: fixed, bottom: 0)
        - Kinder:
          - `.cky-consent-bar` (wrapper)
          - `.cky-notice-btn-wrapper` (Buttons unten rechts)
          - Button: `button.cky-btn.cky-btn-accept` (Accept All)
          - Button: `button.cky-btn.cky-btn-reject` (Reject All)
          - Button: `button.cky-btn.cky-btn-customize` (Customize)
          - Button: `button.cky-btn-close` (kleines X zum Schließen)

        Button-Koordinaten (ViewPort 1200x919):
        - Accept All (Primary CTA): x=1052.5, y=785.5, w=122.5, h=40.0
          → Center: (1113.7, 805.5)
        - Reject All: x=926.3, y=785.5, w=118.2, h=40.0
        - Customize: x=798.9, y=786.5, w=119.4, h=38.0
        - Close: x=374.5, y=1207.5 (außerhalb Viewport, unwichtig)

        PRIORITÄT DER BUTTONS:
        1. Accept All ist bevorzugt → erlaubt alle Cookies + schließt Banner sofort
        2. Falls Accept All nicht verfügbar → Reject All
        3. Falls kein Button gefunden → prüfe ob Banner verschwunden ist (false positive)

        VALIDIERUNG:
        Nach dem Klick prüfen wir ob der Banner wirklich weg ist:
        - Query `.cky-consent-container`
        - Prüfe display: none oder height: 0 (Banner collapse nach Accept)
        - Warte 2 Sekunden auf DOM-Update

        FEHLERQUELLEN UND DEREN HANDHABUNG:
        - Banner bereits dismissed: Wirken JS-Query findet nichts → return True
          (Banner ist entweder nie erschienen oder bereits weg)
        - Accept All Button hat display:none: Phase-2-JS prüft r.width > 0, überspringt
        - Banner hat sich nicht collapsed: JS-Check erkennt height > 0 → return False
          (Banner könnte sich nicht korrekt geschlossen haben)
        - Mehrere "Accept All" Buttons: Wir nehmen den ERSTEN sichtbaren
          (in einem Container mehrere Accept-All-Buttons möglich → im Notice-Banner
          und im Preferences-Panel → wir wollen den Notice-Banner-Button)

        KONTEXT-INFORMATIONEN:
        - Chrome Version: 147.0.7727.138 (macOS, 1200x919 viewport)
        - Session: Verwendet Profile 901 ("SINator (Fireworks AI)")
        - CDP Port: 9222 (Standard SINator Configuration)
        - Page URL: https://app.fireworks.ai/signup
        - Banner erscheint: IMMER auf erstem Page-Load (kein persistentes Consent)
        - Verwendete Library: Cookiebot CMP (cookiebot.com) oder CookieFirst
        - 1722 Tracker-Partner werden in der Banner-Beschreibung erwähnt

        Args:
            client: CDPClient Instance (connected, mit aktiver Session)
            session_id: String CDP Session ID für Target-Attachment

        Returns:
            True  = Cookie Banner erfolgreich dismissed (war sichtbar und wurde
                    per CDP-Koordinaten-Klick geschlossen)
            False = Kein Banner gefunden oder Banner konnte nicht geschlossen werden
                    (in diesem Fall könnte die Registrierung trotzdem funktionieren
                    wenn der Banner gar nicht erschienen ist)

        Side Effects:
            - Sendet CDP Input.dispatchMouseEvent Commands an den Browser
            - Wartet 2 Sekunden nach dem Klick auf DOM-Update
            - Keine Page-Navigation, keine Screenshots

        Performance:
            - JS-Locator: ~50ms
            - CDP Click: ~10ms
            - Sleep + Validierung: ~2100ms
            - Total: ~2.2s pro Aufruf

        Debugging:
            - Setze Log-Level auf DEBUG für detaillierte Koordinaten-Logs
            - Prüfe /tmp/fw_cookie_debug.py für Live-DOM-Analyse
            - Prüfe Screenshot nach navigate() für visuellen Zustand

        Beispiel-HTTP-GET von Cookiebot:
        GET https://consent.cookiebot.com/uc.js?bid=XXXXXXXX
        → Script blockiert Interaktionen bis Consent gegeben
        → Erst nach Accept/Reject verschwindet das Overlay

        """
        logger.debug(
            f"[CookieBanner] Phase 1: JS-Locator sucht Accept-All Button "
            f"im Page-DOM (session={session_id[:16]}...)"
        )

        # ════════════════════════════════════════════════════════════════════════
        # PHASE 1: JavaScript-basierte Button-Lokalisierung
        # ════════════════════════════════════════════════════════════════════════
        #
        # Wir führen JavaScript im Page-Kontext aus via Runtime.evaluate.
        # Das JS sucht sichtbare "Accept All" Buttons im Cookie-Banner-DOM.
        #
        # Suchstrategie (Reihenfolge der Selector-Tests):
        # 1. 'button.cky-btn-accept'          → Cookiebot spezifische Klasse
        # 2. 'button.cky-btn.cky-btn-accept'  → Fallback mit voller Klasse
        # 3. '[class*="cky-btn-accept"]'      → Partial-Class-Match
        # 4. Text-Match im Banner: buttons mit "accept all" (case-insensitive)
        #
        # Für jeden gefundenen Button werden folgende Checks durchgeführt:
        # - getBoundingClientRect(): x, y, width, height
        # - Check r.width > 0 && r.height > 0 → Button ist sichtbar
        # - Check r.x >= 0 && r.y >= 0 → Button ist im Viewport
        #
        # Bei erstem Treffer: Berechne Mittelpunkt-Koordinaten:
        #   center_x = r.x + r.width / 2
        #   center_y = r.y + r.height / 2
        #   → Für Accept All Button: (1113.7, 805.5)
        #
        # Return: {found: true/false, x, y, w, h, text, selector_used}
        #
        js_find_button = '''
        (function() {
            // ─────────────────────────────────────────────────────────────────
            // STRATEGY 1: Direct Class Selector
            // Versuche zuerst den exakten Cookiebot-Selektor.
            // Der Button hat die Klasse "cky-btn-accept" (primär) und
            // zusätzlich "cky-btn" (generisch). Der Text ist "Accept All".
            // ─────────────────────────────────────────────────────────────────
            const selectors = [
                'button.cky-btn-accept',           // Primär: Cookiebot-Klasse
                'button.cky-btn.cky-btn-accept',   // Fallback: Doppel-Klasse
                '[class*="cky-btn-accept"]',       // Partial: beliebiger Wrapper
            ];

            for (const sel of selectors) {
                const btns = document.querySelectorAll(sel);
                for (const btn of btns) {
                    const r = btn.getBoundingClientRect();
                    // Nur sichtbare Buttons im aktuellen Viewport
                    if (r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0) {
                        const text = (btn.textContent || '').trim();
                        // Nur Buttons mit "Accept All" Text akzeptieren
                        if (text.toLowerCase().includes('accept')) {
                            return {
                                found: true,
                                x: r.x + r.width / 2,
                                y: r.y + r.height / 2,
                                w: r.width,
                                h: r.height,
                                text: text.slice(0, 50),
                                selector: sel,
                                phase: 1
                            };
                        }
                    }
                }
            }

            // ─────────────────────────────────────────────────────────────────
            // STRATEGY 2: Container-based Text Search
            // Suche im Cookie-Consent-Container nach Buttons mit "Accept All" Text.
            // Nötig falls der Banner andere Klassennamen verwendet oder
            // der Button in einem verschachtelten Container liegt.
            // ─────────────────────────────────────────────────────────────────
            const containerSelectors = [
                '.cky-consent-container',           // Cookiebot: ganzes Banner
                '.cky-consent-bar',                 // Cookiebot: Notice-Bar
                '[class*="cookie-banner"]',         // Generic: irgendein Banner
                '[class*="consent-banner"]',        // Generic: Consent-Variante
                '[class*="cookie-notice"]',         // Generic: Notice-Element
            ];

            for (const cSel of containerSelectors) {
                const containers = document.querySelectorAll(cSel);
                for (const container of containers) {
                    const cRect = container.getBoundingClientRect();
                    // Nur Container die sichtbar und im Viewport sind
                    if (cRect.width > 0 && cRect.height > 0) {
                        const btns = container.querySelectorAll('button, a, [role="button"]');
                        for (const btn of btns) {
                            const r = btn.getBoundingClientRect();
                            const text = (btn.textContent || '').trim().toLowerCase();
                            if (r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0) {
                                // "accept all" = Accept-Button, "accept" ohne "all" = auch OK
                                if ((text.includes('accept') && text.includes('all')) ||
                                    text === 'accept all') {
                                    return {
                                        found: true,
                                        x: r.x + r.width / 2,
                                        y: r.y + r.height / 2,
                                        w: r.width,
                                        h: r.height,
                                        text: btn.textContent?.trim().slice(0, 50) || 'Accept All',
                                        selector: cSel + ' button',
                                        phase: 2
                                    };
                                }
                            }
                        }
                    }
                }
            }

            // ─────────────────────────────────────────────────────────────────
            // STRATEGY 3: Full-Page Scan
            // Letzter Ausweg: Scan ALLE Buttons auf der gesamten Seite.
            // Sucht Buttons mit "accept" im Text die im Viewport sichtbar sind.
            // ─────────────────────────────────────────────────────────────────
            const allBtns = document.querySelectorAll('button, a, input[type="button"]');
            for (const btn of allBtns) {
                const r = btn.getBoundingClientRect();
                const text = (btn.textContent || '').trim().toLowerCase();
                if (r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0) {
                    if (text.includes('accept') && text.includes('all')) {
                        return {
                            found: true,
                            x: r.x + r.width / 2,
                            y: r.y + r.height / 2,
                            w: r.width,
                            h: r.height,
                            text: btn.textContent?.trim().slice(0, 50) || 'Accept All',
                            selector: 'full-page-scan',
                            phase: 3
                        };
                    }
                }
            }

            // ─────────────────────────────────────────────────────────────────
            // NOTHING FOUND
            // Kein Accept-All Button gefunden → mögliche Szenarien:
            # 1. Banner ist bereits dismissed (Consent previously given)
            # 2. Banner nutzt komplett andere DOM-Struktur
            # 3. Seite hat gar keinen Cookie-Banner (z.B. Bot-Detection)
            # 4. Banner ist im Schatten-DOM (Shadow DOM) versteckt
            # ─────────────────────────────────────────────────────────────────
            return {
                found: false,
                x: null,
                y: null,
                w: null,
                h: null,
                text: null,
                selector: null,
                phase: 0
            };
        })()
        '''

        # Führe den JS-Locator aus
        find_result = await client.evaluate(
            session_id,
            js_find_button,
            return_by_value=True
        )

        # Extrahiere das Ergebnis aus dem CDP-Response-Wrapper
        # Das Ergebnis ist: {"result": {"type": "object", "value": {...actual data...}}}
        raw_val = find_result.get("result", {}).get("value", {})
        btn_info = raw_val if isinstance(raw_val, dict) else {}

        if not btn_info.get("found"):
            # Kein Button gefunden → prüfe ob Banner vielleicht gar nicht da ist
            logger.debug(
                f"[CookieBanner] Phase 0: Kein Accept-All Button gefunden. "
                f"Prüfe ob Banner überhaupt existiert..."
            )

            # Probe: Check ob Consent-Container existiert
            check_banner = await client.evaluate(
                session_id,
                '''
                (function() {
                    const c = document.querySelector('.cky-consent-container');
                    if (!c) return {bannerExists: false};
                    const r = c.getBoundingClientRect();
                    return {
                        bannerExists: true,
                        height: r.height,
                        display: window.getComputedStyle(c).display,
                        opacity: window.getComputedStyle(c).opacity
                    };
                })()
                ''',
                return_by_value=True
            )
            banner_state = check_banner.get("result", {}).get("value", {})

            if banner_state.get("bannerExists"):
                # Banner existiert aber Button nicht gefunden → ernsthaftes Problem
                logger.warning(
                    f"[CookieBanner] Banner existiert (height={banner_state.get('height')}) "
                    f"aber Accept-All Button konnte nicht lokalisiert werden! "
                    f"Banner könnte sich in unbekanntem DOM-Zustand befinden."
                )
                return False
            else:
                # Banner existiert nicht → er wurde bereits vorher dismissed
                logger.debug(
                    f"[CookieBanner] Kein Cookie-Banner auf der Seite. "
                    f"Consent wurde zuvor bereits gegeben oder Banner nie geladen."
                )
                return True

        # ════════════════════════════════════════════════════════════════════════
        # PHASE 2: CDP Coordinate-based Click
        # ════════════════════════════════════════════════════════════════════════
        #
        # WIR HABEN DEN BUTTON GEFUNDEN! Jetzt klicken wir per CDP-Koordinaten.
        #
        # Warum NICHT JS .click() verwenden?
        # → Siehe Kommentar-Dokumentation oben (PROBLEM HISTORISCHER KONTEXT)
        #
        # Warum CDP click_at() funktioniert:
        # 1. Input.dispatchMouseEvent mit type="mousePressed" sendet ein echtes
        #    Mousedown-Event an den Browser-Prozess
        # 2. Input.dispatchMouseEvent mit type="mouseReleased" sendet ein echtes
        #    Mouseup-Event
        # 3. Der Cookiebot-Consent-Handler fängt ECHTE User-Events ab (via
        #    document.addEventListener für mousedown/mouseup)
        # 4. Das synthetische CDP-Event wird als ECHTE User-Interaktion
        #    behandelt → Handler verarbeitet es korrekt
        #
        # Koordinaten-Berechnung:
        # - wir haben center_x = r.x + r.width / 2 (horizontal center)
        # - center_y = r.y + r.height / 2 (vertical center)
        # - Für Accept All: x=1052.5, w=122.5 → center_x=1113.75
        #                   y=785.5, h=40.0 → center_y=805.5
        #
        # click_at() intern:
        # → client.click_at() ruft Input.dispatchMouseEvent zweimal auf:
        #   1. {type: "mousePressed", x: center_x, y: center_y, button: "left"}
        #   2. {type: "mouseReleased", x: center_x, y: center_y, button: "left"}
        # → Dies löst automatisch ein "click" Event nach dem Release aus
        # → Der Browser generiert ein PointerEvent + ClickEvent
        #
        cx = btn_info.get("x")
        cy = btn_info.get("y")
        btn_text = btn_info.get("text", "Accept All")
        btn_selector = btn_info.get("selector", "unknown")
        btn_phase = btn_info.get("phase", 0)
        btn_w = btn_info.get("w", 0)
        btn_h = btn_info.get("h", 0)

        logger.info(
            f"[CookieBanner] Phase {btn_phase}: Accept-All Button gefunden via "
            f"Selector '{btn_selector}'. Koordinaten: ({cx:.1f}, {cy:.1f}), "
            f"Größe: {btn_w:.1f}x{btn_h:.1f}px, Text: '{btn_text}'. "
            f"Sende CDP coordinate click..."
        )

        # Der eigentliche CDP-Koordinaten-Klick
        # WICHTIG: click_at() ist in cdp_client.py implementiert als:
        #   Input.dispatchMouseEvent(type="mousePressed", x=cx, y=cy, button="left")
        #   + Input.dispatchMouseEvent(type="mouseReleased", x=cx, y=cy, button="left")
        await client.click_at(session_id, x=cx, y=cy)

        logger.debug(
            f"[CookieBanner] CDP click gesendet an ({cx:.1f}, {cy:.1f}). "
            f"Warte auf Banner-Collapse..."
        )

        # ════════════════════════════════════════════════════════════════════════
        # PHASE 3: Validierung — Banner wirklich dismissed?
        # ════════════════════════════════════════════════════════════════════════
        #
        # Nach dem Klick wartet der Cookiebot ~500ms und updated dann das DOM:
        # - Der .cky-consent-container bekommt display: none
        # - ODER seine height wird auf 0 reduziert (Animation)
        # - Der Inhalt (Buttons, Text) bleibt im DOM aber ist unsichtbar
        #
        # Wir warten 2 Sekunden (2000ms) und prüfen dann:
        # 1. Ob .cky-consent-container noch sichtbar ist (height > 0)
        # 2. Ob display !== 'none'
        #
        await asyncio.sleep(2)

        validate_js = '''
        (function() {
            const container = document.querySelector('.cky-consent-container');
            if (!container) {
                return {
                    dismissed: true,
                    reason: 'container_gone',
                    containerExists: false
                };
            }
            const r = container.getBoundingClientRect();
            const style = window.getComputedStyle(container);
            const visible = r.height > 0 && style.display !== 'none' && style.opacity !== '0';
            return {
                dismissed: !visible,
                reason: visible ? 'still_visible' : 'collapsed',
                containerExists: true,
                height: r.height,
                display: style.display,
                opacity: style.opacity,
                width: r.width
            };
        })()
        '''

        validate_result = await client.evaluate(
            session_id,
            validate_js,
            return_by_value=True
        )
        validate_state = validate_result.get("result", {}).get("value", {})

        dismissed = validate_state.get("dismissed", False)

        if dismissed:
            logger.info(
                f"[CookieBanner] ✅ SUCCESS: Cookie-Banner dismissed! "
                f"Container ist {'verschwunden' if not validate_state.get('containerExists') else 'collapsed (height=' + str(validate_state.get('height')) + ', display=' + str(validate_state.get('display')) + ')'}. "
                f"Registrierungsformular ist jetzt frei zugänglich."
            )
            return True
        else:
            logger.warning(
                f"[CookieBanner] ⚠️ PARTIAL: CDP click gesendet aber Banner noch sichtbar! "
                f"Container height={validate_state.get('height')}, "
                f"display={validate_state.get('display')}, "
                f"opacity={validate_state.get('opacity')}. "
                f"Versuche alternativen Ansatz (Accept All Button im Preferences-Panel)..."
            )

            # ══════════════════════════════════════════════════════════════════
            # FALLBACK: Accept All Button im Cookie Preferences Panel
            # ══════════════════════════════════════════════════════════════════
            #
            # Manchmal gibt es im Banner zwei "Accept All" Buttons:
            # 1. Im Notice-Banner (ganz unten, sichtbar)
            # 2. Im Customise/Preferences-Panel (wenn man Customize klickt)
            #
            # Der Button im Preferences Panel hat:
            # - x=158.1, y=1849.5 (off-screen, y > viewport height)
            # - Wir müssen erst Customize klicken um ihn sichtbar zu machen
            #
            # Alternativ versuchen wir "Reject All" falls "Accept All" fehlschlug

            fallback_js = '''
            (function() {
                // Suche Reject All Button als Alternative
                const rejectBtns = document.querySelectorAll('.cky-btn-reject, button.cky-btn.cky-btn-reject');
                for (const btn of rejectBtns) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.y >= 0 && r.y < 2000) {
                        return {
                            found: true,
                            x: r.x + r.width / 2,
                            y: r.y + r.height / 2,
                            text: btn.textContent?.trim(),
                            type: 'reject'
                        };
                    }
                }
                // Suche Accept All im Preferences Panel (auch mit Reject All)
                const prefBtns = document.querySelectorAll('.cky-prefrence-btn-wrapper button');
                for (const btn of prefBtns) {
                    const r = btn.getBoundingClientRect();
                    const text = (btn.textContent || '').trim().toLowerCase();
                    if (r.width > 0 && r.height > 0 && text.includes('accept')) {
                        return {
                            found: true,
                            x: r.x + r.width / 2,
                            y: r.y + r.height / 2,
                            text: btn.textContent?.trim(),
                            type: 'accept_preferences'
                        };
                    }
                }
                // Letzte Hoffnung: Button mit aria-label oder data-attribut
                const allBtns = document.querySelectorAll('button');
                for (const btn of allBtns) {
                    const r = btn.getBoundingClientRect();
                    const label = btn.getAttribute('aria-label') || '';
                    const title = btn.getAttribute('title') || '';
                    const text = (btn.textContent || '').trim();
                    if (r.width > 0 && r.height > 0 && r.y >= 0 && r.y < 2000) {
                        if (label.toLowerCase().includes('accept') ||
                            title.toLowerCase().includes('accept') ||
                            (text.toLowerCase().includes('accept') && text.toLowerCase().includes('all'))) {
                            return {
                                found: true,
                                x: r.x + r.width / 2,
                                y: r.y + r.height / 2,
                                text: text || label || title,
                                type: 'aria_fallback'
                            };
                        }
                    }
                }
                return {found: false};
            })()
            '''

            fb_result = await client.evaluate(
                session_id,
                fallback_js,
                return_by_value=True
            )
            fb_info = fb_result.get("result", {}).get("value", {})

            if fb_info.get("found"):
                fb_cx = fb_info.get("x")
                fb_cy = fb_info.get("y")
                fb_text = fb_info.get("text", "Fallback Button")
                fb_type = fb_info.get("type", "unknown")

                logger.info(
                    f"[CookieBanner] Fallback: Klicke '{fb_type}' Button "
                    f"({fb_cx:.1f}, {fb_cy:.1f}): '{fb_text}'"
                )
                await client.click_at(session_id, x=fb_cx, y=fb_cy)
                await asyncio.sleep(2)

                # Erneut validieren
                fb_validate = await client.evaluate(
                    session_id,
                    '''
                    (function() {
                        const c = document.querySelector('.cky-consent-container');
                        if (!c) return {dismissed: true, reason: 'container_gone'};
                        const r = c.getBoundingClientRect();
                        const s = window.getComputedStyle(c);
                        return {
                            dismissed: r.height === 0 || s.display === 'none',
                            height: r.height,
                            display: s.display
                        };
                    })()
                    ''',
                    return_by_value=True
                )
                fb_state = fb_validate.get("result", {}).get("value", {})
                if fb_state.get("dismissed"):
                    logger.info(
                        f"[CookieBanner] ✅ Fallback SUCCESS: Banner dismissed via "
                        f"'{fb_type}' Button."
                    )
                    return True

            # Alles fehlgeschlagen
            logger.error(
                f"[CookieBanner] ❌ FAILURE: Cookie-Banner konnte nicht dismissed "
                f"werden. Accept All (Primär), Reject All (Fallback), "
                f"Preferences Panel, aria-label Fallback — alles versucht, "
                f"nichts hat funktioniert. Registrierung könnte trotzdem "
                f"klappen wenn der Banner sich selbst dismissed oder "
                f"gar nicht erschienen ist."
            )
            return False

    async def register(
        self, email: str, password: str, cdp_port: int = 9222, timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Registriert neuen Fireworks AI Account.

        FLOW:
        1. Navigate zu /signup
        2. Cookie Banner dismissen (Accept All)
        3. Email eingeben
        4. "Next" oder "Continue" klicken
        5. Passwort eingeben
        6. "Create Account" oder "Sign Up" klicken
        7. Warten auf Redirect oder Bestätigungs-Meldung

        Args:
            email: GMX Alias Email
            password: Passwort für Fireworks Account
            cdp_port: CDP Port des Browsers
            timeout: Sekunden pro Schritt

        Returns:
            {"status": "success"|"failed"|"error", "account_email": str}
        """
        start_time = time.time()
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            logger.info(f"Fireworks Registrierung: {email}")

            await client.navigate(session_id, FIREWORKS_SIGNUP_URL)
            await asyncio.sleep(3)

            await self._dismiss_cookie_banner(client, session_id)
            await asyncio.sleep(1)
            await self._screenshot(client, session_id, "fw_signup")

            email_selectors = [
                'input[id="email-display"]',
                'input[type="email"]',
                'input[name="email"]',
                'input[id*="email"]',
                'input[placeholder*="email" i]',
                'input[autocomplete="email"]',
            ]
            if not await self._fill_input(client, session_id, email_selectors, email):
                return {"status": "failed", "account_email": email, "error": "Email-Feld nicht gefunden", "steps_completed": []}
            await asyncio.sleep(1)
            await self._screenshot(client, session_id, "fw_email_filled")

            next_selectors = [
                'button[type="submit"]',
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button:has-text("Weiter")',
                'a:has-text("Next")',
            ]
            if not await self._click_button(client, session_id, next_selectors):
                return {"status": "failed", "account_email": email, "error": "Next-Button nicht gefunden", "steps_completed": ["email_entered"]}
            await asyncio.sleep(4)
            await self._screenshot(client, session_id, "fw_after_next")

            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[id*="password"]',
            ]
            if not await self._fill_input(client, session_id, password_selectors, password):
                return {"status": "failed", "account_email": email, "error": "Passwort-Feld nicht gefunden", "steps_completed": ["email_entered", "next_clicked"]}
            await asyncio.sleep(1)

            create_selectors = [
                'button[type="submit"]',
                'button:has-text("Create")',
                'button:has-text("Sign Up")',
                'button:has-text("Register")',
                'button:has-text("Konto erstellen")',
            ]
            if not await self._click_button(client, session_id, create_selectors):
                return {"status": "failed", "account_email": email, "error": "Create-Button nicht gefunden", "steps_completed": ["email_entered", "next_clicked", "password_entered"]}
            await asyncio.sleep(5)
            await self._screenshot(client, session_id, "fw_after_create")

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

            elapsed = time.time() - start_time
            is_error = any(k in body_text.lower() for k in ["error", "already", "exists", "taken", "invalid"])
            is_success = any(k in body_text.lower() for k in ["verify", "confirm", "email", "sent", "check", "link", "created", "success"])

            if is_error:
                logger.warning(f"Fireworks meldet Fehler: {body_text[:200]}")
                return {"status": "failed", "account_email": email, "error": body_text[:300], "execution_time": f"{elapsed:.2f}s", "steps_completed": ["email_entered", "next_clicked", "password_entered", "create_clicked"]}

            logger.info(f"Registration abgeschlossen: {current_url}")
            return {
                "status": "success",
                "account_email": email,
                "current_url": current_url,
                "execution_time": f"{elapsed:.2f}s",
                "steps_completed": ["email_entered", "next_clicked", "password_entered", "create_clicked", "account_created"],
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Fireworks Registration fehlgeschlagen: {e}")
            return {"status": "error", "account_email": email, "error": str(e), "execution_time": f"{elapsed:.2f}s", "steps_completed": []}
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