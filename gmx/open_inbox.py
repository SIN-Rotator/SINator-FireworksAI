#!/usr/bin/env python3
"""
gmx.open_inbox — Open the GMX inbox (navigator.gmx.net/mail) and verify session.

CLI:     python3 -m gmx.open_inbox [--port 9222]
Compose: from gmx import open_inbox; res = await open_inbox()

Returns: {"status": "success" | "not_logged_in" | "error",
          "current_url": "...", "error": "..."}
"""
import asyncio
from typing import Any, Dict

from gmx._lib import connect_gmx_page, run, DEFAULT_CDP_PORT


async def open_inbox(port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Navigate the GMX tab to the inbox and confirm we are logged in."""
    try:
        _svc, page = await connect_gmx_page(port)
        await page.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        body = await page.evaluate("() => document.body ? document.body.innerText : ''")
        if "Nicht eingeloggt" in body or ("anmelden" in body.lower()[:300] and "E-Mail" not in body):
            return {"status": "not_logged_in", "current_url": page.url}
        return {"status": "success", "current_url": page.url}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _action(args) -> Dict[str, Any]:
    return await open_inbox(port=args.port)


if __name__ == "__main__":
    run(_action, description="Open the GMX inbox")
