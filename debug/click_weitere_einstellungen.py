#!/usr/bin/env python3
"""Click 'Weitere Einstellungen' to find alias settings."""

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
        
        # We're already on the settings page, find and click "Weitere Einstellungen"
        print("Clicking 'Weitere Einstellungen'...")
        weiter_js = """
        (function(){
            const all = document.querySelectorAll('*');
            for(const el of all){
                if(el.textContent.trim() === 'Weitere Einstellungen'){
                    const r = el.getBoundingClientRect();
                    if(r.width > 0 && r.height > 0){
                        return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                }
            }
            return {found: false};
        })()
        """
        result = await client.evaluate(session_id, weiter_js)
        data = result.get("result", {}).get("value", {})
        
        if data.get("found"):
            print(f"   Found at ({data['x']:.0f}, {data['y']:.0f})")
            await client.click_at(session_id, data["x"], data["y"])
            await asyncio.sleep(5)
            
            url = await client.evaluate(session_id, "window.location.href")
            url_val = url.get("result", {}).get("value", "")
            print(f"   URL: {url_val}")
            
            text = await client.evaluate(session_id, "document.body.innerText")
            text_val = text.get("result", {}).get("value", "")[:800]
            print(f"   Body text: {text_val}")
            
            # Look for alias-related text
            if 'alias' in text_val.lower() or 'wunsch' in text_val.lower():
                print("   ✅ Alias settings found!")
        else:
            print("   'Weitere Einstellungen' not found")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_weitere_einstellungen.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
