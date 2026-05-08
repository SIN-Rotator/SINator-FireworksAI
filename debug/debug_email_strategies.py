#!/usr/bin/env python3
"""
Debug-Skript: GMX Webmailer Email-Click Strategien
Teste verschiedene Klick-Methoden um eine Email zu öffnen.
"""
import asyncio
import re
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def test_strategies():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")
    await client.send_to_session(session_id, "Network.enable")

    await asyncio.sleep(2)

    url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_result.get("result", {}).get("value", "")
    print(f"Current URL: {current_url[:100]}")

    # Find verification email element and inspect its shadow root / children
    inspect_res = await client.evaluate(session_id, '''
    (function() {
        function findItems(root, depth) {
            if (depth > 10) return [];
            let items = [];
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item") {
                    const text = el.textContent.toLowerCase();
                    if (text.includes("verify")) {
                        const rect = el.getBoundingClientRect();
                        // Inspect shadow root children
                        let shadowChildren = [];
                        if (el.shadowRoot) {
                            const sc = Array.from(el.shadowRoot.querySelectorAll("*")).slice(0, 15);
                            shadowChildren = sc.map(c => ({
                                tag: c.tagName.toLowerCase(),
                                text: c.textContent.slice(0, 60),
                                rect: (c.getBoundingClientRect && c.getBoundingClientRect().width > 0) ? {
                                    x: c.getBoundingClientRect().x,
                                    y: c.getBoundingClientRect().y,
                                    w: c.getBoundingClientRect().width,
                                    h: c.getBoundingClientRect().height,
                                } : null,
                            }));
                        }
                        // Inspect light DOM children (slotted)
                        let lightChildren = [];
                        const lc = Array.from(el.querySelectorAll("*")).slice(0, 10);
                        lightChildren = lc.map(c => ({
                            tag: c.tagName.toLowerCase(),
                            text: c.textContent.slice(0, 40),
                        }));
                        items.push({
                            id: el.id,
                            rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                            shadowChildren,
                            lightChildren,
                            hasShadow: !!el.shadowRoot,
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
    items = inspect_res.get('result', {}).get('value', [])
    print(f"\nFound {len(items)} verify emails:")
    for i, item in enumerate(items):
        print(f"\n[{i}] id={item['id']} rect={item['rect']} hasShadow={item['hasShadow']}")
        print(f"  Shadow children:")
        for c in item['shadowChildren']:
            print(f"    {c['tag']} | rect={c['rect']} | text={c['text'][:50]}")
        print(f"  Light children:")
        for c in item['lightChildren']:
            print(f"    {c['tag']} | text={c['text'][:40]}")

    if not items:
        print("No verify emails found!")
        await client.disconnect()
        return

    # Try STRATEGY 1: Double-click on list-mail-item center
    item = items[0]
    x = item['rect']['x'] + item['rect']['w'] / 2
    y = item['rect']['y'] + item['rect']['h'] / 2
    print(f"\n--- STRATEGY 1: Double-click list-mail-item at ({x}, {y}) ---")
    for ev in ["mouseMoved", "mousePressed", "mouseReleased", "mousePressed", "mouseReleased"]:
        cc = 2 if ev == "mousePressed" or ev == "mouseReleased" else 1
        await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
            "type": ev, "x": x, "y": y, "button": "left", "clickCount": cc,
        })
        if ev == "mouseMoved":
            await asyncio.sleep(0.3)
    await asyncio.sleep(4)
    url_after = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL after double-click: {url_after.get('result', {}).get('value', '')[:100]}")
    await client.screenshot(session_id, path="/tmp/strategy1_doubleclick.png")

    # If not opened, try STRATEGY 2: Click first clickable shadow child
    if item['shadowChildren']:
        clickable = [c for c in item['shadowChildren'] if c['rect'] and c['rect']['w'] > 0 and c['rect']['h'] > 0]
        if clickable:
            c = clickable[0]
            cx = c['rect']['x'] + c['rect']['w'] / 2
            cy = c['rect']['y'] + c['rect']['h'] / 2
            print(f"\n--- STRATEGY 2: Click shadow child {c['tag']} at ({cx}, {cy}) ---")
            for ev in ["mouseMoved", "mousePressed", "mouseReleased"]:
                await client.send_to_session(session_id, "Input.dispatchMouseEvent", {
                    "type": ev, "x": cx, "y": cy, "button": "left", "clickCount": 1,
                })
                if ev == "mouseMoved":
                    await asyncio.sleep(0.3)
            await asyncio.sleep(4)
            url_after = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            print(f"URL after child click: {url_after.get('result', {}).get('value', '')[:100]}")
            await client.screenshot(session_id, path="/tmp/strategy2_childclick.png")

    # STRATEGY 3: Use JS .click() on the list-mail-item itself (for comparison)
    print(f"\n--- STRATEGY 3: JS .click() on list-mail-item ---")
    click_res = await client.evaluate(session_id, f'''
    (function() {{
        const el = document.querySelector("#{item['id']}");
        if (el) {{ el.click(); return "clicked"; }}
        return "not found";
    }})()
    ''', return_by_value=True)
    print(f"JS click result: {click_res.get('result', {}).get('value', '')}")
    await asyncio.sleep(4)
    url_after = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL after JS click: {url_after.get('result', {}).get('value', '')[:100]}")
    await client.screenshot(session_id, path="/tmp/strategy3_jsclick.png")

    # STRATEGY 4: Look for an open/expand button or link inside the item
    print(f"\n--- STRATEGY 4: Search for link/button inside list-mail-item ---")
    btn_res = await client.evaluate(session_id, f'''
    (function() {{
        const item = document.querySelector("#{item['id']}");
        if (!item) return [];
        function walk(root) {{
            const results = [];
            const all = root.querySelectorAll("a, button, [role='button'], [role='link']");
            for (const el of all) {{
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {{
                    results.push({{
                        tag: el.tagName.toLowerCase(),
                        text: el.textContent.slice(0, 40),
                        rect: {{x: rect.x, y: rect.y, w: rect.width, h: rect.height}},
                        role: el.getAttribute("role"),
                    }});
                }}
            }}
            return results;
        }}
        let results = walk(item);
        if (item.shadowRoot) results = results.concat(walk(item.shadowRoot));
        return results;
    }})()
    ''', return_by_value=True)
    btns = btn_res.get('result', {}).get('value', [])
    print(f"Found {len(btns)} clickable elements inside:")
    for b in btns:
        print(f"  {b['tag']} role={b['role']} rect={b['rect']} text={b['text']}")

    await client.disconnect()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(test_strategies())
