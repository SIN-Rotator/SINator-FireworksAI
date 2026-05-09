#!/usr/bin/env python3
"""Click settings gear icon in GMX mailbox sidebar to access settings."""

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
        
        # Click settings gear icon at bottom left of sidebar
        # From screenshot: gear icon is at approximately (0.097,0.944) = (116, 680)
        print("Clicking settings gear icon at (116, 680)...")
        await client.click_at(session_id, 116, 680)
        await asyncio.sleep(3)
        
        # Check what appeared
        url = await client.evaluate(session_id, "window.location.href")
        url_val = url.get("result", {}).get("value", "")
        print(f"   URL: {url_val}")
        
        # Look for menu items
        menu_js = """
        (function(){
            const items = [];
            const all = document.querySelectorAll('a, button, div[role="menuitem"], li');
            for(const el of all){
                const text = el.textContent.trim().toLowerCase();
                if(text.includes('alias') || text.includes('adresse') || text.includes('email') || text.includes('wunsch') || text.includes('persönlich')){
                    const r = el.getBoundingClientRect();
                    if(r.width > 0 && r.height > 0){
                        items.push({
                            text: el.textContent.trim(),
                            x: r.x + r.width/2,
                            y: r.y + r.height/2,
                            tag: el.tagName
                        });
                    }
                }
            }
            return items.slice(0, 10);
        })()
        """
        menu_result = await client.evaluate(session_id, menu_js)
        menu_items = menu_result.get("result", {}).get("value", [])
        
        print(f"\n   Found {len(menu_items)} alias-related items:")
        for item in menu_items:
            print(f"     - '{item['text']}' <{item['tag']}> at ({item['x']:.0f}, {item['y']:.0f})")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_settings_menu.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
