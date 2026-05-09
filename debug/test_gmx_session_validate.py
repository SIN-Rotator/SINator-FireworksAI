#!/usr/bin/env python3
"""
Debug script: Validate GMX session using the VERIFIED flow from AGENTS.md.
1. Navigate to https://www.gmx.net/
2. Click "E-Mail" via JS (exact text match)
3. Check if we land on navigator.gmx.net/mail?sid=...
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
        
        # Step 1: Navigate to GMX Homepage
        print("Navigating to https://www.gmx.net/ ...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"Current URL: {url.get('result', {}).get('value', '')}")
        
        # Step 2: Click "E-Mail" via JS (exact text match, NOT hardcoded coordinates)
        click_js = """(function(){
            for(const e of document.querySelectorAll('*')){
                if(e.textContent.trim()==='E-Mail'){
                    e.click();
                    return {clicked: true, tag: e.tagName, text: e.textContent.trim()};
                }
            }
            return {clicked: false};
        })()"""
        
        result = await client.evaluate(session_id, click_js, return_by_value=True)
        data = result.get("result", {}).get("value", {})
        print(f"E-Mail click result: {data}")
        
        await asyncio.sleep(5)
        
        url2 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        final_url = url2.get("result", {}).get("value", "")
        print(f"After click URL: {final_url}")
        
        is_valid = "navigator.gmx.net/mail?sid=" in final_url or "bap.navigator.gmx.net/mail?sid=" in final_url
        print(f"Session VALID: {is_valid}")
        
        if not is_valid:
            # Check body for error messages
            body = await client.evaluate(session_id, "document.body.innerText.slice(0, 500)", return_by_value=True)
            body_text = body.get("result", {}).get("value", "")
            print(f"Body text: {body_text}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_session_validate.png")
        print("Screenshot saved to debug/gmx_session_validate.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
