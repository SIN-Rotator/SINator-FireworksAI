#!/usr/bin/env python3
"""
Inject ALL cookies from all-cookies-master.json (223 cookies) and validate GMX.
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target


async def main():
    ws_url = await get_browser_ws_endpoint(cdp_port=9222)
    client = CDPClient(ws_url)
    await client.connect()
    
    try:
        target = await get_page_target(client)
        session_id = await client.attach_to_target(target["targetId"])
        await client.send_to_session(session_id, "Network.enable")
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        
        # Clear all cookies
        print("Clearing all cookies...")
        await client.send_to_session(session_id, "Network.clearBrowserCookies")
        await asyncio.sleep(1)
        
        # Load ALL backup cookies
        backup_path = "/Users/jeremy/dev/SINator-fireworksai/backup/session/all-cookies-master.json"
        with open(backup_path, "r") as f:
            cookies = json.load(f)
        
        print(f"Loaded {len(cookies)} cookies")
        
        # Inject all cookies
        success = 0
        failed = 0
        for cookie in cookies:
            try:
                params = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", ""),
                    "path": cookie.get("path", "/"),
                    "httpOnly": cookie.get("httpOnly", False),
                    "secure": cookie.get("secure", False),
                }
                if cookie.get("expires", -1) > 0:
                    params["expires"] = cookie["expires"]
                same_site = cookie.get("sameSite", "")
                if same_site:
                    params["sameSite"] = same_site
                
                result = await client.send_to_session(session_id, "Network.setCookie", params)
                if result.get("success"):
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        
        print(f"Injected: {success} ok, {failed} failed")
        
        # Navigate and check
        await asyncio.sleep(2)
        print("\nNavigating to gmx.net...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(5)
        
        body = await client.evaluate(session_id, "document.body.innerText.slice(0, 400)", return_by_value=True)
        body_text = body.get("result", {}).get("value", "")
        print(f"Body: {body_text}")
        
        popup_js = """(function(){
            const items = [];
            document.querySelectorAll('button, a').forEach(el => {
                const text = el.textContent.trim();
                if(text === 'Zum Postfach' || text === 'Login' || text === 'Account wechseln'){
                    const r = el.getBoundingClientRect();
                    items.push({text: text, tag: el.tagName, w: r.width, h: r.height});
                }
            });
            return items;
        })()"""
        
        result = await client.evaluate(session_id, popup_js, return_by_value=True)
        items = result.get("result", {}).get("value", [])
        print(f"Popup items: {items}")
        
        if items and items[0].get('text') == 'Zum Postfach':
            print("SESSION ALIVE!")
        else:
            print("SESSION STILL DEAD")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_after_all_cookies.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
