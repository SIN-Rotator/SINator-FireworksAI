"""
Debug: Check if Fireworks email is in GMX inbox.
"""
import asyncio
import json
import logging
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    ws_url = await get_browser_ws_endpoint(9222)
    client = CDPClient(ws_url)
    await client.connect()
    target = await get_page_target(client, url_filter="gmx.net")
    if not target:
        target = await get_page_target(client)
    target_id = target["targetId"]
    session_id = await client.attach_to_target(target_id)
    await client.send_to_session(session_id, "Page.enable")
    await client.send_to_session(session_id, "Runtime.enable")

    # Navigate to bap.navigator.gmx.net/mail to get iframe src
    await client.navigate(session_id, "https://bap.navigator.gmx.net/mail")
    await asyncio.sleep(4)

    # Get iframe src
    iframe_result = await client.evaluate(session_id, '''
    (function() {
        const iframe = document.querySelector("#thirdPartyFrame_mail");
        return iframe ? iframe.src : null;
    })()
    ''', return_by_value=True)
    iframe_src = iframe_result.get('result', {}).get('value', '')
    logger.info(f"iframe src: {iframe_src}")

    if iframe_src:
        await client.navigate(session_id, iframe_src)
        await asyncio.sleep(3)

        # Get all visible text
        text_result = await client.evaluate(session_id, '''
        (function() {
            const all = Array.from(document.querySelectorAll("*"))
                .filter(el => el.offsetParent !== null)
                .map(el => el.textContent.trim())
                .filter(t => t.length > 0);
            return all.slice(0, 30);
        })()
        ''', return_by_value=True)
        texts = text_result.get('result', {}).get('value', [])
        logger.info(f"Visible texts: {json.dumps(texts, indent=2, ensure_ascii=False)}")

        # Search for fireworks
        search = await client.evaluate(session_id, '''
        (function() {
            const bodyText = document.body.textContent.toLowerCase();
            const hasFireworks = bodyText.includes("fireworks");
            const hasConfirm = bodyText.includes("confirm");
            const hasVerify = bodyText.includes("verify");
            return {hasFireworks, hasConfirm, hasVerify, preview: document.body.textContent.trim().slice(0, 500)};
        })()
        ''', return_by_value=True)
        logger.info(f"Search result: {json.dumps(search.get('result', {}).get('value', {}), indent=2, ensure_ascii=False)}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
