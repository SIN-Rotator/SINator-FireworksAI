# Package Index (`__init__.py`)

Public API surface for the `fireworks` package — re-exports the four composable tools as top-level async functions.

## Dependencies

- **Imported by:** external consumers (import `fireworks` or `from fireworks import ...`)
- **Imports:** `fireworks.signup`, `fireworks.login`, `fireworks.create_apikey`, `fireworks.verify_account`

## Exports

| Symbol | Purpose |
|--------|---------|
| `signup()` | create + verify a new Fireworks account |
| `login()` | log in (handles onboarding) |
| `create_apikey()` | generate an API key |
| `verify_account()` | open a verify/confirm URL |

## Usage

```python
import asyncio
from fireworks import signup, login, create_apikey

async def main():
    reg = await signup(email="alias@gmx.de")
    await login(email="alias@gmx.de")
    key = await create_apikey()
    print(key["api_key"])

asyncio.run(main())
```
