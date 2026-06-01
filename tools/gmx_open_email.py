#!/usr/bin/env python3
"""GMX Email opener — finds Fireworks OTP/verify emails, clicks them, reads body.

V18.1: Complete rework with new frame tools (Issue #11 fix).

Flow:
  1. Connect to Chrome CDP
  2. Find GMX webmailer frame
  3. Scan email list via shadow DOM pierce (browser_eval_in_frame)
  4. Click latest Fireworks email via Playwright locator
  5. Scan ALL Playwright frames for email body content
  6. Extract verify URL or OTP code via regex
  7. Return structured result

Usage:
    python3 tools/gmx_open_email.py [--keyword fireworks] [--timeout 30]
"""
import sys, asyncio, argparse, re, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gmx_open_email")

VERIFY_URL_RE = re.compile(
    r'https://app\.fireworks\.ai/signup/confirm\?[^\s"\'<>]+'
)
OTP_RE = re.compile(r'confirmation_code=(\d{6})')

# JS: Find Fireworks emails in the GMX mail list shadow DOM
FIND_FIREWORKS_JS = """
function() {
    var mlc = document.querySelector('mail-list-container');
    if (!mlc || !mlc.shadowRoot) return [];
    var mll = mlc.shadowRoot.querySelector('list-mail-list');
    if (!mll || !mll.shadowRoot) return [];
    var items = mll.shadowRoot.querySelectorAll('list-mail-item');
    var result = [];
    items.forEach(function(li, idx) {
        var txt = (li.innerText || '').trim().toLowerCase();
        if (txt.includes('fireworks')) {
            result.push({idx: idx, text: (li.innerText || '').trim().substring(0, 200)});
        }
    });
    return result.sort(function(a,b){return b.idx - a.idx;});
}
"""


async def find_gmx_page(browser):
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if 'navigator.gmx.net/mail' in pg.url:
                return pg
    return None


async def navigate_to_gmx(page):
    await page.goto("https://www.gmx.net/", wait_until="domcontentloaded")
    await asyncio.sleep(3)
    zum = page.get_by_text("Zum Postfach").first
    if await zum.is_visible():
        await zum.click()
        await asyncio.sleep(8)
    return page


async def get_mail_frame(page):
    for f in page.frames:
        if f.name == "mail":
            return f
    return None


async def find_fireworks_emails(mail_frame):
    from sin_browser_tools.tools.frames import browser_eval_in_frame
    from sin_browser_tools.core import manager

    if hasattr(manager, '_active_page'):
        result = await browser_eval_in_frame(FIND_FIREWORKS_JS, frame_name="mail")
        return result.get('result') or result.get('items') or []
    else:
        data = await mail_frame.evaluate(FIND_FIREWORKS_JS)
        return data


async def click_email(mail_frame, index):
    loc = mail_frame.locator('list-mail-item').nth(index)
    await loc.click(timeout=8000, force=True)
    await asyncio.sleep(8)


async def scan_frames_for_body(page):
    results = []
    for f in page.frames:
        try:
            txt = await f.evaluate(
                "document.body ? document.body.innerText : ''"
            )
        except Exception:
            txt = ''
        if txt and len(txt) > 50:
            m_url = VERIFY_URL_RE.search(txt)
            m_otp = OTP_RE.search(txt)
            if m_url or ('verify' in txt.lower() and 'fireworks' in txt.lower()):
                results.append({
                    'url': m_url.group(0) if m_url else None,
                    'otp': m_otp.group(1) if m_otp else None,
                    'text': txt[:2000],
                    'frame_url': f.url[:80],
                    'frame_name': f.name or '',
                })
    return results


async def main():
    ap = argparse.ArgumentParser(description="GMX OTP Email öffnen + lesen (V18.1)")
    ap.add_argument("--keyword", default="fireworks", help="Keyword im Mail-Text")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--port", type=int, default=9222)
    args = ap.parse_args()

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{args.port}")
        page = await find_gmx_page(browser)

        if not page:
            logger.info("Keine GMX-Seite gefunden — navigiere...")
            page = browser.contexts[0].pages[0]
            page = await navigate_to_gmx(page)

        logger.info(f"GMX URL: {page.url[:80]}")

        mail_frame = await get_mail_frame(page)
        if not mail_frame:
            logger.error("Kein mail-Frame gefunden!")
            return

        logger.info(f"Mail frame: {mail_frame.url[:60]}")

        # Find Fireworks emails
        try:
            from sin_browser_tools.core import manager
            from sin_browser_tools.tools.frames import browser_eval_in_frame

            sin_browser_mgr = manager._require()
            sin_browser_mgr._active_page = page
            sin_browser_mgr._context = page.context

            fw = await browser_eval_in_frame(FIND_FIREWORKS_JS, frame_name="mail")
            fireworks = fw.get('result', [])
        except Exception:
            fireworks = await mail_frame.evaluate(FIND_FIREWORKS_JS)

        if not fireworks:
            logger.warning(f"Keine Fireworks Mails gefunden!")
            return

        logger.info(f"Fireworks Mails: {len(fireworks)}")
        fw_idx = fireworks[0]['idx']
        logger.info(f"Klicke Mail #{fw_idx}: {fireworks[0]['text'][:80]}")

        # Click
        await click_email(mail_frame, fw_idx)

        # Scan frames for body
        bodies = await scan_frames_for_body(page)
        logger.info(f"Frames mit Inhalt: {len(bodies)}")

        for b in bodies:
            if b['url']:
                logger.info(f"✅ Verify-URL: {b['url']}")
            if b['otp']:
                logger.info(f"🔑 OTP-Code: {b['otp']}")
            print(f"\n{b['text'][:1500]}")

        if not bodies:
            logger.warning("Kein Email-Body gefunden!")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
