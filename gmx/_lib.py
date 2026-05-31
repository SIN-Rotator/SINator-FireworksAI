"""
gmx/_lib.py — Shared helpers for the GMX tool library.

Every tool in this package follows the same contract:
  - exposes ONE async function that returns a JSON-serialisable dict with a
    "status" field (e.g. {"status": "success", ...})
  - is runnable from the CLI:  python3 -m gmx.<tool> [--flags]
  - connects to an ALREADY RUNNING Chrome via CDP (default port 9222) that has
    an active GMX session. The tools never launch their own browser and never
    log in implicitly (use gmx.login for that).

The actual browser logic is reused from the proven agent_toolbox GmxService so
the tools behave EXACTLY like the production rotator — they are just clean,
single-purpose, composable entry points around it.
"""
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Any, Callable, Awaitable, Dict, Iterable

# ── Make the repo root importable no matter where the tool is invoked from ──
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_CDP_PORT = 9222

# Statuses that should map to a 0 (success) process exit code.
_OK_STATUSES = {"success", "logged_in", "found", "no_alias", "ok", "verified"}


def get_service():
    """Return a fresh GmxService instance (proven production logic)."""
    from agent_toolbox.core.gmx_service import GmxService
    return GmxService()


def get_credentials(email: str | None = None, password: str | None = None):
    """Resolve GMX credentials, falling back to the project config."""
    if email and password:
        return email, password
    from agent_toolbox.core.config_manager import get_config
    cfg = get_config()
    return (email or cfg.gmx_email), (password or cfg.gmx_password)


async def connect_gmx_page(port: int = DEFAULT_CDP_PORT):
    """Connect to running Chrome (CDP) and return a Playwright Page on a GMX tab.

    Reuses GmxService._pw_connect so page-selection logic stays identical to the
    rotator (prefers allEmailAddresses tab, then any valid gmx.net tab).
    """
    svc = get_service()
    return svc, await svc._pw_connect(port)


def run(action: Callable[[argparse.Namespace], Awaitable[Dict[str, Any]]],
        *,
        description: str,
        add_args: Callable[[argparse.ArgumentParser], None] | None = None,
        ok_statuses: Iterable[str] = ()) -> None:
    """Standard CLI wrapper: parse args, run the coroutine, print JSON, exit.

    Exit code 0 when result["status"] is a success status, else 1. This makes
    the tools trivially chainable in shell scripts (&&) and other agents.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--port", type=int, default=DEFAULT_CDP_PORT,
                        help=f"CDP port of the running Chrome (default: {DEFAULT_CDP_PORT})")
    parser.add_argument("--json", action="store_true",
                        help="Print only the raw JSON result (no extra logging noise)")
    if add_args:
        add_args(parser)
    args = parser.parse_args()

    result = asyncio.run(action(args))
    print(json.dumps(result, indent=2, ensure_ascii=False))

    ok = set(_OK_STATUSES) | set(ok_statuses)
    sys.exit(0 if (result or {}).get("status") in ok else 1)
