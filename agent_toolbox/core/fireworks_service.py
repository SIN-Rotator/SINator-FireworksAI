"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Fireworks Service (Core)                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  Fireworks AI Account-Registrierung, Bestätigung, API-Key-Erstellung         ║
║                                                                              ║
║  ARCHITEKTUR:                                                                 ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │ FireworksService                                                     │    ║
║  │ ├── register_account() → Erstellt Fireworks Account                 │    ║
║  │ ├── confirm_account() → Bestätigt Account via OTP-URL               │    ║
║  │ ├── create_api_key() → Generiert API-Key im Dashboard               │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
import re
from typing import Optional, Dict, Any

from playwright.async_api import Page

logger = logging.getLogger(__name__)

FIREWORKS_SIGNUP_URL = "https://app.fireworks.ai/signup"
FIREWORKS_SETTINGS_URL = "https://app.fireworks.ai/settings/users/api-keys"


class FireworksService:
    """
    Verwaltet Fireworks AI Operationen: Registrierung, Bestätigung, API-Key-Erstellung.
    """

    async def register_account(
        self,
        page: Page,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        timeout: int = 30000,
    ) -> Dict[str, Any]:
        """
        Registriert einen neuen Fireworks AI Account.

        Args:
            page: Playwright Page-Objekt
            email: Email für Registrierung
            password: Passwort für Account
            first_name: Vorname (optional)
            last_name: Nachname (optional)
            timeout: Timeout in ms

        Returns:
            Dict mit status, account_email
        """
        start_time = time.time()

        try:
            logger.info(f"Fireworks AI Registrierung: {email}")
            await page.goto(FIREWORKS_SIGNUP_URL, wait_until="networkidle", timeout=timeout)
            await page.wait_for_timeout(2000)

            # Email eingeben
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="email" i]',
            ]

            email_input = None
            for selector in email_selectors:
                try:
                    email_input = await page.query_selector(selector)
                    if email_input and await email_input.is_visible():
                        break
                except Exception:
                    continue

            if not email_input:
                raise RuntimeError("Email-Feld nicht gefunden")

            await email_input.fill(email)
            await page.wait_for_timeout(500)

            # Next Button
            next_selectors = [
                'button:has-text("Next")',
                'button:has-text("Weiter")',
                'button[type="submit"]',
            ]

            next_btn = None
            for selector in next_selectors:
                try:
                    next_btn = await page.query_selector(selector)
                    if next_btn and await next_btn.is_visible():
                        break
                except Exception:
                    continue

            if not next_btn:
                raise RuntimeError("Next-Button nicht gefunden")

            await next_btn.click()
            await page.wait_for_timeout(2000)

            # Passwort eingeben
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
            ]

            password_input = None
            for selector in password_selectors:
                try:
                    password_input = await page.query_selector(selector)
                    if password_input and await password_input.is_visible():
                        break
                except Exception:
                    continue

            if not password_input:
                raise RuntimeError("Passwort-Feld nicht gefunden")

            await password_input.fill(password)
            await page.wait_for_timeout(500)

            # Create Account Button
            create_selectors = [
                'button:has-text("Create Account")',
                'button:has-text("Account erstellen")',
                'button:has-text("Sign Up")',
                'button[type="submit"]',
            ]

            create_btn = None
            for selector in create_selectors:
                try:
                    create_btn = await page.query_selector(selector)
                    if create_btn and await create_btn.is_visible():
                        break
                except Exception:
                    continue

            if not create_btn:
                raise RuntimeError("Create-Account-Button nicht gefunden")

            await create_btn.click()
            await page.wait_for_timeout(3000)

            elapsed = time.time() - start_time
            logger.info(f"Account-Erstellung abgeschickt in {elapsed:.2f}s")

            return {
                "status": "success",
                "account_email": email,
                "execution_time": f"{elapsed:.2f}s",
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Fireworks Registrierung fehlgeschlagen: {e}")
            return {
                "status": "failed",
                "account_email": email,
                "execution_time": f"{elapsed:.2f}s",
                "error": str(e),
            }

    async def confirm_account(
        self,
        page: Page,
        confirm_url: str,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        timeout: int = 30000,
    ) -> Dict[str, Any]:
        """
        Bestätigt den Fireworks Account via OTP-URL.

        Args:
            page: Playwright Page-Objekt
            confirm_url: Bestätigungs-URL aus OTP-Email
            email: Account Email
            password: Account Passwort
            first_name: Vorname (optional)
            last_name: Nachname (optional)
            timeout: Timeout in ms

        Returns:
            Dict mit status, account_confirmed
        """
        start_time = time.time()

        try:
            logger.info(f"Bestätige Fireworks Account: {confirm_url}")
            await page.goto(confirm_url, wait_until="networkidle", timeout=timeout)
            await page.wait_for_timeout(2000)

            # Sign In Button (falls nötig)
            signin_selectors = [
                'button:has-text("Sign In")',
                'a:has-text("Sign In")',
                'button:has-text("Anmelden")',
            ]

            for selector in signin_selectors:
                try:
                    signin_btn = await page.query_selector(selector)
                    if signin_btn and await signin_btn.is_visible():
                        await signin_btn.click()
                        await page.wait_for_timeout(1500)
                        logger.info("Sign In geklickt")
                        break
                except Exception:
                    continue

            # Email Login Button
            email_login_selectors = [
                'button:has-text("Email Login")',
                'a:has-text("Email Login")',
                'button:has-text("Continue with Email")',
                'button:has-text("Continue with email")',
            ]

            for selector in email_login_selectors:
                try:
                    email_login_btn = await page.query_selector(selector)
                    if email_login_btn and await email_login_btn.is_visible():
                        await email_login_btn.click()
                        await page.wait_for_timeout(1500)
                        logger.info("Email Login geklickt")
                        break
                except Exception:
                    continue

            # Email eingeben
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
            ]

            for selector in email_selectors:
                try:
                    email_input = await page.query_selector(selector)
                    if email_input and await email_input.is_visible():
                        await email_input.fill(email)
                        await page.wait_for_timeout(500)
                        break
                except Exception:
                    continue

            # Passwort eingeben
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
            ]

            for selector in password_selectors:
                try:
                    pass_input = await page.query_selector(selector)
                    if pass_input and await pass_input.is_visible():
                        await pass_input.fill(password)
                        await page.wait_for_timeout(500)
                        break
                except Exception:
                    continue

            # Next/Login Button
            next_selectors = [
                'button:has-text("Next")',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                'button[type="submit"]',
            ]

            for selector in next_selectors:
                try:
                    next_btn = await page.query_selector(selector)
                    if next_btn and await next_btn.is_visible():
                        await next_btn.click()
                        await page.wait_for_timeout(2000)
                        logger.info("Login-Daten abgeschickt")
                        break
                except Exception:
                    continue

            # Vorname + Nachname (falls gefordert)
            if first_name:
                fname_selectors = [
                    'input[name="firstName"]',
                    'input[placeholder*="First" i]',
                    'input[placeholder*="Vorname" i]',
                ]

                for selector in fname_selectors:
                    try:
                        fname_input = await page.query_selector(selector)
                        if fname_input and await fname_input.is_visible():
                            await fname_input.fill(first_name)
                            await page.wait_for_timeout(500)
                            break
                    except Exception:
                        continue

            if last_name:
                lname_selectors = [
                    'input[name="lastName"]',
                    'input[placeholder*="Last" i]',
                    'input[placeholder*="Nachname" i]',
                ]

                for selector in lname_selectors:
                    try:
                        lname_input = await page.query_selector(selector)
                        if lname_input and await lname_input.is_visible():
                            await lname_input.fill(last_name)
                            await page.wait_for_timeout(500)
                            break
                    except Exception:
                        continue

            # Continue Button
            continue_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Weiter")',
                'button[type="submit"]',
            ]

            for selector in continue_selectors:
                try:
                    continue_btn = await page.query_selector(selector)
                    if continue_btn and await continue_btn.is_visible():
                        await continue_btn.click()
                        await page.wait_for_timeout(2000)
                        logger.info("Profil ausgefüllt")
                        break
                except Exception:
                    continue

            elapsed = time.time() - start_time
            logger.info(f"Account bestätigt in {elapsed:.2f}s")

            return {
                "status": "success",
                "account_confirmed": True,
                "execution_time": f"{elapsed:.2f}s",
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Account-Bestätigung fehlgeschlagen: {e}")
            return {
                "status": "failed",
                "account_confirmed": False,
                "execution_time": f"{elapsed:.2f}s",
                "error": str(e),
            }

    async def create_api_key(
        self,
        page: Page,
        key_name: str = "sinator-key",
        timeout: int = 30000,
    ) -> Dict[str, Any]:
        """
        Erstellt einen neuen Fireworks API-Key.

        Args:
            page: Playwright Page-Objekt
            key_name: Name für den API-Key
            timeout: Timeout in ms

        Returns:
            Dict mit status, api_key, key_name
        """
        start_time = time.time()

        try:
            logger.info(f"Erstelle Fireworks API-Key: {key_name}")
            await page.goto(FIREWORKS_SETTINGS_URL, wait_until="networkidle", timeout=timeout)
            await page.wait_for_timeout(2000)

            # Create API Key Button
            create_selectors = [
                'button:has-text("Create API Key")',
                'button:has-text("New API Key")',
                'button:has-text("Add Key")',
                'button:has-text("Create")',
            ]

            create_btn = None
            for selector in create_selectors:
                try:
                    create_btn = await page.query_selector(selector)
                    if create_btn and await create_btn.is_visible():
                        break
                except Exception:
                    continue

            if not create_btn:
                raise RuntimeError("Create-API-Key-Button nicht gefunden")

            await create_btn.click()
            await page.wait_for_timeout(1500)

            # Key Name eingeben
            name_selectors = [
                'input[name="name"]',
                'input[placeholder*="name" i]',
                'input[placeholder*="Key" i]',
                'input[type="text"]',
            ]

            name_input = None
            for selector in name_selectors:
                try:
                    name_input = await page.query_selector(selector)
                    if name_input and await name_input.is_visible():
                        break
                except Exception:
                    continue

            if name_input:
                await name_input.fill(key_name)
                await page.wait_for_timeout(500)

            # Generate Button
            generate_selectors = [
                'button:has-text("Generate")',
                'button:has-text("Create")',
                'button[type="submit"]',
            ]

            generate_btn = None
            for selector in generate_selectors:
                try:
                    generate_btn = await page.query_selector(selector)
                    if generate_btn and await generate_btn.is_visible():
                        break
                except Exception:
                    continue

            if not generate_btn:
                raise RuntimeError("Generate-Button nicht gefunden")

            await generate_btn.click()
            await page.wait_for_timeout(2000)

            # API-Key auslesen
            api_key = None

            key_selectors = [
                'input[readonly]',
                'code',
                'pre',
                '[data-testid*="api-key"]',
                '.api-key',
                'input[value*="fw_"]',
                'span:has-text("fw_")',
            ]

            for selector in key_selectors:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        val = await el.evaluate("node => node.value || node.textContent")
                        if val and val.strip() and len(val.strip()) > 10:
                            api_key = val.strip()
                            break
                except Exception:
                    continue

            if not api_key:
                # Versuche Copy-Button
                try:
                    copy_btn = await page.query_selector('button:has-text("Copy"), button[title*="copy" i]')
                    if copy_btn:
                        await copy_btn.click()
                        await page.wait_for_timeout(500)
                        api_key = await page.evaluate("() => navigator.clipboard.readText()")
                except Exception:
                    pass

            if not api_key:
                raise RuntimeError("API-Key konnte nicht ausgelesen werden")

            elapsed = time.time() - start_time
            logger.info(f"API-Key generiert: {api_key[:12]}...")

            return {
                "status": "success",
                "api_key": api_key,
                "key_name": key_name,
                "execution_time": f"{elapsed:.2f}s",
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"API-Key-Erstellung fehlgeschlagen: {e}")
            return {
                "status": "failed",
                "api_key": None,
                "key_name": key_name,
                "execution_time": f"{elapsed:.2f}s",
                "error": str(e),
            }


_fireworks_service: Optional[FireworksService] = None


def get_fireworks_service() -> FireworksService:
    """Liefert die Singleton-Instanz des Fireworks-Service."""
    global _fireworks_service
    if _fireworks_service is None:
        _fireworks_service = FireworksService()
    return _fireworks_service
