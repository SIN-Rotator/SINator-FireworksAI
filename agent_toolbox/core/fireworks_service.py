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

    async def register(
        self, email: str, password: str, cdp_port: int = 9222, timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Registriert neuen Fireworks AI Account.

        FLOW:
        1. Navigate zu /signup
        2. Email eingeben (input[type=email], input[name=email])
        3. "Next" oder "Continue" klicken
        4. Passwort eingeben
        5. "Create Account" oder "Sign Up" klicken
        6. Warten auf Redirect oder Bestätigungs-Meldung

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
            await asyncio.sleep(5)
            await self._screenshot(client, session_id, "fw_signup")

            email_selectors = [
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