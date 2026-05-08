#!/usr/bin/env python3
"""
Debug-Skript: GMX Webmailer Email-Click Test
Ziel: Testen ob CDP MouseEvent auf list-mail-item die Email öffnet.
"""
import asyncio
import re
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def test_email_click():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    # We are already on webmailer from previous run (or navigate there)
    url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_result.get("result", {}).get("value", "")
    print(f"Current URL: {current_url[:100]}")

    if "3c-bap.gmx.net" not in current_url and "webmailer.gmx.net" not in current_url:
        print("Not on webmailer, need to navigate. Aborting for safety.")
        await client.disconnect()
        return

    # Wait a moment for rendering
    await asyncio.sleep(3)

    # Find list-mail-item elements recursively through shadow roots
    items_res = await client.evaluate(session_id, '''
    (function() {
        function findItems(root, depth) {
            if (depth > 10) return [];
            let items = [];
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item") {
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 0) {
                        items.push({
                            id: el.id || el.getAttribute("data-id") || el.getAttribute("mail-id") || null,
                            mid: el.getAttribute("mid") || null,
                            text: el.textContent.slice(0, 150).replace(/\\s+/g, " "),
                            rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                            tagName: el.tagName,
                        });
                    }
                }
                if (el.shadowRoot) {
                    items = items.concat(findItems(el.shadowRoot, depth + 1));
                }
            }
            return items;
        }
        return findItems(document.body, 0);
    })()
    ''', return_by_value=True)
    items = items_res.get('result', {}).get('value', [])
    print(f"\nFound {len(items)} list-mail-item elements:")
    for i, item in enumerate(items[:10]):
        print(f"  [{i}] {item['tagName']} id={item['id']} mid={item['mid']} rect={item['rect']}")
        print(f"       text={item['text'][:100]}")

    # Find the first verification email (contains "Verify")
    verify_idx = None
    for i, item in enumerate(items):
        if "verify" in item['text'].lower():
            verify_idx = i
            break

    if verify_idx is None:
        print("No verification email found!")
        await client.disconnect()
        return

    target_item = items[verify_idx]
    x = target_item['rect']['x'] + target_item['rect']['w'] / 2
    y = target_item['rect']['y'] + target_item['rect']['h'] / 2
    print(f"\nClicking verification email [{verify_idx}] at ({x}, {y})")

    # CDP Mouse click sequence (like we do for GMX alias delete)
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
    print("Click dispatched, waiting 4s...")
    await asyncio.sleep(4)

    # Check URL change
    url_after = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    new_url = url_after.get("result", {}).get("value", "")
    print(f"URL after click: {new_url[:120]}")

    # Screenshot
    await client.screenshot(session_id, path="/tmp/webmailer_after_click.png")
    print("Screenshot saved to /tmp/webmailer_after_click.png")

    # Extract body text including shadow roots
    body_res = await client.evaluate(session_id, '''
    (function() {
        function t(r,d){if(d>10)return"";let txt=(r.textContent||"");for(const e of r.querySelectorAll("*")){if(e.shadowRoot)txt+=" "+t(e.shadowRoot,d+1);}return txt;}
        return t(document.body,0).slice(0, 2000);
    })()
    ''', return_by_value=True)
    body_text = body_res.get("result", {}).get("value", "")
    print(f"\nBody text (first 1000 chars):\n{body_text[:1000]}")

    # Try to find confirmation URL
    confirm_match = re.search(r'https://app\.fireworks\.ai/[^\s\'"<>]+', body_text)
    if confirm_match:
        print(f"\n✅ CONFIRM URL FOUND: {confirm_match.group(0)}")
    else:
        print(f"\n❌ No confirm URL found in body text")

    await client.disconnect()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(test_email_click())
