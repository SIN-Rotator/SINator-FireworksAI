#!/usr/bin/env python3
"""
Debug script: After Fireworks login lands on /signup/verify, try clicking "Continue"
to see if the previously-verified email allows dashboard access.
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
        
        # We should already be on /signup/verify from the previous script
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        current_url = url.get("result", {}).get("value", "")
        print(f"Current URL: {current_url}")
        
        # Find "Continue" button
        continue_js = """(function(){
            const btns = document.querySelectorAll('button');
            for(const btn of btns){
                const text = btn.textContent.trim().toLowerCase();
                if(text.includes('continue') || text.includes('weiter') || text.includes('fortfahren')){
                    const r = btn.getBoundingClientRect();
                    if(r.width > 50 && r.height > 20){
                        return {found: true, text: btn.textContent.trim(), x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height};
                    }
                }
            }
            return {found: false};
        })()"""
        
        result = await client.evaluate(session_id, continue_js, return_by_value=True)
        data = result.get("result", {}).get("value", {})
        
        if data.get("found"):
            print(f"Found '{data['text']}' button at ({data['x']:.0f}, {data['y']:.0f}), size={data['w']:.0f}x{data['h']:.0f}")
            await client.click_at(session_id, data["x"], data["y"])
            await asyncio.sleep(10)
            
            url2 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            final_url = url2.get("result", {}).get("value", "")
            print(f"After clicking Continue: {final_url}")
            
            body = await client.evaluate(session_id, "document.body.innerText.slice(0, 1000)", return_by_value=True)
            body_text = body.get("result", {}).get("value", "")
            print(f"Body text: {body_text[:500]}")
            
            await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/fireworks_after_continue.png")
            print("Screenshot saved")
        else:
            print("Continue button not found. Dumping all buttons:")
            dump_js = """(function(){
                return Array.from(document.querySelectorAll('button')).map(b => {
                    const r = b.getBoundingClientRect();
                    return {text: b.textContent.trim(), x: r.x, y: r.y, w: r.width, h: r.height};
                }).filter(b => b.w > 30);
            })()"""
            dump = await client.evaluate(session_id, dump_js, return_by_value=True)
            import json
            print(json.dumps(dump.get("result", {}).get("value", []), indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
