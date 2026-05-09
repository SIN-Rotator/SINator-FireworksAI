#!/usr/bin/env python3
"""Check actual GMX login state and navigate to alias settings."""

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
        
        # Navigate directly to GMX mail
        print("1. Navigating to GMX mail...")
        await client.navigate(session_id, "https://navigator.gmx.net/mail")
        await asyncio.sleep(5)
        
        url = await client.evaluate(session_id, "window.location.href")
        url_val = url.get("result", {}).get("value", "")
        print(f"   URL: {url_val}")
        
        # Check if we're actually in mail
        if "navigator.gmx.net/mail" in url_val and "sid=" in url_val:
            print("   ✅ EINGELOGGT!")
        else:
            print("   ❌ NICHT eingeloggt")
            
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_mail_check.png")
        
        # Now navigate to alias settings
        print("\n2. Navigating to alias settings...")
        await client.navigate(session_id, "https://navigator.gmx.net/mail_settings/email_addresses")
        await asyncio.sleep(6)
        
        url2 = await client.evaluate(session_id, "window.location.href")
        url_val2 = url2.get("result", {}).get("value", "")
        print(f"   URL: {url_val2}")
        
        # Check page content
        text = await client.evaluate(session_id, "document.body.innerText")
        text_val = text.get("result", {}).get("value", "")[:500]
        print(f"   Body text: {text_val}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_alias_page.png")
        print("   Screenshot saved: gmx_alias_page.png")
        
        # Check for iframe structure
        frame_script = """
        (function(){
            const iframes = document.querySelectorAll('iframe');
            return Array.from(iframes).map(f => ({
                src: f.src || '',
                id: f.id || '',
                name: f.name || '',
                class: f.className || ''
            }));
        })()
        """
        frame_result = await client.evaluate(session_id, frame_script)
        frames = frame_result.get("result", {}).get("value", [])
        print(f"\n   Found {len(frames)} iframes:")
        for f in frames:
            print(f"     src={f['src'][:60]} id={f['id']} name={f['name']}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
