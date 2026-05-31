#!/usr/bin/env python3
"""
gmx.check_session — Is a GMX session currently active?

CLI:     python3 -m gmx.check_session [--port 9222]
Compose: from gmx import check_session; res = await check_session()

Returns: {"status": "logged_in" | "not_logged_in" | "error",
          "current_url": "...", "error": "..."}
"""
from typing import Any, Dict, Optional

from gmx._lib import get_service, run, DEFAULT_CDP_PORT


async def check_session(port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Check whether the running Chrome has a logged-in GMX session."""
    return await get_service().check_session(cdp_port=port)


async def _action(args) -> Dict[str, Any]:
    return await check_session(port=args.port)


if __name__ == "__main__":
    run(_action, description="Check if a GMX session is active")
