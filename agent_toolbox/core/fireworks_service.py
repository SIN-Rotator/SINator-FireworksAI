"""
SINATOR — Fireworks Service V5 (Playwright + CUA, 2026-05-21)

Lightweight wrapper replacing the 3103-line CDP fireworks_service.py.
Uses Playwright for form interaction, CUA for React checkboxes.
"""
import logging, re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


async def signup_fireworks(email: str, password: str) -> Dict[str, Any]:
    """Create new Fireworks account via signup form + OTP verification.
    
    Flow:
    1. /signup → fill email → Next → fill 2x password → Create Account
    2. Poll GMX for verification email (via MailCheck extension)
    3. Open verify URL to confirm account
    4. Returns {status, verify_url, steps_completed}
    """
    import asyncio, sys, re as _re
    from playwright.async_api import async_playwright
    from pathlib import Path as _Path
    
    steps = []
    try:
        _sys_path = sys.path.copy()
        sys.path.insert(0, str(_Path(__file__).parent))
        
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            page = await browser.contexts[0].new_page()
            
            # Step 1: Signup form
            await page.goto("https://app.fireworks.ai/signup")
            await asyncio.sleep(5)
            
            # Cookie
            try:
                await page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)
                await asyncio.sleep(2)
            except: pass
            
            # Fill email
            email_inp = page.locator('input[name="email"]').first
            if await email_inp.count() == 0:
                email_inp = page.locator('input[type="email"]').first
            await email_inp.fill(email)
            steps.append("email_filled")
            await asyncio.sleep(1)
            
            # Next
            for btn in await page.locator('button[type="submit"]').all():
                if 'Next' in (await btn.text_content() or ''):
                    await btn.click(force=True); await asyncio.sleep(5)
                    break
            steps.append("next_clicked")
            
            # Fill BOTH passwords
            pws = await page.locator('input[type="password"]').all()
            if len(pws) >= 2:
                for pw in pws[:2]:
                    await pw.click(); await asyncio.sleep(0.2)
                    await pw.fill("")
                    await pw.type(password, delay=40)
                    await asyncio.sleep(0.3)
                steps.append("passwords_filled")
                await asyncio.sleep(1)
                
                # Create Account
                for btn in await page.locator('button[type="submit"]').all():
                    if 'Create Account' in (await btn.text_content() or ''):
                        await btn.click(force=True); await asyncio.sleep(8)
                        logger.info("Create Account clicked")
                        break
                steps.append("create_clicked")
            
            # Step 2: Poll for OTP email
            logger.info("Waiting for Fireworks verification email...")
            verify_url = None
            from gmx_service import GmxService
            svc = GmxService()
            
            for attempt in range(10):
                await asyncio.sleep(10)
                verify_url = await svc.read_fireworks_verification_email()
                if verify_url:
                    logger.info(f"✅ OTP found (attempt {attempt+1})")
                    break
                logger.info(f"OTP poll {attempt+1}/10...")
            
            if not verify_url:
                steps.append("otp_not_found")
                return {"status": "partial", "steps_completed": steps, "error": "OTP email not found after 10 attempts"}
            
            steps.append("otp_found")
            
            # Step 3: Verify account
            verified = await verify_account(verify_url)
            if verified:
                steps.append("account_verified")
                logger.info("✅ Account verified")
            else:
                steps.append("verify_failed")
            
            return {
                "status": "success",
                "verify_url": verify_url,
                "steps_completed": steps,
            }
            
    except Exception as e:
        logger.error(f"Signup error: {e}")
        return {"status": "error", "steps_completed": steps, "error": str(e)}


