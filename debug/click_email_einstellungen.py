#!/usr/bin/env python3
"""Click 'E-Mail Einstellungen' in user menu to access alias settings."""

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
        
        # Make sure we're in mailbox with user menu open
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        # Click Zum Postfach
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
        
        # Click user avatar to open menu
        await client.click_at(session_id, 1140, 40)
        await asyncio.sleep(2)
        
        # Click "E-Mail Einstellungen"
        print("Clicking 'E-Mail Einstellungen'...")
        einstellung_js = """
        (function(){
            const all = document.querySelectorAll('*');
            for(const el of all){
                if(el.textContent.trim() === 'E-Mail Einstellungen'){
                    const r = el.getBoundingClientRect();
                    if(r.width > 0 && r.height > 0){
                        return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                }
            }
            return {found: false};
        })()
        """
        einstellung_result = await client.evaluate(session_id, einstellung_js)
        einstellung_data = einstellung_result.get("result", {}).get("value", {})
        
        if einstellung_data.get("found"):
            print(f"   Found at ({einstellung_data['x']:.0f}, {einstellung_data['y']:.0f})")
            await client.click_at(session_id, einstellung_data["x"], einstellung_data["y"])
            await asyncio.sleep(5)
            
            url = await client.evaluate(session_id, "window.location.href")
            url_val = url.get("result", {}).get("value", "")
            print(f"   URL: {url_val}")
            
            text = await client.evaluate(session_id, "document.body.innerText")
            text_val = text.get("result", {}).get("value", "")[:600]
            print(f"   Body text: {text_val}")
            
            # Check for alias-related text
            if 'alias' in text_val.lower() or 'wunsch' in text_val.lower() or 'adresse' in text_val.lower():
                print("   ✅ Alias settings page found!")
        else:
            print("   'E-Mail Einstellungen' not found")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_email_einstellungen.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
