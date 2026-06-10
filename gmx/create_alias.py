#!/usr/bin/env python3
"""
gmx.create_alias — Create a new GMX alias address.

CLI:     python3 -m gmx.create_alias [--name swift-hawk-123] [--port 9222]
Compose: from gmx import create_alias; res = await create_alias()

Returns: {"status": "success" | "failed" | "not_logged_in" | "error",
          "alias_email": "swift-hawk-123@gmx.de", "error": "..."}

Docs: create_alias.doc.md
"""

from typing import Any, Dict, Optional

from gmx._lib import get_credentials, get_service, run, DEFAULT_CDP_PORT


async def create_alias(
    name: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    port: int = DEFAULT_CDP_PORT,
) -> Dict[str, Any]:
    """Create a GMX alias. If name is None a random name is generated."""
    resolved_email, resolved_password = get_credentials(email, password)
    return await get_service().create_alias(
        alias_name=name, cdp_port=port, email=resolved_email, password=resolved_password
    )


def _add_args(p):
    p.add_argument(
        "--name", default=None, help="Alias name without @gmx.de (default: random)"
    )
    p.add_argument("--email", default=None, help="GMX email (default: project config)")
    p.add_argument(
        "--password", default=None, help="GMX password (default: project config)"
    )


async def _action(args) -> Dict[str, Any]:
    return await create_alias(
        name=args.name, email=args.email, password=args.password, port=args.port
    )


if __name__ == "__main__":
    run(_action, description="Create a GMX alias", add_args=_add_args)
