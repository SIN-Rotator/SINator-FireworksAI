"""
SINATOR AGENT-TOOLBOX - Fireworks Service (Vereinfacht v2026-05-28)

Kernfunktionen:
  - Fireworks AI Signup (Email, Password, Confirm)
  - Fireworks Login + Setup
  - API Key Erstellung

Nur raw CDP (websockets) + JS evaluate. Kein Playwright.
"""
import time
import logging
import re
import asyncio
import json
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

logger = logging.getLogger(__name__)

FIREWORKS_SIGNUP_URL = "https://app.fireworks.ai/signup"
FIREWORKS_API_KEYS_URL = "https://" + "app.fireworks.ai" + "/api-keys"


class FireworksService:
    async def _connect(self, cdp_port: int) -> Tuple[CDPClient, str]:
        ws_url = await get_browser_ws_endpoint(cdp_port)
        client = CDPClient(ws_url)
        await client.connect()
        target = await get_page_target(client)
        if not target:
            await client.disconnect()
            raise RuntimeError("Kein Page-Target gefunden")
        session_id = await client.attach_to_target(target["targetId"])
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        return client, session_id

    async def _fill_input(self, client: CDPClient, session_id: str, selectors: list, value: str) -> bool:
        escaped = value.replace("'", "\\'")
        js = f"""
        (function() {{
            const inputs = document.querySelectorAll('{selectors[0]}');
            const input = Array.from(inputs).find(i => i.offsetParent !== null);
            if (!input) return {{error: 'not found'}};
            const ns = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            ns.call(input, '{escaped}');
            input.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
            return {{success: true}};
        }})()
        """
        result = await client.evaluate(session_id, js, return_by_value=True)
        val = result.get("result", {}).get("value", {})
        return val.get("success", False)

    async def _click_text(self, client: CDPClient, session_id: str, texts: list) -> bool:
        js = f"""
        (function() {{
            const btns = document.querySelectorAll('button, a, input[type="submit"]');
            for (const b of btns) {{
                const t = (b.textContent || '').trim().toLowerCase();
                const matches = {json.dumps(texts)};
                if (matches.some(m => t.includes(m.toLowerCase()))) {{
                    const r = b.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {{
                        b.scrollIntoView(); b.click();
                        return {{found: true, x: r.x + r.width/2, y: r.y + r.height/2, text: t}};
                    }}
                }}
            }}
            return null;
        }})()
        """
        result = await client.evaluate(session_id, js, return_by_value=True)
        val = result.get("result", {}).get("value")
        if val and val.get("found"):
            await client.click_at(session_id, val["x"], val["y"])
            return True
        return False

    async def _dismiss_cookie(self, client: CDPClient, session_id: str) -> bool:
        js = """
        (function() {
            const selectors = ['button.cky-btn-accept', '[class*="cky-btn-accept"]', '.cky-btn-reject'];
            for (const sel of selectors) {
                const btns = document.querySelectorAll(sel);
                for (const btn of btns) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0) {
                        btn.click(); return {found: true, text: btn.textContent.trim()};
                    }
                }
            }
            return {found: false};
        })()
        """
        result = await client.evaluate(session_id, js, return_by_value=True)
        val = result.get("result", {}).get("value", {})
        if val.get("found"):
            await asyncio.sleep(2)
            return True
        return False

    async def signup(self, email: str, password: str, cdp_port: int = 9222) -> Dict[str, Any]:
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            await client.navigate(session_id, FIREWORKS_SIGNUP_URL)
            await asyncio.sleep(4)
            await self._dismiss_cookie(client, session_id)
            # Fill email
            if not await self._fill_input(client, session_id, ['input[type="email"]', 'input[name="email"]'], email):
                return {"status": "error", "error": "Email-Input nicht gefunden"}
            await self._click_text(client, session_id, ["next", "weiter"])
            await asyncio.sleep(3)
            # Fill password
            if not await self._fill_input(client, session_id, ['input[type="password"]'], password):
                return {"status": "error", "error": "Password-Input nicht gefunden"}
            # Confirm password
            inputs = await client.evaluate(session_id, "document.querySelectorAll('input[type=\"password\"]')")
            if len(inputs.get("result", {}).get("value", [])) > 1:
                await self._fill_input(client, session_id, ['input[type="password"]'], password)
            await self._click_text(client, session_id, ["create account", "create", "registrieren"])
            await asyncio.sleep(5)
            url = (await client.evaluate(session_id, "window.location.href")).get("result", {}).get("value", "")
            return {"status": "success", "current_url": url}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            if client:
                await client.disconnect()

    async def create_api_key(self, key_name: str = "sinator-key", cdp_port: int = 9222) -> Dict[str, Any]:
        client = None
        try:
            client, session_id = await self._connect(cdp_port)
            await client.navigate(session_id, FIREWORKS_API_KEYS_URL)
            await asyncio.sleep(4)
            await self._dismiss_cookie(client, session_id)
            await self._click_text(client, session_id, ["create api key", "create", "new key"])
            await asyncio.sleep(2)
            if not await self._fill_input(client, session_id, ['input[type="text"]', 'input[name="name"]'], key_name):
                return {"status": "error", "error": "Key-Name Input nicht gefunden"}
            await self._click_text(client, session_id, ["generate", "erstellen", "create"])
            await asyncio.sleep(3)
            # Extract key from page text
            result = await client.evaluate(session_id, "document.body.innerText")
            text = result.get("result", {}).get("value", "")
            key_match = re.search(r'fw_[a-zA-Z0-9_]{20,}', text)
            if key_match:
                return {"status": "success", "api_key": key_match.group(0)}
            return {"status": "error", "error": "API-Key nicht im Text gefunden"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            if client:
                await client.disconnect()


_fireworks_service: Optional[FireworksService] = None


def get_fireworks_service() -> FireworksService:
    global _fireworks_service
    if _fireworks_service is None:
        _fireworks_service = FireworksService()
    return _fireworks_service
