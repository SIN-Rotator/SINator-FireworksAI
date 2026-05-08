#!/usr/bin/env python3
"""
Debug: Teste die JS-Evaluation aus read_otp Schritt für Schritt
"""
import asyncio
import re
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def debug_read_otp_js():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()

    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    # Check current URL
    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_res.get('result', {}).get('value', '')
    print(f"Current URL: {current_url[:100]}")

    # If not on webmailer, navigate there
    if "3c-bap.gmx.net" not in current_url and "webmailer.gmx.net" not in current_url:
        # Get SID from current URL or navigate to get one
        sid = None
        if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
            m = re.search(r'[?&]sid=([^&]+)', current_url)
            sid = m.group(1) if m else None
        
        if not sid:
            print("No SID, navigating to gmx homepage...")
            await client.navigate(session_id, "https://www.gmx.net/")
            await asyncio.sleep(4)
            # click E-Mail
            click_res = await client.evaluate(session_id, '''
            (function(){
                const els = Array.from(document.querySelectorAll("a, button, nav a"));
                const emailEl = els.find(e => (e.textContent||"").trim() === "E-Mail");
                if (emailEl) { emailEl.click(); return true; }
                return false;
            })()
            ''', return_by_value=True)
            print(f"Clicked nav: {click_res}")
            await asyncio.sleep(5)
            url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            current_url = url_res.get('result', {}).get('value', '')
            m = re.search(r'[?&]sid=([^&]+)', current_url)
            sid = m.group(1) if m else None
            print(f"URL after nav: {current_url[:80]}, sid={sid[:20] if sid else None}")

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
            print(f"Iframe src: {iframe_src[:80]}")
            
            if iframe_src:
                await client.navigate(session_id, iframe_src)
                await asyncio.sleep(10)

    # Now test the exact JS from read_otp
    safe_filter = "fireworks"
    items_js = f'''(function() {{
        function findItems(root) {{
            let items = [];
            const all = root.querySelectorAll("*");
            for (const el of all) {{
                if (el.tagName.toLowerCase() === "list-mail-item") {{
                    const text = (el.textContent || "").toLowerCase();
                    if (text.includes("{safe_filter}")) {{
                        const idAttr = el.getAttribute("id");
                        const mailId = idAttr ? idAttr.replace(/^id/, "") : null;
                        if (mailId) {{
                            items.push({{
                                mailId: mailId,
                                text: el.textContent.trim().slice(0, 120).replace(/\\s+/g, " "),
                            }});
                        }}
                    }}
                }}
                if (el.shadowRoot) {{
                    items = items.concat(findItems(el.shadowRoot));
                }}
            }}
            return items;
        }}
        return findItems(document.body);
    }})()'''
    
    items_res = await client.evaluate(session_id, items_js, return_by_value=True)
    items = items_res.get('result', {}).get('value', [])
    print(f"\nFound {len(items)} matching list-mail-item elements:")
    for item in items[:5]:
        print(f"  mailId={item.get('mailId')} | text={item.get('text', '')[:80]}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_read_otp_js())
