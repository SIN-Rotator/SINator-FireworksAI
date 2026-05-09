#!/usr/bin/env python3
"""Validate GMX session after cookie restore."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_toolbox.core.gmx_service import get_gmx_service
from agent_toolbox.core.cdp_client import CDPClient, get_browser_ws_endpoint, get_page_target


async def main():
    ws_url = await get_browser_ws_endpoint(cdp_port=9222)
    client = CDPClient(ws_url)
    await client.connect()
    
    try:
        target = await get_page_target(client)
        session_id = await client.attach_to_target(target["targetId"])
        
        gmx = get_gmx_service()
        result = await gmx._ensure_mail_session(client, session_id)
        print(f"Session check result: {result}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
