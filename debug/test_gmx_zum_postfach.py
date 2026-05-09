#!/usr/bin/env python3
"""
Debug script: Try clicking 'Zum Postfach' on GMX homepage to reach inbox.
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
        
        # We're already on gmx.net from previous script
        # Try clicking "Zum Postfach"
        click_js = """(function(){
            for(const e of document.querySelectorAll('*')){
                const text = e.textContent.trim();
                if(text==='Zum Postfach' || text.includes('Postfach')){
                    e.click();
                    return {clicked: true, tag: e.tagName, text: text, href: e.href || 'none'};
                }
            }
            return {clicked: false};
        })()"""
        
        result = await client.evaluate(session_id, click_js, return_by_value=True)
        data = result.get("result", {}).get("value", {})
        print(f"Zum Postfach click result: {data}")
        
        await asyncio.sleep(5)
        
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        final_url = url.get("result", {}).get("value", "")
        print(f"After click URL: {final_url}")
        
        is_mail = "navigator.gmx.net/mail" in final_url or "bap.navigator.gmx.net/mail" in final_url
        print(f"Reached mail page: {is_mail}")
        
        if not is_mail:
            body = await client.evaluate(session_id, "document.body.innerText.slice(0, 500)", return_by_value=True)
            print(f"Body: {body.get('result', {}).get('value', '')}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_zum_postfach.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
