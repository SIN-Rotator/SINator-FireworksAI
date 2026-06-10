#!/usr/bin/env python3
"""
gmx.read_otp — Poll the GMX inbox for an OTP / verification link.

Uses the proven CDP-based reader (MailCheck/OOPIF + Shadow-DOM aware) that
finds the sender mail, opens it and extracts the confirm/verify URL.

CLI:     python3 -m gmx.read_otp [--sender fireworks] [--retries 12] [--port 9222]
Compose: from gmx import read_otp; res = await read_otp()

Returns: {"status": "success" | "not_found" | "error",
          "otp_url": "https://app.fireworks.ai/...", "error": "..."}

Docs: read_otp.doc.md
"""
from typing import Any, Dict

from gmx._lib import get_service, run, DEFAULT_CDP_PORT


async def read_otp(sender: str = "fireworks", retries: int = 12,
                   retry_delay: int = 5, port: int = DEFAULT_CDP_PORT) -> Dict[str, Any]:
    """Poll the inbox for a verification email and return its confirm URL."""
    return await get_service().read_otp(
        sender_filter=sender, max_retries=retries, retry_delay=retry_delay, cdp_port=port,
    )


def _add_args(p):
    p.add_argument("--sender", default="fireworks", help="Sender keyword to match (default: fireworks)")
    p.add_argument("--retries", type=int, default=12, help="Polling attempts (default: 12)")
    p.add_argument("--retry-delay", type=int, default=5, dest="retry_delay",
                   help="Seconds between attempts (default: 5)")


async def _action(args) -> Dict[str, Any]:
    return await read_otp(sender=args.sender, retries=args.retries,
                          retry_delay=args.retry_delay, port=args.port)


if __name__ == "__main__":
    run(_action, description="Read an OTP / verify URL from the GMX inbox", add_args=_add_args)
