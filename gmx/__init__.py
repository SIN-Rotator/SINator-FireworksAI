"""
GMX tool library — clean, composable, single-purpose async tools.

Every tool attaches to an ALREADY RUNNING Chrome (CDP, default port 9222) that
has an active GMX session. Each function returns a JSON-serialisable dict with a
"status" field and can also be run from the CLI as  python3 -m gmx.<tool>.

Compose freely, e.g.:

    import asyncio
    from gmx import login, rotate_alias, read_otp

    async def main():
        await login()
        alias = await rotate_alias()
        otp = await read_otp(sender="fireworks")
        print(alias, otp)

    asyncio.run(main())

Available actions:
    check_session() -> session status
    login()         -> log in to GMX
    open_inbox()    -> open the inbox
    create_alias()  -> create an alias
    delete_alias()  -> delete the current alias
    rotate_alias()  -> delete + create in one pass
    read_otp()      -> poll inbox for a verify URL / OTP
    find_email()    -> find & open a mail, return its verify URL

Docs: __init__.doc.md
"""
from gmx.check_session import check_session
from gmx.login import login
from gmx.open_inbox import open_inbox
from gmx.create_alias import create_alias
from gmx.delete_alias import delete_alias
from gmx.rotate_alias import rotate_alias
from gmx.read_otp import read_otp
from gmx.find_email import find_email

__all__ = [
    "check_session",
    "login",
    "open_inbox",
    "create_alias",
    "delete_alias",
    "rotate_alias",
    "read_otp",
    "find_email",
]
