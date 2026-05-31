#!/usr/bin/env python3
"""
fireworks.signup — Create a new Fireworks AI account (signup + email verify).

Fills the signup form, polls GMX for the verification email and opens the
verify URL to confirm the account.

CLI:     python3 -m fireworks.signup --email new@gmx.de [--password ..] [--port 9222]
Compose: from fireworks import signup; res = await signup(email="new@gmx.de")

Returns: {"status": "success" | "partial" | "error",
          "verify_url": "...", "steps_completed": [...], "error": "..."}
"""
from typing import Any, Dict, Optional

from fireworks._lib import get_password, run, DEFAULT_CDP_PORT


async def signup(email: str, password: Optional[str] = None,
                 port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Sign up a new Fireworks account for the given (alias) email."""
    from agent_toolbox.core.fireworks_service import signup_fireworks
    return await signup_fireworks(email=email, password=get_password(password), cdp_port=port)


def _add_args(p):
    p.add_argument("--email", required=True, help="Email / GMX alias to register")
    p.add_argument("--password", default=None, help="Account password (default: project config)")


async def _action(args) -> Dict[str, Any]:
    return await signup(email=args.email, password=args.password, port=args.port)


if __name__ == "__main__":
    run(_action, description="Sign up a new Fireworks AI account", add_args=_add_args)
