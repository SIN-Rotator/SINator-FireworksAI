"""
Debug bap.navigator.gmx.net/mail page load.
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

    await client.navigate(session_id, "https://bap.navigator.gmx.net/mail")
    await asyncio.sleep(5)

    url_res = await client.evaluate(session_id, "window.location.href", return_by_value=True)
    current_url = url_res.get('result', {}).get('value', '')
    logger.info(f"URL after nav: {current_url}")

    body = await client.evaluate(session_id, "document.body.innerText.slice(0, 300)", return_by_value=True)
    logger.info(f"Body preview: {body.get('result', {}).get('value', '')}")

    iframes = await client.evaluate(session_id, '''
    (function() {
        const frames = document.querySelectorAll("iframe");
        return Array.from(frames).map(f => ({id: f.id, name: f.name, src: f.src}));
    })()
    ''', return_by_value=True)
    logger.info(f"Iframes: {json.dumps(iframes.get('result', {}).get('value', []), indent=2)}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
