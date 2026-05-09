#!/usr/bin/env python3
"""
Debug script: Inject backup cookies into Chrome via CDP and validate GMX session.
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
        target = await get_page_target(client)
        session_id = await client.attach_to_target(target["targetId"])
        await client.send_to_session(session_id, "Network.enable")
        await client.send_to_session(session_id, "Page.enable")
        await client.send_to_session(session_id, "Runtime.enable")
        
        # Step 1: Clear all cookies first
        print("Clearing all cookies...")
        await client.send_to_session(session_id, "Network.clearBrowserCookies")
        await asyncio.sleep(1)
        
        # Step 2: Load backup cookies
        backup_path = "/Users/jeremy/dev/SINator-fireworksai/backup/session/gmx-cookies-master.json"
        with open(backup_path, "r") as f:
            cookies = json.load(f)
        
        print(f"Loaded {len(cookies)} cookies from backup")
        
        # Step 3: Inject cookies via CDP Network.setCookie
        success = 0
        failed = 0
        for cookie in cookies:
            try:
                # Only set cookies for gmx-related domains
                domain = cookie.get("domain", "")
                if not any(d in domain.lower() for d in ["gmx", "navigator", "mail"]) and not cookie.get("name", "").startswith("gmx"):
                    # Skip non-GMX cookies to avoid polluting
                    continue
                
                params = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", ""),
                    "path": cookie.get("path", "/"),
                    "httpOnly": cookie.get("httpOnly", False),
                    "secure": cookie.get("secure", False),
                }
                
                if cookie.get("expires", -1) > 0:
                    params["expires"] = cookie["expires"]
                
                same_site = cookie.get("sameSite", "")
                if same_site and same_site != "":
                    params["sameSite"] = same_site
                
                result = await client.send_to_session(session_id, "Network.setCookie", params)
                if result.get("success"):
                    success += 1
                else:
                    failed += 1
                    if failed <= 5:
                        print(f"  Failed to set {cookie['name']}: {result}")
            except Exception as e:
                failed += 1
                if failed <= 5:
                    print(f"  Exception setting {cookie['name']}: {e}")
        
        print(f"Cookie injection: {success} succeeded, {failed} failed")
        
        # Step 4: Also inject ALL cookies (not just GMX) for good measure
        # because GMX might depend on Google auth cookies
        print("Injecting all backup cookies...")
        success_all = 0
        failed_all = 0
        for cookie in cookies:
            try:
                params = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", ""),
                    "path": cookie.get("path", "/"),
                    "httpOnly": cookie.get("httpOnly", False),
                    "secure": cookie.get("secure", False),
                }
                
                if cookie.get("expires", -1) > 0:
                    params["expires"] = cookie["expires"]
                
                same_site = cookie.get("sameSite", "")
                if same_site and same_site != "":
                    params["sameSite"] = same_site
                
                result = await client.send_to_session(session_id, "Network.setCookie", params)
                if result.get("success"):
                    success_all += 1
                else:
                    failed_all += 1
            except Exception:
                failed_all += 1
        
        print(f"All cookies: {success_all} succeeded, {failed_all} failed")
        
        # Step 5: Validate session
        await asyncio.sleep(2)
        print("\nValidating GMX session...")
        await client.navigate(session_id, "https://www.gmx.net/")
        await asyncio.sleep(4)
        
        click_js = """(function(){
            for(const e of document.querySelectorAll('*')){
                if(e.textContent.trim()==='E-Mail'){
                    e.click();
                    return {clicked: true, tag: e.tagName};
                }
            }
            return {clicked: false};
        })()"""
        
        result = await client.evaluate(session_id, click_js, return_by_value=True)
        data = result.get("result", {}).get("value", {})
        print(f"E-Mail click: {data}")
        
        await asyncio.sleep(5)
        
        url = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        final_url = url.get("result", {}).get("value", "")
        print(f"After click: {final_url}")
        
        is_valid = "navigator.gmx.net/mail?sid=" in final_url or "bap.navigator.gmx.net/mail?sid=" in final_url
        print(f"Session VALID: {is_valid}")
        
        if not is_valid:
            body = await client.evaluate(session_id, "document.body.innerText.slice(0, 800)", return_by_value=True)
            print(f"Body: {body.get('result', {}).get('value', '')}")
        
        await client.screenshot(session_id, path="/Users/jeremy/dev/SINator-fireworksai/debug/gmx_after_cookie_inject.png")
        print("Screenshot saved")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
