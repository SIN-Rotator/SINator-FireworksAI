#!/usr/bin/env python3
"""
Debug: Prüfe was nach Navigation zum iframe_src tatsächlich gerendert wird.
"""
import asyncio
import re
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def debug_after_nav():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_res.get('result', {}).get('value', '')
    print(f"Current URL: {current_url[:100]}")

    if "3c-bap.gmx.net" not in current_url and "webmailer.gmx.net" not in current_url:
        sid = None
        if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
            m = re.search(r'[?&]sid=([^&]+)', current_url)
            sid = m.group(1) if m else None
        
        if not sid:
            await client.navigate(session_id, "https://www.gmx.net/")
            await asyncio.sleep(4)
            click_res = await client.evaluate(session_id, '''
            (function(){
                const els = Array.from(document.querySelectorAll("a, button, nav a"));
                const emailEl = els.find(e => (e.textContent||"").trim() === "E-Mail");
                if (emailEl) { emailEl.click(); return true; }
                return false;
            })()
            ''', return_by_value=True)
            print(f"Clicked: {click_res}")
            await asyncio.sleep(5)
            url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_res.get('result', {}).get('value', '')
            m = re.search(r'[?&]sid=([^&]+)', current_url)
            sid = m.group(1) if m else None
            print(f"New URL: {current_url[:80]}, sid={sid[:20] if sid else None}")

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
            print(f"Iframe src: {iframe_src[:100]}")
            
            if iframe_src:
                print("Navigating to iframe src...")
                await client.navigate(session_id, iframe_src)
                await asyncio.sleep(10)

    # Take screenshot
    await client.screenshot(session_id, path="/tmp/webmailer_after_fresh_nav.png")
    print("Screenshot saved to /tmp/webmailer_after_fresh_nav.png")

    # Check body text
    body_res = await client.evaluate(session_id, '''
    (function() {
        function t(r,d){if(d>8)return"";let txt=(r.textContent||"");for(const e of r.querySelectorAll("*")){if(e.shadowRoot)txt+=" "+t(e.shadowRoot,d+1);}return txt;}
        return t(document.body,0).slice(0, 2000);
    })()
    ''', return_by_value=True)
    body_text = body_res.get('result', {}).get('value', '')
    print(f"\nBody text (first 1500 chars):\n{body_text[:1500]}")

    # Count list-mail-item elements
    count_res = await client.evaluate(session_id, '''
    (function() {
        function countItems(root) {
            let count = 0;
            const all = root.querySelectorAll("*");
            for (const el of all) {
                if (el.tagName.toLowerCase() === "list-mail-item") count++;
                if (el.shadowRoot) count += countItems(el.shadowRoot);
            }
            return count;
        }
        return countItems(document.body);
    })()
    ''', return_by_value=True)
    count = count_res.get('result', {}).get('value', 0)
    print(f"\nlist-mail-item count: {count}")

    # Check for loading indicators
    loading_res = await client.evaluate(session_id, '''
    (function() {
        const text = document.body.innerText.toLowerCase();
        return {
            hasLoading: text.includes("laden") || text.includes("loading") || text.includes("bitte warten"),
            hasEmpty: text.includes("leer") || text.includes("keine nachrichten") || text.includes("empty"),
        };
    })()
    ''', return_by_value=True)
    loading = loading_res.get('result', {}).get('value', {})
    print(f"Loading indicators: {loading}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_after_nav())
