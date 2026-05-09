#!/usr/bin/env python3
"""Navigate to GMX mailbox via 'Zum Postfach' button, then to alias settings."""

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
        
        # Step 1: Navigate to GMX homepage
        print("1. Navigating to GMX homepage...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        # Step 2: Click "Zum Postfach" button (the popup that says "Sie sind eingeloggt")
        print("2. Clicking 'Zum Postfach'...")
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
            print(f"   Found button: '{postfach_data['text']}' at ({postfach_data['x']:.0f}, {postfach_data['y']:.0f})")
            await client.click_at(session_id, postfach_data["x"], postfach_data["y"])
            await asyncio.sleep(5)
            
            url = await client.evaluate(session_id, "window.location.href")
            url_val = url.get("result", {}).get("value", "")
            print(f"   URL after click: {url_val}")
            
            if "navigator.gmx.net/mail" in url_val:
                print("   ✅ In Mailbox!")
        else:
            print("   'Zum Postfach' not found, trying 'E-Mail' link...")
            # Fallback: click E-Mail in top navigation
            email_js = """
            (function(){
                for(const e of document.querySelectorAll('*')){
                    if(e.textContent.trim()==='E-Mail'){
                        const r = e.getBoundingClientRect();
                        if(r.width > 0 && r.height > 0){
                            return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
                        }
                    }
                }
                return {found: false};
            })()
            """
            email_result = await client.evaluate(session_id, email_js)
            email_data = email_result.get("result", {}).get("value", {})
            if email_data.get("found"):
                await client.click_at(session_id, email_data["x"], email_data["y"])
                await asyncio.sleep(5)
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_inbox.png")
        
        # Step 3: Navigate to alias settings
        print("\n3. Navigating to alias settings...")
        await client.navigate(session_id, "https://navigator.gmx.net/mail_settings/email_addresses")
        await asyncio.sleep(6)
        
        url2 = await client.evaluate(session_id, "window.location.href")
        url_val2 = url2.get("result", {}).get("value", "")
        print(f"   URL: {url_val2}")
        
        text = await client.evaluate(session_id, "document.body.innerText")
        text_val = text.get("result", {}).get("value", "")[:500]
        print(f"   Body text: {text_val}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_alias_settings.png")
        print("   Screenshot saved: gmx_alias_settings.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
