#!/usr/bin/env python3
"""
Navigate to GMX homepage, check login state, then try to reach mail inbox.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target


async def main():
    ws_url = await get_browser_ws_endpoint(cdp_port=9222)
    client = CDPClient(ws_url)
    await client.connect()
    
    try:
        target = await get_page_target(client)
        session_id = await client.attach_to_target(target["targetId"])
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        
        # Navigate to GMX homepage
        print("Navigating to gmx.net...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(5)
        
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"URL: {url.get('result', {}).get('value', '')}")
        
        # Check body for login state
        body = await client.evaluate(session_id, "document.body.innerText.slice(0, 500)", return_by_value=True)
        body_text = body.get("result", {}).get("value", "")
        print(f"Body: {body_text}")
        
        # Find Zum Postfach or Login button
        popup_js = """(function(){
            const items = [];
            document.querySelectorAll('button, a').forEach(el => {
                const text = el.textContent.trim();
                if(text === 'Zum Postfach' || text === 'Login' || text === 'Account wechseln'){
                    const r = el.getBoundingClientRect();
                    items.push({
                        text: text,
                        tag: el.tagName,
                        x: r.x + r.width/2,
                        y: r.y + r.height/2,
                        w: r.width,
                        h: r.height
                    });
                }
            });
            return items;
        })()"""
        
        result = await client.evaluate(session_id, popup_js, return_by_value=True)
        items = result.get("result", {}).get("value", [])
        print(f"\nPopup items: {items}")
        
        # If we see "Zum Postfach", click it
        postfach = [i for i in items if i.get('text') == 'Zum Postfach']
        if postfach:
            p = postfach[0]
            print(f"\nClicking 'Zum Postfach' at ({p['x']:.0f}, {p['y']:.0f})")
            await client.click_at(session_id, p['x'], p['y'])
            await asyncio.sleep(6)
            
            url2 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            final_url = url2.get("result", {}).get("value", "")
            print(f"After click URL: {final_url}")
            
            body2 = await client.evaluate(session_id, "document.body.innerText.slice(0, 500)", return_by_value=True)
            print(f"Body: {body2.get('result', {}).get('value', '')}")
        else:
            print("No 'Zum Postfach' found — checking if we need to click Login first")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_home_check.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
