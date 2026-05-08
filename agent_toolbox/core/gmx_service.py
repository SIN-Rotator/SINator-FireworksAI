"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — GMX Service (CDP+Iframe Edition)      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  GMX Session-Management, Alias-Erstellung/Löschung via RAW CDP + IFRAME     ║
║                                                                              ║
║  ARCHITEKTUR-ENTSCHEIDUNGEN:                                                 ║
║  • Playwright crashed bei GMX Navigator SPA (frame detachment)              ║
║  • Lösung: CDP websocket für Navigation + CDP Page.createIsolatedWorld     ║
║    für DOM-Zugriff im cross-origin iframe `3c-bap.gmx.net`                 ║
║  • Maus-Interaktionen via CDP Input.dispatchMouseEvent (Koordinaten)       ║
║  • Input-Werte via JS in isolierter Welt setzen + Events dispatch         ║
║                                                                              ║
║  IFRAME-STRUKTUR (entscheidend für Automatisierung):                         ║
║  Main Frame: bap.navigator.gmx.net/mail_settings?sid=...                   ║
║    └─ iframe#thirdPartyFrame_mail_settings                                  ║
║       url: 3c-bap.gmx.net/mail/client/settings/allEmailAddresses          ║
║       Enthält: Alias-Tabelle, Formular, Hinzufügen-Buttons                  ║
║                                                                              ║
║  WARUM ISOLATED WORLD?                                                       ║
║  • iframe ist cross-origin (3c-bap.gmx.net ≠ bap.navigator.gmx.net)        ║
║  • document.querySelector('#thirdPartyFrame_mail_settings').contentDocument  ║
║    wirft "cross-origin" Fehler                                              ║
║  • CDP Page.createIsolatedWorld(frameId) erstellt eine Execution Context   ║
║    im iframe mit Zugriff auf dessen DOM                                     ║
║                                                                              ║
║  INTERAKTIONS-PATTERN:                                                         ║
║  1. Element in isolierter Welt finden (querySelector)                       ║
║  2. getBoundingClientRect() → Koordinaten holen                             ║
║  3. iframe-Offset addieren (via DOM.getBoxModel des iframe-Elements)       ║
║  4. CDP Input.dispatchMouseEvent an berechneten Koordinaten                ║
║                                                                              ║
║  ALIAS LÖSCHEN PATTERN:                                                      ║
║  1. Alias-Zeile finden (text.includes('@gmx.de') && !Standardadresse)       ║
║  2. Zeile anklicken (client.click_at) → reveals Bearbeiten + Löschen Icons ║
║  3. Löschen-Icon finden (title.includes('löschen'))                        ║
║  4. Löschen-Icon klicken → Bestätigungs-Dialog                             ║
║  5. OK-Button finden + klicken → "Eintrag wurde erfolgreich gelöscht"       ║
║                                                                              ║
║  ALIAS ERSTELLEN PATTERN:                                                    ║
║  1. Input[name*='localPart'] finden                                         ║
║  2. input.value setzen + dispatch input/change events                      ║
║  3. Hinzufügen-Button finden (textContent == 'Hinzufügen')                  ║
║  4. Button klicken via CDP Koordinaten                                     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import random
import logging
import re
import asyncio
import base64
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

logger = logging.getLogger(__name__)

GMX_HOME_URL = "https://www.gmx.net/"


