"""
Fireworks AI tool library — clean, composable, single-purpose async tools.

Every tool attaches to an ALREADY RUNNING Chrome (CDP, default port 9222). Each
function returns a JSON-serialisable dict with a "status" field and can also be
run from the CLI as  python3 -m fireworks.<tool>.

Full account flow, composed:

    import asyncio
    from gmx import rotate_alias, read_otp
    from fireworks import signup, login, create_apikey

    async def main():
        alias = (await rotate_alias())["created_alias"]
        reg = await signup(email=alias)            # signup polls GMX + verifies
        await login(email=alias)
        key = await create_apikey()
        print(key["api_key"])

    asyncio.run(main())

Available actions:
    signup()         -> create + verify a new account
    login()          -> log in (handles onboarding)
    create_apikey()  -> generate an API key
    verify_account() -> open a verify/confirm URL

Docs: __init__.doc.md
"""
from fireworks.signup import signup
from fireworks.login import login
from fireworks.create_apikey import create_apikey
from fireworks.verify_account import verify_account

__all__ = [
    "signup",
    "login",
    "create_apikey",
    "verify_account",
]
