#!/usr/bin/env python3
"""
Debug script: Click the actual Login BUTTON element on GMX homepage.
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
        
        # Navigate to GMX homepage fresh
        print("Navigating to gmx.net...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        # Find the actual BUTTON with 'Login' text
        find_js = """(function(){
            let best = null;
            document.querySelectorAll('*').forEach(e => {
                const text = e.textContent.trim();
                if(text === 'Login'){
                    const r = e.getBoundingClientRect();
                    if(r.width > 30 && r.height > 15){
                        const area = r.width * r.height;
                        if(!best || area < best.area){
                            best = {
                                tag: e.tagName,
                                x: r.x + r.width/2,
                                y: r.y + r.height/2,
                                w: r.width,
                                h: r.height,
                                area: area
                            };
                        }
                    }
                }
            });
            return best || {found: false};
        })()"""
        
        result = await client.evaluate(session_id, find_js, return_by_value=True)
        data = result.get("result", {}).get("value", {})
        print(f"Best Login element: {data}")
        
        if data and data.get('tag'):
            print(f"Clicking at ({data['x']:.0f}, {data['y']:.0f})")
            await client.click_at(session_id, data['x'], data['y'])
            await asyncio.sleep(6)
            
            url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            final_url = url.get("result", {}).get("value", "")
            print(f"URL after click: {final_url}")
            
            body = await client.evaluate(session_id, "document.body.innerText.slice(0, 800)", return_by_value=True)
            body_text = body.get("result", {}).get("value", "")
            print(f"Body: {body_text}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_login_button_click.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
