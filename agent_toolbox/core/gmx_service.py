"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — GMX Service                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ⚠️  WICHTIG: CUA DRIVER IST IMMER DIE ERSTE WAHL!                           ║
║  GMX Extension für Email-Zugriff — NICHT lightmailer URLs!                   ║
║  Siehe command_registry.json für vollständige Dokumentation.                 ║
║                                                                              ║
║  ZWECK:                                                                      ║
║  GMX Session-Management, Alias-Erstellung/Löschung, OTP-Lesen               ║
║                                                                              ║
║  CUA PRIMÄR FÜR:                                                            ║
║  ✅ Navigation: GMX Homepage → E-Mail → Settings                             ║
║  ✅ Dialog-Buttons: OK, Abbrechen (via AXPress nach Dialog-Scan)            ║
║  ✅ Alias-Erstellungs-Input + Button                                         ║
║                                                                              ║
║  CDP NUR FÜR HOVER + DELETE-ICON (accessible mode workaround):              ║
║  ✅ DOM.performSearch → Alias-Koordinaten im 3c.gmx.net Iframe finden       ║
║  ✅ Input.dispatchMouseEvent mouseMoved → Hover über Alias-Row              ║
║  ✅ DOM.performSearch → delete icon title="E-Mail-Adresse löschen"          ║
║  ✅ Input.dispatchMouseEvent → Klick auf delete icon                        ║
║  ❌ Runtime.evaluate auf GMX accessible pages = leeres {}                   ║
║                                                                              ║
║  GMX EXTENSION (GMX MailCheck) — FÜR OTP/EMAIL:                             ║
║  ✅ Extension ID: camnampocfohlcgbajligmemmabnljcm                           ║
║  ✅ Email-Format: 18 Ziffern                                                ║
║                                                                              ║
║  ❌ VERBOTEN:                                                                ║
║  ❌ CDP Runtime.evaluate auf GMX (accessible mode = leer)                   ║
║  ❌ CDP Page.navigate = HTTP Request = Bot-Detection (413/302/403)          ║
║  ❌ lightmailer-bs.gmx.net URLs                                             ║
║  ❌ Chrome killen (pkill -9)                                                ║
║                                                                              ║
║  ALIAS LÖSCHEN (VERIFIED 2026-05-11):                                        ║
║  1. CUA: zur E-Mail-Adressen Seite navigieren                                ║
║  2. CDP DOM.performSearch: "@gmx.de" im Iframe → Alias-Koordinaten         ║
║  3. CDP Input.dispatchMouseEvent mouseMoved → Hover → Delete-Icon erscheint ║
║  4. CDP DOM.performSearch: "E-Mail-Adresse löschen" → Delete-Icon klicken   ║
║  5. CUA get_window_state: Dialog "OK" Button finden                         ║
║  6. CUA click: "OK" Button → Löschung bestätigen                            ║
║                                                                              ║
║  ALIAS ERSTELLEN:                                                            ║
║  1. Input[name*="localPart"] mit CDP nativeInputValueSetter                  ║
║  2. Hinzufügen-Button via CUA click                                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import random
import logging
import re
import asyncio
import subprocess
import base64
import json
import html as html_module
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import httpx

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

logger = logging.getLogger(__name__)

GMX_HOME_URL = "https://www.gmx.net/"


