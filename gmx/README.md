# `gmx/` — GMX Tool Library

Clean, composable, single-purpose tools for every GMX action used by SINator.
Each tool is **both** a CLI command **and** an importable async function, and they
all share one contract:

- Attach to an **already running Chrome** via CDP (default port `9222`) that has
  an active GMX session. They never launch their own browser.
- Return a JSON-serialisable `dict` with a `"status"` field.
- Reuse the proven `agent_toolbox.core.gmx_service` logic, so behaviour matches
  the production rotator exactly — the rotator itself is **not modified**.

## Tools

| Action | CLI | Function |
| --- | --- | --- |
| Check session | `python3 -m gmx.check_session` | `check_session(port=9222)` |
| Log in | `python3 -m gmx.login [--email --password]` | `login(email=None, password=None, port=9222)` |
| Open inbox | `python3 -m gmx.open_inbox` | `open_inbox(port=9222)` |
| Create alias | `python3 -m gmx.create_alias [--name]` | `create_alias(name=None, port=9222)` |
| Delete alias | `python3 -m gmx.delete_alias` | `delete_alias(port=9222)` |
| Rotate alias | `python3 -m gmx.rotate_alias [--name]` | `rotate_alias(name=None, port=9222)` |
| Read OTP | `python3 -m gmx.read_otp [--sender --retries]` | `read_otp(sender="fireworks", retries=12, port=9222)` |
| Find & open email | `python3 -m gmx.find_email [--keyword --timeout]` | `find_email(keyword="fireworks", timeout=8, port=9222)` |

Each CLI prints the JSON result and exits `0` on a success status, `1` otherwise
— so they chain cleanly in shell: `python3 -m gmx.login && python3 -m gmx.rotate_alias`.

## Compose in Python

```python
import asyncio
from gmx import login, rotate_alias, read_otp

async def main():
    await login()
    alias = await rotate_alias()           # {"status": "success", "created_alias": "..."}
    otp = await read_otp(sender="fireworks")
    print(alias["created_alias"], otp["otp_url"])

asyncio.run(main())
```

## Notes

- `find_email` is the library version of the standalone `tools/gmx_open_email.py`
  debug tool. It only **finds and opens** a mail (Shadow-DOM aware) and returns
  any verify/confirm URL it sees.
- All Shadow-DOM traversal penetrates `sc-webmailer-mail-list-h` (the GMX
  webmailer WebComponent) — see `docs/shadow-dom-fix-plan.md`.
