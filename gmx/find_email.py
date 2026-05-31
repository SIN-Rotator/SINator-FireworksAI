#!/usr/bin/env python3
"""
gmx.find_email — Find an email by keyword and open it (Shadow-DOM aware).

This is the library version of the original tools/gmx_open_email.py: it ONLY
finds and opens an email. It penetrates the GMX webmailer Shadow DOM
(sc-webmailer-mail-list-h), locates the first mail whose text contains the
keyword, clicks it and scans the opened mail body for a verify/confirm URL.

It does NOT log in (use gmx.login) and does NOT launch a browser — it attaches
to the running Chrome via CDP (default port 9222).

CLI:     python3 -m gmx.find_email [--keyword fireworks] [--timeout 8] [--port 9222]
Compose: from gmx import find_email; res = await find_email()

Returns: {"status": "found" | "not_found" | "not_logged_in" | "error",
          "verify_url": "https://app.fireworks.ai/...",
          "matches": int, "frame": "...", "text_preview": "...", "error": "..."}
"""

import asyncio
import re
import html as html_module
from typing import Any, Dict

from gmx._lib import run, DEFAULT_CDP_PORT

_SCAN_JS = r"""
(() => {
    const KW = (arguments[0] || '').toLowerCase();
    let out = [];
    function getText(el) {
        let txt = (el.innerText || el.textContent || '').trim();
        if (el.shadowRoot) {
            const st = el.shadowRoot.body
                ? el.shadowRoot.body.innerText
                : (el.shadowRoot.documentElement ? el.shadowRoot.documentElement.innerText : '');
            if (st && st.trim()) txt = txt ? txt + ' ' + st.trim() : st.trim();
        }
        return txt;
    }
    function walk(root) {
        let nodes;
        try { nodes = root.querySelectorAll('*'); } catch (e) { return; }
        for (const el of nodes) {
            const txt = getText(el);
            if (txt && txt.toLowerCase().includes(KW)) {
                const id = (el.getAttribute('id') || '').replace(/^id/, '') || null;
                out.push({mailId: id, tag: (el.tagName || '').toLowerCase(),
                          text: txt.slice(0, 400), hasShadow: !!el.shadowRoot});
            }
            if (el.shadowRoot) walk(el.shadowRoot);
        }
    }
    if (document.body) walk(document.body);
    return out;
})()
"""

_CLICK_JS = r"""
(() => {
    const KW = (arguments[0] || '').toLowerCase();
    let best = null, bestLen = Infinity;
    function getText(el) {
        let txt = (el.innerText || el.textContent || '').trim();
        if (el.shadowRoot) {
            const st = el.shadowRoot.body
                ? el.shadowRoot.body.innerText
                : (el.shadowRoot.documentElement ? el.shadowRoot.documentElement.innerText : '');
            if (st && st.trim()) txt = txt ? txt + ' ' + st.trim() : st.trim();
        }
        return txt;
    }
    function walk(root) {
        let nodes;
        try { nodes = root.querySelectorAll('*'); } catch (e) { return; }
        for (const el of nodes) {
            const txt = getText(el);
            if (txt && txt.toLowerCase().includes(KW) && txt.length < bestLen) {
                best = el; bestLen = txt.length;
            }
            if (el.shadowRoot) walk(el.shadowRoot);
        }
    }
    if (document.body) walk(document.body);
    if (best) {
        const clickable = best.closest('a, button, [role="button"], [onclick], li, tr') || best;
        clickable.click();
        return true;
    }
    return false;
})()
"""

_TEXT_JS = r"""
(() => {
    let results = [];
    function traverse(node) {
        if (!node) return;
        if (node.shadowRoot) {
            const st = node.shadowRoot.body ? node.shadowRoot.body.innerText
                : (node.shadowRoot.documentElement ? node.shadowRoot.documentElement.innerText : '');
            if (st && st.trim()) results.push(st.trim());
            traverse(node.shadowRoot);
        }
        node.childNodes.forEach(child => {
            if (child.nodeType === Node.TEXT_NODE && child.textContent && child.textContent.trim()) {
                results.push(child.textContent.trim());
            } else if (child.nodeType === Node.ELEMENT_NODE) {
                const elText = (child.innerText || child.textContent || '').trim();
                if (elText) results.push(elText);
                traverse(child);
            }
        });
    }
    if (document.body) traverse(document.body);
    return results.join('\n');
})()
"""

_URL_PATTERN = re.compile(
    r'https?://app\.fireworks\.ai/(?:signup/(?:confirm|verify)|confirm|verify|accounts/confirm)[^\s"\'<>]+'
)


