#!/usr/bin/env python3
"""Click on 'Services' dropdown in top navigation to find alias settings."""

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
        
        # Step 1: Navigate to mailbox first
        print("1. Navigating to GMX mailbox...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        # Click Zum Postfach
        postfach_js = """
        (function(){
            const btns = document.querySelectorAll('button, a');
            for(const btn of btns){
                const text = btn.textContent.trim();
                if(text.includes('Zum Postfach')){
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
            print("   ✅ In mailbox")
        
        # Step 2: Click on "Services" dropdown in top nav
        print("\n2. Clicking 'Services' dropdown...")
        # Services is in top nav, around x=560, y=40 based on screenshot
        await client.click_at(session_id, 560, 40)
        await asyncio.sleep(3)
        
        # Look for menu items
        menu_js = """
        (function(){
            const items = [];
            const all = document.querySelectorAll('a, button, li, div[role="menuitem"]');
            for(const el of all){
                const text = el.textContent.trim().toLowerCase();
                if(text.length > 3){
                    const r = el.getBoundingClientRect();
                    if(r.y > 50 && r.y < 400 && r.width > 50){
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
        
        print(f"   Found {len(menu_items)} menu items:")
        for item in menu_items:
            print(f"     - '{item['text']}' at ({item['x']:.0f}, {item['y']:.0f})")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_services_dropdown.png")
        
        # Step 3: Look for Einstellungen/Settings specifically
        print("\n3. Looking for 'Einstellungen' or 'Adressen'...")
        settings_items = [item for item in menu_items if 'einstellung' in item['text'].lower() or 'adresse' in item['text'].lower() or 'alias' in item['text'].lower() or 'wunsch' in item['text'].lower()]
        
        if settings_items:
            for s in settings_items:
                print(f"   Found: '{s['text']}' at ({s['x']:.0f}, {s['y']:.0f})")
                print(f"   Clicking...")
                await client.click_at(session_id, s['x'], s['y'])
                await asyncio.sleep(5)
                
                url = await client.evaluate(session_id, "window.location.href")
                url_val = url.get("result", {}).get("value", "")
                print(f"   URL: {url_val}")
        else:
            print("   No settings items found in dropdown")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_after_services_click.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
