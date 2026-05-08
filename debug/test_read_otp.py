#!/usr/bin/env python3
"""
Test-Skript: Neue read_otp Methode testen
"""
import asyncio
from agent_toolbox.core.gmx_service import get_gmx_service

async def test_read_otp():
    svc = get_gmx_service()
    result = await svc.read_otp(sender_filter="fireworks", max_retries=3, retry_delay=3, cdp_port=9222)
    print(f"Status: {result['status']}")
    print(f"OTP URL: {result.get('otp_url')}")
    print(f"Execution time: {result.get('execution_time')}")
    print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_read_otp())
