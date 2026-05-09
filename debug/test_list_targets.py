#!/usr/bin/env python3
"""
List all Chrome targets to find any GMX-related tabs.
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
        print(f"Total targets: {len(targets)}\n")
        
        for t in targets:
            url = t.get("url", "")
            title = t.get("title", "")
            tid = t.get("targetId", "")
            ttype = t.get("type", "")
            
            marker = ""
            if "gmx" in url.lower() or "navigator" in url.lower():
                marker = " <-- GMX"
            if "fireworks" in url.lower():
                marker = " <-- FIREWORKS"
            
            print(f"[{ttype}] {title[:80]}")
            print(f"  URL: {url[:120]}")
            print(f"  ID: {tid[:20]}...{marker}")
            print()
        
        # Try to attach to any GMX-related target
        gmx_targets = [t for t in targets if "gmx" in t.get("url", "").lower() or "navigator" in t.get("url", "").lower()]
        if gmx_targets:
            print(f"Found {len(gmx_targets)} GMX-related targets")
            for t in gmx_targets:
                session_id = await client.attach_to_target(t["targetId"])
                url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                body = await client.evaluate(session_id, "document.body.innerText.slice(0, 300)", return_by_value=True)
                print(f"  URL: {url.get('result', {}).get('value', '')}")
                print(f"  Body: {body.get('result', {}).get('value', '')[:200]}")
                print()
        else:
            print("No GMX targets found. Navigating to mail settings directly...")
            
            # Get first page target
            page = [t for t in targets if t.get("type") == "page"][0]
            session_id = await client.attach_to_target(page["targetId"])
            
            # Try direct navigation to alias settings
            print("Navigating to navigator.gmx.net/mail_settings/email_addresses ...")
            await client.navigate(session_id, "https://navigator.gmx.net/mail_settings/email_addresses")
            await asyncio.sleep(5)
            
            url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            final_url = url.get("result", {}).get("value", "")
            print(f"URL: {final_url}")
            
            body = await client.evaluate(session_id, "document.body.innerText.slice(0, 500)", return_by_value=True)
            print(f"Body: {body.get('result', {}).get('value', '')}")
            
            await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_alias_direct.png")
            print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
