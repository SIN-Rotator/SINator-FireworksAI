#!/usr/bin/env python3
"""Click 'E-Mail Einstellungen' using partial text match or known coordinates."""

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
        target = await get_page_target(client, url_filter="gmx")
        if not target:
            targets = await client.get_targets()
            for t in targets:
                if "page" in t.get("type", ""):
                    target = t
                    break
        
        session_id = await client.attach_to_target(target["targetId"])
        
        # Navigate to mailbox
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        postfach_js = """
        (function(){
            const btns = document.querySelectorAll('button, a');
            for(const btn of btns){
                if(btn.textContent.trim().includes('Zum Postfach')){
                    const r = btn.getBoundingClientRect();
                    if(r.width > 0) return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
                }
            }
            return {found: false};
        })()
        """
        result = await client.evaluate(session_id, postfach_js)
        data = result.get("result", {}).get("value", {})
        if data.get("found"):
            await client.click_at(session_id, data["x"], data["y"])
            await asyncio.sleep(5)
        
        # Click user avatar
        await client.click_at(session_id, 1140, 40)
        await asyncio.sleep(2)
        
        # Try clicking with partial match
        print("Trying partial text match for 'Einstellungen'...")
        einstellung_js = """
        (function(){
            const all = document.querySelectorAll('*');
            for(const el of all){
                const text = el.textContent.trim().toLowerCase();
                if(text.includes('einstellung') && text.includes('e-mail')){
                    const r = el.getBoundingClientRect();
                    if(r.width > 0 && r.height > 0 && r.y > 100){
                        return {found: true, x: r.x + r.width/2, y: r.y + r.height/2, text: el.textContent.trim()};
                    }
                }
            }
            return {found: false};
        })()
        """
        einstellung_result = await client.evaluate(session_id, einstellung_js)
        einstellung_data = einstellung_result.get("result", {}).get("value", {})
        
        if einstellung_data.get("found"):
            print(f"   Found: '{einstellung_data['text']}' at ({einstellung_data['x']:.0f}, {einstellung_data['y']:.0f})")
            await client.click_at(session_id, einstellung_data["x"], einstellung_data["y"])
            await asyncio.sleep(5)
            
            url = await client.evaluate(session_id, "window.location.href")
            url_val = url.get("result", {}).get("value", "")
            print(f"   URL: {url_val}")
        else:
            print("   Not found with partial match. Trying known coordinates (985, 240)...")
            await client.click_at(session_id, 985, 240)
            await asyncio.sleep(5)
            
            url = await client.evaluate(session_id, "window.location.href")
            url_val = url.get("result", {}).get("value", "")
            print(f"   URL: {url_val}")
        
        text = await client.evaluate(session_id, "document.body.innerText")
        text_val = text.get("result", {}).get("value", "")[:500]
        print(f"   Body text: {text_val}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_after_einstellungen_click.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
