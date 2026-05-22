"""
Shared pytest fixtures for SINator integration tests.

Requires:
    - Chrome running on port 9222 with --profile-directory="Profile 901"
    - cua-driver daemon running
    - `pip install pytest pytest-asyncio`
"""
import sys
from pathlib import Path

_project_root = str(Path(__file__).parent.parent)
_core_dir = str(Path(__file__).parent.parent / "agent_toolbox" / "core")
sys.path.insert(0, _project_root)
sys.path.insert(0, _core_dir)

import pytest
import pytest_asyncio
import subprocess
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

pytest_plugins = ("pytest_asyncio",)


def pytest_configure():
    logging.basicConfig(level=logging.INFO, format="%(message)s")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _cua_available() -> bool:
    """Check if cua-driver is running."""
    try:
        r = subprocess.run(["cua-driver", "status"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _chrome_available() -> bool:
    """Check if Chrome with CDP port 9222 is reachable."""
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3)
        return True
    except Exception:
        return False


# ── Scope: session sync fixtures ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def chrome_ok() -> bool:
    """Verify Chrome with CDP is running."""
    ok = _chrome_available()
    if not ok:
        pytest.skip("Chrome on port 9222 not available. Start with: chrome ... --remote-debugging-port=9222")
    return ok


@pytest.fixture(scope="session")
def cua_ok() -> bool:
    """Verify cua-driver daemon is running."""
    ok = _cua_available()
    if not ok:
        pytest.skip("cua-driver not running. Start with: cua-driver serve &")
    return ok


# ── Scope: function async fixtures ────────────────────────────────────────────

@pytest_asyncio.fixture
async def browser():
    """Connect to running Chrome via CDP and return the Playwright browser object."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        yield b


@pytest_asyncio.fixture
async def gmx_page(browser):
    """Return a GMX page (navigate to www.gmx.net if not already on GMX)."""
    for pg in browser.contexts[0].pages:
        if "gmx" in pg.url.lower():
            await pg.goto("https://www.gmx.net/")
            await asyncio.sleep(2)
            return pg
    pg = await browser.contexts[0].new_page()
    await pg.goto("https://www.gmx.net/")
    await asyncio.sleep(2)
    return pg


@pytest_asyncio.fixture
async def cua_window():
    """Find and return (pid, wid) for the first on-screen Chrome window."""
    from cua_helper import find_cua_window
    cua = find_cua_window()
    if not cua:
        pytest.skip("No CUA window found")
    return cua


@pytest_asyncio.fixture
async def fireworks_page(browser):
    """Return a fresh clean page on app.fireworks.ai (closed previous FW tabs)."""
    for pg in browser.contexts[0].pages:
        if "fireworks" in pg.url.lower():
            await pg.close()
    pg = await browser.contexts[0].new_page()
    await pg.goto("https://app.fireworks.ai/login")
    await asyncio.sleep(4)
    return pg
