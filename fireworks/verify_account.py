#!/usr/bin/env python3
"""
fireworks.verify_account — Open a Fireworks verify/confirm URL to activate it.

Useful for composing with gmx.read_otp / gmx.find_email which return the URL.

CLI:     python3 -m fireworks.verify_account --url "https://app.fireworks.ai/..." [--port 9222]
Compose: from fireworks import verify_account; res = await verify_account(url)

Returns: {"status": "verified" | "error", "verify_url": "...", "error": "..."}
"""
from typing import Any, Dict

from fireworks._lib import run, DEFAULT_CDP_PORT


async def verify_account(url: str, port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Open the given verify/confirm URL in the running Chrome to activate it."""
    from agent_toolbox.core.fireworks_service import verify_account as _verify
    try:
        ok = await _verify(verify_url=url, cdp_port=port)
        return {"status": "verified" if ok else "error", "verify_url": url}
    except Exception as e:
        return {"status": "error", "verify_url": url, "error": str(e)}


def _add_args(p):
    p.add_argument("--url", required=True, help="Fireworks verify/confirm URL to open")


async def _action(args) -> Dict[str, Any]:
    return await verify_account(url=args.url, port=args.port)


if __name__ == "__main__":
    run(_action, description="Open a Fireworks verify URL", add_args=_add_args)
