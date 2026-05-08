#!/usr/bin/env python3
"""
Debug-Skript: GMX Email-Content speichern und Confirmation URL extrahieren
"""
import asyncio
import re
import json
import httpx
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def save_and_extract():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    await asyncio.sleep(2)

    # Get current URL and extract navsid / templates
    url_result = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_result.get("result", {}).get("value", "")
    navsid = None
    if "navsid=" in current_url:
        m = re.search(r'navsid=([^&]+)', current_url)
        navsid = m.group(1) if m else None

    # Navigate to navigator mail page to get iframe src with fresh jsessionid
    if not navsid:
        print("No navsid found!")
        await client.disconnect()
        return

    mail_url = f"https://bap.navigator.gmx.net/mail?sid={navsid}"
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

    if not iframe_src:
        await client.disconnect()
        return

    jsessionid_match = re.search(r'jsessionid=([^?&]+)', iframe_src)
    jsessionid = jsessionid_match.group(1) if jsessionid_match else None
    print(f"jsessionid: {jsessionid}")

    # Navigate to webmailer to find verify email mailId
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
    print(f"Mail ID: {mail_id}")

    # Extract all cookies
    cookies_res = await client.send_to_session(session_id, "Network.getAllCookies")
    cookies = cookies_res.get("cookies", [])
    cookie_dict = {}
    for c in cookies:
        domain = c.get("domain", "")
        if "gmx" in domain:
            name = c.get("name")
            value = c.get("value", "")
            cookie_dict[name] = value

    # Fetch email HTML
    email_url = f"https://3c-bap.gmx.net/mail/client/mailbody/tmai{mail_id}/true;jsessionid={jsessionid}"
    print(f"Fetching: {email_url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    async with httpx.AsyncClient(cookies=cookie_dict, follow_redirects=True, timeout=20) as http:
        resp = await http.get(email_url, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type', 'unknown')}")
        html = resp.text
        print(f"Body length: {len(html)}")

        with open("/tmp/email_content.html", "w") as f:
            f.write(html)
        print("Saved to /tmp/email_content.html")

        # Extract ALL fireworks.ai URLs
        urls = re.findall(r'https://app\.fireworks\.ai/[^\s\'"<>]+', html)
        print(f"\nAll fireworks.ai URLs found ({len(urls)}):")
        for url in urls:
            print(f"  {url}")

        # Extract confirm/verify/token URLs specifically
        confirm_urls = [u for u in urls if any(k in u.lower() for k in ["confirm", "verify", "token", "auth", "activate", "signup"])]
        print(f"\nConfirm-like URLs: {confirm_urls}")

        # Also search for URLs in href attributes
        href_urls = re.findall(r'href="(https://app\.fireworks\.ai/[^"]+)"', html)
        print(f"\nHREF URLs: {href_urls}")

    await client.disconnect()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(save_and_extract())
