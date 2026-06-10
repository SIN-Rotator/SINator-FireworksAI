#!/usr/bin/env python3
"""Test: OTP via GMX MailCheck Extension + CDP OOPIF attachment.

Restored from commit 7ce418a (2026-05-21) — the working approach.

Docs: test_otp_mailcheck.doc.md
"""
import asyncio
import sys
import re
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

from playwright.async_api import async_playwright
from cdp_client import CDPClient, get_browser_ws_endpoint

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("otp_test")

CDP_PORT = 9222
EXT_URL = "chrome-extension://camnampocfohlcgbajligmemmabnljcm/pages/mail-panel.html"


async def cdp_get_targets():
    """Get all CDP targets."""
    ws_url = await get_browser_ws_endpoint(CDP_PORT)
    client = CDPClient(ws_url)
    await client.connect()
    targets = await client.get_targets()
    await client.disconnect()
    return targets


async def main():
    logger.info("=== OTP MailCheck Extension Test ===")
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        
        # Step 1: Open MailCheck extension popup
        logger.info("Step 1: Opening MailCheck extension...")
        ext_page = await browser.contexts[0].new_page()
        await ext_page.goto(EXT_URL, wait_until="domcontentloaded")
        await asyncio.sleep(5)
        
        # Dump what we see
        text = await ext_page.evaluate("() => document.body.innerText")
        logger.info(f"MailCheck content ({len(text)} chars):")
        for line in text.split('\n')[:30]:
            logger.info(f"  {line.strip()[:120]}")
        
        # Check for Fireworks emails
        if 'fireworks' not in text.lower():
            logger.warning("No Fireworks emails found in MailCheck")
            # Show all email subjects
            subjects = await ext_page.evaluate("""
                () => {
                    const emails = document.querySelectorAll('[data-email-id]');
                    return Array.from(emails).map(e => ({
                        id: e.getAttribute('data-email-id'),
                        text: e.innerText.substring(0, 100)
                    }));
                }
            """)
            logger.info(f"Available emails: {subjects}")
            await ext_page.close()
            return
        
        # Step 2: Record existing targets
        logger.info("Step 2: Recording existing CDP targets...")
        existing_ids = {t['targetId'] for t in (await cdp_get_targets())}
        logger.info(f"  {len(existing_ids)} existing targets")
        
        # Step 3: Click Fireworks email
        logger.info("Step 3: Clicking Fireworks verification email...")
        click_result = await ext_page.evaluate("""
            () => {
                const emails = document.querySelectorAll('[data-email-id]');
                for (const e of emails) {
                    const txt = e.innerText.toLowerCase();
                    if (txt.includes('fireworks') && 
                        (txt.includes('verify') || txt.includes('confirm') || txt.includes('welcome'))) {
                        e.click();
                        return {clicked: true, emailId: e.getAttribute('data-email-id'), preview: e.innerText.substring(0, 80)};
                    }
                }
                // Fallback: click any fireworks email
                for (const e of emails) {
                    if (e.innerText.toLowerCase().includes('fireworks')) {
                        e.click();
                        return {clicked: true, emailId: e.getAttribute('data-email-id'), preview: e.innerText.substring(0, 80), fallback: true};
                    }
                }
                return {clicked: false};
            }
        """)
        logger.info(f"  Click result: {click_result}")
        
        await asyncio.sleep(5)
        await ext_page.close()
        
        if not click_result.get('clicked'):
            logger.warning("Could not click any Fireworks email")
            return
        
        # Step 4: Find new mailbody-ui.de OOPIF
        logger.info("Step 4: Searching for mailbody-ui.de OOPIF...")
        targets = await cdp_get_targets()
        
        mailbody_target = None
        for t in targets:
            url = t.get('url', '')
            tid = t['targetId']
            is_new = tid not in existing_ids
            if 'mailbody-ui.de' in url:
                logger.info(f"  Found mailbody-ui.de: {url[:80]} (new={is_new})")
                if is_new:
                    mailbody_target = t
        
        if not mailbody_target:
            # Fallback: any mailbody-ui.de target
            for t in targets:
                if 'mailbody-ui.de' in t.get('url', ''):
                    mailbody_target = t
                    logger.info(f"  Using existing mailbody-ui.de: {t['url'][:80]}")
                    break
        
        if not mailbody_target:
            logger.error("mailbody-ui.de OOPIF not found!")
            # Show all targets
            for t in targets:
                url = t.get('url', '')[:100]
                if 'mail' in url.lower() or 'gmx' in url.lower():
                    logger.info(f"  Target: {url}")
            return
        
        # Step 5: Attach OOPIF + extract content
        logger.info("Step 5: Attaching to OOPIF...")
        ws_url = await get_browser_ws_endpoint(CDP_PORT)
        client = CDPClient(ws_url)
        await client.connect()
        
        sid = await client.attach_to_target(mailbody_target['targetId'])
        await client.send_to_session(sid, "Runtime.enable")
        
        logger.info("Step 6: Extracting email body...")
        result = await client.send_to_session(sid, "Runtime.evaluate", {
            "expression": "document.body.innerText",
            "returnByValue": True
        })
        
        text = result.get('result', {}).get('value', '')
        logger.info(f"  Email body ({len(text)} chars):")
        for line in text.split('\n')[:20]:
            logger.info(f"  {line.strip()[:120]}")
        
        await client.disconnect()
        
        # Step 7: Extract verify URL
        urls = re.findall(r'https?://app\.fireworks\.ai/[^\s"\'<>]+', text)
        verify_urls = [u for u in urls if any(k in u.lower() for k in ['confirm', 'verify', 'token', 'auth', 'activate'])]
        
        if verify_urls:
            logger.info(f"✅ VERIFY URL: {verify_urls[0]}")
        elif urls:
            logger.info(f"⚠️  Fireworks URLs found (not verify): {urls}")
        else:
            logger.warning("❌ No verify URL found in email body")
            # Show all URLs
            all_urls = re.findall(r'https?://[^\s"\'<>]+', text)
            logger.info(f"  All URLs in body: {all_urls[:10]}")


if __name__ == "__main__":
    asyncio.run(main())