class GmxService:
    """
    Verwaltet GMX-Operationen via RAW CDP WEBSOCKET + IFRAME ISOLATED WORLD.
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
        """Generiert einen Alias-Namen im Format {adj}-{noun}."""
        adj = random.choice(self.adjectives)
        noun = random.choice(self.nouns)
        return f"{adj}-{noun}"

    # ═══════════════════════════════════════════════════════════════════════════════
    #  CDP CONNECTION & IFRAME HELPERS
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

    async def _get_iframe_frame_id(self, client: CDPClient, session_id: str) -> Optional[str]:
        """Findet die frameId des mail_settings iframes via Page.getFrameTree."""
        frame_tree = await client.send_to_session(session_id, "Page.getFrameTree")
        
        def search(node: Dict) -> Optional[str]:
            frame = node.get("frame", {})
            url = frame.get("url", "")
            name = frame.get("name", "")
            if "allEmailAddresses" in url or name == "mail_settings":
                return frame.get("id")
            for child in node.get("childFrames", []):
                result = search(child)
                if result:
                    return result
            return None
        
        return search(frame_tree.get("frameTree", {}))

    async def _create_isolated_context(self, client: CDPClient, session_id: str, iframe_frame_id: str) -> int:
        """Erstellt eine isolierte JS-Welt im iframe und gibt contextId zurück."""
        isolated = await client.send_to_session(session_id, "Page.createIsolatedWorld", {
            "frameId": iframe_frame_id,
            "worldName": "sinator_automation",
        })
        ctx_id = isolated.get("executionContextId")
        logger.info(f"Isolated world contextId: {ctx_id}")
        return ctx_id

    async def _get_iframe_offset(self, client: CDPClient, session_id: str) -> Tuple[float, float]:
        """
        Bestimmt die Screen-Position des iframe#thirdPartyFrame_mail_settings.
        
        Returns:
            (offset_x, offset_y) im main frame Koordinatensystem.
        """
        try:
            doc = await client.send_to_session(session_id, "DOM.getDocument", {"pierce": True})
            root_id = doc.get("root", {}).get("nodeId")
            result = await client.send_to_session(session_id, "DOM.querySelector", {
                "nodeId": root_id,
                "selector": "iframe#thirdPartyFrame_mail_settings",
            })
            iframe_node_id = result.get("nodeId", 0)
            if iframe_node_id and iframe_node_id > 0:
                box = await client.send_to_session(session_id, "DOM.getBoxModel", {"nodeId": iframe_node_id})
                model = box.get("model", {})
                content = model.get("content", [])
                if len(content) >= 2:
                    return content[0], content[1]
        except Exception as e:
            logger.warning(f"Konnte iframe-Offset nicht bestimmen: {e}")
        
        # Fallback: known offset from visual inspection
        logger.info("Verwende Fallback iframe-offset: (0, 80)")
        return 0.0, 80.0

    async def _eval_in_iframe(self, client: CDPClient, session_id: str, ctx_id: int, js: str, timeout: float = 10.0) -> Any:
        """Führt JS in der isolierten Welt des iframes aus."""
        result = await client.send_to_session(session_id, "Runtime.evaluate", {
            "expression": js,
            "contextId": ctx_id,
            "returnByValue": True,
            "awaitPromise": True,
        }, timeout=timeout)
        val = result.get("result", {}).get("value")
        return val

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

    async def _ensure_mail_session(self, client: CDPClient, session_id: str) -> Dict[str, Any]:
        """Öffnet GMX Mail via Klick auf 'Zum Postfach' von der eingeloggten Homepage."""
        await client.navigate(session_id, GMX_HOME_URL)
        await asyncio.sleep(4)

        body_js = '''(function(){
            function t(r,d){if(d>8)return'';let txt=(r.textContent||'');
            for(const e of r.querySelectorAll('*')){if(e.shadowRoot)txt+=' '+t(e.shadowRoot,d+1);}
            return txt;}return t(document.body,0);
        })()'''
        body_text = await client.evaluate(session_id, body_js, return_by_value=True)
        body = body_text.get("result", {}).get("value", "")
        
        if "Sie sind eingeloggt" not in body and "Zum Postfach" not in body:
            logger.warning("Nicht eingeloggt auf GMX Homepage")
            url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            return {"success": False, "current_url": url_result.get("result", {}).get("value", ""), "sid": None}

        logger.info("GMX-Session aktiv auf Homepage")
        
        js = '''(function(){
            function c(r,t,d){if(d>8)return false;
            for(const e of r.querySelectorAll('*')){
            if((e.textContent||'').trim()===t){e.click();return true;}
            if(e.shadowRoot&&c(e.shadowRoot,t,d+1))return true;}
            return false;}return c(document.body,'Zum Postfach',0);})()'''
        await client.evaluate(session_id, js, return_by_value=True)
        await asyncio.sleep(8)
        
        url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        current_url = url_result.get("result", {}).get("value", "")
        
        sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
        sid = sid_match.group(1) if sid_match else None
        
        if sid:
            logger.info(f"GMX sid extrahiert: {sid[:30]}...")
        
        if "navigator.gmx.net" in current_url or "mail.gmx.net" in current_url:
            return {"success": True, "current_url": current_url, "sid": sid}
        return {"success": False, "current_url": current_url, "sid": sid, "error": "Nicht im Mail-Bereich"}

    async def _open_email_addresses(self, client: CDPClient, session_id: str) -> bool:
        """Klickt auf 'E-Mail-Adressen' in der Seitenleiste (CDP Koordinate y≈290)."""
        logger.info("Öffne E-Mail-Adressen via CDP Click bei (80, 290)")
        await client.click_at(session_id, x=80, y=290)
        await asyncio.sleep(6)
        return True

    # ═══════════════════════════════════════════════════════════════════════════════
    #  ALIAS DELETION
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _find_alias_row(self, client: CDPClient, session_id: str, ctx_id: int) -> Optional[Dict[str, Any]]:
        """Findet die erste Alias-Zeile (nicht Standardadresse) im iframe."""
        js = '''(function(){
            const rows = document.querySelectorAll('div, tr, li, a');
            for (const row of rows) {
                const text = row.textContent;
                if (text.includes('@gmx.de') && !text.includes('Standardadresse')) {
                    const rect = row.getBoundingClientRect();
                    return {
                        found: true,
                        text: text.trim().slice(0,50),
                        x: rect.x, y: rect.y, w: rect.width, h: rect.height,
                        cx: rect.x + rect.width / 2,
                        cy: rect.y + rect.height / 2
                    };
                }
            }
            return null;
        })()'''
        return await self._eval_in_iframe(client, session_id, ctx_id, js)

    async def _find_delete_icon(self, client: CDPClient, session_id: str, ctx_id: int) -> Optional[Dict[str, Any]]:
        """Sucht das Löschen-Icon (title='E-Mail-Adresse löschen') im iframe."""
        js = '''(function(){
            const all = document.querySelectorAll('a, button, svg, img, i, span');
            for (const el of all) {
                const title = (el.getAttribute('title') || '').toLowerCase();
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                if (title.includes('löschen') || title.includes('delete') || title.includes('entfernen') ||
                    aria.includes('löschen') || aria.includes('delete')) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        return {
                            found: true,
                            tag: el.tagName,
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2,
                            width: rect.width,
                            height: rect.height,
                            title: el.getAttribute('title') || el.getAttribute('aria-label')
                        };
                    }
                }
            }
            return null;
        })()'''
        return await self._eval_in_iframe(client, session_id, ctx_id, js)

    async def _find_confirm_button(self, client: CDPClient, session_id: str, ctx_id: int) -> Optional[Dict[str, Any]]:
        """Sucht den Bestätigungs-Button (OK/Ja/Löschen) im Dialog."""
        js = '''(function(){
            const btns = document.querySelectorAll('button, a, input[type=submit]');
            for (const b of btns) {
                const t = b.textContent.trim().toLowerCase();
                if (t === 'ja' || t === 'ok' || t === 'löschen' || t === 'entfernen' || t === 'bestätigen') {
                    const rect = b.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        return {
                            found: true,
                            text: b.textContent.trim(),
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2
                        };
                    }
                }
            }
            return null;
        })()'''
        return await self._eval_in_iframe(client, session_id, ctx_id, js)

    async def delete_existing_alias(self, cdp_port: int = 9222) -> Dict[str, Any]:
        """
        Löscht einen existierenden GMX Alias.
        
        FLOW:
        1. Session + E-Mail-Adressen Seite öffnen
        2. iframe frameId finden
        3. Isolierte Welt im iframe erstellen
        4. Alias-Zeile finden
        5. Auf Zeile klicken (reveals Bearbeiten + Löschen Icons)
        6. Löschen-Icon finden und klicken (öffnet Bestätigungs-Dialog)
        7. OK-Button finden und klicken
        
        Returns:
            {"status": "success"|"no_alias"|"not_logged_in"|"error", "deleted": bool, "alias": str|None}
        """
        client = None
        try:
            client, session_id, target_id = await self._connect_to_browser(cdp_port)
            
            session = await self._ensure_mail_session(client, session_id)
            if not session["success"]:
                return {"status": "not_logged_in", "deleted": False}
            
            sid = session.get("sid")
            if sid:
                settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
                await client.navigate(session_id, settings_url)
                await asyncio.sleep(5)
            
            await self._open_email_addresses(client, session_id)
            await self._screenshot(client, session_id, "delete_before")
            
            # iframe finden
            iframe_frame_id = await self._get_iframe_frame_id(client, session_id)
            if not iframe_frame_id:
                return {"status": "error", "deleted": False, "error": "iframe nicht gefunden"}
            
            ctx_id = await self._create_isolated_context(client, session_id, iframe_frame_id)
            offset_x, offset_y = await self._get_iframe_offset(client, session_id)
            
            # Alias-Zeile finden
            alias_row = await self._find_alias_row(client, session_id, ctx_id)
            if not alias_row:
                logger.info("Kein existierender Alias gefunden")
                return {"status": "no_alias", "deleted": True, "alias": None}
            
            alias_text = alias_row.get("text", "")
            logger.info(f"Alias gefunden: {alias_text}")
            
            # Auf Zeile klicken (reveals Trash-Icon)
            row_x = alias_row.get("x", 0) + 10 + offset_x
            row_y = alias_row.get("y", 0) + 10 + offset_y
            logger.info(f"Klicke Alias-Zeile bei ({row_x:.1f}, {row_y:.1f})")
            await client.click_at(session_id, x=row_x, y=row_y)
            await asyncio.sleep(2)
            
            await self._screenshot(client, session_id, "delete_after_row_click")
            
            # Löschen-Icon finden
            trash = await self._find_delete_icon(client, session_id, ctx_id)
            if not trash:
                logger.warning("Löschen-Icon nicht gefunden nach Zeilen-Klick")
                return {"status": "error", "deleted": False, "alias": alias_text, "error": "Löschen-Icon nicht gefunden"}
            
            trash_x = trash["x"] + offset_x
            trash_y = trash["y"] + offset_y
            logger.info(f"Klicke Löschen-Icon bei ({trash_x:.1f}, {trash_y:.1f})")
            await client.click_at(session_id, x=trash_x, y=trash_y)
            await asyncio.sleep(3)
            
            await self._screenshot(client, session_id, "delete_after_trash_click")
            
            # Bestätigungs-Button finden
            confirm = await self._find_confirm_button(client, session_id, ctx_id)
            if not confirm:
                logger.warning("Bestätigungs-Button nicht gefunden")
                return {"status": "error", "deleted": False, "alias": alias_text, "error": "Bestätigungs-Button nicht gefunden"}
            
            confirm_x = confirm["x"] + offset_x
            confirm_y = confirm["y"] + offset_y
            logger.info(f"Klicke Bestätigung '{confirm.get('text')}' bei ({confirm_x:.1f}, {confirm_y:.1f})")
            await client.click_at(session_id, x=confirm_x, y=confirm_y)
            await asyncio.sleep(3)
            
            await self._screenshot(client, session_id, "delete_after_confirm")
            
            logger.info(f"✅ Alias gelöscht: {alias_text}")
            return {"status": "success", "deleted": True, "alias": alias_text}
            
        except Exception as e:
            logger.error(f"Alias-Löschung fehlgeschlagen: {e}")
            return {"status": "error", "deleted": False, "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    # ═══════════════════════════════════════════════════════════════════════════════
    #  ALIAS CREATION
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _find_alias_input(self, client: CDPClient, session_id: str, ctx_id: int) -> Optional[Dict[str, Any]]:
        """Findet das Alias-Name Input-Feld im iframe."""
        js = '''(function(){
            const inputs = document.querySelectorAll('input[name*="localPart"]');
            const input = inputs[0];
            if (!input) return null;
            const rect = input.getBoundingClientRect();
            return {
                found: true,
                name: input.name,
                placeholder: input.placeholder,
                x: rect.x + rect.width / 2,
                y: rect.y + rect.height / 2,
            };
        })()'''
        return await self._eval_in_iframe(client, session_id, ctx_id, js)

    async def _find_hinzufuegen_button(self, client: CDPClient, session_id: str, ctx_id: int) -> Optional[Dict[str, Any]]:
        """Findet den Hinzufügen-Button im iframe."""
        js = '''(function(){
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                if (b.textContent.trim() === 'Hinzufügen') {
                    const rect = b.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        return {
                            found: true,
                            text: b.textContent.trim(),
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2,
                            id: b.id,
                            className: b.className
                        };
                    }
                }
            }
            return null;
        })()'''
        return await self._eval_in_iframe(client, session_id, ctx_id, js)

    async def create_alias(self, alias_name: Optional[str] = None, cdp_port: int = 9222) -> Dict[str, Any]:
        """
        Erstellt einen neuen GMX Alias.
        
        FLOW:
        1. Session + E-Mail-Adressen Seite öffnen
        2. iframe frameId finden
        3. Isolierte Welt erstellen
        4. Input-Wert setzen + Events dispatch (in isolierter Welt)
        5. Hinzufügen-Button via Koordinaten klicken (CDP Input.dispatchMouseEvent)
        
        Returns:
            {"status": "success"|"failed"|"not_logged_in"|"error", "alias_email": str|None}
        """
        start_time = time.time()
        steps = []
        
        if not alias_name:
            alias_name = self.generate_alias_name()
        alias_email = f"{alias_name}@gmx.de"
        logger.info(f"Erstelle GMX Alias: {alias_email}")
        
        client = None
        try:
            client, session_id, target_id = await self._connect_to_browser(cdp_port)
            
            session = await self._ensure_mail_session(client, session_id)
            if not session["success"]:
                return {"status": "not_logged_in", "alias_email": None, "steps_completed": steps}
            steps.append("session_active")
            
            sid = session.get("sid")
            if sid:
                settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
                await client.navigate(session_id, settings_url)
                await asyncio.sleep(5)
            
            await self._open_email_addresses(client, session_id)
            steps.append("opened_addresses_page")
            await self._screenshot(client, session_id, "create_before")
            
            # iframe finden
            iframe_frame_id = await self._get_iframe_frame_id(client, session_id)
            if not iframe_frame_id:
                return {"status": "error", "alias_email": None, "error": "iframe nicht gefunden", "steps_completed": steps}
            
            ctx_id = await self._create_isolated_context(client, session_id, iframe_frame_id)
            offset_x, offset_y = await self._get_iframe_offset(client, session_id)
            
            # Input-Wert setzen in isolierter Welt
            js_fill = f'''
            (function(){{
                const inputs = document.querySelectorAll('input[name*="localPart"]');
                const input = inputs[0];
                if (!input) return {{error: "Input nicht gefunden"}};
                input.value = "{alias_name}";
                input.dispatchEvent(new Event("input", {{bubbles: true}}));
                input.dispatchEvent(new Event("change", {{bubbles: true}}));
                return {{success: true, name: input.name, value: input.value}};
            }})()
            '''
            fill_result = await self._eval_in_iframe(client, session_id, ctx_id, js_fill)
            logger.info(f"Input gefüllt: {fill_result}")
            if not fill_result or not fill_result.get("success"):
                return {"status": "error", "alias_email": None, "error": "Input-Feld nicht gefunden", "steps_completed": steps}
            steps.append("filled_form")
            await asyncio.sleep(1)
            
            # Hinzufügen-Button finden und klicken
            btn = await self._find_hinzufuegen_button(client, session_id, ctx_id)
            if not btn:
                return {"status": "error", "alias_email": None, "error": "Hinzufügen-Button nicht gefunden", "steps_completed": steps}
            
            btn_x = btn["x"] + offset_x
            btn_y = btn["y"] + offset_y
            logger.info(f"Klicke Hinzufügen bei ({btn_x:.1f}, {btn_y:.1f})")
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
            steps.append("clicked_add")
            await asyncio.sleep(5)
            
            await self._screenshot(client, session_id, "create_after")
            
            # Erfolg prüfen
            js_check = f'''(function(){{
                const bodyText = document.body.textContent;
                return {{
                    hasNewAlias: bodyText.includes("{alias_name}"),
                    hasSuccess: /erfolgreich|wurde angelegt|wurde erstellt/.test(bodyText),
                    hasError: /fehler|bereits vergeben|nicht verf|maximal|existiert/.test(bodyText),
                }};
            }})()'''
            check = await self._eval_in_iframe(client, session_id, ctx_id, js_check)
            logger.info(f"Erfolgs-Check: {check}")
            
            elapsed = time.time() - start_time
            
            if check.get("hasError"):
                return {
                    "status": "failed",
                    "alias_email": None,
                    "alias_name": alias_name,
                    "steps_completed": steps,
                    "execution_time": f"{elapsed:.2f}s",
                    "error": "Alias konnte nicht erstellt werden (Fehler von GMX)",
                }
            
            # Wenn wir hier sind, nehmen wir an, dass es funktioniert hat
            # (GMX zeigt manchmal keine explizite Erfolgsmeldung)
            logger.info(f"✅ Alias erstellt: {alias_email}")
            return {
                "status": "success",
                "alias_email": alias_email,
                "alias_name": alias_name,
                "steps_completed": steps,
                "execution_time": f"{elapsed:.2f}s",
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

    async def open_email_addresses_page(self, cdp_port: int = 9222) -> Dict[str, Any]:
        """Navigiert zur E-Mail-Adressen-Verwaltungsseite."""
        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)
            session = await self._ensure_mail_session(client, session_id)
            if not session["success"]:
                return {"status": "not_logged_in", "current_url": session.get("current_url", "")}
            
            sid = session.get("sid")
            if sid:
                settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
                await client.navigate(session_id, settings_url)
                await asyncio.sleep(5)
            
            await self._open_email_addresses(client, session_id)
            url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_result.get("result", {}).get("value", "")
            
            return {"status": "success", "current_url": current_url}
        except Exception as e:
            logger.error(f"E-Mail-Adressen-Seite fehlgeschlagen: {e}")
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

    async def rotate_alias(self, new_alias_name: Optional[str] = None, cdp_port: int = 9222) -> Dict[str, Any]:
        """
        Alias-Rotation: Löscht existierenden Alias und erstellt einen neuen.

        Dies ist der ATOMISCHE Kern-Flow: delete + create in einem Browser-Kontext.
        Beide Operationen teilen sich eine CDP-Verbindung, was Zeit spart und
        Session-Stabilität gewährleistet.

        Args:
            new_alias_name: Optionaler Name. Wenn None, wird generiert.

        Returns:
            {"status": "success"|"partial"|"failed", "deleted_alias": str|None,
             "created_alias": str|None, "created_alias_name": str|None,
             "steps_completed": [...], "steps_failed": [...]}
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

            # --- STEP 1: Ensure mail session ---
            session = await self._ensure_mail_session(client, session_id)
            if not session["success"]:
                steps_failed.append("session_check")
                return {
                    "status": "failed",
                    "deleted_alias": None,
                    "created_alias": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "GMX session nicht aktiv",
                }
            steps_completed.append("session_active")

            # --- STEP 2: Navigate to settings with sid ---
            sid = session.get("sid")
            if sid:
                settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
                await client.navigate(session_id, settings_url)
                await asyncio.sleep(5)
            steps_completed.append("settings_page_loaded")

            # --- STEP 3: Open email-addresses section ---
            await self._open_email_addresses(client, session_id)
            await asyncio.sleep(4)
            steps_completed.append("email_addresses_opened")

            # --- STEP 4: Find iframe and isolated world ---
            iframe_frame_id = await self._get_iframe_frame_id(client, session_id)
            if not iframe_frame_id:
                steps_failed.append("iframe_lookup")
                return {
                    "status": "failed",
                    "deleted_alias": None,
                    "created_alias": None,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "iframe nicht gefunden",
                }

            ctx_id = await self._create_isolated_context(client, session_id, iframe_frame_id)
            offset_x, offset_y = await self._get_iframe_offset(client, session_id)
            steps_completed.append("isolated_world_created")

            # --- STEP 5: Delete existing alias ---
            alias_row = await self._find_alias_row(client, session_id, ctx_id)
            if alias_row:
                alias_text = alias_row.get("text", "")
                row_x = alias_row.get("x", 0) + 10 + offset_x
                row_y = alias_row.get("y", 0) + 10 + offset_y
                await client.click_at(session_id, x=row_x, y=row_y)
                await asyncio.sleep(2)

                trash = await self._find_delete_icon(client, session_id, ctx_id)
                if trash:
                    trash_x = trash["x"] + offset_x
                    trash_y = trash["y"] + offset_y
                    await client.click_at(session_id, x=trash_x, y=trash_y)
                    await asyncio.sleep(3)

                    confirm = await self._find_confirm_button(client, session_id, ctx_id)
                    if confirm:
                        confirm_x = confirm["x"] + offset_x
                        confirm_y = confirm["y"] + offset_y
                        await client.click_at(session_id, x=confirm_x, y=confirm_y)
                        await asyncio.sleep(3)
                        deleted_alias = alias_text
                        steps_completed.append("alias_deleted")
                    else:
                        steps_failed.append("confirm_button_not_found")
                else:
                    steps_failed.append("trash_icon_not_found")
            else:
                steps_completed.append("no_existing_alias")
                deleted_alias = None

            # --- STEP 6: Create new alias ---
            if not new_alias_name:
                new_alias_name = self.generate_alias_name()
            created_alias = f"{new_alias_name}@gmx.de"

            js_fill = f'''
            (function(){{
                const inputs = document.querySelectorAll('input[name*="localPart"]');
                const input = inputs[0];
                if (!input) return {{error: "Input nicht gefunden"}};
                input.value = "{new_alias_name}";
                input.dispatchEvent(new Event("input", {{bubbles: true}}));
                input.dispatchEvent(new Event("change", {{bubbles: true}}));
                return {{success: true}};
            }})()
            '''
            fill_result = await self._eval_in_iframe(client, session_id, ctx_id, js_fill)
            if not fill_result or not fill_result.get("success"):
                steps_failed.append("input_fill")
                return {
                    "status": "partial",
                    "deleted_alias": deleted_alias,
                    "created_alias": None,
                    "created_alias_name": new_alias_name,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "Input-Feld nicht gefunden",
                }
            steps_completed.append("form_filled")
            await asyncio.sleep(1)

            btn = await self._find_hinzufuegen_button(client, session_id, ctx_id)
            if not btn:
                steps_failed.append("hinzufuegen_button_not_found")
                return {
                    "status": "partial",
                    "deleted_alias": deleted_alias,
                    "created_alias": None,
                    "created_alias_name": new_alias_name,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "Hinzufügen-Button nicht gefunden",
                }

            btn_x = btn["x"] + offset_x
            btn_y = btn["y"] + offset_y
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
            steps_completed.append("add_button_clicked")
            await asyncio.sleep(5)

            js_check = f'''(function(){{
                const bodyText = document.body.textContent;
                return {{
                    hasNewAlias: bodyText.includes("{new_alias_name}"),
                    hasError: /fehler|bereits vergeben|nicht verf|maximal|existiert/.test(bodyText),
                }};
            }})()'''
            check = await self._eval_in_iframe(client, session_id, ctx_id, js_check)

            if check.get("hasError"):
                steps_failed.append("alias_create_gmx_error")
                return {
                    "status": "failed",
                    "deleted_alias": deleted_alias,
                    "created_alias": None,
                    "created_alias_name": new_alias_name,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "execution_time": f"{time.time() - start_time:.2f}s",
                    "error": "GMX meldet Fehler bei Alias-Erstellung",
                }

            created_alias_name = new_alias_name
            steps_completed.append("alias_created")
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

    async def read_otp(
        self,
        sender_filter: str = "fireworks",
        max_retries: int = 12,
        retry_delay: int = 5,
        cdp_port: int = 9222,
    ) -> Dict[str, Any]:
        """Liest OTP-URL aus der GMX Inbox (polling)."""
        start_time = time.time()
        client = None
        try:
            client, session_id, _ = await self._connect_to_browser(cdp_port)
            result = await self._ensure_mail_session(client, session_id)
            if not result["success"]:
                return {"status": "not_logged_in", "otp_url": None}
            
            confirm_url = None
            for i in range(max_retries):
                logger.info(f"OTP-Suche: Versuch {i + 1}/{max_retries}")
                await client.navigate(session_id, "https://navigator.gmx.net/mail")
                await asyncio.sleep(3)
                
                body_js = f'''(function(){{
                    function t(r,d){{if(d>8)return'';let txt=(r.textContent||'').toLowerCase();
                    for(const e of r.querySelectorAll('*')){{if(e.shadowRoot)txt+=' '+t(e.shadowRoot,d+1);}}
                    return txt;}}return t(document.body,0);
                }})()'''
                body_result = await client.evaluate(session_id, body_js, return_by_value=True)
                body_text = body_result.get("result", {}).get("value", "")
                
                if sender_filter.lower() in body_text:
                    url_match = re.search(
                        r'https://app\.fireworks\.ai/[^\s\'"<>]+(?:confirm|verify|token)[^\s\'"<>]*',
                        body_text, re.IGNORECASE,
                    )
                    if url_match:
                        confirm_url = url_match.group(0)
                        logger.info(f"OTP-URL gefunden: {confirm_url[:50]}...")
                        break
                
                await asyncio.sleep(retry_delay)
            
            elapsed = time.time() - start_time
            return {
                "status": "success" if confirm_url else "not_found",
                "otp_url": confirm_url,
                "execution_time": f"{elapsed:.2f}s",
                "error": None if confirm_url else f"Nicht gefunden nach {max_retries} Versuchen",
            }
        except Exception as e:
            return {
                "status": "error",
                "otp_url": None,
                "execution_time": f"{time.time()-start_time:.2f}s",
                "error": str(e),
            }
        finally:
            if client:
                await client.disconnect()


_gmx_service: Optional[GmxService] = None


def get_gmx_service() -> GmxService:
    global _gmx_service
    if _gmx_service is None:
        _gmx_service = GmxService()
    return _gmx_service
