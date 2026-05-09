"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Browser Manager (Core)                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Warm-Browser-Singleton der eine Playwright-Instanz im Hintergrund hält      ║
║  und bei Bedarf wiederverwendet. Vermeidet teure Kaltstarts.                 ║
║                                                                              ║
║  ARCHITEKTUR:                                                                 ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │ BrowserManager (Singleton)                                           │    ║
║  │ ├── _instance: Playwright Browser Context                           │    ║
║  │ ├── _profile_dir: Kopiertes Chrome-Profil                           │    ║
║  │ ├── _cdp_port: DevTools Protocol Port                               │    ║
║  │ ├── start() → Initialisiert Browser mit Profil-Kopie                │    ║
║  │ ├── get_page() → Liefert neue Page im bestehenden Context           │    ║
║  │ ├── stop() → Beendet Browser & räumt Temp-Profil auf               │    ║
║  │ └── is_running() → Prüft ob Browser aktiv ist                       │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  WARUM PLAYWRIGHT STATT PUPPETEER?                                           ║
║  • Native Python-Integration (kein Node.js Bridge nötig)                     ║
║  • Bessere CDP-Unterstützung für Chrome-Subprocess                           ║
║  • Eingebaute Stealth-Features (playwright-stealth)                          │    ║
║  • Schnelleres Page-Navigation Handling                                      │    ║
║                                                                              ║
║  PROFIL-KOPIERUNG:                                                            ║
║  Chrome verweigert CDP mit Default user-data-dir.                             ║
║  Lösung: Profil nach /tmp kopieren → Chrome startet mit CDP.                  │    ║
║  WICHTIG: Local State + Profile 901 müssen kopiert werden!                     │    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os
import shutil
import subprocess
import time
import json
import logging
import asyncio
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Warm-Browser-Singleton für Playwright.

    Hält eine Browser-Instanz im Hintergrund und vermeidet teure Neustarts.
    Profil wird beim ersten Start kopiert und wiederverwendet.

    Usage:
        manager = BrowserManager()
        await manager.start()
        page = await manager.get_page()
        # ... automation ...
        await manager.stop()
    """

    def __init__(
        self,
        chrome_path: Optional[str] = None,
        source_profile: Optional[str] = None,
        profile_name: str = "Profile 901",
        cdp_port: int = 9222,
        headless: bool = False,
    ):
        """
        Initialisiert den Browser-Manager.

        Args:
            chrome_path: Pfad zur Chrome Binary (default: macOS Standard)
            source_profile: Pfad zum Chrome user-data-dir (default: macOS Standard)
            profile_name: Name des Profil-Ordners (default: "Profile 901")
            cdp_port: Port für Chrome DevTools Protocol (default: 9222)
            headless: Headless-Modus (default: False für Debugging)
        """
        self.chrome_path = chrome_path or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        self.source_user_data_dir = source_profile or str(
            Path.home() / "Library/Application Support/Google/Chrome"
        )
        self.profile_name = profile_name
        self.cdp_port = cdp_port
        self.headless = headless

        # Singleton state
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._temp_profile_dir: Optional[str] = None
        self._chrome_proc: Optional[subprocess.Popen] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Prüft ob der Browser aktiv ist."""
        return self._is_running and self._browser is not None

    async def start(self) -> Dict[str, Any]:
        """
        Startet Chrome mit kopiertem Profil und verbindet Playwright via CDP.

        ABLAUF:
        1. Profil kopieren (Local State + Profile 901 → /tmp)
        2. Chrome starten via subprocess mit CDP-Port
        3. Auf CDP-Bereitschaft warten
        4. Playwright.connect_over_cdp() zum laufenden Chrome
        5. Stealth-JS injecten

        Returns:
            Dict mit status, browser_info, temp_profile_dir
        """
        if self.is_running:
            logger.info("Browser läuft bereits, verwende bestehende Instanz")
            return {
                "status": "already_running",
                "browser_info": {"cdp_port": self.cdp_port},
                "temp_profile_dir": self._temp_profile_dir,
            }

        logger.info("Starte Browser mit Profil-Kopie...")
        start_time = time.time()

        try:
            # Phase 1: Profil kopieren
            self._temp_profile_dir = self._copy_profile()

            # Phase 2: Chrome starten
            self._chrome_proc = self._launch_chrome()

            # Phase 3: Auf CDP warten
            await self._wait_for_cdp(max_retries=15)

            # Phase 4: Playwright verbinden
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{self.cdp_port}"
            )
            self._context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()

            # Phase 5: Stealth injecten
            await self._inject_stealth()

            self._is_running = True
            elapsed = time.time() - start_time

            logger.info(f"Browser gestartet in {elapsed:.2f}s")
            return {
                "status": "success",
                "browser_info": {
                    "cdp_port": self.cdp_port,
                    "temp_profile": self._temp_profile_dir,
                    "startup_time": f"{elapsed:.2f}s",
                },
                "temp_profile_dir": self._temp_profile_dir,
            }

        except Exception as e:
            logger.error(f"Browser-Start fehlgeschlagen: {e}")
            await self._cleanup()
            raise

    async def get_page(self) -> Page:
        """
        Liefert eine neue Page im bestehenden Browser-Context.

        Returns:
            Playwright Page-Objekt
        """
        if not self.is_running:
            raise RuntimeError("Browser nicht gestartet. Rufe zuerst start() auf.")

        page = await self._context.new_page()
        logger.debug(f"Neue Page erstellt: {page}")
        return page

    async def get_existing_page(self) -> Optional[Page]:
        """
        Liefert die erste bestehende Page im Context (z.B. die beim Start geöffnete).

        Returns:
            Playwright Page-Objekt oder None
        """
        if not self.is_running:
            return None

        pages = self._context.pages
        return pages[0] if pages else None

    async def stop(self) -> Dict[str, Any]:
        """
        Beendet den Browser und räumt das Temp-Profil auf.

        Returns:
            Dict mit status und cleanup_info
        """
        if not self.is_running:
            return {"status": "not_running"}

        logger.info("Beende Browser & räume auf...")
        await self._cleanup()
        return {"status": "stopped", "temp_profile_cleaned": self._temp_profile_dir}

    def _copy_profile(self) -> str:
        """
        Kopiert Chrome-Profil in temporäres Verzeichnis.

        WARUM KOPIEREN (NICHT SYMLINK)?
        Symlink ist BANNED (siehe banned.md). Chrome verschlüsselt Cookies
        mit dem realen Pfad als Key. Kopieren = Cookies funktionieren.

        Returns:
            Pfad zum temporären Verzeichnis (mit kopiertem Profil)
        """
        temp_dir = f"/tmp/sinator-chrome-{int(time.time())}"
        source_profile = os.path.join(self.source_user_data_dir, self.profile_name)

        logger.info(f"Kopiere Profil: {source_profile} → {temp_dir}")
        os.makedirs(temp_dir, exist_ok=True)

        # Local State kopieren (Metadaten, Profil-Liste)
        local_state_src = os.path.join(self.source_user_data_dir, "Local State")
        if os.path.exists(local_state_src):
            shutil.copy2(local_state_src, os.path.join(temp_dir, "Local State"))
            logger.info("Local State kopiert")

        # Last Version kopieren (optional)
        last_version_src = os.path.join(self.source_user_data_dir, "Last Version")
        if os.path.exists(last_version_src):
            shutil.copy2(last_version_src, os.path.join(temp_dir, "Last Version"))

        # Profil-Ordner kopieren (KEIN Symlink!)
        if os.path.exists(source_profile):
            shutil.copytree(
                source_profile,
                os.path.join(temp_dir, self.profile_name),
                symlinks=True,
                ignore_dangling_symlinks=True,
            )
            logger.info(f"{self.profile_name} kopiert")
        else:
            raise FileNotFoundError(f"Profil nicht gefunden: {source_profile}")

        # First Run erstellen (verhindert Welcome-Dialog)
        Path(os.path.join(temp_dir, "First Run")).touch()

        # Lock-Files entfernen
        for pattern in ["*.lock", "Singleton*"]:
            for f in Path(temp_dir).rglob(pattern):
                f.unlink(missing_ok=True)

        return temp_dir

    def _launch_chrome(self) -> subprocess.Popen:
        """
        Startet Chrome als Subprocess mit CDP-Debugging.

        Returns:
            subprocess.Popen-Objekt
        """
        args = [
            self.chrome_path,
            f"--user-data-dir={self._temp_profile_dir}",
            f"--profile-directory={self.profile_name}",
            f"--remote-debugging-port={self.cdp_port}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1280,800",
            "--lang=de-DE",
        ]

        if self.headless:
            args.append("--headless=new")

        logger.info(f"Starte Chrome: {' '.join(args[:3])}...")
        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc

    async def _wait_for_cdp(self, max_retries: int = 15):
        """
        Wartet bis CDP-Endpoint erreichbar ist.

        Args:
            max_retries: Maximale Anzahl Versuche (default: 15)
        """
        for i in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(f"http://127.0.0.1:{self.cdp_port}/json/version")
                    if resp.status_code == 200:
                        logger.info(f"CDP erreichbar nach {i+1}s")
                        return
            except Exception:
                pass
            await asyncio.sleep(1)

        raise TimeoutError(f"CDP nicht erreichbar nach {max_retries}s auf Port {self.cdp_port}")

    async def _inject_stealth(self):
        """
        Injectiert Stealth-JS in alle neuen Pages.

        Überschreibt navigator.webdriver, plugins, languages, window.chrome
        um Bot-Detection zu umgehen.
        """
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
        window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
        (() => {
            const oq = window.navigator.permissions.query;
            window.navigator.permissions.query = (p) => p.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : oq(p);
        })();
        """

        if self._context:
            await self._context.add_init_script(stealth_js)
            logger.info("Stealth-JS injectiert")

    async def _cleanup(self):
        """Räumt Browser und Temp-Profil auf."""
        try:
            if self._browser:
                await self._browser.close()
                logger.info("Browser geschlossen")
        except Exception as e:
            logger.warning(f"Browser close Fehler: {e}")

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

        try:
            if self._chrome_proc:
                self._chrome_proc.terminate()
                self._chrome_proc.wait(timeout=5)
                logger.info("Chrome-Prozess beendet")
        except Exception as e:
            logger.warning(f"Chrome kill Fehler: {e}")

        try:
            if self._temp_profile_dir and os.path.exists(self._temp_profile_dir):
                shutil.rmtree(self._temp_profile_dir, ignore_errors=True)
                logger.info(f"Temp-Profil aufgeräumt: {self._temp_profile_dir}")
        except Exception as e:
            logger.warning(f"Cleanup Fehler: {e}")

        self._is_running = False
        self._browser = None
        self._context = None
        self._playwright = None
        self._chrome_proc = None
        self._temp_profile_dir = None


# Singleton-Instanz
_browser_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    """
    Liefert die Singleton-Instanz des Browser-Managers.

    Returns:
        BrowserManager-Instanz
    """
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager


# Import asyncio for the async sleep
import asyncio
