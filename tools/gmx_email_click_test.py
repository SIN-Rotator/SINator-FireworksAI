"""
GMX Email Click Test - WORKING VERSION
Docs: gmx_email_click_test.doc.md

DISCOVERY: LIST-MAIL-ITEM elements are inside multiple levels of Shadow DOM:
  mail-list-container > shadowRoot > list-mail-list > shadowRoot > list-mail-item

Click via Playwright locator() works. evaluate().click() does NOT work.
Shadow DOM text extraction requires walkShadow() function.
"""
import asyncio, sys, re

sys.path.insert(0, '.')

from sin_browser_tools.core import manager
from sin_browser_tools.tools.accessibility import browser_snapshot_full_oopif
from sin_browser_tools.tools.interaction import browser_click_by_text
from sin_browser_tools.core.spa_waker import SPAWaker


async def click_email_item(frame, index: int = 0):
    """Click email item by index via Playwright locator (NOT evaluate().click())."""
    loc = frame.locator('list-mail-item').nth(index)
    await loc.click(timeout=5000)


def get_shadow_dom_text(frame, max_depth: int = 5) -> str:
    """Walk all shadow DOM levels and return combined text."""
    js = f"""
function() {{
    var result = '';
    function walk(node, depth) {{
        if (depth > {max_depth}) return;
        if (node.shadowRoot) {{
            var children = node.shadowRoot.childNodes;
            for (var i = 0; i < children.length; i++) {{
                var t = children[i].innerText || '';
                if (t.trim().length > 1) result += t.trim() + '\\n';
                walk(children[i], depth + 1);
            }}
        }}
        var children2 = node.childNodes;
        for (var j = 0; j < children2.length; j++) {{
            var t2 = children2[j].innerText || '';
            if (t2.trim().length > 1) result += t2.trim() + '\\n';
            walk(children2[j], depth + 1);
        }}
    }}
    walk(document.body, 0);
    return result;
}}
    """
    return frame.evaluate(js)


async def get_email_items(frame):
    """Get all email items with their IDs and preview text."""
    js = r"""
(function() {
    var mlc = document.querySelector('mail-list-container');
    if (!mlc || !mlc.shadowRoot) return [];
    var mll = mlc.shadowRoot.querySelector('list-mail-list');
    if (!mll || !mll.shadowRoot) return [];
    var lis = mll.shadowRoot.querySelectorAll('list-mail-item');
    var result = [];
    lis.forEach(function(li) {
        var id = li.id || '';
        var txt = (li.innerText || '').trim().substring(0, 100);
        result.push({id: id, text: txt});
    });
    return result;
})()
    """
    return await frame.evaluate(js)


async def main():
    await manager.connect_cdp('http://127.0.0.1:9222')

    gmx_page = None
    for ctx in manager.browser.contexts:
        for pg in ctx.pages:
            if 'navigator.gmx.net' in pg.url:
                gmx_page = pg
                break
        if gmx_page:
            break

    if not gmx_page:
        print('No GMX page found')
        return

    manager.set_active_page(gmx_page)
    print(f'GMX URL: {gmx_page.url[:80]}')

    # 1. Wake GMX SPA
    spa = SPAWaker()
    await spa.wake_gmx_mail(gmx_page)

    # 2. Fresh snapshot (needed after wake)
    await browser_snapshot_full_oopif(pierce=True)

    # 3. Click E-Mail nav button
    res = await browser_click_by_text('E-Mail', role='button')
    print(f'E-Mail click: {res.get("status")} -> {res.get("matched", {}).get("name")}')

    await asyncio.sleep(8)

    # 4. Get mail iframe
    mail_frame = gmx_page.frame('mail')
    if not mail_frame:
        print('No mail frame')
        return
    print(f'Mail frame: {mail_frame.url[:60]}')

    # 5. Get email items
    items = await get_email_items(mail_frame)
    print(f'Email items: {len(items)}')
    for it in items[:3]:
        print(f'  [{it["id"][:20]}] {it["text"][:60]}')

    # 6. Click first item via LOCATOR (not evaluate().click())
    await click_email_item(mail_frame, 0)
    print('Clicked item 0 via locator')

    await asyncio.sleep(5)

    # 7. Read email body
    body = get_shadow_dom_text(mail_frame)
    print(f'Body: {len(body)} chars')

    codes = re.findall(r'\b\d{6}\b', body)
    print(f'6-digit codes: {codes}')

    for line in body.split('\n'):
        if any(k in line.lower() for k in ['fireworks', 'otp', 'verif', 'confirm', 'bestatig', 'konto']):
            print(f'  >> {line[:100]}')

    await manager.cleanup()


if __name__ == '__main__':
    asyncio.run(main())