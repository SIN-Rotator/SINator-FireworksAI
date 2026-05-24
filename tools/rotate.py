#!/usr/bin/env python3
"""
SINator — Single Command Rotation Tool V6 (2026-05-22)
 
 GMX Login (built-in) → Alias Rotation → Fireworks Signup → OTP → Verify → Login → Onboarding → API Key — in einem Lauf.

Usage:
    python tools/rotate.py              # Auto-generated alias
    python tools/rotate.py my-alias-123 # Specific alias name
"""
import sys
import os
import asyncio
import time
import logging
import argparse
import re as _re_inner
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("rotate")

# Add SINator core to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))


async def main():
    parser = argparse.ArgumentParser(description="GMX + Fireworks Rotation")
    parser.add_argument("alias", nargs="?", help="Optional alias name")
    parser.add_argument("--password", default="ZOE.jerry2024!", help="Fireworks password")
    parser.add_argument("--save", action="store_true", default=True, help="Save API key to pool")
    parser.add_argument("--cdp-port", type=int, default=9222, help="CDP port for Chrome")
    parser.add_argument("--chrome-pid", type=int, default=None, help="PID of Chrome process for CUA targeting")
    args = parser.parse_args()
    CDP = f"http://127.0.0.1:{args.cdp_port}"

    import subprocess as _sp_cleanup
    try:
        _lsof = _sp_cleanup.run(["lsof", "-i", f":{args.cdp_port}", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=5)
        for _line in _lsof.stdout.split('\n')[1:]:
            _parts = _line.split()
            if len(_parts) >= 2 and _parts[1].isdigit():
                os.environ["SINATOR_CHROME_PID"] = _parts[1]
                logger.info(f"Chrome PID: {_parts[1]} (port {args.cdp_port})")
                break
    except Exception:
        pass

    from pool_manager import PoolManager
    pool = PoolManager()

    t0 = time.time()

    # ═══ Step 0: GMX Login (frische Session) ═══
    logger.info("=== GMX Login ===")
    from playwright.async_api import async_playwright as _ap
    async with _ap() as _p:
        _b = await _p.chromium.connect_over_cdp(CDP)
        for _old in list(_b.contexts[0].pages):
            try:
                _url = _old.url
                if 'localhost:3000' in _url or 'localhost:8000' in _url:
                    pass
                elif 'gmx' in _url.lower() or 'fireworks' in _url.lower() or 'about:blank' in _url or 'chrome://newtab' in _url or 'chrome://new-tab' in _url or 'mail_settings' in _url:
                    await _old.close()
            except: pass
        _pg = await _b.contexts[0].new_page()
        await _pg.goto("https://www.gmx.net/")
        await asyncio.sleep(3)

        # Cookie banner accept
        try:
            ck = _pg.locator('button:has-text("Accept All")').first
            if await ck.count() > 0:
                await ck.click(force=True); await asyncio.sleep(1)
        except: pass

        # Check if already logged in (session restored from Chrome profile)
        _all_btn_texts = [(await _btn.text_content() or "").strip().lower() for _btn in await _pg.locator('button').all()]
        _is_logged_in = any(t in ('logout', 'zum postfach', 'account wechseln') for t in _all_btn_texts)
        _has_login_btn = any(t in ('login', 'anmelden', 'einloggen') for t in _all_btn_texts)

        if _is_logged_in:
            logger.info("✅ Bereits eingeloggt (Session restored)")
            # Navigate to inbox to refresh SID
            for _btn in await _pg.locator('button').all():
                _t = (await _btn.text_content() or "").strip().lower()
                if _t in ('zum postfach', 'e-mail'):
                    await _btn.click(force=True); await asyncio.sleep(3); break
        elif _has_login_btn:
            for _btn in await _pg.locator('button').all():
                _t = (await _btn.text_content() or "").strip().lower()
                if _t in ('login', 'anmelden', 'einloggen'):
                    await _btn.click(force=True); await asyncio.sleep(3); break

            # Email field
            _email = _pg.locator('input[type="email"]').first
            if await _email.count() == 0:
                _email = _pg.locator('input[name="username"]').first
            if await _email.count() > 0:
                await _email.fill("opensin@gmx.de")
                await asyncio.sleep(1)

                for _btn in await _pg.locator('button').all():
                    _t = (await _btn.text_content() or "").strip().lower()
                    if _t in ('weiter', 'next', 'continue'):
                        await _btn.click(force=True); await asyncio.sleep(2); break

                _pw = _pg.locator('input[type="password"]').first
                if await _pw.count() > 0:
                    await _pw.fill("ZOE.jerry2024")
                    await asyncio.sleep(1)
                    for _btn in await _pg.locator('button').all():
                        _t = (await _btn.text_content() or "").strip().lower()
                        if _t in ('login', 'anmelden', 'einloggen'):
                            await _btn.click(force=True); await asyncio.sleep(4); break

        await asyncio.sleep(2)
        if "sid=" in _pg.url or "navigator.gmx.net" in _pg.url or "bap.navigator.gmx.net" in _pg.url:
            logger.info("✅ GMX Login erfolgreich")
            import json as _json
            _cookies = await _b.contexts[0].cookies()
            _json.dump(_cookies, open("data/gmx-cookies.json", "w"), indent=2)
        else:
            logger.warning("⚠️ GMX Login fehlgeschlagen")
        # Keep page open so GmxService can find it via CDP+CUA

    # ═══ Step 1: GMX Alias Rotation (via GmxService — CUA + Playwright) ═══
    logger.info("=== GMX Alias Rotation ===")
    from gmx_service import GmxService
    svc = GmxService()
    result = await svc.rotate_alias(new_alias_name=args.alias, cdp_port=args.cdp_port)
    if result.get('status') != 'success':
        logger.error(f"❌ GMX rotation failed: {result.get('error')}")
        return
    alias = result.get('created_alias')
    logger.info(f"✅ GMX Alias: {alias} ({result.get('execution_time')})")

    # ═══ Steps 2-3: Fireworks Account + API Key (ONE Playwright instance) ═══
    logger.info("=== Fireworks Account ===")
    from fireworks_service import signup_fireworks

    # First: LOGOUT from any existing Fireworks session (separate PW for cleanup)
    logger.info("Logout from existing Fireworks session...")
    async with _ap() as _p2:
        _b2 = await _p2.chromium.connect_over_cdp(CDP)
        for _pg in _b2.contexts[0].pages:
            if 'fireworks' in _pg.url.lower():
                await _pg.close()
        _cdp = await _b2.contexts[0].new_cdp_session(_b2.contexts[0].pages[0] if _b2.contexts[0].pages else await _b2.contexts[0].new_page())
        all_cookies = await _cdp.send("Network.getAllCookies")
        for ck in all_cookies.get('cookies', []):
            if 'fireworks' in ck.get('domain', ''):
                try:
                    await _cdp.send("Network.deleteCookies", {"name": ck['name'], "domain": ck['domain']})
                except: pass
        await _cdp.send("Network.clearBrowserCookies")
        logger.info("Fireworks logout + cookies cleared")

    # Try signup (new account)
    logger.info("Attempting signup...")
    signup_result = await signup_fireworks(alias, args.password)
    if signup_result.get('status') == 'success':
        logger.info("✅ Fireworks signup + verify OK")
    else:
        logger.info(f"Signup: {signup_result.get('status')} — trying login")

    # ═══ Login + API Key in ONE Playwright session ═══
    import json as _json_inner, subprocess as _sp
    key_name = alias.split("@")[0].split("-")[0] if alias else "sinator-key"
    api_key = None

    async with _ap() as _p3:
        _b3 = await _p3.chromium.connect_over_cdp(CDP)
        _page = await _b3.contexts[0].new_page()

        # --- LOGIN ---
        await _page.goto("https://app.fireworks.ai/login")
        await asyncio.sleep(2)

        try:
            await _page.locator('button:has-text("Accept All")').first.click(force=True, timeout=3000)
            await asyncio.sleep(1)
        except: pass

        for attempt in range(3):
            try:
                em = _page.locator('a:has-text("Email Login")').first
                if await em.count() > 0:
                    await em.click()
                else:
                    await _page.goto("https://app.fireworks.ai/login?useEmail=true")
                await asyncio.sleep(2)
                if await _page.locator('input[name="email"]').first.count() > 0:
                    break
                await _page.goto("https://app.fireworks.ai/login?useEmail=true")
                await asyncio.sleep(2)
                if await _page.locator('input[name="email"]').first.count() > 0:
                    break
            except: pass
            await asyncio.sleep(2)

        await _page.locator('input[name="email"]').first.fill(alias)
        await _page.locator('input[name="password"]').first.fill(args.password)
        await asyncio.sleep(1)

        for btn in await _page.locator('button[type="submit"]').all():
            if 'Next' in (await btn.text_content() or ''):
                await btn.click(force=True); await asyncio.sleep(5); break

        # --- ONBOARDING (CUA-first, Playwright fallback) ---
        _logged_in = False
        if 'onboarding' in _page.url:
            logger.info("Onboarding — trying CUA first (AXPress works for React checkboxes)")
            try:
                from cua_helper import find_cua_window
                _cua_result = find_cua_window(title_keywords=["fireworks"])
                if _cua_result:
                    _pid, _wid = _cua_result
                    def _cua_click(e): _sp.run(["cua-driver", "call", "click"], capture_output=True, text=True, timeout=10,
                        input=_json_inner.dumps({"pid": _pid, "window_id": _wid, "element_index": e}))
                    def _cua_type(t): _sp.run(["cua-driver", "call", "type_text"], capture_output=True, text=True, timeout=5,
                        input=_json_inner.dumps({"pid": _pid, "text": t}))
                    def _cua_scan():
                        from cua_helper import cua_get_window_state
                        return cua_get_window_state(_pid, _wid)
                    def _cua_find(t, elt="AXButton"):
                        for ln in _cua_scan().split('\n'):
                            s = ln.strip()
                            if t in s and elt in s:
                                m2 = _re_inner.search(r'\]?\s*-\s*\[(\d+)\]', s)
                                if m2: return int(m2.group(1))
                        return None
                    
                    for nm, target in [("Super", "First"), ("Cheetah", "Last")]:
                        el = _cua_find(target, "AXTextField")
                        if el:
                            _cua_click(el); await asyncio.sleep(0.3)
                            _cua_type(nm); await asyncio.sleep(0.3)

                    el = _cua_find("agree", "AXCheckBox")
                    if el: _cua_click(el); await asyncio.sleep(0.3)

                    el = _cua_find("Continue")
                    if el: _cua_click(el); await asyncio.sleep(3)

                    for uc in ["Prototype", "Flexible", "Conversational", "Search"]:
                        el = _cua_find(uc, "AXCheckBox")
                        if el: _cua_click(el); await asyncio.sleep(0.2)

                    el = _cua_find("Submit")
                    if el: _cua_click(el)

                    for _ in range(10):
                        await asyncio.sleep(2)
                        try:
                            if any(x in _page.url for x in ['home', 'account', 'settings']):
                                logger.info("CUA onboarding → redirect OK")
                                _logged_in = True; break
                        except: pass
            except Exception as e:
                logger.warning(f"CUA onboarding failed: {e}")

            if not _logged_in:
                logger.info("CUA failed — Playwright fallback (type() with delay for React)")
                try:
                    fn = _page.locator('input[name="firstName"]').first
                    if await fn.count() == 0: fn = _page.locator('input[name="first"]').first
                    if await fn.count() > 0:
                        await fn.click(); await asyncio.sleep(0.2)
                        await fn.type("Super", delay=50); await asyncio.sleep(0.3)

                    ln = _page.locator('input[name="lastName"]').first
                    if await ln.count() == 0: ln = _page.locator('input[name="last"]').first
                    if await ln.count() > 0:
                        await ln.click(); await asyncio.sleep(0.2)
                        await ln.type("Cheetah", delay=50); await asyncio.sleep(0.3)

                    for cb in await _page.locator('input[type="checkbox"]').all():
                        try:
                            aid = (await cb.get_attribute('aria-label') or '').lower()
                            nid = (await cb.get_attribute('id') or '').lower()
                            if 'terms' in aid or 'agree' in aid or 'terms' in nid:
                                await cb.click(force=True); await asyncio.sleep(0.2); break
                        except: pass

                    for btn in await _page.locator('button').all():
                        try:
                            t = (await btn.text_content() or '').strip()
                            if 'Continue' in t or 'Next' in t:
                                await btn.click(force=True); await asyncio.sleep(3); break
                        except: pass

                    for uc in ["Prototype", "Flexible capacity", "Conversational", "Search"]:
                        try:
                            for cb in await _page.locator('input[type="checkbox"]').all():
                                try:
                                    aid = (await cb.get_attribute('aria-label') or '').lower()
                                    nid = (await cb.get_attribute('id') or '').lower()
                                    if 'cky' in nid: continue
                                    if uc.lower() in aid:
                                        await cb.click(force=True); await asyncio.sleep(0.2); break
                                except: pass
                        except: pass

                    for btn in await _page.locator('button').all():
                        try:
                            t = (await btn.text_content() or '').strip()
                            if 'Submit' in t or 'Get' in t:
                                await btn.click(force=True); await asyncio.sleep(2); break
                        except: pass

                    for _ in range(20):
                        await asyncio.sleep(2)
                        try:
                            if any(x in _page.url for x in ['home', 'account', 'settings']):
                                logger.info("Playwright onboarding → redirect OK")
                                _logged_in = True; break
                        except: pass
                except Exception as e:
                    logger.warning(f"Playwright onboarding failed: {e}")
        else:
            _logged_in = True

        if _logged_in:
            logger.info("✅ Fireworks Login + Onboarding OK")
        else:
            logger.warning("⚠️ Onboarding may not have completed")
            # Force navigate to home and hope session works
            await _page.goto("https://app.fireworks.ai/", wait_until='domcontentloaded')
            await asyncio.sleep(2)

        logger.info("=== API Key ===")
        for _api_retry in range(3):
            api_key = None
            await _page.goto("https://app.fireworks.ai/settings/users/api-keys", wait_until='domcontentloaded')
            await asyncio.sleep(3)

            if 'login' in _page.url.lower():
                logger.error("API keys redirect to login — session lost")
                break

            try:
                for _ in range(2):
                    for btn in await _page.locator('button').all():
                        t = (await btn.text_content() or '').strip()
                        if t in ('Accept All', 'Reject All'):
                            await btn.click(force=True); await asyncio.sleep(1); break
            except: pass

            _found_create = False
            for btn in await _page.locator('button').all():
                if 'Create API Key' in (await btn.text_content() or ''):
                    await btn.click(force=True); await asyncio.sleep(2)
                    _found_create = True; break
            if not _found_create:
                await asyncio.sleep(5)
                for btn in await _page.locator('button').all():
                    if 'Create API Key' in (await btn.text_content() or ''):
                        await btn.click(force=True); await asyncio.sleep(2)
                        _found_create = True; break

            mi = _page.locator('[role="menuitem"]:has-text("API Key")')
            for _ in range(5):
                if await mi.count() > 0: break
                await asyncio.sleep(1)
            if await mi.count() > 0:
                await mi.first.click(force=True); await asyncio.sleep(2)

            _name_inp = _page.locator('input[name="name"]').first
            if await _name_inp.count() > 0:
                await _name_inp.click(); await asyncio.sleep(0.2)
                await _name_inp.type(key_name, delay=40); await asyncio.sleep(1)
            else:
                for inp in await _page.locator('input').all():
                    if 'name' in (await inp.get_attribute('name') or '').lower():
                        await inp.click(); await asyncio.sleep(0.2)
                        await inp.type(key_name, delay=40); await asyncio.sleep(1); break

            _generate_clicked = False
            for _ in range(15):
                for btn in await _page.locator('button').all():
                    t = (await btn.text_content() or '').strip()
                    if 'Generate' in t and not await btn.is_disabled():
                        await btn.click(force=True); await asyncio.sleep(1)
                        _generate_clicked = True; break
                if _generate_clicked: break
                await asyncio.sleep(1)

            if not _generate_clicked:
                logger.warning(f"Generate button not found/clicked (retry {_api_retry+1}/3)")
                continue

            for _ in range(20):
                body = await _page.evaluate("document.body.innerText")
                m = _re_inner.search(r'fw_[a-zA-Z0-9]{20,}', body)
                if m:
                    api_key = m.group(0)
                    logger.info(f"✅ API Key: {api_key}")
                    break
                if 'Missing' in body and 'Name' in body:
                    logger.warning("Missing Name modal — closing + retry")
                    for btn in await _page.locator('button').all():
                        t = (await btn.text_content() or '').strip()
                        if t in ['Close', 'Cancel', 'OK', '×']:
                            await btn.click(force=True); await asyncio.sleep(1); break
                    break
                await asyncio.sleep(1)

            if api_key:
                break
            logger.warning(f"API key not extracted (retry {_api_retry+1}/3)")

    if not api_key:
        logger.error("❌ API Key creation failed")
        return

    # ═══ Step 4: Save to pool ═══
    if args.save:
        pool.add_key(api_key=api_key, alias_email=alias, key_name=key_name)
        logger.info(f"✅ Saved to pool ({pool.get_stats()['total']} keys total)")

    elapsed = time.time() - t0
    logger.info(f"\n🎉 ROTATION COMPLETE — {elapsed:.1f}s")
    logger.info(f"   Alias:   {alias}")
    logger.info(f"   API Key: {api_key}")


if __name__ == "__main__":
    asyncio.run(main())
