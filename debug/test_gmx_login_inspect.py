#!/usr/bin/env python3
"""
Debug script: Navigate to GMX homepage, inspect Login link href, then click it.
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
        
        # Navigate to GMX homepage fresh
        print("Navigating to gmx.net...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        # Inspect ALL elements with 'Login' text
        inspect_js = """(function(){
            const matches = [];
            document.querySelectorAll('*').forEach(e => {
                const text = e.textContent.trim();
                if(text === 'Login' || text === 'Anmelden'){
                    const r = e.getBoundingClientRect();
                    matches.push({
                        tag: e.tagName,
                        text: text,
                        href: e.href || e.closest('a')?.href || 'none',
                        onclick: e.onclick ? 'yes' : 'no',
                        id: e.id || 'none',
                        className: e.className || 'none',
                        x: r.x, y: r.y, w: r.width, h: r.height,
                        parentChain: []
                    });
                    // Get parent chain
                    let p = e.parentElement;
                    for(let i=0; i<3 && p; i++){
                        matches[matches.length-1].parentChain.push({
                            tag: p.tagName,
                            href: p.href || 'none',
                            className: p.className?.slice(0, 50) || 'none'
                        });
                        p = p.parentElement;
                    }
                }
            });
            return matches;
        })()"""
        
        result = await client.evaluate(session_id, inspect_js, return_by_value=True)
        matches = result.get("result", {}).get("value", [])
        
        import json
        print(f"Found {len(matches)} 'Login' elements:")
        for m in matches:
            print(json.dumps(m, indent=2, ensure_ascii=False))
        
        # Click the first one that's visible and has a reasonable size
        for m in matches:
            if m.get('w', 0) > 30 and m.get('h', 0) > 15:
                print(f"\nClicking element at ({m['x'] + m['w']/2:.0f}, {m['y'] + m['h']/2:.0f})")
                await client.click_at(session_id, m['x'] + m['w']/2, m['y'] + m['h']/2)
                await asyncio.sleep(5)
                
                url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                final_url = url.get("result", {}).get("value", "")
                print(f"URL after click: {final_url}")
                
                body = await client.evaluate(session_id, "document.body.innerText.slice(0, 500)", return_by_value=True)
                print(f"Body: {body.get('result', {}).get('value', '')}")
                break
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_login_inspect.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
