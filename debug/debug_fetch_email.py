#!/usr/bin/env python3
"""
Debug-Skript: GMX Email-Content via direkter HTTP-Request mit frischen Cookies
"""
import asyncio
import re
import json
import base64
import httpx
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def fetch_email_via_api():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    # Step 1: Get current URL and extract navsid / templates if on webmailer
    url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_result.get("result", {}).get("value", "")
    print(f"Current URL: {current_url[:120]}")

    # Step 2: If on webmailer, extract templates parameter and decode
    templates_data = None
    navsid = None
    if "templates=" in current_url:
        m = re.search(r'templates=([^&]+)', current_url)
        if m:
            templates_b64 = m.group(1)
            try:
                # URL-safe base64 might need padding
                padded = templates_b64 + '=' * (4 - len(templates_b64) % 4)
                templates_json = base64.urlsafe_b64decode(padded).decode('utf-8')
                templates_data = json.loads(templates_json)
                print(f"Decoded templates: {json.dumps(templates_data, indent=2)[:500]}")
            except Exception as e:
                print(f"Failed to decode templates: {e}")

    if "navsid=" in current_url:
        navsid = re.search(r'navsid=([^&]+)', current_url)
        navsid = navsid.group(1) if navsid else None
        print(f"navsid: {navsid}")

    # Step 3: Extract iframe src to get jsessionid (if not already on 3c-bap)
    iframe_src = None
    jsessionid = None
    if "3c-bap.gmx.net" not in current_url:
        # Need to navigate to navigator mail page first
        print("Not on 3c-bap, need to get iframe src...")
        # Get SID from current URL or navigate to get one
        sid = None
        if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
            sid = re.search(r'[?&]sid=([^&]+)', current_url)
            sid = sid.group(1) if sid else None
        if not sid and navsid:
            sid = navsid
        if sid:
            mail_url = f"https://bap.navigator.gmx.net/mail?sid={sid}"
            await client.navigate(session_id, mail_url)
            await asyncio.sleep(6)
            iframe_res = await client.evaluate(session_id, '''
            (function() {
                const iframe = document.querySelector("#thirdPartyFrame_mail");
                return iframe ? iframe.src : null;
            })()
            ''', return_by_value=True)
            iframe_src = iframe_res.get('result', {}).get('value', '')
            print(f"Iframe src: {iframe_src}")
    else:
        iframe_src = current_url

    if iframe_src:
        jsessionid_match = re.search(r'jsessionid=([^?&]+)', iframe_src)
        if jsessionid_match:
            jsessionid = jsessionid_match.group(1)
            print(f"Extracted jsessionid: {jsessionid}")

    if not jsessionid:
        print("No jsessionid found!")
        await client.disconnect()
        return

    # Step 4: Find verify email ID from webmailer
    await client.navigate(session_id, iframe_src)
    await asyncio.sleep(5)

    id_res = await client.evaluate(session_id, '''
    (function() {
        function findItems(root) {
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item" && el.textContent.toLowerCase().includes("verify")) {
                    const idAttr = el.getAttribute("id");
                    return idAttr ? idAttr.replace(/^id/, "") : null;
                }
                if (el.shadowRoot) {
                    const found = findItems(el.shadowRoot);
                    if (found) return found;
                }
            }
            return null;
        }
        return findItems(document.body);
    })()
    ''', return_by_value=True)
    mail_id = id_res.get('result', {}).get('value', '')
    print(f"Mail ID from list-mail-item: {mail_id}")

    # Step 5: Extract all cookies from browser
    cookies_res = await client.send_to_session(session_id, "Network.getAllCookies")
    cookies = cookies_res.get("cookies", [])
    print(f"Total cookies: {len(cookies)}")

    # Build cookie dict for httpx
    cookie_dict = {}
    for c in cookies:
        domain = c.get("domain", "")
        if "gmx" in domain:
            name = c.get("name")
            value = c.get("value", "")
            cookie_dict[name] = value

    # Step 6: Try multiple URL patterns
    urls_to_try = []
    if mail_id:
        urls_to_try.append(f"https://3c-bap.gmx.net/mail/client/mailbody/{mail_id}/true;jsessionid={jsessionid}")
        urls_to_try.append(f"https://3c-bap.gmx.net/mail/client/mailbody/{mail_id}/false;jsessionid={jsessionid}")
        urls_to_try.append(f"https://3c-bap.gmx.net/mail/client/mail/print;jsessionid={jsessionid}?mailId={mail_id}&showExternalContent=true")

    # Also try with tmai prefix if mail_id is numeric
    if mail_id and mail_id.isdigit():
        urls_to_try.append(f"https://3c-bap.gmx.net/mail/client/mailbody/tmai{mail_id}/true;jsessionid={jsessionid}")
        urls_to_try.append(f"https://3c-bap.gmx.net/mail/client/mailbody/tmai{mail_id}/false;jsessionid={jsessionid}")

    # Try fetching via templates printUrl with substituted mailId
    if templates_data and mail_id:
        print_url_template = templates_data.get("printUrl", "")
        if print_url_template:
            # Replace tmai0 or {id} with actual mailId
            actual_print_url = print_url_template.replace("tmai0", mail_id).replace("{id}", mail_id)
            urls_to_try.append(actual_print_url)
            print_url_template2 = templates_data.get("withExternal", "")
            if print_url_template2:
                actual_url2 = print_url_template2.replace("tmai0", mail_id).replace("{id}", mail_id)
                urls_to_try.append(actual_url2)

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    print(f"\nTrying {len(urls_to_try)} URLs with {len(cookie_dict)} cookies...")
    for url in urls_to_try:
        print(f"\n--- Trying: {url[:120]}... ---")
        try:
            async with httpx.AsyncClient(cookies=cookie_dict, follow_redirects=True, timeout=20) as http:
                resp = await http.get(url, headers=headers)
                print(f"Status: {resp.status_code}")
                print(f"Content-Type: {resp.headers.get('content-type', 'unknown')}")
                text = resp.text
                if len(text) < 500:
                    print(f"Body: {text[:300]}")
                else:
                    print(f"Body length: {len(text)}")
                    # Check for confirm URL
                    confirm_match = re.search(r'https://app\.fireworks\.ai/[^\s\'"<>]+', text)
                    if confirm_match:
                        print(f"\n✅✅✅ CONFIRM URL FOUND: {confirm_match.group(0)}")
                        break
                    # Check for login page indicator
                    if "login" in text.lower() and "gmx" in text.lower():
                        print(f"⚠️ Got GMX login page")
                    elif "jsessionid" in text.lower() or "session" in text.lower():
                        print(f"⚠️ Possible session error")
                    else:
                        print(f"Body preview: {text[:300]}")
        except Exception as e:
            print(f"Error: {e}")

    await client.disconnect()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(fetch_email_via_api())
