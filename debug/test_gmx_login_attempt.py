#!/usr/bin/env python3
"""
Debug script: Try 'Account wechseln' and direct login.gmx.net navigation.
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
        
        # Test 1: Click "Account wechseln"
        print("=== Test 1: Click 'Account wechseln' ===")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(3)
        
        click_js = """(function(){
            for(const e of document.querySelectorAll('*')){
                const text = e.textContent.trim();
                if(text==='Account wechseln'){
                    e.click();
                    return {clicked: true, tag: e.tagName, text: text};
                }
            }
            return {clicked: false};
        })()"""
        
        result = await client.evaluate(session_id, click_js, return_by_value=True)
        data = result.get("result", {}).get("value", {})
        print(f"Click result: {data}")
        
        await asyncio.sleep(4)
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"URL after Account wechseln: {url.get('result', {}).get('value', '')}")
        
        body = await client.evaluate(session_id, "document.body.innerText.slice(0, 400)", return_by_value=True)
        print(f"Body: {body.get('result', {}).get('value', '')}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_account_wechseln.png")
        
        # Test 2: Direct navigation to login.gmx.net
        print("\n=== Test 2: Direct nav to login.gmx.net ===")
        await client.navigate(session_id, "https://login.gmx.net/")
        await asyncio.sleep(5)
        
        url2 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        final_url = url2.get("result", {}).get("value", "")
        print(f"URL: {final_url}")
        
        body2 = await client.evaluate(session_id, "document.body.innerText.slice(0, 800)", return_by_value=True)
        body_text = body2.get("result", {}).get("value", "")
        print(f"Body: {body_text}")
        
        # Look for Google login option
        google_js = """(function(){
            const links = [];
            document.querySelectorAll('a, button').forEach(el => {
                const text = el.textContent.trim().toLowerCase();
                if(text.includes('google') || text.includes('gmail') || text.includes('weiter mit') || text.includes('login mit')){
                    links.push({text: el.textContent.trim(), tag: el.tagName, href: el.href || 'none'});
                }
            });
            return links;
        })()"""
        
        google_result = await client.evaluate(session_id, google_js, return_by_value=True)
        google_links = google_result.get("result", {}).get("value", [])
        print(f"Google login options: {google_links}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_login_direct.png")
        print("Screenshots saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