class GmxService:
    """
    Verwaltet GMX-Operationen via RAW CDP WEBSOCKET im Main Frame Default Context.
    """

    def __init__(self):
        self.adjectives = [
            "elron", "dark", "swift", "iron", "silver", "golden", "crystal", "shadow",
            "storm", "frost", "blaze", "thunder", "cosmic", "neon", "cyber", "quantum",
            "alpha", "beta", "delta", "omega", "zenith", "nexus", "vortex", "pulse",
            "echo", "phantom", "spectra", "turbo", "hyper", "ultra", "mega", "super",
        ]
        self.nouns = [
            "vader", "runner", "hawk", "wolf", "fox", "tiger", "eagle", "shark",
            "dragon", "phoenix", "falcon", "panther", "cobra", "lynx", "raven", "jaguar",
            "bear", "lion", "whale", "dolphin", "puma", "cheetah", "otter", "badger",
            "wolverine", "raptor", "condor", "falcon", "scorpion", "spider", "mantis", "beetle",
        ]

    def generate_alias_name(self) -> str:
        """Generiert einen Alias-Namen im Format {adj}-{noun}-{number}.
        
        Der 3-stellige Zufallszahl-Suffix reduziert Kollisionen auf GMX erheblich.
        """
        adj = random.choice(self.adjectives)
        noun = random.choice(self.nouns)
        num = random.randint(100, 999)
        return f"{adj}-{noun}-{num}"

    # ═══════════════════════════════════════════════════════════════════════════════
    #  CDP CONNECTION
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _connect_to_browser(self, cdp_port: int) -> Tuple[CDPClient, str, str]:
        """Erstellt eine CDP-Verbindung zum laufenden Browser."""
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
        logger.info(f"CDP Session bereit: target={target_id[:15]}...")
        return client, session_id, target_id

    async def _screenshot(self, client: CDPClient, session_id: str, label: str) -> str:
        """Macht einen Screenshot und speichert ihn unter /tmp."""
        ts = int(time.time())
        path = f"/tmp/gmx_{label}_{ts}.png"
        try:
            await client.screenshot(session_id, path=path)
            return path
        except Exception as e:
            logger.warning(f"Screenshot fehlgeschlagen für {label}: {e}")
            return ""

    # ═══════════════════════════════════════════════════════════════════════════════
    #  NAVIGATION
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _inject_saved_cookies(self, client: CDPClient, session_id: str) -> int:
        """Injiziert gespeicherte GMX-Cookies aus data/gmx-cookies.json via CDP.

        Wichtig: Wenn Chrome neu gestartet wurde, sind die Session-Cookies
        (die den eingeloggten Zustand bei GMX halten) verloren. Die gespeicherte
        Cookie-Datei enthält die Cookies von der letzten funktionierenden Session.
        Durch Injektion via CDP Network.setCookie können wir die Session
        wiederherstellen OHNE erneuten Login.

        Args:
            client: CDPClient Instanz (bereits verbunden)
            session_id: CDP Session ID des Tabs

        Returns:
            Anzahl erfolgreich injizierter Cookies
        """
        cookies_file = Path("./data/gmx-cookies.json")
        if not cookies_file.exists():
            logger.warning("Keine gespeicherten Cookies gefunden: %s", cookies_file)
            return 0

        try:
            with open(cookies_file, "r") as f:
                cookies = json.load(f)
        except Exception as e:
            logger.warning("Cookie-Datei konnte nicht geladen werden: %s", e)
            return 0

        injected = 0
        for cookie in cookies:
            try:
                # CDP Network.setCookie Parameter
                params = {
                    "name": cookie.get("name"),
                    "value": cookie.get("value"),
                    "domain": cookie.get("domain"),
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                }
                # sameSite kann "Strict", "Lax", "None" oder undefined sein
                same_site = cookie.get("sameSite")
                if same_site and same_site != "None":
                    params["sameSite"] = same_site

                # expires: -1 = Session-Cookie, sonst Unix-Timestamp
                expires = cookie.get("expires", -1)
                if expires and expires != -1:
                    try:
                        params["expires"] = float(expires)
                    except (ValueError, TypeError):
                        pass  # Ungültiger Wert, überspringen

                result = await client.send_to_session(session_id, "Network.setCookie", params)
                if result and not result.get("error"):
                    injected += 1
                else:
                    logger.debug("Cookie-Injektion fehlgeschlagen für %s: %s",
                                 cookie.get("name"), result.get("error") if result else "no response")
            except Exception as e:
                logger.debug("Cookie-Injektion fehlgeschlagen für %s: %s", cookie.get("name"), e)

        logger.info("%d/%d GMX-Cookies via CDP injiziert", injected, len(cookies))
        return injected

    async def _ensure_mail_session(self, client: CDPClient, session_id: str) -> Dict[str, Any]:
        """Stellt sicher, dass eine GMX Mail-Session aktiv ist.

        STRATEGIE (mit Cookie-Injektion):
        1. Zuerst gespeicherte Cookies injizieren (wiederhergestellte Session)
        2. Dann zur GMX Homepage navigieren
        3. Wenn Cookies funktionieren: E-Mail Link führt direkt zu bap.navigator.gmx.net/mail?sid=...
        4. Wenn nicht: Session ist abgelaufen → Fehler (manueller Login nötig)

        Returns:
            {"success": bool, "current_url": str, "sid": str|None}
        """
        # ── STEP 0: Gespeicherte Cookies injizieren ─────────────────────────────
        await self._inject_saved_cookies(client, session_id)
        await asyncio.sleep(1)

        url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        current_url = url_result.get("result", {}).get("value", "")

        # Already on 3c-bap settings page (direct navigation successful)
        if "3c-bap.gmx.net" in current_url and "jsessionid" in current_url:
            logger.info(f"Bereits auf GMX Settings: {current_url[:80]}")
            return {"success": True, "current_url": current_url, "sid": None}

        # Already on mail_settings or mail page with SID
        if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
            sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
            sid = sid_match.group(1) if sid_match else None
            if sid and "mail_settings" in current_url:
                return {"success": True, "current_url": current_url, "sid": sid}
            if sid and "mail" in current_url:
                # Navigate to mail_settings with SID
                settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
                await client.navigate(session_id, settings_url)
                await asyncio.sleep(5)
                return {"success": True, "current_url": settings_url, "sid": sid}

        # Navigate to GMX homepage first (unless already there)
        # We must be on the homepage for the E-Mail nav click to lead to the
        # logged-in mailbox (bap.navigator.gmx.net/mail?sid=...).
        # On subpages (e.g. /magazine/...), the E-Mail link goes to a marketing
        # page without SID.
        is_homepage = current_url.rstrip('/') in ["https://www.gmx.net", "https://www.gmx.net/", "http://www.gmx.net", "http://www.gmx.net/"]
        if not is_homepage:
            logger.info("Navigiere zu GMX Homepage vor E-Mail Klick")
            await client.navigate(session_id, "https://www.gmx.net/")
            await asyncio.sleep(4)
        else:
            logger.info("Bereits auf GMX Homepage")
        
        # Click E-Mail nav
        click_result = await client.evaluate(session_id, '''
        (function(){
            const els = Array.from(document.querySelectorAll("a, button, [role=link], nav a"));
            const emailEl = els.find(e => (e.textContent||"").trim() === "E-Mail");
            if (emailEl) { emailEl.click(); return true; }
            return false;
        })()''', return_by_value=True)
        clicked = click_result.get("result", {}).get("value", False)
        if not clicked:
            logger.warning("E-Mail Nav Element nicht gefunden, fallback via JS querySelectorAll")
            await client.evaluate(
                session_id,
                """
                (function() {
                    var links = document.querySelectorAll('a');
                    for (var i=0; i<links.length; i++) {
                        var t = links[i].textContent.trim().toLowerCase();
                        if (t === 'e-mail') {
                            links[i].click();
                            return true;
                        }
                    }
                    return false;
                })()
                """,
                return_by_value=True,
            )
        await asyncio.sleep(5)

        # Extract SID from mail page URL
        url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        current_url = url_result.get("result", {}).get("value", "")

        sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
        sid = sid_match.group(1) if sid_match else None

        if sid and "navigator.gmx.net" in current_url:
            logger.info(f"GMX sid extrahiert: {sid[:30]}...")
            # Navigate to mail_settings with SID
            settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
            await client.navigate(session_id, settings_url)
            await asyncio.sleep(5)
            return {"success": True, "current_url": settings_url, "sid": sid}

        return {"success": False, "current_url": current_url, "error": "Konnte keine GMX Session aktivieren"}

    async def _click_element_by_text_cdp(self, client: CDPClient, session_id: str, text: str) -> bool:
        """
        ════════════════════════════════════════════════════════════════════════════════
        CDP MOUSE CLICK BY TEXT CONTENT — WICKET EVENT BYPASS
        ════════════════════════════════════════════════════════════════════════════════

        ZWECK:
        Findet ein DOM-Element anhand seines `textContent.trim()` und führt einen
        echten Maus-Click via Chrome DevTools Protocol `Input.dispatchMouseEvent`
        aus. Das ist der EINZIGE zuverlässige Weg, Wicket-basierte SPAs wie GMX
        zu bedienen.

        WARUM KEIN JS .click()?
        ────────────────────────────────────────────────────────────────────────────────
        GMX's Wicket Framework reagiert NICHT auf synthetische JS-Events wie
        `element.click()`, `dispatchEvent(new MouseEvent(...))`, oder
        `dispatchEvent(new PointerEvent(...))`. Wicket verlangt echte
        Chrome-Compositor Mouse-Events die über CDP `Input.dispatchMouseEvent`
        mit den korrekten Sequenzen (`mouseMoved` → `mousePressed` →
        `mouseReleased`) gesendet werden.

        ERKENNTNIS (2026-05-08):
        JS .click() auf "E-Mail-Adressen" Link auf der 3c-bap Signature Seite
        ändert die URL NICHT. CDP Input.dispatchMouseEvent auf die exakten
        Koordinaten des <A> Tags ändert die URL innerhalb von 3 Sekunden zu
        `allEmailAddresses`.

        DOM-SELEKTIONSSTRATEGIE:
        ────────────────────────────────────────────────────────────────────────────────
        Wir suchen in einem breiten Selektor-Pool:
          "a, button, [role=link], [role=button], li, span, div"
        Das erste Element dessen `textContent.trim() === text` ist wird
        selektiert. Wir bevorzugen damit interaktive Elemente (A, BUTTON)
        gegenüber generischen Container-DIVs.

        KOORDINATENBERECHNUNG:
        ────────────────────────────────────────────────────────────────────────────────
        Wir berechnen den Mittelpunkt des Elements via `getBoundingClientRect()`:
          x = rect.x + rect.width / 2
          y = rect.y + rect.height / 2
        Das Element MUSS `rect.width > 0 && rect.height > 0` haben,
        sonst ist es nicht gerendert (z.B. display:none).

        CDP EVENT SEQUENZ:
        ────────────────────────────────────────────────────────────────────────────────
        1. mouseMoved   → positioniert den virtuellen Mauszeiger
        2. sleep(0.3s)  → gibt Chrome Zeit für Hover-Effekte / event bubbling
        3. mousePressed → linke Maustaste drücken (clickCount=1)
        4. mouseReleased→ linke Maustaste loslassen (clickCount=1)

        Args:
            client: CDPClient Instanz (bereits verbunden)
            session_id: CDP Session ID des Tabs
            text: Exakter textContent.trim() des zu klickenden Elements

        Returns:
            True wenn das Element gefunden und geklickt wurde, False sonst
        ════════════════════════════════════════════════════════════════════════════════
        """
        safe_text = text.replace('"', '\\"')
        # JS-Funktion die durch alle interaktiven Elemente iteriert und
        # das erste mit matching textContent zurückgibt.
        js = f'''(function(){{
            const all = document.querySelectorAll("a, button, [role=link], [role=button], li, span, div");
            for (const el of all) {{
                if (el.textContent.trim() === "{safe_text}") {{
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {{
                        return {{
                            found: true,
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2,
                            tag: el.tagName,
                        }};
                    }}
                }}
            }}
            return {{found: false}};
        }})()'''
        result = await client.evaluate(session_id, js, return_by_value=True)
        val = result.get("result", {}).get("value", {})
        if not val.get("found"):
            logger.warning(f"Element mit Text '{text}' nicht gefunden oder hat zero rect")
            return False
        x, y = val["x"], val["y"]
        logger.info(f"CDP click '{text}' ({val.get('tag')}) at ({x:.1f}, {y:.1f})")
        # CDP Mouse Event Sequenz (kritisch für Wicket):
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y,
        })
        await asyncio.sleep(0.3)
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1,
        })
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1,
        })
        return True

    async def _navigate_to_all_email_addresses(self, client: CDPClient, session_id: str) -> bool:
        """
        ════════════════════════════════════════════════════════════════════════════════
        NAVIGATION ZU allEmailAddresses (GMX Alias-Verwaltung)
        ════════════════════════════════════════════════════════════════════════════════

        ZWECK:
        Navigiert zur Seite "E-Mail-Adressen" (allEmailAddresses) im GMX
        Mail-Settings Bereich, wo Aliasse erstellt und gelöscht werden können.

        GMX URL-ARCHITEKTUR (SPA / Wicket):
        ────────────────────────────────────────────────────────────────────────────────
        GMX nutzt eine komplexe Single-Page-Application mit mehreren Hosts:

          bap.navigator.gmx.net     → Navigator-Frame (SID-basierte Navigation)
          3c-bap.gmx.net            → Mail-Client SPA (Wicket, jsessionid-basiert)
          webmailer.gmx.net         → Webmailer-Wrapper (iframe-Loader)

        Die Navigation zwischen diesen Hosts erfolgt via:
          1. `navigator/jump/to/mail_settings?sid=...` → redirect zu 3c-bap
          2. SPA-Click auf "E-Mail-Adressen" → history.pushState zu allEmailAddresses

        NAVIGATIONSPFADE (abgedeckt in dieser Methode):
        ────────────────────────────────────────────────────────────────────────────────
        PFAD A: Bereits auf allEmailAddresses
          → Keine Navigation nötig, sofort return True.

        PFAD B: Auf 3c-bap.gmx.net Signature-Seite
          → CDP-Click auf "E-Mail-Adressen" Link (JS .click() funktioniert NICHT).
          → Warte 6 Sekunden auf SPA-Transition.
          → Prüfe ob URL `allEmailAddresses` enthält.

        PFAD C: Auf bap.navigator.gmx.net mit SID
          → Extrahiere SID aus aktueller URL.
          → Navigiere zu `navigator/jump/to/mail_settings?sid=...`
          → Warte auf Redirect zu 3c-bap Signature-Seite.
          → CDP-Click auf "E-Mail-Adressen" (wie PFAD B).

        PFAD D: Fallback (beliebige andere Seite)
          → Rufe `_ensure_mail_session()` auf um SID zu erhalten.
          → Navigiere via Jump-URL zu 3c-bap.
          → CDP-Click auf "E-Mail-Adressen".

        WARUM CDP CLICK STATT JS .click()?
        ────────────────────────────────────────────────────────────────────────────────
        Die "E-Mail-Adressen" Navigation ist ein <A> Tag mit href. Man würde
        erwarten, dass JS .click() funktioniert. Aber empirisch (2026-05-08)
        hat sich gezeigt, dass JS .click() auf diesem Link die URL NICHT ändert,
        während CDP Input.dispatchMouseEvent die URL innerhalb von 3 Sekunden
        zu allEmailAddresses ändert.

        MÖGLICHE URSACHE:
        Wicket's Link-Component überprüft event.isTrusted oder nutzt einen
        mousedown-Handler der auf synthetische Events nicht reagiert.
        CDP-generierte Events haben isTrusted=true im Browser-Compositor.

        Args:
            client: CDPClient Instanz (bereits verbunden)
            session_id: CDP Session ID des Tabs

        Returns:
            True wenn die Navigation erfolgreich war und die URL
            `allEmailAddresses` enthält, False sonst.
        ════════════════════════════════════════════════════════════════════════════════
        """
        url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        current_url = url_result.get("result", {}).get("value", "")

        # ──────────────────────────────────────────────────────────────────────────────
        # PFAD A: Bereits auf allEmailAddresses → nichts tun
        # ──────────────────────────────────────────────────────────────────────────────
        if "allEmailAddresses" in current_url:
            logger.info("Bereits auf allEmailAddresses")
            return True

        # ──────────────────────────────────────────────────────────────────────────────
        # PFAD B: Auf 3c-bap Signature/Settings Seite
        # Wenn wir bereits auf der 3c-bap Settings Seite sind (nach Jump-URL
        # oder direkter Navigation), müssen wir nur noch den "E-Mail-Adressen"
        # Link in der Sidebar klicken.
        # ──────────────────────────────────────────────────────────────────────────────
        if "3c-bap.gmx.net" in current_url and "signature" in current_url:
            logger.info("Auf 3c-bap signature Seite, klicke E-Mail-Adressen via CDP")
            clicked = await self._click_element_by_text_cdp(client, session_id, "E-Mail-Adressen")
            logger.info(f"E-Mail-Adressen CDP click: {clicked}")
            await asyncio.sleep(6)
            url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_result.get("result", {}).get("value", "")
            if "allEmailAddresses" in current_url:
                return True
            logger.warning(f"allEmailAddresses nicht geladen nach click, URL: {current_url[:80]}")
            return False

        # ──────────────────────────────────────────────────────────────────────────────
        # PFAD C: Auf bap.navigator.gmx.net mit SID
        # Wenn wir auf der Navigator-Seite sind (z.B. nach E-Mail Klick auf
        # der Homepage), extrahieren wir die SID und nutzen die Jump-URL.
        # ──────────────────────────────────────────────────────────────────────────────
        if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
            sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
            sid = sid_match.group(1) if sid_match else None
            if sid:
                jump_url = f"https://bap.navigator.gmx.net/navigator/jump/to/mail_settings?sid={sid}"
                logger.info(f"Navigiere via jump URL: {jump_url}")
                await client.navigate(session_id, jump_url)
                await asyncio.sleep(6)
                url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                current_url = url_result.get("result", {}).get("value", "")
                
                if "3c-bap.gmx.net" in current_url and "signature" in current_url:
                    # Nach Jump-URL sind wir auf der 3c-bap Signature Seite.
                    # CDP-Click auf "E-Mail-Adressen" wie in PFAD B.
                    clicked = await self._click_element_by_text_cdp(client, session_id, "E-Mail-Adressen")
                    logger.info(f"E-Mail-Adressen CDP click auf 3c-bap: {clicked}")
                    await asyncio.sleep(6)
                    url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                    current_url = url_result.get("result", {}).get("value", "")
                    if "allEmailAddresses" in current_url:
                        return True
                    return False
                elif "allEmailAddresses" in current_url:
                    # In seltenen Fällen landet die Jump-URL direkt auf
                    # allEmailAddresses (z.B. wenn wir von dort kamen).
                    return True
            return False

        # ──────────────────────────────────────────────────────────────────────────────
        # PFAD D: Fallback — Session aktivieren und navigieren
        # Wenn wir auf einer anderen Seite sind (z.B. Webmailer, about:blank,
        # oder Fireworks), rufen wir _ensure_mail_session auf um eine frische
        # GMX Session mit SID zu bekommen, und navigieren dann via Jump-URL.
        # ──────────────────────────────────────────────────────────────────────────────
        session = await self._ensure_mail_session(client, session_id)
        if not session["success"]:
            return False
        
        sid = session.get("sid")
        if sid:
            jump_url = f"https://bap.navigator.gmx.net/navigator/jump/to/mail_settings?sid={sid}"
            await client.navigate(session_id, jump_url)
            await asyncio.sleep(6)
            url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_result.get("result", {}).get("value", "")
            
            if "3c-bap.gmx.net" in current_url and "signature" in current_url:
                clicked = await self._click_element_by_text_cdp(client, session_id, "E-Mail-Adressen")
                logger.info(f"E-Mail-Adressen CDP click (fallback): {clicked}")
                await asyncio.sleep(6)
                url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                current_url = url_result.get("result", {}).get("value", "")
                if "allEmailAddresses" in current_url:
                    return True
        
        return False

    # ═══════════════════════════════════════════════════════════════════════════════
    #  ALIAS DELETION
    # ═══════════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════════
    #  ALIAS DELETION (VERIFIED 2026-05-11)
    #  HYBRID: CDP DOM + Input.dispatchMouseEvent for hover/delete-icon
    #          CUA for dialog OK button
    #  Key: Alias content is in 3c.gmx.net CROSS-ORIGIN IFRAME
    #       Runtime.evaluate returns EMPTY on accessible GMX pages
    #       Use DOM.performSearch + Input.dispatchMouseEvent instead
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _get_gmx_iframe_frame_id(self, client: CDPClient, session_id: str) -> Optional[str]:
        """Findet die frameId des 3c.gmx.net Iframes im Haupt-Dokument."""
        doc = await client.send_to_session(session_id, "DOM.getDocument", {"depth": 2})
        result = await client.send_to_session(session_id, "DOM.querySelectorAll", {
            "nodeId": doc['root']['nodeId'],
            "selector": "iframe[src*='3c.gmx.net']"
        })
        if not result.get('nodeIds'):
            logger.warning("3c.gmx.net iframe nicht gefunden")
            return None
        info = await client.send_to_session(session_id, "DOM.describeNode", {
            "nodeId": result['nodeIds'][0], "depth": 1
        })
        return info['node'].get('frameId')

    async def _find_alias_coords_in_iframe(
        self, client: CDPClient, session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Findet den Alias (nicht opensin@gmx.de) via DOM.performSearch und gibt Koordinaten zurück.
        
        Returns: {text: str, x: float, y: float, w: float, h: float} oder None
        """
        search = await client.send_to_session(session_id, "DOM.performSearch", {
            "query": "@gmx.de",
            "includeUserAgentShadowDOM": True
        })
        if search['resultCount'] == 0:
            return None

        nodes = await client.send_to_session(session_id, "DOM.getSearchResults", {
            "searchId": search['searchId'],
            "fromIndex": 0,
            "toIndex": search['resultCount']
        })

        for nid in nodes['nodeIds']:
            try:
                info = await client.send_to_session(session_id, "DOM.describeNode", {
                    "nodeId": nid, "depth": 1
                })
                val = (info['node'].get('nodeValue', '') or '').strip()
                tag = info['node'].get('nodeName', '')
                # Skip JSON data, script content, main email
                if not val or val.startswith('{') or val == 'opensin@gmx.de' or tag != '#text':
                    continue
                if '@gmx.de' not in val:
                    continue

                box = await client.send_to_session(session_id, "DOM.getBoxModel", {
                    "nodeId": nid
                })
                c = box['model']['content']
                w = c[2] - c[0]
                h = c[7] - c[1]
                if w < 30 or h < 8:
                    continue

                return {
                    "text": val,
                    "x": c[0],
                    "y": c[1],
                    "w": w,
                    "h": h,
                    "nodeId": nid
                }
            except Exception:
                continue
        return None

    async def _cdp_hover(self, client: CDPClient, session_id: str, x: float, y: float):
        """Sendet CDP Input.dispatchMouseEvent mouseMoved (triggert CSS :hover)."""
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y
        })

    async def _cdp_click(self, client: CDPClient, session_id: str, x: float, y: float):
        """Sendet CDP Input.dispatchMouseEvent pressed + released."""
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": "left", "clickCount": 1
        })
        await asyncio.sleep(0.1)
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": "left", "clickCount": 1
        })

    async def _find_delete_icon_coords(
        self, client: CDPClient, session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Sucht nach dem Delete-Icon (title='E-Mail-Adresse löschen') VOR oder NACH hover."""
        for query in ["E-Mail-Adresse löschen", "löschen", "Löschen"]:
            search = await client.send_to_session(session_id, "DOM.performSearch", {
                "query": query,
                "includeUserAgentShadowDOM": True
            })
            if search['resultCount'] == 0:
                continue

            nodes = await client.send_to_session(session_id, "DOM.getSearchResults", {
                "searchId": search['searchId'],
                "fromIndex": 0,
                "toIndex": min(search['resultCount'], 10)
            })

            for nid in nodes['nodeIds']:
                try:
                    info = await client.send_to_session(session_id, "DOM.describeNode", {
                        "nodeId": nid, "depth": 2
                    })
                    node = info['node']
                    attrs = node.get('attributes', [])
                    attr_dict = {}
                    for j in range(0, len(attrs) - 1, 2):
                        attr_dict[attrs[j]] = attrs[j + 1]
                    title = attr_dict.get('title', '')

                    if 'lösch' not in title.lower():
                        continue

                    box = await client.send_to_session(session_id, "DOM.getBoxModel", {
                        "nodeId": nid
                    })
                    c = box['model']['content']
                    w = c[2] - c[0]
                    h = c[7] - c[1]
                    if w < 5 or h < 5:
                        continue

                    return {
                        "x": c[0] + w / 2,
                        "y": c[1] + h / 2,
                        "w": w,
                        "h": h,
                        "title": title,
                        "nodeId": nid
                    }
                except Exception:
                    continue
        return None

    async def _cua_click_ok_button(self, pid: int, window_id: int) -> bool:
        """Nutzt CUA um den OK-Button im Lösch-Bestätigungsdialog zu klicken."""
        import subprocess, re
        result = subprocess.run(
            ["cua-driver", "call", "get_window_state"],
            input=json.dumps({"pid": pid, "window_id": window_id}),
            capture_output=True, text=True, timeout=15
        )
        state = json.loads(result.stdout)
        lines = state.get('tree_markdown', '').split('\n')

        for line in lines:
            s = line.strip()
            if 'AXButton "OK"' not in s and 'AXButton "Abbrechen"' not in s:
                continue
            if 'OK' not in s:
                continue
            # Extract element_index from [pid] - [element_index] pattern
            m = re.search(r'\]\s*-\s*\[(\d+)\]\s*AXButton\s*"OK"', s)
            if m:
                el = int(m.group(1))
                logger.info(f"CUA click OK button at element_index {el}")
                subprocess.run(
                    ["cua-driver", "call", "click"],
                    input=json.dumps({
                        "pid": pid, "window_id": window_id, "element_index": el
                    }),
                    capture_output=True, text=True, timeout=10
                )
                return True
        logger.warning("OK button not found in CUA AX tree")
        return False

    async def delete_existing_alias(self, cdp_port: int = 9222) -> Dict[str, Any]:
        """Löscht einen existierenden GMX Alias.
        
        VERIFIED FLOW (2026-05-11):
        1. Navigiere zu E-Mail-Adressen (CUA, done externally or before)
        2. CDP DOM.performSearch "@gmx.de" → Alias-Koordinaten im Iframe
        3. CDP Input.dispatchMouseEvent mouseMoved → Hover → Delete-Icon erscheint
        4. CDP DOM.performSearch "löschen" → Delete-Icon Koordinaten
        5. CDP Input.dispatchMouseEvent → Klick auf Delete-Icon
        6. CUA scan + click → "OK" Button im Dialog
        
        Returns:
            {"status": "success"|"no_alias"|"not_logged_in"|"error", "deleted": bool, "alias": str|None}
        """
        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)
            await client.send_to_session(session_id, "DOM.enable")
            await asyncio.sleep(0.5)

            # Step 1: Ensure we're on E-Mail-Adressen page
            nav_ok = await self._navigate_to_all_email_addresses(client, session_id)
            if not nav_ok:
                return {"status": "not_logged_in", "deleted": False,
                        "error": "Konnte nicht zu allEmailAddresses navigieren"}

            # Step 2: Find alias in iframe via CDP DOM
            alias_info = await self._find_alias_coords_in_iframe(client, session_id)
            if not alias_info:
                logger.info("Kein Alias gefunden")
                return {"status": "no_alias", "deleted": True, "alias": None}

            alias_text = alias_info['text']
            logger.info(f"Alias gefunden: {alias_text} at ({alias_info['x']:.0f},{alias_info['y']:.0f})")

            # Step 3: CDP HOVER over alias row (triggers CSS :hover → delete icon appears)
            hover_x = alias_info['x'] + alias_info['w'] / 2
            hover_y = alias_info['y'] + alias_info['h'] / 2
            logger.info(f"Hover at ({hover_x:.0f}, {hover_y:.0f})")
            await self._cdp_hover(client, session_id, hover_x, hover_y)
            await asyncio.sleep(1)

            # Step 4: Find delete icon (now visible after hover)
            delete_info = await self._find_delete_icon_coords(client, session_id)
            if not delete_info:
                return {"status": "error", "deleted": False, "alias": alias_text,
                        "error": "Delete-Icon nicht gefunden nach Hover"}

            logger.info(f"Delete icon at ({delete_info['x']:.0f},{delete_info['y']:.0f})")

            # Step 5: CDP click on delete icon
            await self._cdp_click(client, session_id, delete_info['x'], delete_info['y'])
            await asyncio.sleep(3)

            # Step 6: CUA click OK button in dialog
            # We need the Chrome window pid + window_id
            # Use a known/fixed pid: 85447, or detect dynamically
            try:
                import subprocess as sp
                res = sp.run(
                    ["cua-driver", "call", "list_windows"],
                    input=json.dumps({"query": "Chrome"}),
                    capture_output=True, text=True, timeout=10
                )
                windows_data = json.loads(res.stdout)
                cua_pid = None
                cua_wid = None
                for w in windows_data.get('windows', []):
                    if 'GMX' in w.get('title', '') and w.get('is_on_screen'):
                        cua_pid = w['pid']
                        cua_wid = w['window_id']
                        break

                if cua_pid and cua_wid:
                    ok_clicked = await self._cua_click_ok_button(cua_pid, cua_wid)
                    if ok_clicked:
                        await asyncio.sleep(3)
                        logger.info(f"✅ Alias gelöscht: {alias_text}")
                        return {"status": "success", "deleted": True, "alias": alias_text}
                    else:
                        return {"status": "error", "deleted": False, "alias": alias_text,
                                "error": "OK-Button nicht gefunden im Dialog"}
                else:
                    return {"status": "error", "deleted": False, "alias": alias_text,
                            "error": "GMX Chrome window nicht gefunden via CUA"}
            except Exception as e:
                logger.error(f"CUA OK click failed: {e}")
                return {"status": "error", "deleted": False, "alias": alias_text,
                        "error": f"CUA dialog interaction failed: {e}"}

        except Exception as e:
            logger.error(f"Alias-Löschung fehlgeschlagen: {e}")
            return {"status": "error", "deleted": False, "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    # ═══════════════════════════════════════════════════════════════════════════════
    #  ALIAS CREATION
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _find_alias_input_info(self, client: CDPClient, session_id: str) -> Optional[Dict[str, Any]]:
        """Findet das Alias-Name Input-Feld."""
        js = '''(function(){
            const inputs = document.querySelectorAll('input[name*="localPart"], input[placeholder*="ihr-name"]');
            const input = inputs[0];
            if (!input) return null;
            const rect = input.getBoundingClientRect();
            return {
                found: true,
                name: input.name,
                placeholder: input.placeholder,
                id: input.id,
                x: rect.x + rect.width / 2,
                y: rect.y + rect.height / 2,
            };
        })()'''
        result = await client.evaluate(session_id, js, return_by_value=True)
        return result.get("result", {}).get("value")

    async def _find_hinzufuegen_button(self, client: CDPClient, session_id: str) -> Optional[Dict[str, Any]]:
        """Findet den Hinzufügen-Button."""
        js = '''(function(){
            const btns = document.querySelectorAll("button");
            for (const b of btns) {
                if (b.textContent.trim() === "Hinzufügen") {
                    const rect = b.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        return {
                            found: true,
                            text: b.textContent.trim(),
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2,
                            id: b.id,
                            className: b.className,
                        };
                    }
                }
            }
            return null;
        })()'''
        result = await client.evaluate(session_id, js, return_by_value=True)
        return result.get("result", {}).get("value")

    async def _fill_alias_input(self, client: CDPClient, session_id: str, alias_name: str) -> bool:
        """Füllt das Alias-Input-Feld und dispatcht Events."""
        js = f'''(function(){{
            const inputs = document.querySelectorAll('input[name*="localPart"], input[placeholder*="ihr-name"]');
            const input = inputs[0];
            if (!input) return {{error: "Input nicht gefunden", available: Array.from(document.querySelectorAll("input")).map(i => ({{name: i.name, type: i.type, placeholder: i.placeholder}})).slice(0, 10)}};
            input.value = "{alias_name}";
            input.dispatchEvent(new Event("input", {{bubbles: true}}));
            input.dispatchEvent(new Event("change", {{bubbles: true}}));
            input.dispatchEvent(new Event("blur", {{bubbles: true}}));
            return {{success: true, name: input.name, value: input.value}};
        }})()'''
        result = await client.evaluate(session_id, js, return_by_value=True)
        val = result.get("result", {}).get("value", {})
        logger.info(f"Input fill: {val}")
        return val.get("success", False) if isinstance(val, dict) else False

    async def _click_button_via_cdp(self, client: CDPClient, session_id: str, btn_info: Dict[str, Any]) -> None:
        """Klickt einen Button via CDP Input.dispatchMouseEvent."""
        btn_x = btn_info["x"]
        btn_y = btn_info["y"]
        logger.info(f"CDP Mouse click bei ({btn_x:.1f}, {btn_y:.1f})")
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": btn_x, "y": btn_y, "button": "left",
        })
        await asyncio.sleep(0.3)
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": btn_x, "y": btn_y, "button": "left", "clickCount": 1,
        })
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": btn_x, "y": btn_y, "button": "left", "clickCount": 1,
        })

    async def _check_creation_success(self, client: CDPClient, session_id: str, alias_name: str) -> Dict[str, Any]:
        """Prüft ob Alias erfolgreich erstellt wurde.
        
        Prüft:
        1. Alias erscheint in einer .table_body-row
        2. Erfolgsmeldung im Body-Text
        3. Keine Fehlermeldung
        4. Spezifisch: "nicht verfügbar" = Alias ist bereits vergeben
        """
        js = f'''(function(){{
            const bodyText = document.body.textContent;
            
            // Check rows specifically
            const rows = document.querySelectorAll(".table_body-row, .table_row");
            let foundInRow = false;
            for (const row of rows) {{
                if (row.textContent.includes("{alias_name}")) {{
                    foundInRow = true;
                    break;
                }}
            }}
            
            const hasSuccess = /erfolgreich|angelegt|erstellt|hinzugef.gt/.test(bodyText);
            const hasError = /fehler|bereits vergeben|nicht verf.gbar|maximal|existiert/.test(bodyText);
            const unavailableMatch = bodyText.match(/Diese E-Mail-Adresse \\([^)]+\\) ist nicht verf.gbar/);
            
            return {{
                foundInRow: foundInRow,
                hasSuccess: hasSuccess,
                hasError: hasError,
                isUnavailable: !!unavailableMatch,
                unavailableMsg: unavailableMatch ? unavailableMatch[0] : null,
                bodyHasAlias: bodyText.includes("{alias_name}"),
            }};
        }})()'''
        result = await client.evaluate(session_id, js, return_by_value=True)
        return result.get("result", {}).get("value", {})

    async def create_alias(self, alias_name: Optional[str] = None, cdp_port: int = 9222) -> Dict[str, Any]:
        """Erstellt einen neuen GMX Alias.
        
        Flow:
        1. Navigiere zu allEmailAddresses
        2. Fülle Input-Feld
        3. Klicke Hinzufügen via CDP Mouse Event
        4. Verifiziere: Alias in Tabelle + Erfolgsmeldung
        5. Wenn "nicht verfügbar" (bereits vergeben): Generiere neuen Namen und wiederhole (max 3 Versuche)
        
        Returns:
            {"status": "success"|"failed"|"not_logged_in"|"error", "alias_email": str|None}
        """
        start_time = time.time()
        steps = []
        
        if not alias_name:
            alias_name = self.generate_alias_name()
        
        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)
            
            # Navigate to allEmailAddresses
            nav_ok = await self._navigate_to_all_email_addresses(client, session_id)
            if not nav_ok:
                return {"status": "not_logged_in", "alias_email": None, "steps_completed": steps, "error": "Konnte nicht zu allEmailAddresses navigieren"}
            steps.append("navigated_to_addresses")
            
            await self._screenshot(client, session_id, "create_before")
            
            for attempt in range(3):
                current_alias = alias_name if attempt == 0 else self.generate_alias_name()
                alias_email = f"{current_alias}@gmx.de"
                logger.info(f"Erstelle GMX Alias (Versuch {attempt + 1}/3): {alias_email}")
                
                # Clear and fill input
                fill_ok = await self._fill_alias_input(client, session_id, current_alias)
                if not fill_ok:
                    return {"status": "error", "alias_email": None, "steps_completed": steps, "error": "Input-Feld nicht gefunden"}
                if attempt == 0:
                    steps.append("filled_form")
                await asyncio.sleep(1)
                
                # Find and click Hinzufügen button
                btn = await self._find_hinzufuegen_button(client, session_id)
                if not btn:
                    return {"status": "error", "alias_email": None, "steps_completed": steps, "error": "Hinzufügen-Button nicht gefunden"}
                
                await self._click_button_via_cdp(client, session_id, btn)
                if attempt == 0:
                    steps.append("clicked_add")
                await asyncio.sleep(5)
                
                await self._screenshot(client, session_id, f"create_after_{attempt}")
                
                # Verify
                check = await self._check_creation_success(client, session_id, current_alias)
                logger.info(f"Creation check (Versuch {attempt + 1}): {check}")
                
                if check.get("foundInRow") or check.get("hasSuccess") or check.get("bodyHasAlias"):
                    logger.info(f"✅ Alias erstellt: {alias_email}")
                    elapsed = time.time() - start_time
                    return {
                        "status": "success",
                        "alias_email": alias_email,
                        "alias_name": current_alias,
                        "steps_completed": steps,
                        "execution_time": f"{elapsed:.2f}s",
                    }
                
                if not check.get("isUnavailable"):
                    # Real error (not just taken) — stop retrying
                    elapsed = time.time() - start_time
                    return {
                        "status": "failed",
                        "alias_email": None,
                        "alias_name": current_alias,
                        "steps_completed": steps,
                        "execution_time": f"{elapsed:.2f}s",
                        "error": f"Alias konnte nicht erstellt werden: {check.get('unavailableMsg') or 'GMX Fehler'}",
                    }
                
                logger.warning(f"Alias {alias_email} nicht verfügbar, generiere neuen Namen...")
                await asyncio.sleep(1)
            
            # All attempts exhausted
            elapsed = time.time() - start_time
            return {
                "status": "failed",
                "alias_email": None,
                "alias_name": alias_name,
                "steps_completed": steps,
                "execution_time": f"{elapsed:.2f}s",
                "error": "Alle 3 Versuche fehlgeschlagen — Alias-Namen sind nicht verfügbar",
            }
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Alias-Erstellung fehlgeschlagen: {e}")
            return {
                "status": "error",
                "alias_email": None,
                "alias_name": alias_name,
                "steps_completed": steps,
                "execution_time": f"{elapsed:.2f}s",
                "error": str(e),
            }
        finally:
            if client:
                await client.disconnect()

    # ═══════════════════════════════════════════════════════════════════════════════
    #  FULL ROTATION
    # ═══════════════════════════════════════════════════════════════════════════════

    async def rotate_alias(self, new_alias_name: Optional[str] = None, cdp_port: int = 9222) -> Dict[str, Any]:
        """Alias-Rotation: Löscht existierenden Alias und erstellt einen neuen.

        Beide Operationen teilen sich eine CDP-Verbindung, was Zeit spart.
        """
        start_time = time.time()
        steps_completed = []
        steps_failed = []
        deleted_alias = None
        created_alias = None
        created_alias_name = None

        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)

            # --- STEP 1: Navigate to allEmailAddresses ---
            nav_ok = await self._navigate_to_all_email_addresses(client, session_id)
            if not nav_ok:
                steps_failed.append("navigation")
                return {
                    "status": "failed",
                    "deleted_alias": None,
                    "created_alias": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "Konnte nicht zu allEmailAddresses navigieren",
                }
            steps_completed.append("navigated_to_addresses")

            # --- STEP 2: Delete existing alias (HYBRID CDP DOM + CUA) ---
            await client.send_to_session(session_id, "DOM.enable")
            await asyncio.sleep(0.3)

            alias_info = await self._find_alias_coords_in_iframe(client, session_id)
            if alias_info:
                alias_text = alias_info['text']
                logger.info(f"Alias gefunden: {alias_text} at ({alias_info['x']:.0f},{alias_info['y']:.0f})")

                # CDP HOVER over alias row
                hover_x = alias_info['x'] + alias_info['w'] / 2
                hover_y = alias_info['y'] + alias_info['h'] / 2
                await self._cdp_hover(client, session_id, hover_x, hover_y)
                await asyncio.sleep(1)

                # Find delete icon (now visible after hover)
                delete_info = await self._find_delete_icon_coords(client, session_id)
                if delete_info:
                    await self._cdp_click(client, session_id, delete_info['x'], delete_info['y'])
                    await asyncio.sleep(3)

                    # CUA click OK button
                    import subprocess as sp
                    res = sp.run(
                        ["cua-driver", "call", "list_windows"],
                        input=json.dumps({"query": "Chrome"}),
                        capture_output=True, text=True, timeout=10
                    )
                    try:
                        wd = json.loads(res.stdout)
                        cua_pid, cua_wid = None, None
                        for w in wd.get('windows', []):
                            if 'GMX' in w.get('title', '') and w.get('is_on_screen'):
                                cua_pid = w['pid']; cua_wid = w['window_id']
                                break
                        if cua_pid and cua_wid:
                            ok = await self._cua_click_ok_button(cua_pid, cua_wid)
                            if ok:
                                await asyncio.sleep(3)
                                # Verify: search again to confirm deletion
                                alias_check = await self._find_alias_coords_in_iframe(client, session_id)
                                if alias_check and alias_check['text'] == alias_text:
                                    steps_failed.append("alias_delete_verify")
                                else:
                                    deleted_alias = alias_text
                                    steps_completed.append("alias_deleted")
                            else:
                                steps_failed.append("confirm_button_not_found")
                        else:
                            steps_failed.append("cua_window_not_found")
                    except Exception:
                        steps_failed.append("cua_confirm_error")
                else:
                    steps_failed.append("trash_icon_not_found")
            else:
                steps_completed.append("no_existing_alias")
                deleted_alias = None

            # --- STEP 3: Create new alias (with retry for unavailable names) ---
            if not new_alias_name:
                new_alias_name = self.generate_alias_name()
            
            alias_created = False
            for attempt in range(3):
                current_alias = new_alias_name if attempt == 0 else self.generate_alias_name()
                current_alias_email = f"{current_alias}@gmx.de"
                logger.info(f"Erstelle Alias (Versuch {attempt + 1}/3): {current_alias_email}")
                
                fill_ok = await self._fill_alias_input(client, session_id, current_alias)
                if not fill_ok:
                    steps_failed.append("input_fill")
                    return {
                        "status": "partial",
                        "deleted_alias": deleted_alias,
                        "created_alias": None,
                        "created_alias_name": current_alias,
                        "steps_completed": steps_completed,
                        "steps_failed": steps_failed,
                        "execution_time": f"{time.time() - start_time:.2f}s",
                        "error": "Input-Feld nicht gefunden",
                    }
                if attempt == 0:
                    steps_completed.append("form_filled")
                await asyncio.sleep(1)

                btn = await self._find_hinzufuegen_button(client, session_id)
                if not btn:
                    steps_failed.append("hinzufuegen_button_not_found")
                    return {
                        "status": "partial",
                        "deleted_alias": deleted_alias,
                        "created_alias": None,
                        "created_alias_name": current_alias,
                        "steps_completed": steps_completed,
                        "steps_failed": steps_failed,
                        "execution_time": f"{time.time() - start_time:.2f}s",
                        "error": "Hinzufügen-Button nicht gefunden",
                    }

                await self._click_button_via_cdp(client, session_id, btn)
                if attempt == 0:
                    steps_completed.append("add_button_clicked")
                await asyncio.sleep(5)

                check = await self._check_creation_success(client, session_id, current_alias)
                logger.info(f"Creation check (Versuch {attempt + 1}): {check}")

                if check.get("foundInRow") or check.get("hasSuccess") or check.get("bodyHasAlias"):
                    created_alias_name = current_alias
                    created_alias = current_alias_email
                    alias_created = True
                    steps_completed.append("alias_created")
                    break
                
                if not check.get("isUnavailable"):
                    # Real error, not just unavailable
                    steps_failed.append("alias_create_gmx_error")
                    return {
                        "status": "failed",
                        "deleted_alias": deleted_alias,
                        "created_alias": None,
                        "created_alias_name": current_alias,
                        "steps_completed": steps_completed,
                        "steps_failed": steps_failed,
                        "execution_time": f"{time.time() - start_time:.2f}s",
                        "error": f"GMX meldet Fehler bei Alias-Erstellung: {check.get('unavailableMsg') or 'Unbekannter Fehler'}",
                    }
                
                logger.warning(f"Alias {current_alias_email} nicht verfügbar, generiere neuen Namen...")
                await asyncio.sleep(1)
            
            if alias_created:
                logger.info(f"✅ Rotation complete: {deleted_alias} -> {created_alias}")
                return {
                    "status": "success",
                    "deleted_alias": deleted_alias,
                    "created_alias": created_alias,
                    "created_alias_name": created_alias_name,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                }
            else:
                steps_failed.append("alias_create_all_attempts_failed")
                return {
                    "status": "failed",
                    "deleted_alias": deleted_alias,
                    "created_alias": None,
                    "created_alias_name": new_alias_name,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "Alle 3 Versuche fehlgeschlagen — Alias-Namen sind nicht verfügbar",
                }

        except Exception as e:
            logger.error(f"Alias-Rotation fehlgeschlagen: {e}")
            return {
                "status": "failed",
                "deleted_alias": deleted_alias,
                "created_alias": None,
                "created_alias_name": created_alias_name,
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "execution_time": f"{time.time() - start_time:.2f}s",
                "error": str(e),
            }
        finally:
            if client:
                await client.disconnect()

    # ═══════════════════════════════════════════════════════════════════════════════
    #  PUBLIC API (Session, Inbox, OTP)
    # ═══════════════════════════════════════════════════════════════════════════════

    async def check_session(self, cdp_port: int = 9222) -> Dict[str, Any]:
        """Prüft ob eine GMX-Session aktiv ist."""
        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)
            result = await self._ensure_mail_session(client, session_id)
            return {
                "status": "logged_in" if result["success"] else "not_logged_in",
                "current_url": result.get("current_url", ""),
                "session_active": result["success"],
                "sid": result.get("sid"),
            }
        except Exception as e:
            logger.error(f"GMX Session-Check fehlgeschlagen: {e}")
            return {"status": "error", "session_active": False, "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    async def ensure_gmx_session(
        self,
        email: str = "opensin@gmx.de",
        password: str = "ZOE.jerry2024",
        cdp_port: int = 9222,
    ) -> Dict[str, Any]:
        """
        ════════════════════════════════════════════════════════════════════════════════
        FLOW 0: GMX LOGIN — Session-Wiederherstellung oder Fresh Login
        ════════════════════════════════════════════════════════════════════════════════

        PRÜFT: Ob GMX Inbox erreichbar ist (Session OK → Flow 1 weiter)
        
        FALLS NICHT: Vollständiger Logout → Login Flow:
          a) Profil-Icon klicken → Logout
          b) Profil-Icon klicken → Login
          c) Profil-Icon klicken → Login (GMX braucht 2x)
          d) Email: opensin@gmx.de + Weiter
          e) Passwort: ZOE.jerry2024 + Login

        NUR DIESER FLOW WIRD ANGEFASST. Flow 1, 2, 3 sind READ-ONLY.
        """
        import time
        start_time = time.time()

        async def _click_profile_icon_and_action(client, session_id, action_text: str) -> bool:
            """Klickt Profil-Icon und dann action_text via JS .click() im Shadow DOM."""
            # CRITICAL: Shadow DOM dropdown buttons are NOT accessible via CDP click_at()
            # getBoundingClientRect() returns 0x0 for shadow DOM elements until clicked via JS
            # Step 1: Open dropdown by clicking avatar via JS
            open_js = """
            (function() {
                var avatar = document.querySelector('ACCOUNT-AVATAR') || 
                             document.querySelector('ACCOUNT-AVATAR-NAVIGATOR');
                if (!avatar) return {found: false};
                
                // Open flyout by clicking avatar
                avatar.click();
                avatar.dispatchEvent(new Event('mouseenter', {bubbles: true}));
                
                return {found: true, tag: avatar.tagName};
            })()
            """
            await client.evaluate(session_id, open_js, return_by_value=True)
            await asyncio.sleep(3)  # Wait for shadow DOM to fully render
            
            # Step 2: Click the action button directly inside shadow DOM via JS
            action_js = """
            (function() {
                var text = "%s";
                var searchTerms = [text];
                if (text === 'logout') {
                    searchTerms = ['logout', 'abmelden', 'ausloggen'];
                } else if (text === 'login') {
                    searchTerms = ['login', 'anmelden', 'einloggen', 'zum postfach'];
                }
                
                var avatar = document.querySelector('ACCOUNT-AVATAR') || 
                             document.querySelector('ACCOUNT-AVATAR-NAVIGATOR');
                if (!avatar || !avatar.shadowRoot) return {found: false, error: 'no shadow'};
                
                // Search in shadow DOM for button with matching text
                var buttons = avatar.shadowRoot.querySelectorAll('button, a');
                for (var i=0; i<buttons.length; i++) {
                    var t = (buttons[i].textContent || '').trim().toLowerCase();
                    for (var s=0; s<searchTerms.length; s++) {
                        if (t.indexOf(searchTerms[s]) !== -1) {
                            buttons[i].click();
                            buttons[i].dispatchEvent(new Event('click', {bubbles: true}));
                            return {found: true, clicked: t, index: i};
                        }
                    }
                }
                
                // Fallback: click first button if any exist
                if (buttons.length > 0) {
                    buttons[0].click();
                    return {found: true, clicked: buttons[0].textContent.trim(), fallback: true};
                }
                
                return {found: false, buttons: buttons.length};
            })()
            """ % action_text
            action_result = await client.evaluate(session_id, action_js, return_by_value=True)
            action_val = action_result.get("result", {}).get("value", {})
            
            if not action_val.get("found"):
                logger.warning(f"[Flow 0] Could not find '{action_text}' in shadow DOM: {action_val}")
                return False
            
            logger.info(f"[Flow 0] Clicked '{action_text}' in shadow DOM: '{action_val.get('clicked')}'")
            await asyncio.sleep(2)
            return True

        async def _wait_for_page_stable(client, session_id, timeout: int = 10) -> str:
            """Wartet bis Seite stable ist und gibt URL zurück."""
            url = ""
            for _ in range(timeout):
                await asyncio.sleep(1)
                r = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                url = r.get("result", {}).get("value", "") or ""
                if "gmx" in url.lower():
                    break
            return url

        async def _do_email_password_login(client, session_id, email: str, password: str) -> bool:
            """Füllt Email + Password Form aus und klickt login via CDP click_at."""
            # Step 1: Fill email
            email_js = """
            (function() {
                var input = document.querySelector('input[type="email"], input[name="email"], input[id="email"], input[autocomplete="email"]');
                if (!input) return {found: false};
                
                var nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(input, '%s');
                input.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
                
                // Find button coordinates for click_at
                var buttons = document.querySelectorAll('button, input[type="submit"], a[role="button"]');
                for (var i=0; i<buttons.length; i++) {
                    var btn = buttons[i];
                    var text = (btn.textContent || '').trim().toLowerCase();
                    var rect = btn.getBoundingClientRect();
                    if (text.indexOf('weiter') !== -1 || text.indexOf('next') !== -1 || 
                        text.indexOf('continue') !== -1 || text.indexOf('angemeldet') !== -1) {
                        return {found: true, clickX: Math.round(rect.left + rect.width/2), clickY: Math.round(rect.top + rect.height/2), text: text};
                    }
                }
                return {found: true, clickX: 0, clickY: 0};
            })()
            """ % email
            r = await client.evaluate(session_id, email_js, return_by_value=True)
            val = r.get("result", {}).get("value", {})
            if not val.get("found"):
                logger.info("[Flow 0] No email input found")
                return False
            
            # Click "Weiter" button via CDP
            if val.get("clickX", 0) > 0:
                await client.click_at(session_id, val["clickX"], val["clickY"])
            await asyncio.sleep(4)
            
            # Step 2: Fill password
            pw_js = """
            (function() {
                var input = document.querySelector('input[type="password"], input[name="password"]');
                if (!input) return {found: false};
                
                var nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(input, '%s');
                input.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
                
                // Find login button coordinates
                var buttons = document.querySelectorAll('button, input[type="submit"], a[role="button"]');
                for (var i=0; i<buttons.length; i++) {
                    var btn = buttons[i];
                    var text = (btn.textContent || '').trim().toLowerCase();
                    var rect = btn.getBoundingClientRect();
                    if (text.indexOf('anmelden') !== -1 || text.indexOf('login') !== -1 || text.indexOf('einloggen') !== -1) {
                        return {found: true, clickX: Math.round(rect.left + rect.width/2), clickY: Math.round(rect.top + rect.height/2), text: text};
                    }
                }
                return {found: true, clickX: 0, clickY: 0};
            })()
            """ % password
            r2 = await client.evaluate(session_id, pw_js, return_by_value=True)
            val2 = r2.get("result", {}).get("value", {})
            
            # Click "Anmelden" button via CDP
            if val2.get("clickX", 0) > 0:
                await client.click_at(session_id, val2["clickX"], val2["clickY"])
            
            logger.info(f"[Flow 0] Email+Password login: email_btn='{val.get('text','none')}', pw_btn='{val2.get('text','none')}'")
            return True

        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)
            
            # STEP 0: Check if we can already access email page
            logger.info("[Flow 0] Checking if GMX session is active...")
            await client.navigate(session_id, "https://www.gmx.net/")
            await asyncio.sleep(3)
            
            # Click E-Mail header button via JS - find the one with navigator.gmx.net in href
            await client.evaluate(
                session_id,
                """
                (function() {
                    var links = document.querySelectorAll('a');
                    for (var i=0; i<links.length; i++) {
                        var t = links[i].textContent.trim();
                        if (t === 'E-Mail' || t === 'Email') {
                            var href = links[i].href || '';
                            if (href.indexOf('navigator.gmx.net') !== -1 || href.indexOf('gmx.net/mail') !== -1) {
                                links[i].click();
                                return {clicked: true, href: href};
                            }
                        }
                    }
                    // Fallback: click any E-Mail link
                    for (var i=0; i<links.length; i++) {
                        var t = links[i].textContent.trim().toLowerCase();
                        if (t === 'e-mail' || t === 'email' || t === 'postfach') {
                            links[i].click();
                            return {clicked: true, fallback: true};
                        }
                    }
                    return {clicked: false};
                })()
                """,
                return_by_value=True,
            )
            await asyncio.sleep(5)
            
            url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_result.get("result", {}).get("value", "") or ""
            
            if "navigator.gmx.net/mail?sid=" in current_url or "bap.navigator.gmx.net/mail?sid=" in current_url:
                logger.info("[Flow 0] ✅ Session already active - proceeding to Flow 1")
                sid_val = ""
                if "sid=" in current_url:
                    sid_val = current_url.split("sid=")[1].split("&")[0]
                return {
                    "status": "success",
                    "action": "session_active",
                    "current_url": current_url,
                    "sid": sid_val,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                }
            
            # STEP 1: Session not active - need logout/login
            logger.info("[Flow 0] ❌ Session NOT active - starting logout/login flow")
            
            # Go to GMX homepage
            await client.navigate(session_id, "https://www.gmx.net/")
            await asyncio.sleep(3)
            
            # a) Click profile icon → logout
            logger.info("[Flow 0] Step A: Logout via profile icon...")
            logout_ok = await _click_profile_icon_and_action(client, session_id, "logout")
            if logout_ok:
                await asyncio.sleep(3)
            
            # b) Click profile icon → login (ERSTE login attempt - wird von GMX ignoriert!)
            logger.info("[Flow 0] Step B: First login attempt (GMX ignores this click)...")
            await _click_profile_icon_and_action(client, session_id, "login")
            await asyncio.sleep(3)
            
            # STILL enter email + password (first attempt - will be ignored by GMX)
            logger.info("[Flow 0] Step B2: Enter email+password (first attempt - GMX ignores)...")
            await _do_email_password_login(client, session_id, email, password)
            await asyncio.sleep(4)
            
            # c) Click profile icon → login again (ZWEITE login attempt - jetzt funktioniert)
            logger.info("[Flow 0] Step C: Second login attempt (this one works)...")
            await _click_profile_icon_and_action(client, session_id, "login")
            await asyncio.sleep(4)
            
            # Check if login form is visible
            login_form_result = await client.evaluate(
                session_id,
                """
                (function() {
                    const emailInput = document.querySelector('input[type="email"], input[name="email"], input[id="email"], input[autocomplete="email"]');
                    const pwInput = document.querySelector('input[type="password"], input[name="password"]');
                    return {
                        hasEmailInput: !!emailInput,
                        hasPasswordInput: !!pwInput,
                        bodyText: document.body.innerText.substring(0, 300)
                    };
                })()
                """,
                return_by_value=True,
            )
            form_val = login_form_result.get("result", {}).get("value", {})
            
            if not form_val.get("hasEmailInput"):
                logger.info("[Flow 0] Login form not visible, trying URL navigation...")
                await client.navigate(session_id, "https://www.gmx.net/")
                await asyncio.sleep(3)
                await _click_profile_icon_and_action(client, session_id, "login")
                await asyncio.sleep(3)
            
