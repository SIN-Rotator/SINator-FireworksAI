"""
fireworks/_lib.py — Shared helpers for the Fireworks AI tool library.

Every tool in this package follows the same contract:
  - exposes ONE async function returning a JSON-serialisable dict with a
    "status" field
  - is runnable from the CLI:  python3 -m fireworks.<tool> [--flags]
  - attaches to an ALREADY RUNNING Chrome via CDP (default port 9222)

The browser logic is reused from the proven agent_toolbox.core.fireworks_service
so the tools behave EXACTLY like the production rotator — they are just clean,
single-purpose, composable entry points around it.

Docs: _lib.doc.md
"""
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

# ── Make the repo root importable no matter where the tool is invoked from ──
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_CDP_PORT = 9222

_OK_STATUSES = {"success", "ok", "verified"}


def get_password(password: Optional[str] = None) -> str:
    """Resolve the Fireworks password, falling back to the project config."""
    if password:
        return password
    from agent_toolbox.core.config_manager import get_config
    return get_config().fireworks_password


def run(action: Callable[[argparse.Namespace], Awaitable[Dict[str, Any]]],
        *,
        description: str,
        add_args: Callable[[argparse.ArgumentParser], None] | None = None,
        ok_statuses: Iterable[str] = ()) -> None:
    """Standard CLI wrapper: parse args, run the coroutine, print JSON, exit 0/1."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--port", type=int, default=DEFAULT_CDP_PORT,
                        help=f"CDP port of the running Chrome (default: {DEFAULT_CDP_PORT})")
    if add_args:
        add_args(parser)
    args = parser.parse_args()

    result = asyncio.run(action(args))
    print(json.dumps(result, indent=2, ensure_ascii=False))

    ok = set(_OK_STATUSES) | set(ok_statuses)
    sys.exit(0 if (result or {}).get("status") in ok else 1)
