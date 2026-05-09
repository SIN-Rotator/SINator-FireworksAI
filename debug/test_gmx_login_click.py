#!/usr/bin/env python3
"""
Debug script: Click 'Login' on GMX homepage and inspect the resulting page.
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
        
        # We're already on gmx.net from previous script, which shows "Login"
        print("Clicking 'Login'...")
        click_js = """(function(){
            for(const e of document.querySelectorAll('*')){
                const text = e.textContent.trim();
                if(text==='Login'){
                    const r = e.getBoundingClientRect();
                    if(r.width > 30 && r.height > 15){
                        e.click();
                        return {clicked: true, tag: e.tagName, text: text, x: r.x+r.width/2, y: r.y+r.height/2};
                    }
                }
            }
            return {clicked: false};
        })()"""
        
        result = await client.evaluate(session_id, click_js, return_by_value=True)
        data = result.get("result", {}).get("value", {})
        print(f"Click result: {data}")
        
        await asyncio.sleep(5)
        
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        final_url = url.get("result", {}).get("value", "")
        print(f"URL after Login click: {final_url}")
        
        body = await client.evaluate(session_id, "document.body.innerText.slice(0, 1000)", return_by_value=True)
        body_text = body.get("result", {}).get("value", "")
        print(f"Body text: {body_text}")
        
        # Check for Google login option
        options_js = """(function(){
            const opts = [];
            document.querySelectorAll('a, button, div, span').forEach(el => {
                const text = el.textContent.trim().toLowerCase();
                if(text.includes('google') || text.includes('gmail') || text.includes('weiter mit google') || text.includes('mit google') || text.includes('google login')){
                    opts.push({text: el.textContent.trim().slice(0, 100), tag: el.tagName});
                }
            });
            return opts.slice(0, 10);
        })()"""
        
        opts_result = await client.evaluate(session_id, options_js, return_by_value=True)
        opts = opts_result.get("result", {}).get("value", [])
        print(f"Google-related options: {opts}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_after_login_click.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
