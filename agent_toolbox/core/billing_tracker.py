"""
Billing-Tracker für Fireworks API-Keys.

Prüft via CDP/Playwright das verbleibende Guthaben auf
https://app.fireworks.ai/account/billing

Wird verwendet von:
  - /pool/report  → Guthaben vor Markierung checken
  - /pool/health  → Periodische Prüfung aller aktiven Keys
"""
import re as _re
import json as _json
import time as _time
import logging

_logger = logging.getLogger(__name__)


async def check_key_credits_via_cdp(api_key: str) -> dict:
    """
    Prüft das Guthaben eines Keys via CDP-Browser.

    1. Navigiert zu https://app.fireworks.ai/account/billing
    2. Wartet auf client-seitiges Rendern
    3. Extrahiert $XX.XX Guthaben via DOM-Query

    Returns:
        {"credits_remaining": float, "currency": "$", "error": None}
        oder {"credits_remaining": None, "error": "..."}
    """
    try:
        from cdp_client import CDPClient, get_browser_ws_endpoint

        ws = await get_browser_ws_endpoint(9222)
        client = CDPClient(ws)
        await client.connect()

        targets = await client.get_targets()
        if not targets:
            await client.disconnect()
            return {"credits_remaining": None, "error": "No browser targets"}

        sid = await client.attach_to_target(targets[0]["targetId"])

        await client.navigate(sid, "https://app.fireworks.ai/account/billing")
        await _time.sleep(5)

        body = await client.evaluate(sid, "document.body.innerText", return_by_value=True)
        body_text = ""
        if isinstance(body, dict):
            for sub in ("result", "value"):
                v = body.get(sub, {})
                if isinstance(v, dict):
                    body_text = v.get("value", "") or _json.dumps(v)
                    break

        if not body_text:
            await client.disconnect()
            return {"credits_remaining": None, "error": "Empty page body"}

        patterns = [
            r'\$(\d+\.?\d*)\s*(?:credits?|remaining|balance|guthaben)',
            r'(?:credits?|remaining|balance|guthaben)\s*\$?(\d+\.?\d*)',
            r'\$(\d+\.?\d*)\s*/\s*\$6',
        ]
        for pat in patterns:
            m = _re.search(pat, body_text, _re.IGNORECASE)
            if m:
                credits = float(m.group(1))
                _logger.info(f"Credits via CDP: ${credits:.2f}")
                await client.disconnect()
                return {"credits_remaining": credits, "currency": "$", "error": None}

        await client.disconnect()
        return {"credits_remaining": None, "error": "Credits not found in page. Maybe not logged in?"}

    except Exception as e:
        _logger.error(f"CDP billing check failed: {e}")
        return {"credits_remaining": None, "error": str(e)}


async def check_key_credits_via_playwright(api_key: str) -> dict:
    """
    Playwright-basierte Guthaben-Prüfung.
    Nutzt chromium.launch() (V15.4).

    Returns:
        {"credits_remaining": float, ...} oder {"credits_remaining": None, "error": "..."}
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto("https://app.fireworks.ai/account/billing",
                           wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            body_text = await page.evaluate("document.body.innerText")

            patterns = [
                r'\$(\d+\.?\d*)\s*(?:credits?|remaining|balance|guthaben)',
                r'(?:credits?|remaining|balance|guthaben)\s*\$?(\d+\.?\d*)',
                r'\$(\d+\.?\d*)\s*/\s*\$6',
            ]
            for pat in patterns:
                m = _re.search(pat, body_text, _re.IGNORECASE)
                if m:
                    credits = float(m.group(1))
                    _logger.info(f"Credits via Playwright: ${credits:.2f}")
                    await page.close()
                    return {"credits_remaining": credits, "currency": "$", "error": None}

            await page.close()
            return {"credits_remaining": None, "error": "Credits not found in page"}

    except Exception as e:
        _logger.error(f"Playwright billing check failed: {e}")
        return {"credits_remaining": None, "error": str(e)}
