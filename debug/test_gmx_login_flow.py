#!/usr/bin/env python3
"""
Debug script: Continue GMX login flow on auth.gmx.net.
Fill email and click Weiter to see next step.
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
        
        # We should already be on auth.gmx.net from previous script
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"Current URL: {url.get('result', {}).get('value', '')}")
        
        # Inspect page structure
        inspect_js = """(function(){
            const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
                type: i.type,
                name: i.name,
                id: i.id,
                placeholder: i.placeholder,
                rect: JSON.stringify(i.getBoundingClientRect())
            }));
            const buttons = Array.from(document.querySelectorAll('button')).map(b => ({
                text: b.textContent.trim(),
                rect: JSON.stringify(b.getBoundingClientRect())
            }));
            return {inputs, buttons};
        })()"""
        
        result = await client.evaluate(session_id, inspect_js, return_by_value=True)
        data = result.get("result", {}).get("value", {})
        import json
        print(f"Page structure: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Find email input
        email_js = """(function(){
            const inp = document.querySelector('input[type="email"]') || 
                       document.querySelector('input[name="email"]') ||
                       document.querySelector('input#email') ||
                       document.querySelector('input[placeholder*="E-Mail" i]');
            if(inp){
                const r = inp.getBoundingClientRect();
                return {found: true, x: r.x + r.width/2, y: r.y + r.height/2, tag: inp.tagName};
            }
            return {found: false};
        })()"""
        
        email_result = await client.evaluate(session_id, email_js, return_by_value=True)
        email_data = email_result.get("result", {}).get("value", {})
        print(f"Email input: {email_data}")
        
        if email_data.get("found"):
            # Click and type email
            print("Filling email...")
            await client.click_at(session_id, email_data["x"], email_data["y"])
            await asyncio.sleep(0.5)
            await client.type_text(session_id, "zukunftsorientierte.energie@gmail.com")
            await asyncio.sleep(0.5)
            
            # Find and click Weiter button
            weiter_js = """(function(){
                const btns = document.querySelectorAll('button');
                for(const b of btns){
                    const text = b.textContent.trim().toLowerCase();
                    if(text === 'weiter' || text === 'continue' || text === 'next'){
                        const r = b.getBoundingClientRect();
                        if(r.width > 50 && r.height > 20){
                            return {found: true, x: r.x + r.width/2, y: r.y + r.height/2, text: b.textContent.trim()};
                        }
                    }
                }
                return {found: false};
            })()"""
            
            weiter_result = await client.evaluate(session_id, weiter_js, return_by_value=True)
            weiter_data = weiter_result.get("result", {}).get("value", {})
            print(f"Weiter button: {weiter_data}")
            
            if weiter_data.get("found"):
                print(f"Clicking '{weiter_data['text']}' at ({weiter_data['x']:.0f}, {weiter_data['y']:.0f})")
                await client.click_at(session_id, weiter_data["x"], weiter_data["y"])
                await asyncio.sleep(6)
                
                url2 = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                final_url = url2.get("result", {}).get("value", "")
                print(f"URL after Weiter: {final_url}")
                
                body = await client.evaluate(session_id, "document.body.innerText.slice(0, 1000)", return_by_value=True)
                body_text = body.get("result", {}).get("value", "")
                print(f"Body text: {body_text}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_after_weiter.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
