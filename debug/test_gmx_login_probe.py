#!/usr/bin/env python3
"""
Debug script: Attempt GMX Google Login via CDP.
Navigate to GMX login page and try Google Login button.
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
        
        # Navigate to GMX login page
        print("Navigating to GMX login...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        # Look for login/account link
        login_js = """(function(){
            const links = [];
            document.querySelectorAll('a').forEach(a => {
                const text = a.textContent.trim().toLowerCase();
                if(text.includes('login') || text.includes('einloggen') || text.includes('anmelden') || text.includes('postfach')){
                    links.push({text: a.textContent.trim(), href: a.href || 'none'});
                }
            });
            return links.slice(0, 10);
        })()"""
        
        result = await client.evaluate(session_id, login_js, return_by_value=True)
        links = result.get("result", {}).get("value", [])
        print(f"Found login links: {links}")
        
        # Check if we already see "Account wechseln" or similar
        body = await client.evaluate(session_id, "document.body.innerText.slice(0, 300)", return_by_value=True)
        print(f"Body: {body.get('result', {}).get('value', '')}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_login_page.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
