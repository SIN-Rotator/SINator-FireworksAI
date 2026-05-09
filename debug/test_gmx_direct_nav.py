#!/usr/bin/env python3
"""
Debug script: Try direct navigation to navigator.gmx.net/mail
and inspect the E-Mail element properties.
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
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        
        # First, inspect the E-Mail element
        print("=== Inspecting E-Mail element ===")
        inspect_js = """(function(){
            for(const e of document.querySelectorAll('*')){
                if(e.textContent.trim()==='E-Mail'){
                    return {
                        tag: e.tagName,
                        href: e.href || 'none',
                        onclick: e.onclick ? 'yes' : 'no',
                        id: e.id || 'none',
                        className: e.className || 'none',
                        parentTag: e.parentElement ? e.parentElement.tagName : 'none',
                        parentHref: e.parentElement ? (e.parentElement.href || 'none') : 'none',
                        rect: JSON.stringify(e.getBoundingClientRect()),
                        dataAttributes: Object.keys(e.dataset).length > 0 ? JSON.stringify(e.dataset) : 'none'
                    };
                }
            }
            return {found: false};
        })()"""
        
        result = await client.evaluate(session_id, inspect_js, return_by_value=True)
        data = result.get("result", {}).get("value", {})
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        # Also inspect Zum Postfach
        print("\n=== Inspecting Zum Postfach element ===")
        inspect2_js = """(function(){
            for(const e of document.querySelectorAll('*')){
                const text = e.textContent.trim();
                if(text==='Zum Postfach'){
                    return {
                        tag: e.tagName,
                        href: e.href || 'none',
                        onclick: e.onclick ? 'yes' : 'no',
                        id: e.id || 'none',
                        className: e.className || 'none',
                        parentTag: e.parentElement ? e.parentElement.tagName : 'none',
                        parentHref: e.parentElement ? (e.parentElement.href || 'none') : 'none',
                        rect: JSON.stringify(e.getBoundingClientRect()),
                    };
                }
            }
            return {found: false};
        })()"""
        
        result2 = await client.evaluate(session_id, inspect2_js, return_by_value=True)
        data2 = result2.get("result", {}).get("value", {})
        print(json.dumps(data2, indent=2, ensure_ascii=False))
        
        # Now try direct navigation to navigator.gmx.net/mail
        print("\n=== Direct navigation to navigator.gmx.net/mail ===")
        await client.navigate(session_id, "https://navigator.gmx.net/mail")
        await asyncio.sleep(5)
        
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        final_url = url.get("result", {}).get("value", "")
        print(f"URL after direct nav: {final_url}")
        
        body = await client.evaluate(session_id, "document.body.innerText.slice(0, 500)", return_by_value=True)
        print(f"Body: {body.get('result', {}).get('value', '')}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_direct_nav.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
