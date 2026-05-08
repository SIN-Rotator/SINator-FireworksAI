#!/usr/bin/env python3
"""
Debug: Teste CDP Click auf das EXACTE <A> Element für E-Mail-Adressen
"""
import asyncio
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def test_exact_link_click():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    # Get exact coordinates of the <A> element
    link_res = await client.evaluate(session_id, '''
    (function() {
        const links = Array.from(document.querySelectorAll("a"));
        const a = links.find(el => el.textContent.trim() === "E-Mail-Adressen");
        if (a) {
            const rect = a.getBoundingClientRect();
            return {
                found: true,
                x: rect.x + rect.width / 2,
                y: rect.y + rect.height / 2,
                href: a.href,
                text: a.textContent.trim(),
            };
        }
        return {found: false};
    })()
    ''', return_by_value=True)
    link = link_res.get('result', {}).get('value', {})
    print(f"Link info: {link}")

    if not link.get('found'):
        print("Link not found!")
        await client.disconnect()
        return

    x, y = link['x'], link['y']
    print(f"Clicking at ({x}, {y})")

    # CDP click sequence
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

    await asyncio.sleep(3)
    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL after 3s: {url_res.get('result', {}).get('value', '')[:100]}")

    await asyncio.sleep(3)
    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL after 6s: {url_res.get('result', {}).get('value', '')[:100]}")

    await asyncio.sleep(3)
    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL after 9s: {url_res.get('result', {}).get('value', '')[:100]}")

    await client.disconnect()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(test_exact_link_click())
