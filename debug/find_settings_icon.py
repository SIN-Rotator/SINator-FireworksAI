#!/usr/bin/env python3
"""Close the 'Add folder' dialog and find the actual settings menu."""

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
        
        # Step 1: Close the "Ordner hinzufügen" dialog by clicking "Abbrechen"
        print("1. Closing 'Ordner hinzufügen' dialog...")
        # "Abbrechen" button is at approximately x=750, y=535
        await client.click_at(session_id, 750, 535)
        await asyncio.sleep(2)
        
        # Step 2: Look for settings icon more carefully
        print("2. Searching for settings icon...")
        icon_js = """
        (function(){
            // Find all clickable elements in the bottom left area
            const icons = [];
            const all = document.querySelectorAll('button, a, [role="button"], svg, .icon, i');
            for(const el of all){
                const r = el.getBoundingClientRect();
                // Bottom left area: x < 250, y > 650
                if(r.x < 250 && r.y > 650 && r.width > 10 && r.height > 10){
                    const title = el.getAttribute('title') || '';
                    const aria = el.getAttribute('aria-label') || '';
                    icons.push({
                        tag: el.tagName,
                        class: (el.className || '').substring(0, 30),
                        title: title,
                        aria: aria,
                        x: r.x + r.width/2,
                        y: r.y + r.height/2,
                        width: r.width,
                        height: r.height,
                        text: el.textContent.trim().substring(0, 20)
                    });
                }
            }
            return icons;
        })()
        """
        icon_result = await client.evaluate(session_id, icon_js)
        icons = icon_result.get("result", {}).get("value", [])
        
        print(f"   Found {len(icons)} icons in bottom left:")
        for icon in icons:
            print(f"     <{icon['tag']}> class='{icon['class']}' title='{icon['title']}' aria='{icon['aria']}' text='{icon['text']}' at ({icon['x']:.0f}, {icon['y']:.0f})")
        
        # Step 3: Also look for the "Services" dropdown in the top nav
        print("\n3. Checking 'Services' dropdown...")
        services_js = """
        (function(){
            const services = document.querySelectorAll('[class*="services"], [class*="dropdown"]');
            const results = [];
            for(const s of services){
                const r = s.getBoundingClientRect();
                if(r.y < 100 && r.width > 50){
                    results.push({
                        text: s.textContent.trim().substring(0, 30),
                        class: (s.className || '').substring(0, 40),
                        x: r.x + r.width/2,
                        y: r.y + r.height/2,
                        width: r.width
                    });
                }
            }
            return results;
        })()
        """
        services_result = await client.evaluate(session_id, services_js)
        services = services_result.get("result", {}).get("value", [])
        
        print(f"   Found {len(services)} top-nav services elements:")
        for s in services:
            print(f"     '{s['text']}' class='{s['class']}' at ({s['x']:.0f}, {s['y']:.0f})")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_after_closing_dialog.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
