"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Cookie Manager (Core)                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Verwaltet GMX-Session-Cookies: Extrahieren, Speichern, Injizieren.          ║
║  Cookies sind der Schlüssel zur Session-Persistenz ohne erneutes Login.      ║
║                                                                              ║
║  WARUM COOKIE-MANAGEMENT?                                                     ║
║  • GMX zeigt CAPTCHA nach Email-Eingabe im Login-Flow                        ║
║  • Automatisches Login ist nicht zuverlässig möglich                         ║
║  • Lösung: Einmal manuell einloggen → Cookies speichern → injecten           ║
║                                                                              ║
║  ARCHITEKTUR:                                                                 ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │ CookieManager                                                        │    ║
║  │ ├── extract_cookies(page) → List[Cookie]                            │    ║
║  │ ├── save_cookies(cookies, filepath) → None                          │    ║
║  │ ├── load_cookies(filepath) → List[Cookie]                           │    ║
║  │ ├── inject_cookies(context, cookies) → None                         │    ║
║  │ └── verify_session(page) → bool                                     │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from playwright.async_api import BrowserContext, Page

logger = logging.getLogger(__name__)


class CookieManager:
    """
    Verwaltet Browser-Cookies für Session-Persistenz.

    Extrahiert, speichert und injiziert Cookies ohne dass ein Login nötig ist.
    """

    def __init__(self, cookies_dir: str = "./data"):
        """
        Initialisiert den Cookie-Manager.

        Args:
            cookies_dir: Verzeichnis für Cookie-Dateien (default: ./data)
        """
        self.cookies_dir = Path(cookies_dir)
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

    def extract_cookies(self, page: Page, domain_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extrahiert alle Cookies der aktuellen Page.

        Args:
            page: Playwright Page-Objekt
            domain_filter: Optionaler Domain-Filter (z.B. "gmx")

        Returns:
            Liste von Cookie-Dicts
        """
        cookies = page.context.cookies()
        if domain_filter:
            cookies = [c for c in cookies if domain_filter in c.get("domain", "")]

        logger.info(f"{len(cookies)} Cookies extrahiert" + (f" (Filter: {domain_filter})" if domain_filter else ""))
        return cookies

    def save_cookies(self, cookies: List[Dict[str, Any]], filename: str = "gmx-cookies.json") -> str:
        """
        Speichert Cookies in eine JSON-Datei.

        Args:
            cookies: Liste von Cookie-Dicts
            filename: Dateiname (default: gmx-cookies.json)

        Returns:
            Pfad zur gespeicherten Datei
        """
        filepath = self.cookies_dir / filename

        # Serialisieren (manche Felder können None sein)
        serializable = []
        for c in cookies:
            serializable.append({
                "name": c.get("name"),
                "value": c.get("value"),
                "domain": c.get("domain"),
                "path": c.get("path", "/"),
                "expires": c.get("expires", -1),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": c.get("sameSite", "None"),
            })

        with open(filepath, "w") as f:
            json.dump(serializable, f, indent=2)

        logger.info(f"{len(serializable)} Cookies gespeichert: {filepath}")
        return str(filepath)

    def load_cookies(self, filename: str = "gmx-cookies.json") -> List[Dict[str, Any]]:
        """
        Lädt Cookies aus einer JSON-Datei.

        Args:
            filename: Dateiname (default: gmx-cookies.json)

        Returns:
            Liste von Cookie-Dicts
        """
        filepath = self.cookies_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Cookie-Datei nicht gefunden: {filepath}")

        with open(filepath, "r") as f:
            cookies = json.load(f)

        logger.info(f"{len(cookies)} Cookies geladen: {filepath}")
        return cookies

    async def inject_cookies(self, context: BrowserContext, cookies: List[Dict[str, Any]]) -> int:
        """
        Injiziert Cookies in einen Browser-Context.

        Args:
            context: Playwright BrowserContext
            cookies: Liste von Cookie-Dicts

        Returns:
            Anzahl injizierter Cookies
        """
        count = 0
        for cookie in cookies:
            try:
                await context.add_cookies([cookie])
                count += 1
            except Exception as e:
                logger.warning(f"Cookie-Injektion fehlgeschlagen für {cookie.get('name')}: {e}")

        logger.info(f"{count}/{len(cookies)} Cookies injiziert")
        return count

    async def verify_session(self, page: Page, expected_url: str = "navigator.gmx.net") -> bool:
        """
        Prüft ob eine GMX-Session aktiv ist.

        Args:
            page: Playwright Page-Objekt
            expected_url: URL-Substring der auf eine aktive Session hinweist

        Returns:
            True wenn Session aktiv, False sonst
        """
        try:
            await page.goto(f"https://{expected_url}/mail", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)

            current_url = page.url
            is_logged_in = expected_url in current_url and "login" not in current_url

            if is_logged_in:
                logger.info(f"Session aktiv: {current_url}")
            else:
                logger.warning(f"Session nicht aktiv: {current_url}")

            return is_logged_in

        except Exception as e:
            logger.error(f"Session-Prüfung fehlgeschlagen: {e}")
            return False

    def get_cookie_stats(self, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generiert Statistik über Cookies.

        Args:
            cookies: Liste von Cookie-Dicts

        Returns:
            Dict mit Statistiken
        """
        domains = {}
        for c in cookies:
            domain = c.get("domain", "unknown")
            domains[domain] = domains.get(domain, 0) + 1

        return {
            "total": len(cookies),
            "domains": domains,
            "http_only": sum(1 for c in cookies if c.get("httpOnly")),
            "secure": sum(1 for c in cookies if c.get("secure")),
            "session_cookies": sum(1 for c in cookies if c.get("expires", -1) == -1),
        }


# Singleton-Instanz
_cookie_manager: Optional[CookieManager] = None


def get_cookie_manager() -> CookieManager:
    """
    Liefert die Singleton-Instanz des Cookie-Managers.

    Returns:
        CookieManager-Instanz
    """
    global _cookie_manager
    if _cookie_manager is None:
        _cookie_manager = CookieManager()
    return _cookie_manager
