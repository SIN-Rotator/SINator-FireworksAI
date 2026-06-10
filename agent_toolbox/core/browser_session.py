"""
Zentrale Browser-Session — EIN Chrome für den gesamten Rotator-Lauf.

Startet genau einmal ein Bot-Chrome mit GPU-Flags (Display-Crash fix).
Alle anderen Module verbinden sich via connect_over_cdp() — kein eigener launch().
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CDP_PORT = 9222

_LAUNCH_ARGS = [
    f"--remote-debugging-port={CDP_PORT}",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--window-size=1200,800",
    "--disable-gpu",
    "--disable-gpu-compositing",
    "--disable-software-rasterizer",
    "--use-angle=swiftshader",
]


class BrowserSession:
    """Singleton: genau eine Chromium-Instanz für den gesamten Prozess."""

    _instance: Optional["BrowserSession"] = None

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    @classmethod
    def get(cls) -> "BrowserSession":
        if cls._instance is None:
            cls._instance = BrowserSession()
        return cls._instance

    @property
    def is_running(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    @property
    def page(self):
        return self._page

    @property
    def context(self):
        return self._context

    @property
    def browser(self):
        return self._browser

    async def start(self):
        """Einmalig starten — idempotent bei Mehrfachaufruf."""
        if self.is_running:
            return self

        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=False,
            args=_LAUNCH_ARGS,
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1200, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="de-DE",
            timezone_id="Europe/Berlin",
        )
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            window.chrome = { runtime: {} };
        """)
        self._page = await self._context.new_page()
        logger.info("[BrowserSession] Bot-Chrome gestartet")
        return self

    async def new_tab(self):
        """Neuer Tab im gleichen Browser — teilt Cookies/Session."""
        if not self.is_running:
            await self.start()
        return await self._context.new_page()

    async def stop(self):
        """Nur am ENDE der Rotation aufrufen."""
        for closer in (
            lambda: self._context and self._context.close(),
            lambda: self._browser and self._browser.close(),
            lambda: self._pw and self._pw.stop(),
        ):
            try:
                res = closer()
                if res:
                    await res
            except Exception as e:
                logger.warning(f"[BrowserSession] stop fehlgeschlagen: {e}")
        self._pw = self._browser = self._context = self._page = None
        BrowserSession._instance = None
        logger.info("[BrowserSession] Bot-Chrome geschlossen")


async def connect_cdp():
    """Mit laufendem Bot-Chrome via CDP verbinden (kein neuer Browser)."""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
    return pw, browser
