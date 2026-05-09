#!/usr/bin/env python3
"""Find and click 'Weitere Einstellungen' using coordinates from screenshot."""

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
        
        # From screenshot, "Weitere Einstellungen" is in left sidebar at approximately y=200
        print("Searching for sidebar items...")
        sidebar_js = """
        (function(){
            const items = [];
            const all = document.querySelectorAll('a, button, li, div, span');
            for(const el of all){
                const text = el.textContent.trim();
                if(text.length > 3 && text.length < 50){
                    const r = el.getBoundingClientRect();
                    if(r.x < 250 && r.y > 50 && r.y < 400 && r.width > 50){
                        items.push({
                            text: text,
                            x: r.x + r.width/2,
                            y: r.y + r.height/2,
                            tag: el.tagName
                        });
                    }
                }
            }
            return items;
        })()
        """
        result = await client.evaluate(session_id, sidebar_js)
        items = result.get("result", {}).get("value", [])
        
        print(f"Found {len(items)} sidebar items:")
        for item in items:
            print(f"  - '{item['text']}' <{item['tag']}> at ({item['x']:.0f}, {item['y']:.0f})")
        
        # Click on "Weitere Einstellungen" if found
        weiter = [item for item in items if 'weitere' in item['text'].lower() or 'einstellung' in item['text'].lower()]
        if weiter:
            item = weiter[0]
            print(f"\nClicking '{item['text']}' at ({item['x']:.0f}, {item['y']:.0f})")
            await client.click_at(session_id, item['x'], item['y'])
            await asyncio.sleep(5)
            
            url = await client.evaluate(session_id, "window.location.href")
            url_val = url.get("result", {}).get("value", "")
            print(f"   URL: {url_val}")
            
            text = await client.evaluate(session_id, "document.body.innerText")
            text_val = text.get("result", {}).get("value", "")[:600]
            print(f"   Body text: {text_val}")
        else:
            print("\n'Weitere Einstellungen' not found in sidebar. Trying coordinates (100, 250)...")
            await client.click_at(session_id, 100, 250)
            await asyncio.sleep(5)
            
            url = await client.evaluate(session_id, "window.location.href")
            url_val = url.get("result", {}).get("value", "")
            print(f"   URL: {url_val}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_after_weitere.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
