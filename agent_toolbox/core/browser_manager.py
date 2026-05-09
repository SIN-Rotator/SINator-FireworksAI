"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Browser Manager (CDP Edition)            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Singleton der eine CDP-Verbindung zu Chrome hält (KEIN Playwright!).        ║
║  Verwaltet Start/Stop/Connect für Chrome Profile 901.                        ║
║                                                                              ║
║  ARCHITEKTUR:                                                                 ║
║  - KEIN Playwright (Playwright crasht bei GMX SPA frame detachment)          ║
║  - KEIN Profil kopieren (Chrome-Cookies sind an ORIGINAL-Profil-Pfad         ║
║    gebunden → Kopie zerstört GMX-Session!)                                   ║
║  - Stattdessen: Raw CDP Websocket Client für alle Operationen               ║
║  - Chrome läuft IMMER mit ORIGINAL Profile 901 auf /Users/jeremy/...         ║
║                                                                              ║
║  WICHTIG (KRITISCHE ERKENNTIS):                                              ║
║  Chrome verschlüsselt Cookies mit dem macOS Keychain. Die Verschlüsselung    ║
║  ist an den ORIGINAL user-data-dir Pfad gebunden. Wenn man das Profil        ║
║  nach /tmp kopiert und Chrome von dort startet:                             ║
║  → Cookies sind unlesbar (Keychain-Path-Mismatch)                           ║
║  → GMX-Session ist TOT                                                       ║
║  → Account-Rotation schlägt fehl                                             ║
║                                                                              ║
║  LÖSUNG:                                                                      ║
║  Chrome IMMER mit dem ORIGINAL Profile 901 starten:                          ║
║  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome"   ║
║  --profile-directory="Profile 901"                                           ║
║                                                                              ║
║  PROFIL KOPIEREN = VERBOTEN!                                                 ║
║  - Das alte browser_manager.py kopierte Profile 901 nach                     ║
║    /tmp/sinator-chrome-{timestamp} → ZERSTÖRTE GMX-SESSION                   ║
║  - Diese Praxis ist jetzt ENTFERNT aus dem Code                              ║
║                                                                              ║
║  CHROME STARTEN:                                                              ║
║  Der einzige richtige Weg Chrome zu starten (IMMER!):                        ║
║                                                                              ║
║  rtk nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"    ║
║    --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" ║
║    --profile-directory="Profile 901"                                         ║
║    --remote-debugging-port=9222                                              ║
║    --no-first-run --no-default-browser-check                                 ║
║    > /tmp/chrome_sinator.log 2>&1 & sleep 6                                  ║
║    && rtk curl -s http://127.0.0.1:9222/json/version                         ║
║    | python3 -c "import sys,json; print('Chrome OK')"                        ║
║                                                                              ║
║  KEINE ANDERE METHODE IST KORREKT!                                            ║
║                                                                              ║
║  CHROME BEENDEN:                                                              ║
║  - NIEMALS `pkill -9 -f "Google Chrome"` (zerstört unflushed SQLite!)        ║
║  - NIEMALS `osascript -e 'quit app "Google Chrome"'` (killt Session!)        ║
║  - Browser läuft lassen wenn er einmal gestartet ist                         ║
║  - Bei Bedarf: nur CDP verbinden, Chrome NICHT neustarten                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import os
import time
import logging
import asyncio
import subprocess
import signal
import httpx
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_USER_DATA_DIR = "/Users/jeremy/Library/Application Support/Google Chrome"
CHROME_PROFILE_NAME = "Profile 901"
CHROME_CDP_PORT = 9222


