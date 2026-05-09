#!/usr/bin/env python3
"""
Debug script: Fireworks login → capture what happens after clicking "Next".
GOAL: Understand why login redirects to /signup/verify instead of dashboard.
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target


def pprint(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


async def main():
    ws_url = await get_browser_ws_endpoint(cdp_port=9222)
    client = CDPClient(ws_url)
    await client.connect()
    
    try:
        target = await get_page_target(client)
        session_id = await client.attach_to_target(target["targetId"])
        
        # Enable Network to see all requests
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        await client.send_to_session(session_id, "Network.enable")
        
        # Step 0: Clear ONLY Fireworks cookies/storage
        cookies_result = await client.send_to_session(session_id, "Network.getAllCookies")
        cookies = cookies_result.get("cookies", [])
        fireworks_cookies = [c for c in cookies if "fireworks" in c.get("domain", "")]
        for cookie in fireworks_cookies:
            await client.send_to_session(session_id, "Network.deleteCookies", {
                "name": cookie["name"],
                "domain": cookie["domain"],
                "path": cookie.get("path", "/")
            })
        print(f"Cleared {len(fireworks_cookies)} Fireworks cookies")
        
        # Clear Fireworks localStorage/sessionStorage
        await client.evaluate(session_id, """
            (function(){
                for(let i = localStorage.length - 1; i >= 0; i--){
                    const key = localStorage.key(i);
                    if(key && (key.includes('fireworks') || key.includes('cognito') || key.includes('auth'))){
                        localStorage.removeItem(key);
                    }
                }
                for(let i = sessionStorage.length - 1; i >= 0; i--){
                    const key = sessionStorage.key(i);
                    if(key && (key.includes('fireworks') || key.includes('cognito') || key.includes('auth'))){
                        sessionStorage.removeItem(key);
                    }
                }
                return {cleared: true};
            })()
        """)
        
        # Step 1: Navigate to login
        await client.navigate(session_id, "https://app.fireworks.ai/login")
        await asyncio.sleep(6)
        
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"1. Initial URL: {url.get('result', {}).get('value', '')}")
        
        # Step 2: Accept cookie banner
        accept_js = """(function(){
            const btns = document.querySelectorAll('button');
            for(const btn of btns){
                if(btn.textContent.trim() === 'Accept All'){
                    const r = btn.getBoundingClientRect();
                    return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
                }
            }
            return {found: false};
        })()"""
        accept_result = await client.evaluate(session_id, accept_js, return_by_value=True)
        accept_data = accept_result.get("result", {}).get("value", {})
        if accept_data.get("found"):
            await client.click_at(session_id, accept_data["x"], accept_data["y"])
            await asyncio.sleep(3)
            print("2. Cookie banner accepted")
        
        # Step 3: Click "Email Login"
        email_login_js = """(function(){
            const all = document.querySelectorAll('*');
            for(const el of all){
                if(el.textContent.trim() === 'Email Login'){
                    const r = el.getBoundingClientRect();
                    if(r.width > 0 && r.height > 0){
                        return {found: true, x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                }
            }
            return {found: false};
        })()"""
        el_result = await client.evaluate(session_id, email_login_js, return_by_value=True)
        el_data = el_result.get("result", {}).get("value", {})
        if el_data.get("found"):
            await client.click_at(session_id, el_data["x"], el_data["y"])
            await asyncio.sleep(5)
            url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            print(f"3. After Email Login click: {url.get('result', {}).get('value', '')}")
        
        # Step 4: Fill email
        await client.evaluate(session_id, "document.querySelector('#email').select()")
        await asyncio.sleep(0.3)
        await client.type_text(session_id, "test-6307@gmx.de")
        print("4. Email filled")
        
        # Step 5: Fill password
        await client.evaluate(session_id, "document.querySelector('#password').select()")
        await asyncio.sleep(0.3)
        await client.type_text(session_id, "SinatorTest2024!")
        print("5. Password filled")
        
        # Step 6: Click "Next" button
        next_js = """(function(){
            const buttons = document.querySelectorAll('button');
            let best = null;
            for(const btn of buttons){
                const text = btn.textContent.trim().toLowerCase();
                const r = btn.getBoundingClientRect();
                if((text === 'next' || text === 'sign in') &&
                   r.width > 200 && r.left > 600 && r.height > 30){
                    if(!best || r.width > best.width){
                        best = {x: r.x + r.width/2, y: r.y + r.height/2, width: r.width, text: btn.textContent.trim()};
                    }
                }
            }
            return best ? {found: true, ...best} : {found: false};
        })()"""
        next_result = await client.evaluate(session_id, next_js, return_by_value=True)
        next_data = next_result.get("result", {}).get("value", {})
        
        if next_data.get("found"):
            print(f"6. Found Next button: '{next_data.get('text')}' at ({next_data['x']:.0f}, {next_data['y']:.0f}), width={next_data['width']:.0f}")
            await client.click_at(session_id, next_data["x"], next_data["y"])
        else:
            print("6. Next button NOT FOUND - dumping all buttons:")
            dump_js = """(function(){
                const btns = document.querySelectorAll('button');
                return Array.from(btns).map(b => {
                    const r = b.getBoundingClientRect();
                    return {text: b.textContent.trim(), x: r.x, y: r.y, w: r.width, h: r.height, left: r.left};
                }).filter(b => b.w > 50);
            })()"""
            dump_result = await client.evaluate(session_id, dump_js, return_by_value=True)
            pprint(dump_result.get("result", {}).get("value", []))
            return
        
        # Wait for redirect
        await asyncio.sleep(20)
        
        # Step 7: Capture final state
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        final_url = url.get("result", {}).get("value", "")
        print(f"7. Final URL after 20s: {final_url}")
        
        body_js = """(function(){return document.body.innerText.slice(0, 2000);})()"""
        body_result = await client.evaluate(session_id, body_js, return_by_value=True)
        body_text = body_result.get("result", {}).get("value", "")
        print(f"8. Body text (first 2000 chars):\n{body_text}\n{'='*60}")
        
        # Check for error messages
        error_js = """(function(){
            const errs = [];
            document.querySelectorAll('*').forEach(el => {
                const text = el.textContent.trim().toLowerCase();
                if(text.includes('error') || text.includes('invalid') || text.includes('incorrect') || text.includes('wrong')){
                    errs.push(el.textContent.trim().slice(0, 200));
                }
            });
            return errs.slice(0, 5);
        })()"""
        error_result = await client.evaluate(session_id, error_js, return_by_value=True)
        errors = error_result.get("result", {}).get("value", [])
        if errors:
            print(f"9. Potential error messages found: {errors}")
        
        # Screenshot
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/fireworks_login_after_next.png")
        print("10. Screenshot saved to debug/fireworks_login_after_next.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
