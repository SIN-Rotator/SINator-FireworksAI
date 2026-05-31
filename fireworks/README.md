# `fireworks/` — Fireworks AI Tool Library

Clean, composable, single-purpose tools for every Fireworks AI action used by
SINator. Each tool is **both** a CLI command **and** an importable async
function, and they all share one contract:

- Attach to an **already running Chrome** via CDP (default port `9222`).
- Return a JSON-serialisable `dict` with a `"status"` field.
- Reuse the proven `agent_toolbox.core.fireworks_service` logic, so behaviour
  matches the production rotator exactly — the rotator itself is **not modified**.

## Tools

| Action | CLI | Function |
| --- | --- | --- |
| Sign up + verify | `python3 -m fireworks.signup --email acc@gmx.de` | `signup(email, password=None, port=9222)` |
| Log in | `python3 -m fireworks.login --email acc@gmx.de` | `login(email, password=None, port=9222)` |
| Create API key | `python3 -m fireworks.create_apikey [--name]` | `create_apikey(name="sinator-key", port=9222)` |
| Verify URL | `python3 -m fireworks.verify_account --url "..."` | `verify_account(url, port=9222)` |

Passwords default to the project config (`agent_toolbox.core.config_manager`) when
not passed explicitly. Each CLI prints JSON and exits `0` on success, `1` otherwise.

## Compose a full account flow

```python
import asyncio
from gmx import rotate_alias, read_otp
from fireworks import signup, login, create_apikey

async def main():
    alias = (await rotate_alias())["created_alias"]   # fresh GMX alias
    await signup(email=alias)                          # signup polls GMX + verifies
    await login(email=alias)                           # log in (+ onboarding)
    key = await create_apikey()
    print("API key:", key["api_key"])

asyncio.run(main())
```

`signup` already polls GMX for the verification email and opens the verify URL.
Use the standalone `verify_account` only when you obtained a URL separately (e.g.
from `gmx.read_otp` / `gmx.find_email`).