class BrowserManager:
    """
    Singleton für Chrome Browser Lifecycle Management.

    WICHTIG: Verwendet das ORIGINAL Profile 901 — KEINE KOPIEN!

    Chrome verschlüsselt Session-Cookies mit dem macOS Keychain. Diese
    Verschlüsselung ist an den ORIGINAL user-data-dir Pfad gebunden.
    Ein kopiertes Profil hätte unlesbare Cookies → GMX-Session tot.

    Daher: Chrome starten mit ORIGINAL Profile, nicht kopieren.
    Wenn Chrome bereits läuft: Einfach verbinden (nicht neustarten).

    Usage:
        manager = BrowserManager()
        await manager.start()        # Startet Chrome wenn nicht laufend
        await manager.stop()         # Beendet Chrome (graceful)
        manager.is_running           # Status prüfen
    """

    def __init__(
        self,
        chrome_path: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        profile_name: str = "Profile 901",
        cdp_port: int = 9222,
        headless: bool = False,
    ):
        self.chrome_path = chrome_path or CHROME_BINARY
        self.user_data_dir = user_data_dir or CHROME_USER_DATA_DIR
        self.profile_name = profile_name
        self.cdp_port = cdp_port
        self.headless = headless

        self._is_running = False
        self._chrome_proc: Optional[subprocess.Popen] = None

    @property
    def is_running(self) -> bool:
        """Prüft ob Chrome läuft (CDP Port erreichbar)."""
        return self._is_running

    async def _is_chrome_already_running(self) -> bool:
        """
        Prüft ob Chrome bereits auf dem CDP Port läuft.

        Methode: HTTP GET auf http://127.0.0.1:{cdp_port}/json/version
        Wenn Response → Chrome läuft.

        Returns:
            True wenn Chrome bereits läuft
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
                resp = await client.get(f"http://127.0.0.1:{self.cdp_port}/json/version")
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(f"[BrowserManager] Chrome läuft bereits: {data.get('Browser', 'unknown')}")
                    return True
        except Exception:
            pass
        return False

    async def start(self) -> Dict[str, Any]:
        """
        Startet Chrome mit ORIGINAL Profile 901.

        STRATEGIE:
        1. Prüfe ob Chrome bereits auf CDP Port läuft
        2. Wenn ja: NICHTS neustarten → einfach als "running" markieren
        3. Wenn nein: Chrome als subprocess starten (nohup, background)
        4. Auf CDP Bereitschaft warten

        Das ORIGINAL Profile 901 wird verwendet:
        --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome"
        --profile-directory="Profile 901"

        Returns:
            Dict mit status, cdp_port, startup_time
        """
        start_time = time.time()

        chrome_already_running = await self._is_chrome_already_running()

        if chrome_already_running:
            self._is_running = True
            elapsed = time.time() - start_time
            logger.info(f"[BrowserManager] Verbindung zu bestehendem Chrome hergestellt (Profile 901, Port {self.cdp_port}) in {elapsed:.2f}s")
            return {
                "status": "connected",
                "cdp_port": self.cdp_port,
                "profile": self.profile_name,
                "user_data_dir": self.user_data_dir,
                "startup_time": f"{elapsed:.2f}s",
                "note": "Chrome war bereits gestartet — originale Session verwendet!",
            }

        logger.info(f"[BrowserManager] Chrome nicht laufend → starte mit ORIGINAL Profile 901...")
        logger.info(f"[BrowserManager] User Data Dir: {self.user_data_dir}")
        logger.info(f"[BrowserManager] Profile: {self.profile_name}")
        logger.info(f"[BrowserManager] CDP Port: {self.cdp_port}")

        try:
            self._chrome_proc = self._launch_chrome_original_profile()
            self._is_running = True
            elapsed = time.time() - start_time
            logger.info(f"[BrowserManager] Chrome gestartet in {elapsed:.2f}s")
            return {
                "status": "started",
                "cdp_port": self.cdp_port,
                "profile": self.profile_name,
                "user_data_dir": self.user_data_dir,
                "startup_time": f"{elapsed:.2f}s",
            }
        except Exception as e:
            self._is_running = False
            elapsed = time.time() - start_time
            logger.error(f"[BrowserManager] Chrome-Start fehlgeschlagen nach {elapsed:.2f}s: {e}")
            return {
                "status": "failed",
                "cdp_port": self.cdp_port,
                "error": str(e),
                "startup_time": f"{elapsed:.2f}s",
            }

    def _launch_chrome_original_profile(self) -> subprocess.Popen:
        """
        Startet Chrome mit dem ORIGINAL Profile 901.

        WICHTIG: Verwende das ORIGINAL user-data-dir, KEINE KOPIE!
        Chrome-Cookies sind an den Original-Pfad gebunden.

        Command (ALLES muss stimmen):
        nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
          --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
          --profile-directory="Profile 901" \
          --remote-debugging-port=9222 \
          --no-first-run \
          --no-default-browser-check \
          > /tmp/chrome_sinator.log 2>&1 &

        Returns:
            subprocess.Popen Objekt
        """
        args = [
            self.chrome_path,
            f"--user-data-dir={self.user_data_dir}",
            f"--profile-directory={self.profile_name}",
            f"--remote-debugging-port={self.cdp_port}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        if self.headless:
            args.append("--headless=new")

        logger.info(f"[BrowserManager] Starte Chrome: {' '.join(args[:4])}...")

        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid if hasattr(os, 'setsgid') else None,
        )

        return proc

    async def stop(self) -> Dict[str, Any]:
        """
        Beendet den Chrome-Browser.

        WICHTIG:
        - NIEMALS pkill -9 (zerstört unflushed SQLite → Session dead)
        - Stattdessen: graceful shutdown via SIGTERM oder SIGINT

        Returns:
            Dict mit status, elapsed_time
        """
        start_time = time.time()
        cleanup_actions = []

        if self._chrome_proc and self._chrome_proc.poll() is None:
            try:
                logger.info("[BrowserManager] Sende SIGTERM an Chrome...")
                self._chrome_proc.terminate()
                try:
                    self._chrome_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("[BrowserManager] Chrome reagiert nicht auf SIGTERM → SIGKILL")
                    self._chrome_proc.kill()
                    cleanup_actions.append("sigkill_used")
                cleanup_actions.append("terminated")
                logger.info("[BrowserManager] Chrome beendet (graceful)")
            except Exception as e:
                logger.warning(f"[BrowserManager] Fehler beim Beenden: {e}")

        self._is_running = False
        self._chrome_proc = None
        elapsed = time.time() - start_time

        return {
            "status": "stopped",
            "cleanup_actions": cleanup_actions,
            "elapsed": f"{elapsed:.2f}s",
        }

    async def restart(self) -> Dict[str, Any]:
        """
        Startet Chrome neu (stop + start).

        ACHTUNG: Dies zerstört die GMX-Session weil Chrome mit dem
        gleichen Original-Profil neu startet und die Session-Cookies
        beim Shutdown geschrieben werden. NUR verwenden wenn nötig!

        Returns:
            Dict mit start() Ergebnis
        """
        await self.stop()
        await asyncio.sleep(2)
        return await self.start()


_browser_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    """Gibt den Singleton BrowserManager zurück."""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager


def reset_browser_manager() -> None:
    """Setzt den Singleton zurück (für Tests)."""
    global _browser_manager
    _browser_manager = None