# d/e) Two-step login form: Email + Weiter, then Password + Login
            logger.info(f"[Flow 0] Step D: Fill email and click Weiter...")
            
            # Step 1: Fill email and click Weiter
            email_js = """
            (function() {
                var email = '%s';
                
                var emailInput = document.querySelector('input[type="email"], input[name="email"], input[autocomplete="email"]');
                if (!emailInput) return {found: false, msg: 'no email input'};
                
                var nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(emailInput, email);
                emailInput.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                emailInput.dispatchEvent(new Event('change', {bubbles: true}));
                
                // Find Weiter button
                var buttons = document.querySelectorAll('button, input[type="submit"]');
                for (var i=0; i<buttons.length; i++) {
                    var text = (buttons[i].textContent || '').trim().toLowerCase();
                    var rect = buttons[i].getBoundingClientRect();
                    if (rect.width > 10 && rect.height > 10) {
                        if (text.indexOf('weiter') !== -1 || text.indexOf('next') !== -1 || text.indexOf('continue') !== -1) {
                            buttons[i].click();
                            return {found: true, clicked: text, hasPw: false};
                        }
                    }
                }
                
                return {found: true, clicked: 'none', hasPw: false};
            })()
            """ % email
            r1 = await client.evaluate(session_id, email_js, return_by_value=True)
            val1 = r1.get("result", {}).get("value", {})
            logger.info(f"[Flow 0] Email step: {val1}")
            await asyncio.sleep(4)
            
            # Step 2: Fill password and click Login
            logger.info("[Flow 0] Step E: Fill password and click Login...")
            pw_js = """
            (function() {
                var password = '%s';
                
                var pwInput = document.querySelector('input[type="password"], input[name="password"]');
                if (!pwInput) return {found: false, msg: 'no password input', url: window.location.href};
                
                var nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                nativeSetter.call(pwInput, password);
                pwInput.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                pwInput.dispatchEvent(new Event('change', {bubbles: true}));
                
                // Find Login/Anmelden button
                var buttons = document.querySelectorAll('button, input[type="submit"]');
                for (var i=0; i<buttons.length; i++) {
                    var text = (buttons[i].textContent || '').trim().toLowerCase();
                    var rect = buttons[i].getBoundingClientRect();
                    if (rect.width > 10 && rect.height > 10) {
                        if (text.indexOf('login') !== -1 || text.indexOf('anmelden') !== -1 || text.indexOf('einloggen') !== -1) {
                            buttons[i].click();
                            return {found: true, clicked: text};
                        }
                    }
                }
                
                return {found: true, clicked: 'none'};
            })()
            """ % password
            r2 = await client.evaluate(session_id, pw_js, return_by_value=True)
            val2 = r2.get("result", {}).get("value", {})
            logger.info(f"[Flow 0] Password step: {val2}")
            await asyncio.sleep(5)
            
            # Verify login success - click E-Mail via CDP click_at (find coordinates first)
            email_verify_js = """
            (function() {
                var links = document.querySelectorAll('a');
                for (var i=0; i<links.length; i++) {
                    var t = links[i].textContent.trim().toLowerCase();
                    if (t === 'e-mail' || t === 'email') {
                        var rect = links[i].getBoundingClientRect();
                        var href = links[i].href || '';
                        if (href.indexOf('navigator.gmx.net') !== -1 || href.indexOf('gmx.net/mail') !== -1) {
                            return {found: true, x: Math.round(rect.left + rect.width/2), y: Math.round(rect.top + rect.height/2), href: href};
                        }
                    }
                }
                // Fallback: any E-Mail link
                for (var i=0; i<links.length; i++) {
                    var t = links[i].textContent.trim().toLowerCase();
                    if (t === 'e-mail' || t === 'email') {
                        var rect = links[i].getBoundingClientRect();
                        return {found: true, x: Math.round(rect.left + rect.width/2), y: Math.round(rect.top + rect.height/2), href: links[i].href};
                    }
                }
                return {found: false};
            })()
            """
            verify_result = await client.evaluate(session_id, email_verify_js, return_by_value=True)
            verify_val = verify_result.get("result", {}).get("value", {})
            if verify_val.get("found"):
                logger.info(f"[Flow 0] Clicking E-Mail at ({verify_val['x']}, {verify_val['y']})...")
                await client.click_at(session_id, verify_val["x"], verify_val["y"])
            await asyncio.sleep(5)
            
            final_url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            final_url = final_url_result.get("result", {}).get("value", "") or ""
            
            if "navigator.gmx.net/mail?sid=" in final_url or "bap.navigator.gmx.net/mail?sid=" in final_url:
                sid = final_url.split("sid=")[1].split("&")[0] if "sid=" in final_url else ""
                logger.info(f"[Flow 0] ✅ Login successful! SID: {sid[:30]}...")
                return {
                    "status": "success",
                    "action": "login_completed",
                    "current_url": final_url,
                    "sid": sid,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                }
            else:
                logger.warning(f"[Flow 0] Login may have failed. URL: {final_url[:80]}")
                return {
                    "status": "partial",
                    "action": "login_attempted",
                    "current_url": final_url,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "Login completed but could not verify session",
                }
                
        except Exception as e:
            logger.error(f"[Flow 0] Error: {e}")
            return {
                "status": "error",
                "action": "failed",
                "error": str(e),
                "execution_time": f"{time.time() - start_time:.2f}s",
            }
        finally:
            if client:
                await client.disconnect()

    async def open_email_addresses_page(self, cdp_port: int = 9222) -> Dict[str, Any]:
        """Navigiert zur E-Mail-Adressen-Verwaltungsseite."""
        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)
            nav_ok = await self._navigate_to_all_email_addresses(client, session_id)
            if not nav_ok:
                return {"status": "error", "error": "Konnte nicht zu allEmailAddresses navigieren"}
            
            url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_result.get("result", {}).get("value", "")
            return {"status": "success", "current_url": current_url}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    async def open_inbox(self, cdp_port: int = 9222) -> Dict[str, Any]:
        """Öffnet die GMX Inbox."""
        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)
            result = await self._ensure_mail_session(client, session_id)
            if not result["success"]:
                return {"status": "not_logged_in", "current_url": result.get("current_url", "")}
            
            await client.evaluate(session_id, '''(function(){
                function c(r,t,d){if(d>8)return false;
                for(const e of r.querySelectorAll('*')){
                if((e.textContent||'').trim()===t){e.click();return true;}
                if(e.shadowRoot&&c(e.shadowRoot,t,d+1))return true;}
                return false;}return c(document.body,'E-Mail',0);})()''')
            await asyncio.sleep(5)
            
            url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            return {"status": "success", "current_url": url_result.get("result", {}).get("value", "")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    async def get_latest_email(
        self, sender_filter: str = "fireworks", cdp_port: int = 9222
    ) -> Dict[str, Any]:
        """
        Öffnet GMX Inbox, findet neueste Email mit sender_filter, gibt confirm URL zurück.
        """
        start_time = time.time()
        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)

            # Navigate to GMX bap URL if not already there
            url_check = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_check.get("result", {}).get("value", "")
            if "bap.navigator.gmx.net" not in current_url and "navigator.gmx.net" not in current_url:
                await client.navigate(session_id, "https://bap.navigator.gmx.net/mail")

            # Get mail iframe URL
            iframe_result = await client.evaluate(session_id, '''
            (function() {
                const iframe = document.querySelector("#thirdPartyFrame_mail");
                return iframe ? iframe.src : null;
            })()
            ''', return_by_value=True)
            iframe_src = iframe_result.get("result", {}).get("value", "")
            if not iframe_src:
                return {"status": "error", "error": "thirdPartyFrame_mail nicht gefunden", "confirm_url": None}

            # Navigate to webmailer
            await client.navigate(session_id, iframe_src)

            # Find email with sender_filter in the rendered list
            email_js = f'''
            (function() {{
                const filter = "{sender_filter}".toLowerCase();
                function walkAll(node, depth) {{
                    if (depth > 15) return "";
                    let txt = "";
                    if (node.nodeType === 3) {{
                        const v = node.nodeValue.trim();
                        if (v.length > 0) txt += v + " ";
                    }}
                    const children = node.childNodes;
                    for (let i = 0; i < children.length; i++) {{
                        txt += walkAll(children[i], depth + 1);
                    }}
                    return txt;
                }}
                const allText = walkAll(document.body, 0);
                const hasFilter = allText.toLowerCase().includes(filter);
                if (!hasFilter) return JSON.stringify({{found: false, reason: "no filter match"}});

                const allEls = document.querySelectorAll("*");
                const clickable = Array.from(allEls).filter(el => {{
                    const text = (el.textContent||"").toLowerCase();
                    return text.includes(filter) && el.offsetParent !== null && (el.click || el.tagName === "A");
                }});

                if (clickable.length > 0) {{
                    const el = clickable[0];
                    el.scrollIntoView();
                    if (el.click) el.click();
                    else if (el.dispatchEvent) el.dispatchEvent(new MouseEvent("click", {{bubbles: true}}));
                    return JSON.stringify({{
                        found: true,
                        clicked: el.textContent.trim().slice(0, 100),
                        url: window.location.href
                    }});
                }}
                return JSON.stringify({{found: false, reason: "no clickable element"}});
            }})()
            '''
            email_result = await client.evaluate(session_id, email_js, return_by_value=True, timeout=15.0)
            email_data_str = email_result.get("result", {}).get("value", "{}")
            try:
                email_data = json.loads(email_data_str)
            except:
                email_data = {"found": False, "reason": "parse error"}

            if not email_data.get("found"):
                return {
                    "status": "not_found",
                    "confirm_url": None,
                    "iframe_src": iframe_src,
                    "execution_time": f"{time.time()-start_time:.2f}s",
                    "error": email_data.get("reason", "email nicht gefunden"),
                }

            logger.info(f"Email geklickt: {email_data.get('clicked')}")

            # Now extract confirm URL from opened email
            await asyncio.sleep(2)

            confirm_js = '''
            (function() {
                function walkAll(node, depth) {
                    if (depth > 15) return "";
                    let txt = "";
                    if (node.nodeType === 3) {
                        const v = node.nodeValue.trim();
                        if (v.length > 0) txt += v + " ";
                    }
                    const children = node.childNodes;
                    for (let i = 0; i < children.length; i++) {
                        txt += walkAll(children[i], depth + 1);
                    }
                    return txt;
                }
                const allText = walkAll(document.body, 0).toLowerCase();
                const match = allText.match(/https:\\/\\/app\\.fireworks\\.ai[^\\s'"<>]+(?:confirm|verify|token|email_verification)[^\\s'"<>]*/);
                return match ? match[0] : null;
            })()
            '''
            confirm_result = await client.evaluate(session_id, confirm_js, return_by_value=True, timeout=15.0)
            confirm_url = confirm_result.get("result", {}).get("value", "")

            elapsed = time.time() - start_time
            if confirm_url:
                logger.info(f"Confirm URL gefunden: {confirm_url[:60]}...")
                return {
                    "status": "success",
                    "confirm_url": confirm_url,
                    "execution_time": f"{elapsed:.2f}s",
                }
            else:
                return {
                    "status": "found_no_url",
                    "confirm_url": None,
                    "email_clicked": email_data.get("clicked"),
                    "execution_time": f"{elapsed:.2f}s",
                    "error": "Email geöffnet aber keine confirm URL gefunden",
                }

        except Exception as e:
            return {
                "status": "error",
                "confirm_url": None,
                "execution_time": f"{time.time()-start_time:.2f}s",
                "error": str(e),
            }
        finally:
            if client:
                await client.disconnect()

    async def read_otp(
        self,
        sender_filter: str = "fireworks",
        max_retries: int = 12,
        retry_delay: int = 5,
        cdp_port: int = 9222,
        exclude_mail_ids: Optional[set] = None,
    ) -> Dict[str, Any]:
        """
        ════════════════════════════════════════════════════════════════════════════════
        GMX OTP / CONFIRMATION URL EXTRACTION — ARCHITECTURE & LESSONS LEARNED
        ════════════════════════════════════════════════════════════════════════════════

        ZWECK:
        Extrahiert die Bestätigungs-URL (z.B. Fireworks signup/confirm) aus der
        GMX Inbox OHNE auf Shadow-DOM Elemente klicken zu müssen.

        WARUM DIESE METHODE EXISTIERT:
        ────────────────────────────────────────────────────────────────────────────────
        Die GMX Webmailer-SPA (Single Page Application) basiert auf Wicket und
        nutzt geschachtelte Custom Elements mit Shadow DOM. Standard-CDP
        Input.dispatchMouseEvent und JS .click() funktionieren NICHT auf
        <list-mail-item> Elementen, weil diese entweder:
          (a) in einem closed Shadow Root liegen und elementFromPoint den Host
              zurückgibt statt des eigentlichen Elements, oder
          (b) eigene Event-Handler besitzen die auf synthesized Events
              (MouseEvent, PointerEvent) nicht reagieren.

        ERKENNTNIS (2026-05-08):
        CDP Input.dispatchMouseEvent auf <list-mail-item> verändert die URL
        nicht — die Email öffnet sich nicht. JS .click() auf dem Element
        oder seinen Child-DIVs hat ebenfalls keine Wirkung.

        LÖSUNG:
        ────────────────────────────────────────────────────────────────────────────────
        Statt die Email per UI-Interaktion zu öffnen, greifen wir direkt auf
        GMX's interne REST-API zu. Die Webmailer-Seite enthält ein
        `templates` Base64-JSON im iframe-src, das URL-Templates wie
        `mailbody/tmai{mailId}/{showExternal};jsessionid={...}` enthält.

        KRITISCHE URL-PATTERN (durch Debug-Skripte reverse-engineered):
        ────────────────────────────────────────────────────────────────────────────────
        Primary:   https://3c-bap.gmx.net/mail/client/mailbody/tmai{mailId}/true;jsessionid={j}
        Fallback:  https://3c-bap.gmx.net/mail/client/mailbody/tmai{mailId}/false;jsessionid={j}
        Print:     https://3c-bap.gmx.net/mail/client/mail/print;jsessionid={j}?mailId=tmai{mailId}&showExternalContent=true

        WICHTIGE DETAILS:
        ────────────────────────────────────────────────────────────────────────────────
        • `mailId` ist NICHT die rohe DOM `id`. Die DOM `id` ist z.B.
          `id1778259980144262526`. Der API-Pfad braucht `tmai1778259980144262526`.
          → Wir strippen das `id` Präfix via `replace(/^id/, "")` und
            präfixen mit `tmai` beim URL-Build.
        • `jsessionid` muss FRISCH aus dem iframe-src extrahiert werden.
          Der `jsessionid` im `templates` Base64-Parameter ist oft STALE
          und führt zu "Es ist ein technischer Fehler aufgetreten".
        • Cookies müssen mit dem Request mitgesendet werden. Wir extrahieren
          ALLE GMX-Cookies via CDP `Network.getAllCookies` und packen sie
          in einen `httpx.AsyncClient(cookies=cookie_dict)`.
        • Die Response ist HTML mit Fireworks-Confirm-URL. URLs sind
          HTML-escaped (`&amp;` statt `&`). Wir nutzen `html.unescape()`.
        • Die Bestätigungs-URL hat das Pattern:
          `https://app.fireworks.ai/signup/confirm?client_id=...&user_name=...&confirmation_code=...`

        ANTI-PATTERN (was wir gelernt haben NICHT zu tun):
        ────────────────────────────────────────────────────────────────────────────────
        1.  CDP click auf list-mail-item → Keine URL-Änderung (getestet).
        2.  JS .click() auf list-mail-item → Keine URL-Änderung (getestet).
        3.  Double-click, Keyboard-Enter, mousedown/mouseup Synthesizer →
            Alles getestet, nichts öffnet die Email.
        4.  Direkter API-Zugriff mit `mailbody/{mailId}/true` (ohne `tmai` Prefix)
            → Liefert "Es ist ein technischer Fehler aufgetreten".
        5.  Verwendung des `jsessionid` aus dem `templates` Parameter
            → Cookies sind stale, Antwort ist GMX Login-Seite.

        FLOW:
        ────────────────────────────────────────────────────────────────────────────────
        1.  Browser-Tab auf GMX Seite mit aktiver SID bringen (via Homepage →
            E-Mail Klick oder direkte URL).
        2.  Zu `bap.navigator.gmx.net/mail?sid={sid}` navigieren und
            `#thirdPartyFrame_mail` iframe-src extrahieren.
        3.  `jsessionid` aus iframe-src parsen (Regex auf `jsessionid=([^?&]+)`).
        4.  Zu iframe-src navigieren (lädt den Webmailer SPA).
        5.  8 Sekunden warten bis die <list-mail-item> Elemente gerendert sind.
        6.  Rekursiv durch Shadow DOMs iterieren und <list-mail-item> Elemente
            finden die `sender_filter` (z.B. "fireworks") im textContent enthalten.
        7.  `mailId` aus `id` Attribut extrahieren (`id` → `tmai{id}`).
        8.  Alle GMX Cookies via CDP `Network.getAllCookies` holen.
        9.  `httpx.AsyncClient` mit Cookies aufbauen und die Email-Body-URL
            fetchen (`mailbody/tmai{mailId}/true;jsessionid={jsessionid}`).
       10.  HTML parsen nach `https://app.fireworks.ai/...` URLs.
       11.  URLs filtern die `confirm|verify|token|auth|activate|signup` enthalten.
       12.  HTML-Entities unescapen (`&amp;` → `&`).
       13.  Bestätigungs-URL zurückgeben.

        STALE-EMAIL PROBLEM & LÖSUNG:
        ────────────────────────────────────────────────────────────────────────────────
        Die GMX Inbox enthält typischerweise ALTE Fireworks Emails von
        vorherigen Rotationen. Wenn wir sofort die erste gefundene Email
        fetchen, bekommen wir einen abgelaufenen Confirm-Link.

        LÖSUNG — `exclude_mail_ids` PARAMETER:
        Der Aufrufer (rotation.py) kann eine Menge von `mailId`s übergeben,
        die als "bekannt/stale" betrachtet werden. Diese IDs werden
        komplett übersprungen. Nach einem fehlgeschlagenen Confirm-Versuch
        kann rotation.py die fehlgeschlagene `mailId` zu `exclude_mail_ids`
        hinzufügen und `read_otp()` erneut aufrufen.

        BASELINE SCAN (wenn exclude_mail_ids=None):
        Wenn keine Exclusion-Liste übergeben wird, führen wir einen
        "Baseline Scan" durch: Wir sammeln ALLE aktuell sichtbaren
        Fireworks mailIds als "bekannt" und überspringen sie. Damit
        werden nur NOCH-NICHT-GESEHENE Emails (die nach dem Baseline-Scan
        eintreffen) verarbeitet.

        GMX WEBMAILER RENDERING DELAY:
        ────────────────────────────────────────────────────────────────────────────────
        Auf frischer Navigation zum Webmailer (z.B. nach Browser-Restart oder
        nachdem der Tab auf `about:blank` war) braucht die SPA 8-15
        Sekunden bis <list-mail-item> Elemente im DOM erscheinen.
        Die `await asyncio.sleep(8)` nach `client.navigate(iframe_src)`
        ist deshalb kritisch. Weniger als 6 Sekunden führt zu 0 Treffern.

        Args:
            sender_filter: Text-Filter für Emails (default "fireworks").
            max_retries: Maximale Anzahl Polling-Versuche (default 12).
            retry_delay: Sekunden zwischen Polling-Versuchen (default 5).
            cdp_port: Chrome DevTools Protocol Port (default 9222).
            exclude_mail_ids: Set von mailIds die als stale/stale betrachtet
                werden und übersprungen werden sollen. Wenn None, wird ein
                Baseline-Scan durchgeführt und alle aktuell sichtbaren
                Fireworks-Emails als "bekannt" markiert.

        Returns:
            Dict mit keys:
                status:     "success" | "not_found" | "error"
                otp_url:    Die extrahierte Bestätigungs-URL (oder None)
                mail_id:    Die mailId der Email aus der die URL kam (oder None)
                execution_time: Dauer als formatierter String
                error:      Fehlermeldung (oder None)
        ════════════════════════════════════════════════════════════════════════════════
        """
        start_time = time.time()
        client = None
        # Menge von mailIds die als "bekannt/stale" betrachtet werden
        known_mail_ids: set = exclude_mail_ids or set()
        try:
            # ════════════════════════════════════════════════════════════════════════
            # PHASE 1: GMX SESSION ESTABLISHMENT
            # ──────────────────────────────────────────────────────────────────────
            # Wir brauchen eine gültige GMX Session mit SID (Session ID).
            # Die SID ist ein langer Token in der URL der Form:
            #   https://bap.navigator.gmx.net/mail?sid=...
            # Wenn wir bereits auf einer GMX Seite mit SID sind, extrahieren
            # wir sie direkt. Sonst navigieren wir zur Homepage, klicken
            # "E-Mail" im Navigation-Menü und extrahieren die SID aus der
            # resultierenden URL.
            # ════════════════════════════════════════════════════════════════════════
            client, session_id, _ = await self._connect_to_browser(cdp_port)
            url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_result.get("result", {}).get("value", "")
            sid = None

            if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
                sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
                sid = sid_match.group(1) if sid_match else None
                logger.info(f"SID aus aktueller URL extrahiert: {sid[:30] if sid else None}...")

            if not sid:
                logger.info("Navigiere zu GMX Homepage für neue Session")
                await client.navigate(session_id, "https://www.gmx.net/")
                await asyncio.sleep(4)

                # Login-Status prüfen: GMX zeigt "Sie sind eingeloggt" oder
                # "Zum Postfach" wenn die Session-Cookies noch gültig sind.
                body_text = await client.evaluate(session_id, "document.body.innerText", return_by_value=True)
                text = body_text.get("result", {}).get("value", "")
                if "Sie sind eingeloggt" not in text and "Zum Postfach" not in text:
                    return {
                        "status": "error",
                        "otp_url": None,
                        "mail_id": None,
                        "execution_time": f"{time.time()-start_time:.2f}s",
                        "error": "GMX nicht eingeloggt",
                    }

                # E-Mail Navigation klicken. Der Link hat kein href sondern
                # nur einen JS Event-Handler (Wicket). click() reicht hier.
                click_result = await client.evaluate(session_id, '''
                (function(){
                    const els = Array.from(document.querySelectorAll("a, button, [role=link], nav a"));
                    const emailEl = els.find(e => (e.textContent||"").trim() === "E-Mail");
                    if (emailEl) { emailEl.click(); return true; }
                    return false;
                })()''', return_by_value=True)
                clicked = click_result.get("result", {}).get("value", False)
                if not clicked:
                    # Fallback: CDP click auf bekannte Koordinaten der E-Mail
                    # Navigation im Header (x=302, y=44).
                    await client.click_at(session_id, x=302, y=44)
                await asyncio.sleep(5)

                url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                current_url = url_result.get("result", {}).get("value", "")
                sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
                sid = sid_match.group(1) if sid_match else None
                logger.info(f"SID nach Homepage-Navigation: {sid[:30] if sid else None}...")

            if not sid:
                return {
                    "status": "error",
                    "otp_url": None,
                    "mail_id": None,
                    "execution_time": f"{time.time()-start_time:.2f}s",
                    "error": "Konnte keine GMX SID extrahieren",
                }

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 2: IFRAME SRC EXTRACTION
            # ──────────────────────────────────────────────────────────────────────
            # Die GMX Mail-Seite lädt den Webmailer in einem iframe:
            #   <iframe id="thirdPartyFrame_mail" src="...">
            # Der iframe-src enthält den CRITICAL jsessionid Parameter,
            # der für die interne API-Authentifizierung benötigt wird.
            # Wir müssen diesen jsessionid EXTRAHIEREN BEVOR wir zum
            # Webmailer navigieren, da die URL nach der Navigation auf
            # webmailer.gmx.net wechselt und den jsessionid verliert.
            # ════════════════════════════════════════════════════════════════════════
            mail_url = f"https://bap.navigator.gmx.net/mail?sid={sid}"
            logger.info(f"Navigiere zu GMX Mail: {mail_url[:80]}...")
            await client.navigate(session_id, mail_url)
            await asyncio.sleep(6)

            iframe_result = await client.evaluate(session_id, '''
            (function() {
                const iframe = document.querySelector("#thirdPartyFrame_mail");
                return iframe ? iframe.src : null;
            })()
            ''', return_by_value=True)
            iframe_src = iframe_result.get('result', {}).get('value', '')

            if not iframe_src:
                url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                current_url = url_res.get('result', {}).get('value', '')
                return {
                    "status": "error",
                    "otp_url": None,
                    "mail_id": None,
                    "execution_time": f"{time.time()-start_time:.2f}s",
                    "error": f"Mail iframe nicht gefunden. URL: {current_url[:80]}...",
                }

            # Navigate to iframe to establish fresh webmailer session
            logger.info(f"Navigiere zu webmailer: {iframe_src[:80]}...")
            await client.navigate(session_id, iframe_src)
            await asyncio.sleep(5)
            
            # Get jsessionid from BROWSER COOKIES (set by webmailer, not from stale iframe_src)
            # The webmailer sets a JSESSIONID cookie. We extract it from the browser's
            # current cookie jar rather than from the iframe URL (which is stale).
            cookies_res = await client.send_to_session(session_id, "Network.getAllCookies")
            jsessionid = None
            for c in cookies_res.get("cookies", []):
                if c.get("name") == "JSESSIONID":
                    jsessionid = c.get("value", "")
                    break
            
            if not jsessionid:
                # Fallback: extract from current page URL
                current_url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                current_page_url = current_url_result.get('result', {}).get('value', '')
                jsessionid_match = re.search(r'jsessionid=([^?&;]+)', current_page_url)
                jsessionid = jsessionid_match.group(1) if jsessionid_match else None
            
            logger.info(f"JSESSIONID extrahiert: {jsessionid[:30] if jsessionid else None}...")

            if not jsessionid:
                return {
                    "status": "error",
                    "otp_url": None,
                    "mail_id": None,
                    "execution_time": f"{time.time()-start_time:.2f}s",
                    "error": "Konnte kein JSESSIONID aus iframe src extrahieren",
                }

            # ════════════════════════════════════════════════════════════════════════
            # PHASE 3: WEBMAILER LOADING (already navigated above)
            # ──────────────────────────────────────────────────────────────────────
            # The webmailer was already loaded during jsessionid extraction.
            # Wait additional time for list-mail-item elements to render.
            # ════════════════════════════════════════════════════════════════════════
            await asyncio.sleep(5)

            # ════════════════════════════════════════════════════════════════════════
            # NOTE: Baseline scan removed. We fetch ALL found items to maximize
            # chance of finding the OTP email. The sender_filter on the list
            # already ensures we only look at Fireworks emails.
            # ════════════════════════════════════════════════════════════════════════
            pass

            confirm_url = None
            found_mail_id = None
            # ════════════════════════════════════════════════════════════════════════
            # PHASE 4: POLLING LOOP
            # ──────────────────────────────────────────────────────────────────────
            # Wir pollen die Inbox nach Emails die `sender_filter` enthalten.
            # Bei jeder Iteration:
            #   1. Rekursive JS-Suche nach <list-mail-item> Elementen.
            #   2. Für jedes Element: prüfe ob textContent `sender_filter` enthält.
            #   3. Extrahiere mailId aus `id` Attribut (strip `id` prefix).
            #   4. Überspringe bekannte mailIds (aus exclude_mail_ids oder Baseline).
            #   5. Lade bis zu 5 Emails via HTTP API und parse nach Confirm-URL.
            #   6. Wenn nichts gefunden: warte `retry_delay` Sekunden, wiederhole.
            # ════════════════════════════════════════════════════════════════════════
            for i in range(max_retries):
                logger.info(f"OTP-Suche: Versuch {i + 1}/{max_retries} (bekannte IDs: {len(known_mail_ids)})")

                safe_filter = sender_filter.lower().replace("'", "\\'")
                # JS Funktion die rekursiv durch Shadow DOMs traversiert.
                # WICHTIG: `el.shadowRoot` ist nur verfügbar für OPEN shadow roots.
                # GMX's Webmailer nutzt für <webmailer-mail-list> und
                # <smartsearch-root> OPEN shadow roots, weshalb unser
                # rekursiver Walk funktioniert.
                items_js = f'''(function() {{
                    function findItems(root) {{
                        let items = [];
                        const all = root.querySelectorAll("*");
                        for (const el of all) {{
                            if (el.tagName.toLowerCase() === "list-mail-item") {{
                                const text = (el.textContent || "").toLowerCase();
                                if (text.includes("{safe_filter}")) {{
                                    const idAttr = el.getAttribute("id");
                                    const mailId = idAttr ? idAttr.replace(/^id/, "") : null;
                                    if (mailId) {{
                                        items.push({{
                                            mailId: mailId,
                                            text: el.textContent.trim().slice(0, 120).replace(/\\s+/g, " "),
                                        }});
                                    }}
                                }}
                            }}
                            if (el.shadowRoot) {{
                                items = items.concat(findItems(el.shadowRoot));
                            }}
                        }}
                        return items;
                    }}
                    return findItems(document.body);
                }})()'''
                items_result = await client.evaluate(session_id, items_js, return_by_value=True)
                items = items_result.get('result', {}).get('value', [])
                logger.info(f"Gefunden: {len(items)} list-mail-item mit '{sender_filter}'")

                if items:
                    # Filtere bekannte mailIds heraus
                    new_items = [it for it in items if it.get("mailId") not in known_mail_ids]
                    if len(new_items) < len(items):
                        logger.info(f"{len(items) - len(new_items)} bekannte/stale Emails übersprungen")

                    if new_items:
                        # ───────────────────────────────────────────────────────────
                        # COOKIE EXTRACTION (CDP Network.getAllCookies)
                        # ───────────────────────────────────────────────────────────
                        # Wir brauchen ALLE GMX Cookies für die HTTP-Anfrage.
                        # CRITICAL FIX (2026-05-10): Using ALL GMX cookies (79+) causes
                        # GMX mailbody API to return "413 Request Entity Too Large"
                        # with "Bitte loeschen Sie Ihre Browser Cookies" error.
                        # ONLY use essential GMX session cookies — this makes the
                        # mailbody API return 200 instead of 413!
                        # ───────────────────────────────────────────────────────────
                        cookies_res = await client.send_to_session(session_id, "Network.getAllCookies")
                        cookies = cookies_res.get("cookies", [])
                        essential_cookies = {"JSESSIONID", "SESSION", "lps", "navigator", "iac_token"}
                        cookie_dict = {}
                        for c in cookies:
                            if c.get("name") in essential_cookies:
                                cookie_dict[c.get("name")] = c.get("value", "")

                        headers = {
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                            "Referer": "https://3c-bap.gmx.net/mail/client/start",
                        }

                        # ════════════════════════════════════════════════════════════════
                        # PHASE 5: EMAIL BODY FETCHING VIA GMX INTERNAL API
                        # ──────────────────────────────────────────────────────────────
                        # Wir iterieren über die ersten 5 matching Emails.
                        # Die Emails sind nach Eingangszeit sortiert (neueste zuerst).
                        # Wir priorisieren Verify-Emails ("verify" / "confirm" im Text)
                        # gegenüber Welcome-Emails, indem wir ALLE Emails durchgehen
                        # und die erste mit einer Confirm-URL zurückgeben.
                        # ════════════════════════════════════════════════════════════════
                        async with httpx.AsyncClient(cookies=cookie_dict, follow_redirects=True, timeout=20) as http:
                            for item in new_items[:5]:  # Max 5 Emails pro Iteration
                                mail_id = item.get("mailId")
                                if not mail_id:
                                    continue
                                logger.info(f"Versuche mailId={mail_id} (NEU) | {item.get('text', '')[:60]}")

                                # Zwei Varianten probieren:
                                #   /true  → mit externen Bildern/Content
                                #   /false → ohne externen Content
                                # Die Confirm-URL ist im Plain-Text/HTML der Email.
                                urls_to_try = [
                                    f"https://3c-bap.gmx.net/mail/client/mailbody/tmai{mail_id}/true;jsessionid={jsessionid}",
                                    f"https://3c-bap.gmx.net/mail/client/mailbody/tmai{mail_id}/false;jsessionid={jsessionid}",
                                ]

                                for email_url in urls_to_try:
                                    try:
                                        resp = await http.get(email_url, headers=headers)
                                        # Validierung: HTTP 200 und Content > 1000 Bytes
                                        # (technische Fehlerseiten sind typischerweise < 200 Bytes)
                                        if resp.status_code == 200 and len(resp.text) > 1000:
                                            # ───────────────────────────────────────
                                            # CONFIRM URL EXTRACTION
                                            # ───────────────────────────────────────
                                            # Regex findet ALLE app.fireworks.ai URLs.
                                            # Dann filtern wir auf URLs die Bestätigungs-
                                            # relevante Keywords enthalten.
                                            # Achtung: HTML-escaping in URLs!
                                            #   &amp;  → muss zu & dekodiert werden.
                                            # ───────────────────────────────────────
                                            urls = re.findall(r'https://app\.fireworks\.ai/[^\s"\'<>]+', resp.text)
                                            confirm_candidates = [
                                                u for u in urls
                                                if any(k in u.lower() for k in ["confirm", "verify", "token", "auth", "activate", "signup"])
                                            ]
                                            if confirm_candidates:
                                                confirm_url = html_module.unescape(confirm_candidates[0])
                                                found_mail_id = mail_id
                                                logger.info(f"OTP-URL gefunden: {confirm_url[:80]}...")
                                                break
                                    except Exception as e:
                                        logger.warning(f"HTTP fetch fehlgeschlagen für {email_url[:80]}: {e}")

                                if confirm_url:
                                    break

                if confirm_url:
                    break

                # Alle gesehenen mailIds als "bekannt" markieren (auch alte)
                # damit sie in zukünftigen Iterationen übersprungen werden.
                for it in items:
                    mid = it.get("mailId")
                    if mid:
                        known_mail_ids.add(mid)

                if i < max_retries - 1:
                    logger.info(f"Kein neues OTP gefunden, warte {retry_delay}s...")
                    await asyncio.sleep(retry_delay)

            elapsed = time.time() - start_time
            return {
                "status": "success" if confirm_url else "not_found",
                "otp_url": confirm_url,
                "mail_id": found_mail_id,
                "execution_time": f"{elapsed:.2f}s",
                "error": None if confirm_url else f"Nicht gefunden nach {max_retries} Versuchen",
            }
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"OTP-Suche fehlgeschlagen: {e}")
            return {
                "status": "error",
                "otp_url": None,
                "mail_id": None,
                "execution_time": f"{elapsed:.2f}s",
                "error": str(e),
            }


_gmx_service: Optional[GmxService] = None


def get_gmx_service() -> GmxService:
    global _gmx_service
    if _gmx_service is None:
        _gmx_service = GmxService()
    return _gmx_service