#!/usr/bin/env python3
"""
Navigate to GMX account settings and find sidebar items.
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
        
        # Navigate to GMX account settings
        print("Navigating to navigator.gmx.net/ciss ...")
        await client.navigate(session_id, "https://navigator.gmx.net/ciss")
        await asyncio.sleep(5)
        
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"URL: {url.get('result', {}).get('value', '')}")
        
        # Find sidebar items (left side, x < 300)
        sidebar_js = """
        (function(){
            const items = [];
            const all = document.querySelectorAll('a, button, li, div, span');
            for(const el of all){
                const text = el.textContent.trim();
                if(text.length > 3 && text.length < 50){
                    const r = el.getBoundingClientRect();
                    if(r.x < 300 && r.y > 50 && r.y < 600 && r.width > 50){
                        items.push({
                            text: text,
                            x: r.x + r.width/2,
                            y: r.y + r.height/2,
                            tag: el.tagName,
                            href: el.href || 'none'
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
            print(f"  - '{item['text']}' <{item['tag']}> at ({item['x']:.0f}, {item['y']:.0f}) href={item['href']}")
        
        # Look for "Weitere Einstellungen"
        weiter = [item for item in items if 'weitere' in item['text'].lower() or 'einstellung' in item['text'].lower()]
        if weiter:
            item = weiter[0]
            print(f"\nClicking '{item['text']}' at ({item['x']:.0f}, {item['y']:.0f})")
            await client.click_at(session_id, item['x'], item['y'])
            await asyncio.sleep(5)
            
            url2 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            print(f"   URL: {url2.get('result', {}).get('value', '')}")
            
            text = await client.evaluate(session_id, "document.body.innerText")
            text_val = text.get("result", {}).get("value", "")[:800]
            print(f"   Body text: {text_val}")
        else:
            print("\n'Weitere Einstellungen' not found. Dumping all sidebar text:")
            texts = set()
            for item in items:
                texts.add(item['text'])
            for t in sorted(texts):
                print(f"  '{t}'")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_ciss_page.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
