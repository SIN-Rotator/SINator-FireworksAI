#!/usr/bin/env python3
"""Click user menu (JS avatar) in top right to find account/alias settings."""

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
        
        # Make sure we're in mailbox
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
        
        # Click on user avatar "JS" in top right
        print("Clicking user avatar 'JS' in top right...")
        # Based on screenshot, it's around x=1140, y=40
        await client.click_at(session_id, 1140, 40)
        await asyncio.sleep(3)
        
        # Look for menu items
        menu_js = """
        (function(){
            const items = [];
            const all = document.querySelectorAll('a, button, li, div');
            for(const el of all){
                const text = el.textContent.trim().toLowerCase();
                if(text.length > 2){
                    const r = el.getBoundingClientRect();
                    if(r.y > 50 && r.y < 500 && r.x > 800){
                        items.push({
                            text: el.textContent.trim(),
                            x: r.x + r.width/2,
                            y: r.y + r.height/2,
                            href: el.href || ''
                        });
                    }
                }
            }
            return items;
        })()
        """
        menu_result = await client.evaluate(session_id, menu_js)
        menu_items = menu_result.get("result", {}).get("value", [])
        
        print(f"Found {len(menu_items)} menu items in top-right area:")
        for item in menu_items:
            print(f"  - '{item['text']}' at ({item['x']:.0f}, {item['y']:.0f})")
        
        # Filter for settings-related
        settings = [item for item in menu_items if any(kw in item['text'].lower() for kw in ['einstellung', 'setting', 'adresse', 'alias', 'wunsch', 'profil', 'account', 'konto'])]
        print(f"\nSettings-related: {len(settings)}")
        for s in settings:
            print(f"  - '{s['text']}' at ({s['x']:.0f}, {s['y']:.0f})")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_user_menu.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
