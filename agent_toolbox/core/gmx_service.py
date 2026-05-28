"""
SINATOR AGENT-TOOLBOX — GMX Service (Vereinfacht v2026-05-28)

Kernfunktionen:
  - GMX Session-Management (Cookie-Injektion, SID-Extraktion)
  - Alias-Rotation (Löschen + Erstellen)
  - OTP/Confirm-URL Extraktion via GMX Mail

WICHTIG: Kein Playwright, kein CUA-Driver-Fallback.
Nur raw CDP (websockets) + JS evaluate.
"""
import time
import random
import logging
import re
import asyncio
import json
import html as html_module
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import httpx

from agent_toolbox.core.cdp_client import (
    CDPClient,
    OopifContext,
    get_browser_ws_endpoint,
    get_page_target,
)

logger = logging.getLogger(__name__)

GMX_HOME_URL = "https://www.gmx.net/"


class GmxService:
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
            "wolverine", "raptor", "condor", "viper", "scorpion", "spider", "mantis", "beetle",
        ]

    def generate_alias_name(self) -> str:
        adj = random.choice(self.adjectives)
        noun = random.choice(self.nouns)
        num = random.randint(100, 999)
        return f"{adj}-{noun}-{num}"

    # ── CDP Connection ───────────────────────────────────────────────────

    async def _connect(self, cdp_port: int) -> Tuple[CDPClient, str]:
        ws_url = await get_browser_ws_endpoint(cdp_port)
        client = CDPClient(ws_url)
        await client.connect()
        targets = await client.get_targets()
        target = None
        for t in targets:
            if t.get("type") == "page" and "sid=" in t.get("url", "") and "gmx.net" in t.get("url", ""):
                target = t
                break
        if not target:
            target = await get_page_target(client, url_filter="gmx.net")
        if not target:
            await client.disconnect()
            raise RuntimeError("Kein GMX Page-Target gefunden")
        session_id = await client.attach_to_target(target["targetId"])
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        return client, session_id

    # ── Navigation ─────────────────────────────────────────────────────

    async def _inject_cookies(self, client: CDPClient, session_id: str) -> int:
        cookies_file = Path("./data/gmx-cookies.json")
        if not cookies_file.exists():
            return 0
        try:
            with open(cookies_file) as f:
                cookies = json.load(f)
        except Exception:
            return 0
        injected = 0
        for cookie in cookies:
            try:
                params = {
                    "name": cookie.get("name"),
                    "value": cookie.get("value"),
                    "domain": cookie.get("domain"),
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                }
                same_site = cookie.get("sameSite")
                if same_site and same_site != "None":
                    params["sameSite"] = same_site
                expires = cookie.get("expires", -1)
                if expires and expires != -1:
                    try:
                        params["expires"] = float(expires)
                    except (ValueError, TypeError):
                        pass
                result = await client.send_to_session(session_id, "Network.setCookie", params)
                if result and not result.get("error"):
                    injected += 1
            except Exception:
                pass
        logger.info(f"{injected}/{len(cookies)} Cookies injiziert")
        return injected

    async def _ensure_mail_session(self, client: CDPClient, session_id: str) -> Dict[str, Any]:
        await self._inject_cookies(client, session_id)
        await asyncio.sleep(1)
        url_result = await client.evaluate(session_id, "window.location.href")
        current_url = url_result.get("result", {}).get("value", "")
        if "3c-bap.gmx.net" in current_url and "jsessionid" in current_url:
            return {"success": True, "current_url": current_url, "sid": None}
        if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
            sid = re.search(r'[?&]sid=([^&]+)', current_url)
            sid = sid.group(1) if sid else None
            if sid and "mail_settings" in current_url:
                return {"success": True, "current_url": current_url, "sid": sid}
            if sid:
                settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
                await client.navigate(session_id, settings_url)
                await asyncio.sleep(5)
                return {"success": True, "current_url": settings_url, "sid": sid}
        is_homepage = current_url.rstrip('/') in ["https://www.gmx.net", "https://www.gmx.net/", "http://www.gmx.net", "http://www.gmx.net/"]
        if not is_homepage:
            await client.navigate(session_id, "https://www.gmx.net/")
            await asyncio.sleep(4)
        await client.evaluate(session_id, """
        (function(){
            var as = document.querySelectorAll('a');
            for (var i=0; i<as.length; i++) {
                if (as[i].textContent.trim() === 'E-Mail') { as[i].click(); return true; }
            }
            return false;
        })()
        """, return_by_value=True)
        await asyncio.sleep(5)
        url_result = await client.evaluate(session_id, "window.location.href")
        current_url = url_result.get("result", {}).get("value", "")
        sid = re.search(r'[?&]sid=([^&]+)', current_url)
        sid = sid.group(1) if sid else None
        if sid and "navigator.gmx.net" in current_url:
            settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
            await client.navigate(session_id, settings_url)
            await asyncio.sleep(5)
            return {"success": True, "current_url": settings_url, "sid": sid}
        return {"success": False, "current_url": current_url, "error": "Keine Session"}

    async def _navigate_to_all_email_addresses(self, client: CDPClient, session_id: str) -> bool:
        ur = await client.evaluate(session_id, "window.location.href")
        url = ur.get("result", {}).get("value", "") or ""
        if "allEmailAddresses" in url:
            return True
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        await client.evaluate(session_id, """
        (function() {
            var as = document.querySelectorAll('a');
            for (var i=0; i<as.length; i++) {
                if (as[i].textContent.trim() === 'E-Mail') { as[i].click(); return true; }
            }
            return false;
        })()
        """, return_by_value=True)
        await asyncio.sleep(5)
        ur = await client.evaluate(session_id, "window.location.href")
        url = ur.get("result", {}).get("value", "") or ""
        m = re.search(r'[?&]sid=([a-f0-9]{70,})', url)
        sid = m.group(1) if m else None
        if not sid:
            targets = await client.get_targets()
            for t in targets:
                t_url = t.get("url", "")
                if t.get("type") == "page" and "gmx.net" in t_url:
                    m2 = re.search(r'[?&]sid=([a-f0-9]{70,})', t_url)
                    if m2:
                        sid = m2.group(1)
                        break
        if not sid:
            logger.error("Kein SID gefunden")
            return False
        iframe_url = f"https://navigator.gmx.net/navigator/jump/to/mail_settings?sid={sid}"
        await client.navigate(session_id, iframe_url)
        await asyncio.sleep(6)
        ur = await client.evaluate(session_id, "window.location.href")
        url = ur.get("result", {}).get("value", "") or ""
        if "allEmailAddresses" in url:
            return True
        if "settings" in url and "3c.gmx.net" in url:
            await client.evaluate(session_id, """
            (function() {
                var allEls = document.querySelectorAll('a, span, li, div, p');
                for (var i=0; i<allEls.length; i++) {
                    var el = allEls[i];
                    if (el.children.length === 0 && el.textContent.trim() === 'E-Mail-Adressen') {
                        var rect = el.getBoundingClientRect();
                        var cx = rect.x + rect.width/2;
                        var cy = rect.y + rect.height/2;
                        ['mousedown','mouseup','click'].forEach(function(t){
                            el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window, clientX:cx, clientY:cy}));
                        });
                        return {clicked:true};
                    }
                }
                return {clicked:false};
            })()
            """, return_by_value=True)
            await asyncio.sleep(5)
            ur = await client.evaluate(session_id, "window.location.href")
            url = ur.get("result", {}).get("value", "") or ""
        return "allEmailAddresses" in url

    # ── Alias Deletion ──────────────────────────────────────────────────

    async def _find_alias(self, client: CDPClient, session_id: str) -> Optional[Dict[str, Any]]:
        result = await client.evaluate(session_id, """
        (function() {
            var body = document.body.innerText;
            var lines = body.split('\\n');
            for (var i=0; i<lines.length; i++) {
                var line = lines[i].trim();
                var idx = line.indexOf('@gmx.');
                if (idx < 0) continue;
                var parts = line.split(/\\s+/);
                var email = parts[parts.length-1];
                if (!email.includes('@gmx.')) continue;
                if (email === 'opensin@gmx.de') continue;
                var allEls = document.querySelectorAll('span, div, td, p, a');
                for (var j=0; j<allEls.length; j++) {
                    var el = allEls[j];
                    if (el.children.length === 0 && el.textContent.trim().includes(email)) {
                        var rect = el.getBoundingClientRect();
                        if (rect.width > 30 && rect.height > 8) {
                            return {text: email, x: Math.round(rect.x), y: Math.round(rect.y),
                                    w: Math.round(rect.width), h: Math.round(rect.height),
                                    cx: Math.round(rect.x + rect.width/2), cy: Math.round(rect.y + rect.height/2)};
                        }
                    }
                }
            }
            return null;
        })()
        """, return_by_value=True)
        return result.get("result", {}).get("value")

    async def _find_delete_icon(self, client: CDPClient, session_id: str) -> Optional[Dict[str, Any]]:
        result = await client.evaluate(session_id, """
        (function() {
            var allEls = document.querySelectorAll('a, button, span, i, img');
            for (var i=0; i<allEls.length; i++) {
                var el = allEls[i];
                var title = (el.getAttribute('title') || '').toLowerCase();
                var aria = (el.getAttribute('aria-label') || '').toLowerCase();
                if (title.includes('l\u00f6sch') || title.includes('email-adresse') || aria.includes('l\u00f6sch')) {
                    var rect = el.getBoundingClientRect();
                    if (rect.width > 5 && rect.height > 5) {
                        return {x: Math.round(rect.x + rect.width/2), y: Math.round(rect.y + rect.height/2),
                                w: Math.round(rect.width), h: Math.round(rect.height), title: el.getAttribute('title') || ''};
                    }
                }
            }
            return null;
        })()
        """, return_by_value=True)
        return result.get("result", {}).get("value")

    async def delete_alias(self, cdp_port: int = 9222) -> Dict[str, Any]:
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            await client.send_to_session(session_id, "DOM.enable")
            await asyncio.sleep(0.5)
            if not await self._navigate_to_all_email_addresses(client, session_id):
                return {"status": "not_logged_in", "deleted": False, "error": "Navigation fehlgeschlagen"}
            alias_info = await self._find_alias(client, session_id)
            if not alias_info:
                return {"status": "no_alias", "deleted": True, "alias": None}
            alias_text = alias_info['text']
            logger.info(f"Alias gefunden: {alias_text}")
            await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": alias_info['cx'], "y": alias_info['cy']
            })
            await asyncio.sleep(1)
            delete_info = await self._find_delete_icon(client, session_id)
            if not delete_info:
                return {"status": "error", "deleted": False, "alias": alias_text, "error": "Delete-Icon nicht gefunden"}
            await client.click_at(session_id, delete_info['x'], delete_info['y'])
            await asyncio.sleep(3)
            # Confirm dialog: click OK via JS (simplest reliable method)
            await client.evaluate(session_id, """
            (function() {
                var btns = document.querySelectorAll('button, a[role="button"]');
                for (var i=0; i<btns.length; i++) {
                    var t = btns[i].textContent.trim().toLowerCase();
                    if (t === 'ok' || t === 'l\u00f6schen' || t === 'ja') {
                        btns[i].click(); return true;
                    }
                }
                return false;
            })()
            """, return_by_value=True)
            await asyncio.sleep(3)
            verified = await self._verify_alias(client, session_id, alias_text, present=False)
            if verified:
                return {"status": "success", "deleted": True, "alias": alias_text}
            return {"status": "error", "deleted": False, "alias": alias_text, "error": "Verifikation fehlgeschlagen"}
        except Exception as e:
            logger.error(f"Alias-Löschung fehlgeschlagen: {e}")
            return {"status": "error", "deleted": False, "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    # ── Alias Creation ──────────────────────────────────────────────────

    async def _fill_alias_input(self, client: CDPClient, session_id: str, alias_name: str) -> bool:
        result = await client.evaluate(session_id, f"""
        (function() {{
            var inp = document.querySelector('input[name*="localPart"]');
            if (!inp) return {{ok: false, error: 'no input'}};
            var ns = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            ns.call(inp, '{alias_name}');
            inp.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
            return {{ok: inp.value === '{alias_name}', value: inp.value}};
        }})()
        """, return_by_value=True)
        val = result.get("result", {}).get("value", {})
        return val.get("ok", False) if val else False

    async def _find_add_button(self, client: CDPClient, session_id: str) -> Optional[Dict[str, Any]]:
        result = await client.evaluate(session_id, """
        (function() {
            var inputs = document.querySelectorAll('input[name*="localPart"]');
            if (inputs.length === 0) return null;
            var inp = inputs[0];
            var form = inp.closest('form');
            if (!form) return null;
            var btn = form.querySelector('button');
            if (!btn) return null;
            var rect = btn.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return null;
            return {x: Math.round(rect.x + rect.width/2), y: Math.round(rect.y + rect.height/2),
                    w: Math.round(rect.width), h: Math.round(rect.height)};
        })()
        """, return_by_value=True)
        return result.get("result", {}).get("value")

    async def create_alias(self, alias_name: Optional[str] = None, cdp_port: int = 9222) -> Dict[str, Any]:
        if not alias_name:
            alias_name = self.generate_alias_name()
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            await client.send_to_session(session_id, "DOM.enable")
            await asyncio.sleep(0.3)
            if not await self._navigate_to_all_email_addresses(client, session_id):
                return {"status": "not_logged_in", "alias_email": None, "error": "Navigation fehlgeschlagen"}
            for attempt in range(3):
                current_alias = alias_name if attempt == 0 else self.generate_alias_name()
                alias_email = f"{current_alias}@gmx.de"
                logger.info(f"Erstelle Alias (Versuch {attempt+1}/3): {alias_email}")
                if not await self._fill_alias_input(client, session_id, current_alias):
                    return {"status": "error", "alias_email": None, "error": "Input-Fill fehlgeschlagen"}
                await asyncio.sleep(1)
                btn = await self._find_add_button(client, session_id)
                if not btn:
                    return {"status": "error", "alias_email": None, "error": "Hinzufügen-Button nicht gefunden"}
                await client.click_at(session_id, btn['x'], btn['y'])
                await asyncio.sleep(3)
                if await self._verify_alias(client, session_id, alias_email, present=True):
                    return {"status": "success", "alias_email": alias_email}
                await asyncio.sleep(1)
            return {"status": "failed", "alias_email": None, "error": "Alle Versuche fehlgeschlagen"}
        except Exception as e:
            logger.error(f"Alias-Erstellung fehlgeschlagen: {e}")
            return {"status": "error", "alias_email": None, "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    # ── Verification ─────────────────────────────────────────────────────

    async def _verify_alias(self, client: CDPClient, session_id: str, alias_email: str, present: bool = True, max_wait: float = 12.0) -> bool:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            result = await client.evaluate(session_id, f"""
            (function() {{
                return document.body.innerText.indexOf({json.dumps(alias_email)}) >= 0;
            }})()
            """, return_by_value=True)
            found = result.get("result", {}).get("value", False)
            if present and found:
                return True
            if not present and not found:
                return True
            await asyncio.sleep(1)
        return False

    # ── Alias Rotation ────────────────────────────────────────────────────

    async def rotate_alias(self, new_alias_name: Optional[str] = None, cdp_port: int = 9222) -> Dict[str, Any]:
        start_time = time.time()
        steps = []
        deleted_alias = None
        created_alias = None
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            if not await self._navigate_to_all_email_addresses(client, session_id):
                return {"status": "failed", "deleted_alias": None, "created_alias": None,
                        "error": "Navigation fehlgeschlagen", "execution_time": f"{time.time()-start_time:.2f}s"}
            steps.append("navigated")
            await client.send_to_session(session_id, "DOM.enable")
            await asyncio.sleep(0.3)
            alias_info = await self._find_alias(client, session_id)
            if alias_info:
                alias_text = alias_info['text']
                await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
                    "type": "mouseMoved", "x": alias_info['cx'], "y": alias_info['cy']
                })
                await asyncio.sleep(1)
                delete_info = await self._find_delete_icon(client, session_id)
                if delete_info:
                    await client.click_at(session_id, delete_info['x'], delete_info['y'])
                    await asyncio.sleep(3)
                    await client.evaluate(session_id, """
                    (function() {
                        var btns = document.querySelectorAll('button, a[role="button"]');
                        for (var i=0; i<btns.length; i++) {
                            var t = btns[i].textContent.trim().toLowerCase();
                            if (t === 'ok' || t === 'l\u00f6schen' || t === 'ja') { btns[i].click(); return true; }
                        }
                        return false;
                    })()
                    """, return_by_value=True)
                    await asyncio.sleep(3)
                    if await self._verify_alias(client, session_id, alias_text, present=False):
                        deleted_alias = alias_text
                        steps.append("deleted")
            if not deleted_alias:
                steps.append("no_alias_to_delete")
            if not new_alias_name:
                new_alias_name = self.generate_alias_name()
            for attempt in range(3):
                current_alias = new_alias_name if attempt == 0 else self.generate_alias_name()
                alias_email = f"{current_alias}@gmx.de"
                if await self._fill_alias_input(client, session_id, current_alias):
                    await asyncio.sleep(1)
                    btn = await self._find_add_button(client, session_id)
                    if btn:
                        await client.click_at(session_id, btn['x'], btn['y'])
                        await asyncio.sleep(3)
                        if await self._verify_alias(client, session_id, alias_email, present=True):
                            created_alias = alias_email
                            steps.append("created")
                            break
                await asyncio.sleep(1)
            if created_alias:
                return {"status": "success", "deleted_alias": deleted_alias, "created_alias": created_alias,
                        "steps": steps, "execution_time": f"{time.time()-start_time:.2f}s"}
            return {"status": "failed", "deleted_alias": deleted_alias, "created_alias": None,
                    "error": "Erstellung fehlgeschlagen", "steps": steps, "execution_time": f"{time.time()-start_time:.2f}s"}
        except Exception as e:
            logger.error(f"Rotation fehlgeschlagen: {e}")
            return {"status": "failed", "error": str(e), "steps": steps, "execution_time": f"{time.time()-start_time:.2f}s"}
        finally:
            if client:
                await client.disconnect()

    # ── OTP / Confirm URL ───────────────────────────────────────────────────

    async def read_otp(self, sender_filter: str = "fireworks", max_retries: int = 12, retry_delay: int = 5, cdp_port: int = 9222) -> Dict[str, Any]:
        start_time = time.time()
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            url_result = await client.evaluate(session_id, "window.location.href")
            current_url = url_result.get("result", {}).get("value", "")
            sid = None
            if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
                sid = re.search(r'[?&]sid=([^&]+)', current_url)
                sid = sid.group(1) if sid else None
            if not sid:
                await client.navigate(session_id, "https://www.gmx.net/")
                await asyncio.sleep(4)
                body = await client.evaluate(session_id, "document.body.innerText")
                text = body.get("result", {}).get("value", "")
                if "Sie sind eingeloggt" not in text and "Zum Postfach" not in text:
                    return {"status": "error", "otp_url": None, "error": "Nicht eingeloggt"}
                await client.evaluate(session_id, """
                (function(){
                    var els = Array.from(document.querySelectorAll('a, button, [role=link], nav a'));
                    var el = els.find(e => (e.textContent||'').trim() === 'E-Mail');
                    if (el) { el.click(); return true; }
                    return false;
                })()
                """, return_by_value=True)
                await asyncio.sleep(5)
                url_result = await client.evaluate(session_id, "window.location.href")
                current_url = url_result.get("result", {}).get("value", "")
                sid = re.search(r'[?&]sid=([^&]+)', current_url)
                sid = sid.group(1) if sid else None
            if not sid:
                return {"status": "error", "otp_url": None, "error": "Kein SID"}
            mail_url = f"https://bap.navigator.gmx.net/mail?sid={sid}"
            await client.navigate(session_id, mail_url)
            await asyncio.sleep(6)
            iframe_result = await client.evaluate(session_id, """
            (function() {
                var iframe = document.querySelector('#thirdPartyFrame_mail');
                return iframe ? iframe.src : null;
            })()
            """, return_by_value=True)
            iframe_src = iframe_result.get("result", {}).get("value", "")
            if not iframe_src:
                return {"status": "error", "otp_url": None, "error": "Mail iframe nicht gefunden"}
            await client.navigate(session_id, iframe_src)
            await asyncio.sleep(5)
            cookies_res = await client.send_to_session(session_id, "Network.getAllCookies")
            jsessionid = None
            for c in cookies_res.get("cookies", []):
                if c.get("name") == "JSESSIONID":
                    jsessionid = c.get("value", "")
                    break
            if not jsessionid:
                current_url_result = await client.evaluate(session_id, "window.location.href")
                current_page_url = current_url_result.get("result", {}).get("value", "")
                jsessionid_match = re.search(r'jsessionid=([^?&;]+)', current_page_url)
                jsessionid = jsessionid_match.group(1) if jsessionid_match else None
            if not jsessionid:
                return {"status": "error", "otp_url": None, "error": "Kein JSESSIONID"}
            known_ids = set()
            for i in range(max_retries):
                logger.info(f"OTP-Suche: Versuch {i+1}/{max_retries}")
                safe_filter = sender_filter.lower().replace("'", "\\'")
                items_js = f"""
                (function() {{
                    function findItems(root) {{
                        let items = [];
                        const all = root.querySelectorAll('*');
                        for (const el of all) {{
                            if (el.tagName.toLowerCase() === 'list-mail-item') {{
                                const text = (el.textContent || '').toLowerCase();
                                if (text.includes('{safe_filter}')) {{
                                    const idAttr = el.getAttribute('id');
                                    const mailId = idAttr ? idAttr.replace(/^id/, '') : null;
                                    if (mailId) {{
                                        items.push({{mailId: mailId, text: el.textContent.trim().slice(0, 120)}});
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
                }})()
                """
                items_result = await client.evaluate(session_id, items_js, return_by_value=True)
                items = items_result.get("result", {}).get("value", [])
                new_items = [it for it in items if it.get("mailId") not in known_ids]
                if new_items:
                    cookies_res = await client.send_to_session(session_id, "Network.getAllCookies")
                    cookies = cookies_res.get("cookies", [])
                    essential = {"JSESSIONID", "SESSION", "lps", "navigator", "iac_token"}
                    cookie_dict = {c.get("name"): c.get("value", "") for c in cookies if c.get("name") in essential}
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Referer": "https://3c-bap.gmx.net/mail/client/start",
                    }
                    async with httpx.AsyncClient(cookies=cookie_dict, follow_redirects=True, timeout=20) as http:
                        for item in new_items[:5]:
                            mail_id = item.get("mailId")
                            if not mail_id:
                                continue
                            for suffix in ["true", "false"]:
                                email_url = f"https://3c-bap.gmx.net/mail/client/mailbody/tmai{mail_id}/{suffix};jsessionid={jsessionid}"
                                try:
                                    resp = await http.get(email_url, headers=headers)
                                    if resp.status_code == 200 and len(resp.text) > 1000:
                                        urls = re.findall(r'https://app\.fireworks\.ai/[^\s"\'<>]+', resp.text)
                                        candidates = [u for u in urls if any(k in u.lower() for k in ["confirm", "verify", "token", "auth", "activate", "signup"])]
                                        if candidates:
                                            confirm_url = html_module.unescape(candidates[0])
                                            return {"status": "success", "otp_url": confirm_url, "mail_id": mail_id,
                                                    "execution_time": f"{time.time()-start_time:.2f}s"}
                                except Exception:
                                    pass
                for it in items:
                    mid = it.get("mailId")
                    if mid:
                        known_ids.add(mid)
                if i < max_retries - 1:
                    await asyncio.sleep(retry_delay)
            return {"status": "not_found", "otp_url": None, "error": "Nicht gefunden"}
        except Exception as e:
            logger.error(f"OTP-Suche fehlgeschlagen: {e}")
            return {"status": "error", "otp_url": None, "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    # ── Public Helpers ────────────────────────────────────────────────────

    async def check_session(self, cdp_port: int = 9222) -> Dict[str, Any]:
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            result = await self._ensure_mail_session(client, session_id)
            return {"status": "logged_in" if result["success"] else "not_logged_in",
                    "current_url": result.get("current_url", ""), "sid": result.get("sid")}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    async def open_email_addresses(self, cdp_port: int = 9222) -> Dict[str, Any]:
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            ok = await self._navigate_to_all_email_addresses(client, session_id)
            url = (await client.evaluate(session_id, "window.location.href")).get("result", {}).get("value", "")
            return {"status": "success" if ok else "error", "current_url": url}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            if client:
                await client.disconnect()


_gmx_service: Optional[GmxService] = None


def get_gmx_service() -> GmxService:
    global _gmx_service
    if _gmx_service is None:
        _gmx_service = GmxService()
    return _gmx_service
