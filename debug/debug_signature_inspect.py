#!/usr/bin/env python3
"""
Debug: Inspektiere die 3c-bap signature Seite und finde das korrekte E-Mail-Adressen Element
"""
import asyncio
import re
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def inspect_signature_page():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_res.get('result', {}).get('value', '')
    print(f"Current URL: {current_url[:100]}")

    if "3c-bap.gmx.net" not in current_url or "signature" not in current_url:
        print("Not on signature page. Need to navigate there first.")
        # Navigate there via jump URL if we have SID
        sid_match = re.search(r'jsessionid=([^?&]+)', current_url)
        jsessionid = sid_match.group(1) if sid_match else None
        if not jsessionid:
            # Try to get SID from navigator URL
            await client.navigate(session_id, "https://www.gmx.net/")
            await asyncio.sleep(4)
            click_res = await client.evaluate(session_id, '''
            (function(){
                const els = Array.from(document.querySelectorAll("a, button, nav a"));
                const emailEl = els.find(e => (e.textContent||"").trim() === "E-Mail");
                if (emailEl) { emailEl.click(); return true; }
                return false;
            })()
            ''', return_by_value=True)
            print(f"Clicked nav: {click_res}")
            await asyncio.sleep(5)
            url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_res.get('result', {}).get('value', '')
            sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
            sid = sid_match.group(1) if sid_match else None
            if sid:
                settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
                print(f"Navigating to settings: {settings_url}")
                await client.navigate(session_id, settings_url)
                await asyncio.sleep(6)
        else:
            # Already on 3c-bap, stay here
            pass

    # Now inspect the signature page
    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_res.get('result', {}).get('value', '')
    print(f"\nInspecting page: {current_url[:100]}")

    # Find all elements containing "E-Mail-Adressen"
    els_res = await client.evaluate(session_id, '''
    (function() {
        const matches = [];
        const all = document.querySelectorAll("a, button, [role=link], [role=button], li, span, div");
        for (const el of all) {
            const text = el.textContent.trim();
            if (text === "E-Mail-Adressen" || text.includes("E-Mail-Adressen")) {
                const rect = el.getBoundingClientRect();
                matches.push({
                    tag: el.tagName,
                    text: text,
                    href: el.href || null,
                    role: el.getAttribute("role"),
                    className: el.className,
                    rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                    clickable: !!el.click,
                });
            }
        }
        return matches;
    })()
    ''', return_by_value=True)
    matches = els_res.get('result', {}).get('value', [])
    print(f"\nElements matching 'E-Mail-Adressen': {len(matches)}")
    for m in matches:
        print(f"  {m['tag']} | text={m['text']} | href={m['href']} | role={m['role']} | rect={m['rect']} | clickable={m['clickable']}")

    # Try CDP click on the first element with valid rect
    if matches:
        first = matches[0]
        if first['rect'] and first['rect']['w'] > 0:
            x = first['rect']['x'] + first['rect']['w'] / 2
            y = first['rect']['y'] + first['rect']['h'] / 2
            print(f"\nTrying CDP click at ({x}, {y})")
            await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": x, "y": y,
            })
            await asyncio.sleep(0.3)
            await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1,
            })
            await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1,
            })
            await asyncio.sleep(6)
            url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            print(f"URL after CDP click: {url_res.get('result', {}).get('value', '')[:100]}")

    await client.disconnect()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(inspect_signature_page())
