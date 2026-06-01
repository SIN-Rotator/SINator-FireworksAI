#!/usr/bin/env python3
"""
gmx.delete_alias — Delete the existing GMX alias (if any).

Composes the proven GmxService primitives: navigate to the email-addresses
page, find the current alias row, delete it and verify it is gone.

CLI:     python3 -m gmx.delete_alias [--port 9222]
Compose: from gmx import delete_alias; res = await delete_alias()

Returns: {"status": "success" | "no_alias" | "not_logged_in" | "error",
          "deleted": bool, "alias": "old@gmx.de", "error": "..."}

Docs: delete_alias.doc.md
"""

import asyncio
from typing import Any, Dict, Optional

from gmx._lib import connect_gmx_page, get_credentials, run, DEFAULT_CDP_PORT


async def delete_alias(
    email: Optional[str] = None,
    password: Optional[str] = None,
    port: int = DEFAULT_CDP_PORT,
) -> Dict[str, Any]:
    """Delete the current GMX alias. Returns no_alias when none exists."""
    try:
        resolved_email, resolved_password = get_credentials(email, password)
        svc, page = await connect_gmx_page(port)
        if not await svc._navigate_to_all_email_addresses(
            page, email=resolved_email, password=resolved_password
        ):
            return {
                "status": "not_logged_in",
                "deleted": False,
                "error": "Navigation failed",
            }

        alias_email = await svc._find_alias_row(page)
        if not alias_email:
            return {"status": "no_alias", "deleted": False, "alias": None}

        deleted = await svc._delete_alias(page, alias_email)
        if deleted:
            await asyncio.sleep(2)
            gone = await svc._verify_alias(page, alias_email, present=False)
            return {
                "status": "success",
                "deleted": True,
                "alias": alias_email,
                "verified_gone": gone,
            }
        return {
            "status": "error",
            "deleted": False,
            "alias": alias_email,
            "error": "Delete failed",
        }
    except Exception as e:
        return {"status": "error", "deleted": False, "error": str(e)}


async def _action(args) -> Dict[str, Any]:
    return await delete_alias(email=args.email, password=args.password, port=args.port)


def _add_args(p):
    p.add_argument("--email", default=None, help="GMX email (default: project config)")
    p.add_argument(
        "--password", default=None, help="GMX password (default: project config)"
    )


if __name__ == "__main__":
    run(_action, description="Delete the existing GMX alias", add_args=_add_args)
