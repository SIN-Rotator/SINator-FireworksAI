#!/usr/bin/env python3
"""
fireworks.create_apikey — Generate a Fireworks AI API key (with auto-retry).

Requires an already logged-in Fireworks session in the running Chrome.

CLI:     python3 -m fireworks.create_apikey [--name sinator-key] [--port 9222]
Compose: from fireworks import create_apikey; res = await create_apikey()

Returns: {"status": "success" | "error", "api_key": "fw_...", "error": "..."}
"""
from typing import Any, Dict

from fireworks._lib import run, DEFAULT_CDP_PORT


async def create_apikey(name: str = "sinator-key", port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Create a new Fireworks API key and return its value."""
    from agent_toolbox.core.fireworks_service import create_api_key
    return await create_api_key(key_name=name, cdp_port=port)


def _add_args(p):
    p.add_argument("--name", default="sinator-key", help="API key name (default: sinator-key)")


async def _action(args) -> Dict[str, Any]:
    return await create_apikey(name=args.name, port=args.port)


if __name__ == "__main__":
    run(_action, description="Create a Fireworks AI API key", add_args=_add_args)
