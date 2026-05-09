#!/usr/bin/env python3
"""
Debug script: Search for Google login option on GMX, and try GMX-domain email.
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
        
        # Test 1: Navigate to gmx.net and search for Google login option
        print("=== Test 1: Search for Google login on gmx.net ===")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        search_js = """(function(){
            const matches = [];
            document.querySelectorAll('a, button').forEach(el => {
                const text = el.textContent.trim().toLowerCase();
                const href = (el.href || '').toLowerCase();
                if(text.includes('google') || text.includes('gmail') || href.includes('google') || 
                   text.includes('weiter mit') || text.includes('anmelden mit') || text.includes('login mit')){
                    matches.push({
                        text: el.textContent.trim(),
                        tag: el.tagName,
                        href: el.href || 'none'
                    });
                }
            });
            return matches;
        })()"""
        
        result = await client.evaluate(session_id, search_js, return_by_value=True)
        matches = result.get("result", {}).get("value", [])
        print(f"Found {len(matches)} potential login options:")
        import json
        for m in matches:
            print(json.dumps(m, indent=2, ensure_ascii=False))
        
        # Test 2: Try GMX-domain email on auth.gmx.net
        print("\n=== Test 2: Try zukunftsorientierte.energie@gmx.de ===")
        await client.navigate(session_id, "https://auth.gmx.net/login")
        await asyncio.sleep(4)
        
        # Fill email
        email_js = """(function(){
            const inp = document.querySelector('input#username');
            if(inp){
                const r = inp.getBoundingClientRect();
                return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
            }
            return {found: false};
        })()"""
        
        email_result = await client.evaluate(session_id, email_js, return_by_value=True)
        email_data = email_result.get("result", {}).get("value", {})
        
        if email_data.get("found"):
            await client.click_at(session_id, email_data["x"], email_data["y"])
            await asyncio.sleep(0.3)
            await client.type_text(session_id, "zukunftsorientierte.energie@gmx.de")
            await asyncio.sleep(0.5)
            
            # Click Weiter
            weiter_js = """(function(){
                const btn = document.querySelector('button');
                if(btn && btn.textContent.trim() === 'Weiter'){
                    const r = btn.getBoundingClientRect();
                    return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
                }
                return {found: false};
            })()"""
            
            weiter_result = await client.evaluate(session_id, weiter_js, return_by_value=True)
            weiter_data = weiter_result.get("result", {}).get("value", {})
            
            if weiter_data.get("found"):
                await client.click_at(session_id, weiter_data["x"], weiter_data["y"])
                await asyncio.sleep(6)
                
                url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                print(f"URL after GMX email: {url.get('result', {}).get('value', '')}")
                
                body = await client.evaluate(session_id, "document.body.innerText.slice(0, 800)", return_by_value=True)
                print(f"Body: {body.get('result', {}).get('value', '')}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_google_search.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
