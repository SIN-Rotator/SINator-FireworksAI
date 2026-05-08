#!/usr/bin/env python3
"""
Debug: Teste das EXACTE JS aus read_otp auf der aktuellen Seite
"""
import asyncio
import re
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def test_exact_js():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    # Check if we're on webmailer; if not navigate there first
    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_res.get('result', {}).get('value', '')
    print(f"Current URL: {current_url[:100]}")

    if "3c-bap.gmx.net" not in current_url and "webmailer.gmx.net" not in current_url:
        print("Navigating to webmailer first...")
        # Quick nav via homepage
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        await client.evaluate(session_id, '''(function(){const e=Array.from(document.querySelectorAll("a,button,nav a")).find(x=>x.textContent.trim()==="E-Mail");if(e)e.click();})()''', return_by_value=True)
        await asyncio.sleep(5)
        url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        current_url = url_res.get('result', {}).get('value', '')
        m = re.search(r'[?&]sid=([^&]+)', current_url)
        sid = m.group(1) if m else None
        if sid:
            await client.navigate(session_id, f"https://bap.navigator.gmx.net/mail?sid={sid}")
            await asyncio.sleep(6)
            iframe_res = await client.evaluate(session_id, '''(function(){const f=document.querySelector("#thirdPartyFrame_mail");return f?f.src:null;})()''', return_by_value=True)
            iframe_src = iframe_res.get('result', {}).get('value', '')
            if iframe_src:
                await client.navigate(session_id, iframe_src)
                await asyncio.sleep(10)

    # Test 1: simple count
    count_res = await client.evaluate(session_id, '''
    (function() {
        function countItems(root) {
            let count = 0;
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item") count++;
                if (el.shadowRoot) count += countItems(el.shadowRoot);
            }
            return count;
        }
        return countItems(document.body);
    })()
    ''', return_by_value=True)
    print(f"Total list-mail-item count: {count_res.get('result', {}).get('value', 0)}")

    # Test 2: exact JS from read_otp with fireworks filter
    safe_filter = "fireworks"
    items_js = f'''(function() {{
        function findItems(root) {{
            let items = [];
            const all = root.querySelectorAll("*");
            for (const el of all) {{
                if (el.tagName.toLowerCase() === "list-mail-item") {{
                    const text = (el.textContent || "").toLowerCase();
                    if (text.includes("{safe_filter}")) {{
                        const idAttr = el.getAttribute("id");
                        const mailId = idAttr ? idAttr.replace(/^id/, "") : null;
                        if (mailId) {{
                            items.push({{
                                mailId: mailId,
                                text: el.textContent.trim().slice(0, 120).replace(/\\s+/g, " "),
                            }});
                        }}
                    }}
                }}
                if (el.shadowRoot) {{
                    items = items.concat(findItems(el.shadowRoot));
                }}
            }}
            return items;
        }}
        return findItems(document.body);
    }})()'''
    
    print(f"\nJS to execute (first 500 chars):\n{items_js[:500]}")
    
    items_res = await client.evaluate(session_id, items_js, return_by_value=True)
    items = items_res.get('result', {}).get('value', [])
    print(f"\nFiltered items found: {len(items)}")
    for item in items[:5]:
        print(f"  mailId={item.get('mailId')} text={item.get('text', '')[:80]}")

    # Test 3: check first list-mail-item attributes
    attr_res = await client.evaluate(session_id, '''
    (function() {
        function findFirst(root) {
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item") {
                    return {
                        tag: el.tagName,
                        idAttr: el.getAttribute("id"),
                        idProp: el.id,
                        text: el.textContent.slice(0, 60),
                    };
                }
                if (el.shadowRoot) {
                    const res = findFirst(el.shadowRoot);
                    if (res) return res;
                }
            }
            return null;
        }
        return findFirst(document.body);
    })()
    ''', return_by_value=True)
    first = attr_res.get('result', {}).get('value', {})
    print(f"\nFirst list-mail-item: {json.dumps(first, indent=2)}")

    await client.disconnect()

if __name__ == "__main__":
    import json
    asyncio.run(test_exact_js())
