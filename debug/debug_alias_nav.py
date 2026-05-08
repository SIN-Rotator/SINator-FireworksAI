#!/usr/bin/env python3
"""
Debug: Teste _navigate_to_all_email_addresses wenn Browser auf webmailer ist
"""
import asyncio
import re
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def debug_alias_nav():
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

    # Simulate what _navigate_to_all_email_addresses does when not on allEmailAddresses
    if "allEmailAddresses" in current_url:
        print("Already on allEmailAddresses")
        await client.disconnect()
        return

    if "3c-bap.gmx.net" in current_url and "signature" in current_url:
        print("On 3c-bap signature page")
        # Click E-Mail-Adressen
        click_res = await client.evaluate(session_id, '''
        (function(){
            const ea = Array.from(document.querySelectorAll("*")).find(e => e.textContent.trim() === "E-Mail-Adressen");
            if (ea) { ea.click(); return true; }
            return false;
        })()
        ''', return_by_value=True)
        print(f"Clicked E-Mail-Adressen: {click_res}")
        await asyncio.sleep(6)
        url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        print(f"URL after click: {url_res.get('result', {}).get('value', '')[:100]}")
        await client.disconnect()
        return

    if "bap.navigator.gmx.net" in current_url and "sid=" in current_url:
        sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
        sid = sid_match.group(1) if sid_match else None
        if sid:
            jump_url = f"https://bap.navigator.gmx.net/navigator/jump/to/mail_settings?sid={sid}"
            print(f"Using jump URL: {jump_url}")
            await client.navigate(session_id, jump_url)
            await asyncio.sleep(6)
            url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            new_url = url_res.get('result', {}).get('value', '')
            print(f"URL after jump: {new_url[:100]}")
            if "3c-bap.gmx.net" in new_url and "signature" in new_url:
                click_res = await client.evaluate(session_id, '''
                (function(){
                    const ea = Array.from(document.querySelectorAll("*")).find(e => e.textContent.trim() === "E-Mail-Adressen");
                    if (ea) { ea.click(); return true; }
                    return false;
                })()
                ''', return_by_value=True)
                print(f"Clicked E-Mail-Adressen: {click_res}")
                await asyncio.sleep(6)
                url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
                print(f"URL after click: {url_res.get('result', {}).get('value', '')[:100]}")
            await client.disconnect()
            return

    # Fallback: _ensure_mail_session equivalent
    print("Using _ensure_mail_session fallback...")
    await client.navigate(session_id, "https://www.gmx.net/")
    await asyncio.sleep(4)

    body_text = await client.evaluate(session_id, "document.body.innerText", return_by_value=True)
    text = body_text.get("result", {}).get("value", "")
    if "Sie sind eingeloggt" not in text and "Zum Postfach" not in text and "E-Mail" not in text:
        print("NOT LOGGED IN!")
        await client.disconnect()
        return

    click_res = await client.evaluate(session_id, '''
    (function(){
        const els = Array.from(document.querySelectorAll("a, button, [role=link], nav a"));
        const emailEl = els.find(e => (e.textContent||"").trim() === "E-Mail");
        if (emailEl) { emailEl.click(); return true; }
        return false;
    })()
    ''', return_by_value=True)
    print(f"Clicked E-Mail nav: {click_res}")
    await asyncio.sleep(5)

    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_res.get('result', {}).get('value', '')
    print(f"URL after E-Mail click: {current_url[:100]}")

    sid_match = re.search(r'[?&]sid=([^&]+)', current_url)
    sid = sid_match.group(1) if sid_match else None
    print(f"SID extracted: {sid[:30] if sid else None}")

    if sid and "navigator.gmx.net" in current_url:
        settings_url = f"https://bap.navigator.gmx.net/mail_settings?sid={sid}"
        print(f"Navigating to settings: {settings_url}")
        await client.navigate(session_id, settings_url)
        await asyncio.sleep(5)
        url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        settings_url_actual = url_res.get('result', {}).get('value', '')
        print(f"Settings URL actual: {settings_url_actual[:100]}")

        # Now try jump URL from settings
        jump_url = f"https://bap.navigator.gmx.net/navigator/jump/to/mail_settings?sid={sid}"
        print(f"Navigating to jump URL: {jump_url}")
        await client.navigate(session_id, jump_url)
        await asyncio.sleep(6)
        url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
        jump_url_actual = url_res.get('result', {}).get('value', '')
        print(f"Jump URL actual: {jump_url_actual[:100]}")

        if "3c-bap.gmx.net" in jump_url_actual and "signature" in jump_url_actual:
            click_res = await client.evaluate(session_id, '''
            (function(){
                const ea = Array.from(document.querySelectorAll("*")).find(e => e.textContent.trim() === "E-Mail-Adressen");
                if (ea) { ea.click(); return true; }
                return false;
            })()
            ''', return_by_value=True)
            print(f"Clicked E-Mail-Adressen on 3c-bap: {click_res}")
            await asyncio.sleep(6)
            url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
            final_url = url_res.get('result', {}).get('value', '')
            print(f"Final URL: {final_url[:100]}")
            if "allEmailAddresses" in final_url:
                print("✅ SUCCESS: on allEmailAddresses")
            else:
                print("❌ FAILED: not on allEmailAddresses")
        else:
            print(f"❌ Not on 3c-bap signature page after jump")
    else:
        print("❌ No SID or not on navigator domain")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(debug_alias_nav())
