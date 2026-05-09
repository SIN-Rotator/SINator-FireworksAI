#!/usr/bin/env python3
"""
Debug script: Check GMX inbox for Fireworks verification emails.
Uses iframe attachment method (VERIFIED for mailbody extraction).
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target


async def main():
    ws_url = await get_browser_ws_endpoint(cdp_port=9222)
    client = CDPClient(ws_url)
    await client.connect()
    
    try:
        # Navigate to GMX inbox
        targets = await client.get_targets()
        page_target = None
        for t in targets:
            if t.get("type") == "page":
                page_target = t
                break
        
        if not page_target:
            print("No page target found")
            return
        
        session_id = await client.attach_to_target(page_target["targetId"])
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        
        # Navigate to GMX mail
        await client.navigate(session_id, "https://navigator.gmx.net/mail")
        await asyncio.sleep(5)
        
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"GMX URL: {url.get('result', {}).get('value', '')}")
        
        # Get all targets to find mailbody iframe
        targets2 = await client.get_targets()
        mailbody_targets = [t for t in targets2 if "mailbody" in t.get("url", "")]
        print(f"Found {len(mailbody_targets)} mailbody targets")
        
        for t in mailbody_targets[:5]:
            print(f"  - {t.get('title', 'no title')}: {t.get('url', '')[:100]}")
        
        # If no mailbody targets, check main frame for email list
        if not mailbody_targets:
            print("\nNo mailbody iframes. Checking main frame for email subjects...")
            # Try to find email subjects in the main frame
            subjects_js = """(function(){
                const subjects = [];
                document.querySelectorAll('*').forEach(el => {
                    const text = el.textContent.trim();
                    if(text.length > 10 && text.length < 200){
                        subjects.push(text);
                    }
                });
                return subjects.slice(0, 20);
            })()"""
            result = await client.evaluate(session_id, subjects_js, return_by_value=True)
            texts = result.get("result", {}).get("value", [])
            print(f"Some texts from page: {texts[:10]}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_inbox_check.png")
        print("Screenshot saved to debug/gmx_inbox_check.png")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
