#!/usr/bin/env python3
"""Test FULL rotation flow: GMX alias + Fireworks registration + confirm + login + API key."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_toolbox.core.gmx_service import get_gmx_service
from agent_toolbox.core.fireworks_service import get_fireworks_service


async def main():
    gmx = get_gmx_service()
    fw = get_fireworks_service()
    
    # STEP 1: Rotate GMX alias
    print("=== STEP 1: Rotate GMX Alias ===")
    alias_result = await gmx.rotate_alias(cdp_port=9222)
    print(f"Alias result: {alias_result}")
    
    if alias_result.get("status") != "success":
        print("Alias rotation failed — cannot proceed")
        return
    
    alias_email = alias_result.get("created_alias")
    alias_name = alias_result.get("created_alias_name")
    print(f"New alias: {alias_email}")
    
    # STEP 2: Register Fireworks
    print("\n=== STEP 2: Register Fireworks ===")
    password = "SinatorTest2024!"
    reg_result = await fw.register(
        email=alias_email,
        password=password,
        cdp_port=9222,
    )
    print(f"Registration result: {reg_result}")
    
    if reg_result.get("status") != "success":
        print("Registration failed — cannot proceed")
        return
    
    # STEP 3: Read verification email from GMX
    print("\n=== STEP 3: Read GMX OTP ===")
    otp_result = await gmx.read_otp(
        sender_filter="fireworks",
        max_retries=12,
        retry_delay=5000,
        cdp_port=9222,
    )
    print(f"OTP result: {otp_result}")
    
    if otp_result.get("status") != "success":
        print("OTP not found — cannot proceed")
        return
    
    confirm_url = otp_result.get("otp_url")
    print(f"Confirm URL: {confirm_url}")
    
    # STEP 4: Confirm Fireworks account
    print("\n=== STEP 4: Confirm Fireworks ===")
    confirm_result = await fw.confirm(
        confirm_url=confirm_url,
        email=alias_email,
        password=password,
        cdp_port=9222,
    )
    print(f"Confirm result: {confirm_result}")
    
    # STEP 5: Login to Fireworks
    print("\n=== STEP 5: Login to Fireworks ===")
    login_result = await fw.login(
        email=alias_email,
        password=password,
        cdp_port=9222,
    )
    print(f"Login result: {login_result}")
    
    if not login_result.get("logged_in"):
        print("Login failed — cannot proceed")
        return
    
    # STEP 6: Create API key
    print("\n=== STEP 6: Create API Key ===")
    key_result = await fw.create_api_key(
        key_name=f"sinator-{alias_name}",
        cdp_port=9222,
    )
    print(f"API Key result: {key_result}")
    
    if key_result.get("status") == "success":
        print(f"\n✅ FULL FLOW COMPLETE!")
        print(f"Alias: {alias_email}")
        print(f"API Key: {key_result.get('api_key')}")
    else:
        print(f"\n⚠️ Flow incomplete — API key creation failed")


if __name__ == "__main__":
    asyncio.run(main())
