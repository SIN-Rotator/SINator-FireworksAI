#!/usr/bin/env python3
"""Navigate to GMX mailbox, then find settings/einstellungen link for alias management."""

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
        
        # Step 1: Navigate to GMX homepage and click Zum Postfach
        print("1. Navigating to GMX and clicking 'Zum Postfach'...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        postfach_js = """
        (function(){
            const buttons = document.querySelectorAll('button, a');
            for(const btn of buttons){
                const text = btn.textContent.trim();
                if(text.includes('Zum Postfach') || text.includes('Postfach')){
                    const r = btn.getBoundingClientRect();
                    if(r.width > 0 && r.height > 0){
                        return {found: true, x: r.x + r.width/2, y: r.y + r.height/2, text: text};
                    }
                }
            }
            return {found: false};
        })()
        """
        postfach_result = await client.evaluate(session_id, postfach_js)
        postfach_data = postfach_result.get("result", {}).get("value", {})
        
        if postfach_data.get("found"):
            await client.click_at(session_id, postfach_data["x"], postfach_data["y"])
            await asyncio.sleep(5)
            
            url = await client.evaluate(session_id, "window.location.href")
            url_val = url.get("result", {}).get("value", "")
            print(f"   ✅ In Mailbox: {url_val[:80]}...")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_inbox_loaded.png")
        
        # Step 2: Look for settings/einstellungen links in the mailbox
        print("\n2. Searching for settings links...")
        settings_js = """
        (function(){
            const links = document.querySelectorAll('a, button');
            const settings = [];
            for(const link of links){
                const text = link.textContent.trim().toLowerCase();
                if(text.includes('einstellung') || text.includes('setting') || text.includes('alias') || text.includes('adresse') || text.includes('email')){
                    const r = link.getBoundingClientRect();
                    settings.push({
                        text: link.textContent.trim(),
                        href: link.href || '',
                        x: r.x + r.width/2,
                        y: r.y + r.height/2,
                        width: r.width,
                        height: r.height
                    });
                }
            }
            return settings.slice(0, 20);
        })()
        """
        settings_result = await client.evaluate(session_id, settings_js)
        settings_data = settings_result.get("result", {}).get("value", [])
        
        print(f"   Found {len(settings_data)} settings-related links:")
        for s in settings_data:
            print(f"     - '{s['text']}' href={s['href'][:40]} at ({s['x']:.0f}, {s['y']:.0f})")
        
        # Step 3: Try clicking on "Einstellungen" or similar
        if settings_data:
            # Find the first link that looks like settings
            for s in settings_data:
                if 'einstellung' in s['text'].lower() or 'setting' in s['text'].lower():
                    print(f"\n3. Clicking '{s['text']}'...")
                    await client.click_at(session_id, s['x'], s['y'])
                    await asyncio.sleep(5)
                    
                    url = await client.evaluate(session_id, "window.location.href")
                    url_val = url.get("result", {}).get("value", "")
                    print(f"   URL: {url_val}")
                    break
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_after_settings_click.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
