#!/usr/bin/env python3
"""
Inspect the appa.gmx.net/account-manager.html iframe — might contain the logged-in session.
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint


async def main():
    ws_url = await get_browser_ws_endpoint(cdp_port=9222)
    client = CDPClient(ws_url)
    await client.connect()
    
    try:
        targets = await client.get_targets()
        
        # Find the account-manager iframe
        acct_target = None
        for t in targets:
            if "account-manager" in t.get("url", ""):
                acct_target = t
                break
        
        if not acct_target:
            print("account-manager iframe not found")
            return
        
        session_id = await client.attach_to_target(acct_target["targetId"])
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        
        print("=== account-manager.html content ===")
        body = await client.evaluate(session_id, "document.body.innerText", return_by_value=True)
        body_text = body.get("result", {}).get("value", "")
        print(f"Body text:\n{body_text[:1000]}\n")
        
        # Check for any links or buttons
        links_js = """(function(){
            const links = [];
            document.querySelectorAll('a, button').forEach(el => {
                links.push({
                    text: el.textContent.trim().slice(0, 80),
                    href: el.href || 'none',
                    tag: el.tagName
                });
            });
            return links;
        })()"""
        
        links_result = await client.evaluate(session_id, links_js, return_by_value=True)
        links = links_result.get("result", {}).get("value", [])
        print(f"Links/buttons found: {len(links)}")
        for l in links[:20]:
            print(f"  [{l['tag']}] '{l['text']}' -> {l['href'][:80] if l['href'] != 'none' else 'none'}")
        
        # Check URL
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"\nURL: {url.get('result', {}).get('value', '')}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_account_manager.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
