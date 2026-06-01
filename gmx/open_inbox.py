#!/usr/bin/env python3
"""
gmx.open_inbox — Open the GMX inbox (navigator.gmx.net/mail) and verify session.

CLI:     python3 -m gmx.open_inbox [--port 9222]
Compose: from gmx import open_inbox; res = await open_inbox()

Returns: {"status": "success" | "not_logged_in" | "error",
          "current_url": "...", "error": "..."}

Docs: open_inbox.doc.md
"""

import asyncio
from typing import Any, Dict

from gmx._lib import connect_gmx_page, run, DEFAULT_CDP_PORT


async def open_inbox(port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Navigate the GMX tab to the inbox and confirm we are logged in.

    Strategy: direct goto(navigator.gmx.net/mail) fails without SID — GMX
    redirects back to www.gmx.net. Instead we go to www.gmx.net first,
    detect the login state, and click "Zum Postfach" which creates a valid
    SID session. Only if already on navigator with SID do we stay.
    """
    try:
        _svc, page = await connect_gmx_page(port)
        current_url = page.url or ""

        # Already on inbox with SID? Done.
        if "navigator.gmx.net/mail" in current_url and "sid=" in current_url:
            return {"status": "success", "current_url": current_url}

        # Navigate to www.gmx.net homepage (establishes cookie context)
        await page.goto(
            "https://www.gmx.net/", wait_until="domcontentloaded", timeout=30000
        )
        await asyncio.sleep(4)
        current_url = page.url

        if (
            "status=inactive" in current_url
            or "session-expired" in current_url
            or "logoutlounge" in current_url
        ):
            return {
                "status": "not_logged_in",
                "current_url": current_url,
                "error": "Session inactive or expired",
            }

        body = await page.evaluate(
            "() => document.body ? document.body.innerText.substring(0, 800) : ''"
        )

        if "Sie sind eingeloggt" in body or "Zum Postfach" in body:
            try:
                postfach = page.locator("text=Zum Postfach").first
                if await postfach.is_visible(timeout=5000):
                    await postfach.click()
                    await asyncio.sleep(6)
                    current_url = page.url
                    if (
                        "navigator.gmx.net/mail" in current_url
                        and "sid=" in current_url
                    ):
                        return {"status": "success", "current_url": current_url}
                    if "navigator.gmx.net" in current_url:
                        return {"status": "success", "current_url": current_url}
                    return {
                        "status": "not_logged_in",
                        "current_url": current_url,
                        "error": "Postfach click did not navigate to inbox",
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "current_url": current_url,
                    "error": f"Zum Postfach click failed: {e}",
                }

        if "anmelden" in body.lower()[:300] and "E-Mail" not in body:
            return {"status": "not_logged_in", "current_url": current_url}

        return {
            "status": "not_logged_in",
            "current_url": current_url,
            "error": "No active session detected",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _action(args) -> Dict[str, Any]:
    return await open_inbox(port=args.port)


if __name__ == "__main__":
    run(_action, description="Open the GMX inbox")
