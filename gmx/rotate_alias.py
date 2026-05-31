#!/usr/bin/env python3
"""
gmx.rotate_alias — Atomically delete the old alias and create a new one.

CLI:     python3 -m gmx.rotate_alias [--name swift-hawk-123] [--port 9222]
Compose: from gmx import rotate_alias; res = await rotate_alias()

Returns: {"status": "success" | "failed",
          "deleted_alias": "old@gmx.de", "created_alias": "new@gmx.de",
          "steps": [...], "error": "..."}
"""

from typing import Any, Dict, Optional

from gmx._lib import get_credentials, get_service, run, DEFAULT_CDP_PORT


async def rotate_alias(
    name: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    port: int = DEFAULT_CDP_PORT,
) -> Dict[str, Any]:
    """Delete the current alias and create a fresh one in a single pass."""
    resolved_email, resolved_password = get_credentials(email, password)
    return await get_service().rotate_alias(
        new_alias_name=name,
        cdp_port=port,
        email=resolved_email,
        password=resolved_password,
    )


def _add_args(p):
    p.add_argument(
        "--name", default=None, help="New alias name without @gmx.de (default: random)"
    )
    p.add_argument("--email", default=None, help="GMX email (default: project config)")
    p.add_argument(
        "--password", default=None, help="GMX password (default: project config)"
    )


async def _action(args) -> Dict[str, Any]:
    return await rotate_alias(
        name=args.name, email=args.email, password=args.password, port=args.port
    )


if __name__ == "__main__":
    run(
        _action,
        description="Rotate (delete + create) the GMX alias",
        add_args=_add_args,
    )
