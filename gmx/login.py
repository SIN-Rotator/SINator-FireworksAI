#!/usr/bin/env python3
"""
gmx.login — Log in to GMX (two-step: email -> Weiter -> password -> Login).

Connects to the running Chrome (CDP), drives the GMX login form and verifies a
session was established. Credentials fall back to the project config when not
passed explicitly.

CLI:     python3 -m gmx.login [--email ..] [--password ..] [--port 9222]
Compose: from gmx import login; res = await login()

Returns: {"status": "logged_in" | "not_logged_in" | "error",
          "current_url": "...", "error": "..."}

Docs: login.doc.md
"""
import asyncio
from typing import Any, Dict, Optional

from gmx._lib import connect_gmx_page, get_credentials, get_service, run, DEFAULT_CDP_PORT


async def login(email: Optional[str] = None, password: Optional[str] = None,
                port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Log in to GMX on the running Chrome. Idempotent: skips if already in."""
    email, password = get_credentials(email, password)
    svc, page = await connect_gmx_page(port)

    # Already logged in? Don't re-run the flow.
    pre = await svc.check_session(cdp_port=port, page=page)
    if pre.get("status") == "logged_in":
        return {"status": "logged_in", "current_url": pre.get("current_url"), "note": "already_logged_in"}

    ok = await svc._login(page, email=email, password=password)
    await asyncio.sleep(3)
    post = await svc.check_session(cdp_port=port, page=page)
    status = "logged_in" if (ok and post.get("status") == "logged_in") else "not_logged_in"
    return {"status": status, "current_url": post.get("current_url"), "login_returned": ok}


def _add_args(p):
    p.add_argument("--email", default=None, help="GMX email (default: project config)")
    p.add_argument("--password", default=None, help="GMX password (default: project config)")


async def _action(args) -> Dict[str, Any]:
    return await login(email=args.email, password=args.password, port=args.port)


if __name__ == "__main__":
    run(_action, description="Log in to GMX", add_args=_add_args)