async def login_fireworks(email: str, password: str) -> Dict[str, Any]:
    """Login to Fireworks via Playwright + CUA onboarding.
    Returns: {status, steps_completed, error}"""
    import asyncio, json, subprocess
    from playwright.async_api import async_playwright

    steps = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            page = await browser.contexts[0].new_page()

            await page.goto("https://app.fireworks.ai/login")
            await asyncio.sleep(4)

            # Cookie accept
            try:
                await page.locator('button:has-text("Accept All")').first.click(force=True, timeout=5000)
                await asyncio.sleep(2)
            except: pass

            # Email Login
            await page.locator('a:has-text("Email Login")').first.click()
            await asyncio.sleep(4)
            steps.append("login_page")

            # Fill credentials
            await page.locator('input[name="email"]').first.fill(email)
            await page.locator('input[name="password"]').first.fill(password)
            steps.append("credentials_filled")

            # Submit
            for btn in await page.locator('button[type="submit"]').all():
                if 'Next' in (await btn.text_content() or ''):
                    await btn.click()
                    await asyncio.sleep(6)
                    break
            steps.append("form_submitted")

            # Onboarding via CUA
            if 'onboarding' in page.url:
                logger.info("Onboarding — via CUA")
                res = subprocess.run(["cua-driver", "call", "list_windows"],
                    capture_output=True, text=True, timeout=10,
                    input=json.dumps({"query": "Chrome"}))
                for w in json.loads(res.stdout).get('windows', []):
                    if 'Google Chrome' == w.get('app_name', '') and w.get('is_on_screen') and 'Fireworks' in w.get('title', ''):
                        pid, wid = w['pid'], w['window_id']
                        # Names
                        for el_idx, name in [(124, "Super"), (128, "Cheetah")]:
                            subprocess.run(["cua-driver", "call", "click"],
                                capture_output=True, text=True, timeout=10,
                                input=json.dumps({"pid": pid, "window_id": wid, "element_index": el_idx}))
                            await asyncio.sleep(0.3)
                            subprocess.run(["cua-driver", "call", "type_text"],
                                capture_output=True, text=True, timeout=5,
                                input=json.dumps({"pid": pid, "text": name}))
                            await asyncio.sleep(0.3)
                        # Terms + Continue
                        subprocess.run(["cua-driver", "call", "click"],
                            capture_output=True, text=True, timeout=10,
                            input=json.dumps({"pid": pid, "window_id": wid, "element_index": 129}))
                        await asyncio.sleep(0.3)
                        subprocess.run(["cua-driver", "call", "click"],
                            capture_output=True, text=True, timeout=10,
                            input=json.dumps({"pid": pid, "window_id": wid, "element_index": 137}))
                        await asyncio.sleep(6)
                        # Use-cases
                        for uc_idx in [112, 115, 145, 151]:
                            subprocess.run(["cua-driver", "call", "click"],
                                capture_output=True, text=True, timeout=5,
                                input=json.dumps({"pid": pid, "window_id": wid, "element_index": uc_idx}))
                        await asyncio.sleep(0.2)
                        subprocess.run(["cua-driver", "call", "click"],
                            capture_output=True, text=True, timeout=10,
                            input=json.dumps({"pid": pid, "window_id": wid, "element_index": 160}))
                        await asyncio.sleep(6)
                        break
                steps.append("onboarding_complete")

            if 'home' in page.url or 'account' in page.url:
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}

            return {"status": "error", "steps_completed": steps, "error": f"Login failed: {page.url[:80]}"}

    except Exception as e:
        logger.error(f"Fireworks login error: {e}")
        return {"status": "error", "steps_completed": steps, "error": str(e)}


async def create_api_key(key_name: str = "sinator-key") -> Dict[str, Any]:
    """Create Fireworks API Key via Playwright. Returns {status, api_key, error}"""
    import asyncio
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            for pg in browser.contexts[0].pages:
                if 'fireworks' in pg.url and ('home' in pg.url or 'account' in pg.url):
                    await pg.goto("https://app.fireworks.ai/settings/users/api-keys")
                    await asyncio.sleep(5)

                    for btn in await pg.locator('button').all():
                        if 'Create API Key' == (await btn.text_content() or '').strip():
                            await btn.click(force=True); await asyncio.sleep(2)
                            break

                    await pg.locator('[role="menuitem"]:has-text("API Key")').first.click(force=True)
                    await asyncio.sleep(3)

                    for inp in await pg.locator('input').all():
                        if 'name' in (await inp.get_attribute('name') or '').lower():
                            await inp.fill(key_name); break

                    for btn in await pg.locator('button').all():
                        if 'Generate' in (await btn.text_content() or '').strip():
                            await btn.click(force=True); await asyncio.sleep(5)
                            break

                    content = await pg.content()
                    text = await pg.evaluate("() => document.body.innerText")
                    keys = re.findall(r'fw_[a-zA-Z0-9]{20,}', content + text)
                    if keys:
                        logger.info(f"API Key created: {keys[0][:12]}...")
                        return {"status": "success", "api_key": keys[0]}

            return {"status": "error", "error": "API Key not found on page"}

    except Exception as e:
        logger.error(f"API Key error: {e}")
        return {"status": "error", "error": str(e)}


async def verify_account(verify_url: str) -> bool:
    """Open Fireworks verify URL to confirm account. Returns True if confirmed."""
    import asyncio
    from playwright.async_api import async_playwright
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            page = await browser.contexts[0].new_page()
            await page.goto(verify_url)
            await asyncio.sleep(5)
            logger.info(f"Verify URL opened: {page.url[:80]}")
            await page.close()
            return True
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return False
