import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

async def test_gmx_login():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()
    target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")
    
    # Navigate to GMX
    await client.navigate(session_id, "https://www.gmx.net/")
    await asyncio.sleep(4)
    
    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL: {url_res.get('result', {}).get('value', '')}")
    
    body_res = await client.evaluate(session_id, "document.body.innerText.slice(0, 200)", return_by_value=True)
    body = body_res.get("result", {}).get("value", "")
    print(f"Body: {body}")
    
    if "Sie sind eingeloggt" in body:
        print("ALREADY LOGGED IN!")
        await client.disconnect()
        return
    
    # Try clicking Login
    click_res = await client.evaluate(session_id, '''
    (function(){
        const btn = Array.from(document.querySelectorAll("a, button")).find(e => 
            (e.textContent || "").trim() === "Login"
        );
        if (btn) { btn.click(); return {clicked: true, text: btn.textContent.trim()}; }
        return {clicked: false};
    })()
    ''', return_by_value=True)
    print(f"Login click: {click_res.get('result', {}).get('value', {})}")
    await asyncio.sleep(4)
    
    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    print(f"URL after click: {url_res.get('result', {}).get('value', '')}")
    
    # Check for email input
    res = await client.evaluate(session_id, '''
    (function(){
        const inputs = document.querySelectorAll("input[type='email'], input[name='username'], input[name='login']");
        return {count: inputs.length, placeholders: Array.from(inputs).map(i => i.placeholder || i.name)};
    })()
    ''', return_by_value=True)
    print(f"Inputs: {res.get('result', {}).get('value', {})}")
    
    body_res = await client.evaluate(session_id, "document.body.innerText.slice(0, 300)", return_by_value=True)
    print(f"Body after click: {body_res.get('result', {}).get('value', '')}")
    
    await client.disconnect()

asyncio.run(test_gmx_login())
