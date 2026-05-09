#!/usr/bin/env python3
"""Extract current cookies via CDP and save as new master backup."""

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
        # Find a page target and attach
        targets = await client.send("Target.getTargets")
        target = None
        for t in targets.get("targetInfos", []):
            if t.get("type") == "page":
                target = t
                break
        
        if not target:
            print("No page target found")
            return
        
        session_id = await client.send("Target.attachToTarget", {
            "targetId": target["targetId"],
            "flatten": True
        })
        session_id = session_id.get("sessionId")
        
        # Enable Network domain
        await client.send_to_session(session_id, "Network.enable")
        await asyncio.sleep(0.5)
        
        # Get all cookies
        result = await client.send_to_session(session_id, "Network.getAllCookies")
        cookies = result.get("cookies", [])
        
        print(f"Extracted {len(cookies)} cookies")
        
        # Save to data/gmx-cookies.json
        data_path = "/Users/jeremy/dev/SINator-fireworksai/data/gmx-cookies.json"
        with open(data_path, "w") as f:
            json.dump(cookies, f, indent=2)
        print(f"Saved to: {data_path}")
        
        # Also save as new master backup
        backup_path = "/Users/jeremy/dev/SINator-fireworksai/backup/session/gmx-cookies-master.json"
        with open(backup_path, "w") as f:
            json.dump(cookies, f, indent=2)
        
        # Make read-only
        os.chmod(backup_path, 0o444)
        print(f"Master backup updated: {backup_path} (read-only)")
        
        # Show GMX-related cookies
        gmx_cookies = [c for c in cookies if "gmx" in (c.get("domain", "") + c.get("name", "")).lower()]
        print(f"\nGMX-related cookies: {len(gmx_cookies)}")
        for c in gmx_cookies[:5]:
            print(f"  {c['name']}: {c['domain']} (expires: {c.get('expires', 'session')})")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