async def _navigate_to_inbox(page) -> Dict[str, Any]:
    """Navigate page to the GMX inbox. Returns error dict on failure, None on success."""
    current_url = page.url or ""
    if "navigator.gmx.net/mail" in current_url and "sid=" in current_url:
        return None

    await page.goto(
        "https://www.gmx.net/", wait_until="domcontentloaded", timeout=30000
    )
    await asyncio.sleep(4)
    current_url = page.url

    if (
        "status=inactive" in current_url
        or "session-expired" in current_url
        or "logoutlounge" in current_url
    ):
        return {
            "status": "not_logged_in",
            "verify_url": None,
            "error": "Session inactive or expired",
        }

    try:
        postfach = page.locator("text=Zum Postfach").first
        if await postfach.is_visible(timeout=5000):
            await postfach.click()
            await asyncio.sleep(6)
            current_url = page.url
            if "navigator.gmx.net/mail" not in current_url:
                return {
                    "status": "not_logged_in",
                    "verify_url": None,
                    "error": "Postfach click did not navigate to inbox",
                }
        else:
            return {
                "status": "not_logged_in",
                "verify_url": None,
                "error": "No Zum Postfach — not logged in",
            }
    except Exception as e:
        return {
            "status": "not_logged_in",
            "verify_url": None,
            "error": f"Postfach navigation failed: {e}",
        }

    body = await page.evaluate("() => document.body ? document.body.innerText : ''")
    if "Nicht eingeloggt" in body or (
        "anmelden" in body.lower()[:300] and "E-Mail" not in body
    ):
        return {"status": "not_logged_in", "verify_url": None}

    return None


async def _wait_for_inbox_content(page, max_wait: int = 30) -> bool:
    """Wait until the webmailer frame has loaded mail items (shadow-DOM aware)."""
    deadline = asyncio.get_event_loop().time() + max_wait
    while asyncio.get_event_loop().time() < deadline:
        for frame in page.frames:
            if "webmailer.gmx.net" in (frame.url or ""):
                try:
                    count = await frame.evaluate("""() => {
                        let count = 0;
                        function walk(root) {
                            if (!root) return;
                            try {
                                root.querySelectorAll('*').forEach(el => {
                                    if (el.tagName.toLowerCase() === 'list-mail-item') count++;
                                    if (el.shadowRoot) walk(el.shadowRoot);
                                });
                            } catch(e) {}
                        }
                        if (document.body) walk(document.body);
                        return count;
                    }""")
                    if count and count > 0:
                        return True
                except Exception:
                    pass
        await asyncio.sleep(2)
    return False


