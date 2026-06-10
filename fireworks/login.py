#!/usr/bin/env python3
"""
fireworks.login — Log in to Fireworks AI (handles onboarding if present).

CLI:     python3 -m fireworks.login --email acc@gmx.de [--password ..] [--port 9222]
Compose: from fireworks import login; res = await login(email="acc@gmx.de")

Returns: {"status": "success" | "error", "steps_completed": [...], "error": "..."}

Docs: login.doc.md
"""
from typing import Any, Dict, Optional

from fireworks._lib import get_password, run, DEFAULT_CDP_PORT


async def login(email: str, password: Optional[str] = None,
                port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Log in to Fireworks; completes onboarding via CUA/Playwright if needed."""
    from agent_toolbox.core.fireworks_service import login_fireworks
    return await login_fireworks(email=email, password=get_password(password), cdp_port=port)


def _add_args(p):
    p.add_argument("--email", required=True, help="Account email to log in with")
    p.add_argument("--password", default=None, help="Account password (default: project config)")


async def _action(args) -> Dict[str, Any]:
    return await login(email=args.email, password=args.password, port=args.port)


if __name__ == "__main__":
    run(_action, description="Log in to Fireworks AI", add_args=_add_args)
