#!/usr/bin/env python3
"""
gmx.delete_alias — Delete the existing GMX alias (if any).

Composes the proven GmxService primitives: navigate to the email-addresses
page, find the current alias row, delete it and verify it is gone.

CLI:     python3 -m gmx.delete_alias [--port 9222]
Compose: from gmx import delete_alias; res = await delete_alias()

Returns: {"status": "success" | "no_alias" | "not_logged_in" | "error",
          "deleted": bool, "alias": "old@gmx.de", "error": "..."}
"""
import asyncio
from typing import Any, Dict

from gmx._lib import connect_gmx_page, run, DEFAULT_CDP_PORT


async def delete_alias(port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Delete the current GMX alias. Returns no_alias when none exists."""
    try:
        svc, page = await connect_gmx_page(port)
        if not await svc._navigate_to_all_email_addresses(page):
            return {"status": "not_logged_in", "deleted": False, "error": "Navigation failed"}

        alias_email = await svc._find_alias_row(page)
        if not alias_email:
            return {"status": "no_alias", "deleted": False, "alias": None}

        deleted = await svc._delete_alias(page, alias_email)
        if deleted:
            await asyncio.sleep(2)
            gone = await svc._verify_alias(page, alias_email, present=False)
            return {"status": "success", "deleted": True, "alias": alias_email, "verified_gone": gone}
        return {"status": "error", "deleted": False, "alias": alias_email, "error": "Delete failed"}
    except Exception as e:
        return {"status": "error", "deleted": False, "error": str(e)}


async def _action(args) -> Dict[str, Any]:
    return await delete_alias(port=args.port)


if __name__ == "__main__":
    run(_action, description="Delete the existing GMX alias")