async def find_email(
    keyword: str = "fireworks", timeout: int = 8, port: int = DEFAULT_CDP_PORT
) -> Dict[str, Any]:
    """Find the first inbox mail matching keyword, open it, return any verify URL."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")

        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if "navigator.gmx.net/mail" in (pg.url or "") and "sid=" in (
                    pg.url or ""
                ):
                    page = pg
                    break
            if page:
                break
        if page is None:
            for ctx in browser.contexts:
                for pg in ctx.pages:
                    if "gmx.net" in (pg.url or "") and "consent" not in (pg.url or ""):
                        page = pg
                        break
                if page:
                    break
        if page is None:
            page = await (
                browser.contexts[0].new_page()
                if browser.contexts
                else browser.new_page()
            )

        nav_err = await _navigate_to_inbox(page)
        if nav_err:
            return nav_err

        if not await _wait_for_inbox_content(page, max_wait=30):
            return {
                "status": "not_found",
                "verify_url": None,
                "matches": 0,
                "error": "Inbox content did not load within 30s",
            }

        target_frame, matches = None, []
        for frame in page.frames:
            try:
                found = await frame.evaluate(
                    f"""(KW) => {{
                    let out = [];
                    function getText(el) {{
                        let txt = (el.innerText || el.textContent || '').trim();
                        if (el.shadowRoot) {{
                            const st = el.shadowRoot.body
                                ? el.shadowRoot.body.innerText
                                : (el.shadowRoot.documentElement ? el.shadowRoot.documentElement.innerText : '');
                            if (st && st.trim()) txt = txt ? txt + ' ' + st.trim() : st.trim();
                        }}
                        return txt;
                    }}
                    function walk(root) {{
                        let nodes;
                        try {{ nodes = root.querySelectorAll('*'); }} catch (e) {{ return; }}
                        for (const el of nodes) {{
                            const txt = getText(el);
                            if (txt && txt.toLowerCase().includes(KW)) {{
                                const id = (el.getAttribute('id') || '').replace(/^id/, '') || null;
                                out.push({{mailId: id, tag: (el.tagName || '').toLowerCase(),
                                          text: txt.slice(0, 400), hasShadow: !!el.shadowRoot}});
                            }}
                            if (el.shadowRoot) walk(el.shadowRoot);
                        }}
                    }}
                    if (document.body) walk(document.body);
                    return out;
                }}""",
                    keyword.lower(),
                )
            except Exception:
                found = []
            if found:
                target_frame, matches = frame, found
                break

        if not target_frame:
            return {"status": "not_found", "verify_url": None, "matches": 0}

        # URL already present in the list text?
        joined = "\n".join(m.get("text", "") for m in matches)
        m = _URL_PATTERN.search(joined)
        if m:
            return {
                "status": "found",
                "verify_url": html_module.unescape(m.group(0)),
                "matches": len(matches),
                "frame": target_frame.url[:80],
                "source": "list",
            }

        # 2) Open the mail (Shadow DOM aware click).
        try:
            clicked = await target_frame.evaluate(
                f"""(KW) => {{
                let best = null, bestLen = Infinity;
                function getText(el) {{
                    let txt = (el.innerText || el.textContent || '').trim();
                    if (el.shadowRoot) {{
                        const st = el.shadowRoot.body
                            ? el.shadowRoot.body.innerText
                            : (el.shadowRoot.documentElement ? el.shadowRoot.documentElement.innerText : '');
                        if (st && st.trim()) txt = txt ? txt + ' ' + st.trim() : st.trim();
                    }}
                    return txt;
                }}
                function walk(root) {{
                    let nodes;
                    try {{ nodes = root.querySelectorAll('*'); }} catch (e) {{ return; }}
                    for (const el of nodes) {{
                        const txt = getText(el);
                        if (txt && txt.toLowerCase().includes(KW) && txt.length < bestLen) {{
                            best = el; bestLen = txt.length;
                        }}
                        if (el.shadowRoot) walk(el.shadowRoot);
                    }}
                }}
                if (document.body) walk(document.body);
                if (best) {{
                    const clickable = best.closest('a, button, [role="button"], [onclick], li, tr') || best;
                    clickable.click();
                    return true;
                }}
                return false;
            }}""",
                keyword.lower(),
            )
        except Exception:
            clicked = False
        await asyncio.sleep(timeout)

        # 3) Scan the opened mail body (new OOPIF frame may have appeared).
        biggest = ""
        for frame in page.frames:
            try:
                text = await frame.evaluate("""() => {
                    let results = [];
                    function traverse(node) {
                        if (!node) return;
                        if (node.shadowRoot) {
                            const st = node.shadowRoot.body ? node.shadowRoot.body.innerText
                                : (node.shadowRoot.documentElement ? node.shadowRoot.documentElement.innerText : '');
                            if (st && st.trim()) results.push(st.trim());
                            traverse(node.shadowRoot);
                        }
                        node.childNodes.forEach(child => {
                            if (child.nodeType === Node.TEXT_NODE && child.textContent && child.textContent.trim()) {
                                results.push(child.textContent.trim());
                            } else if (child.nodeType === Node.ELEMENT_NODE) {
                                const elText = (child.innerText || child.textContent || '').trim();
                                if (elText) results.push(elText);
                                traverse(child);
                            }
                        });
                    }
                    if (document.body) traverse(document.body);
                    return results.join('\\n');
                }""")
            except Exception:
                continue
            if text and len(text) > len(biggest):
                biggest = text
            mm = _URL_PATTERN.search(text or "")
            if mm:
                return {
                    "status": "found",
                    "verify_url": html_module.unescape(mm.group(0)),
                    "matches": len(matches),
                    "frame": frame.url[:80],
                    "clicked": clicked,
                    "source": "body",
                }

        return {
            "status": "not_found",
            "verify_url": None,
            "matches": len(matches),
            "clicked": clicked,
            "text_preview": (biggest or "")[:500],
        }


def _add_args(p):
    p.add_argument(
        "--keyword",
        default="fireworks",
        help="Keyword in the mail text (default: fireworks)",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=8,
        help="Seconds to wait after the click (default: 8)",
    )


async def _action(args) -> Dict[str, Any]:
    return await find_email(keyword=args.keyword, timeout=args.timeout, port=args.port)


if __name__ == "__main__":
    run(
        _action,
        description="Find and open a GMX email (Shadow-DOM aware)",
        add_args=_add_args,
    )
