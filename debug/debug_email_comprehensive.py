#!/usr/bin/env python3
"""
Debug-Skript: GMX Webmailer — Verschiedene Email-Öffnungs-Strategien
"""
import asyncio
import json
import re
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def comprehensive_test():
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

    # --- FIND VERIFY EMAIL ITEM ---
    find_res = await client.evaluate(session_id, '''
    (function() {
        function findItems(root) {
            let items = [];
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item" && el.textContent.toLowerCase().includes("verify")) {
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 0) {
                        // Find first child div with width>0 as alternative click target
                        let childTargets = [];
                        const children = el.querySelectorAll("*");
                        for (const c of children) {
                            const cr = c.getBoundingClientRect();
                            if (cr.width > 50 && cr.height > 10) {
                                childTargets.push({
                                    tag: c.tagName.toLowerCase(),
                                    text: c.textContent.slice(0, 40),
                                    rect: {x: cr.x, y: cr.y, w: cr.width, h: cr.height},
                                });
                            }
                        }
                        // Also check shadow root
                        if (el.shadowRoot) {
                            const sc = el.shadowRoot.querySelectorAll("*");
                            for (const c of sc) {
                                const cr = c.getBoundingClientRect();
                                if (cr.width > 50 && cr.height > 10) {
                                    childTargets.push({
                                        tag: c.tagName.toLowerCase(),
                                        text: c.textContent.slice(0, 40),
                                        rect: {x: cr.x, y: cr.y, w: cr.width, h: cr.height},
                                        inShadow: true,
                                    });
                                }
                            }
                        }
                        items.push({
                            id: el.id,
                            rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                            childTargets: childTargets.slice(0, 8),
                            allAttrs: Array.from(el.attributes).map(a => ({name: a.name, value: a.value.slice(0, 60)})),
                        });
                    }
                }
                if (el.shadowRoot) {
                    items = items.concat(findItems(el.shadowRoot));
                }
            }
            return items;
        }
        return findItems(document.body);
    })()
    ''', return_by_value=True)
    items = find_res.get('result', {}).get('value', [])
    if not items:
        print("No verify emails found!")
        await client.disconnect()
        return

    item = items[0]
    print(f"Target verify email: id={item['id']}")
    print(f"  rect: {item['rect']}")
    print(f"  allAttrs: {json.dumps(item['allAttrs'], indent=2)}")
    print(f"  childTargets:")
    for c in item['childTargets']:
        print(f"    {c['tag']} rect={c['rect']} text={c['text'][:40]} shadow={c.get('inShadow')}")

    # --- TEST 1: Click on list-mail-item itself ---
    x = item['rect']['x'] + item['rect']['w'] / 2
    y = item['rect']['y'] + item['rect']['h'] / 2
    print(f"\n--- TEST 1: Click list-mail-item center ({x}, {y}) ---")
    await client.click_at(session_id, x, y)
    await asyncio.sleep(4)
    url1 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL: {url1.get('result', {}).get('value', '')[:100]}")
    body1 = await client.evaluate(session_id, '''(function() { return document.body.innerText.slice(0, 500); })()''', return_by_value=True)
    print(f"Body: {body1.get('result', {}).get('value', '')[:200]}")
    await client.screenshot(session_id, path="/tmp/test1_item_click.png")

    # --- TEST 2: Click on first child target (if any) ---
    if item['childTargets']:
        c = item['childTargets'][0]
        cx = c['rect']['x'] + c['rect']['w'] / 2
        cy = c['rect']['y'] + c['rect']['h'] / 2
        print(f"\n--- TEST 2: Click child {c['tag']} at ({cx}, {cy}) ---")
        await client.click_at(session_id, cx, cy)
        await asyncio.sleep(4)
        url2 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"URL: {url2.get('result', {}).get('value', '')[:100]}")
        body2 = await client.evaluate(session_id, '''(function() { return document.body.innerText.slice(0, 500); })()''', return_by_value=True)
        print(f"Body: {body2.get('result', {}).get('value', '')[:200]}")
        await client.screenshot(session_id, path="/tmp/test2_child_click.png")

    # --- TEST 3: Double-click on list-mail-item ---
    print(f"\n--- TEST 3: Double-click list-mail-item at ({x}, {y}) ---")
    await client.send_to_session(session_id, "Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    await asyncio.sleep(0.2)
    await client.send_to_session(session_id, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 2})
    await asyncio.sleep(0.1)
    await client.send_to_session(session_id, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 2})
    await asyncio.sleep(4)
    url3 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL: {url3.get('result', {}).get('value', '')[:100]}")
    body3 = await client.evaluate(session_id, '''(function() { return document.body.innerText.slice(0, 500); })()''', return_by_value=True)
    print(f"Body: {body3.get('result', {}).get('value', '')[:200]}")
    await client.screenshot(session_id, path="/tmp/test3_doubleclick.png")

    # --- TEST 4: Keyboard Enter after focusing via JS ---
    print(f"\n--- TEST 4: Focus + Enter via JS ---")
    focus_res = await client.evaluate(session_id, '''
    (function() {
        function findItems(root) {
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item" && el.textContent.toLowerCase().includes("verify")) {
                    el.focus();
                    el.tabIndex = 0;
                    el.focus();
                    // Also try scrolling into view
                    el.scrollIntoView({block: "center"});
                    return {found: true, id: el.id, focused: document.activeElement === el};
                }
                if (el.shadowRoot) {
                    const res = findItems(el.shadowRoot);
                    if (res && res.found) return res;
                }
            }
            return {found: false};
        }
        return findItems(document.body);
    })()
    ''', return_by_value=True)
    print(f"Focus result: {focus_res.get('result', {}).get('value', {})}")
    await asyncio.sleep(1)
    await client.send_to_session(session_id, "Input.dispatchKeyEvent", {
        "type": "keyDown", "key": "Enter", "code": "Enter", "keyCode": 13,
    })
    await client.send_to_session(session_id, "Input.dispatchKeyEvent", {
        "type": "keyUp", "key": "Enter", "code": "Enter", "keyCode": 13,
    })
    await asyncio.sleep(4)
    url4 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL: {url4.get('result', {}).get('value', '')[:100]}")
    body4 = await client.evaluate(session_id, '''(function() { return document.body.innerText.slice(0, 500); })()''', return_by_value=True)
    print(f"Body: {body4.get('result', {}).get('value', '')[:200]}")
    await client.screenshot(session_id, path="/tmp/test4_focus_enter.png")

    # --- TEST 5: elementFromPoint check ---
    efp_res = await client.evaluate(session_id, f'''
    (function() {{
        const el = document.elementFromPoint({x}, {y});
        return el ? {{tag: el.tagName.toLowerCase(), text: el.textContent.slice(0, 60)}} : null;
    }})()
    ''', return_by_value=True)
    print(f"\n--- elementFromPoint({x}, {y}): {efp_res.get('result', {}).get('value', {})}")

    # --- TEST 6: Extract cookies via CDP ---
    print(f"\n--- TEST 6: Extract cookies via CDP ---")
    try:
        cookies_res = await client.send_to_session(session_id, "Network.getAllCookies")
        cookies = cookies_res.get("cookies", [])
        gmx_cookies = [c for c in cookies if "gmx" in c.get("domain", "")]
        print(f"Total cookies: {len(cookies)}, GMX cookies: {len(gmx_cookies)}")
        for c in gmx_cookies[:10]:
            print(f"  {c.get('name')} = {c.get('value', '')[:40]} (domain={c.get('domain')})")
        # Save to file for manual testing
        with open("/tmp/gmx_cookies.json", "w") as f:
            json.dump(gmx_cookies, f, indent=2)
        print("Saved GMX cookies to /tmp/gmx_cookies.json")
    except Exception as e:
        print(f"Cookie extraction failed: {e}")

    await client.disconnect()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(comprehensive_test())
