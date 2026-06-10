# UA Patch (`_ua_patch.py`)

Monkey-patches the `openai.OpenAI` constructor to spoof the User-Agent header
(Mozilla/Chrome instead of `OpenAI/Python`) and disable SDK-level retries.

## Dependencies

- **Imported by:** (import at project entry point before any OpenAI calls)
- **Imports:** `openai`, `functools`

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `_patched_init(self, *args, **kwargs)` | Wraps `OpenAI.__init__` — injects `default_headers` and sets `max_retries=0` |

## Important Config/Limits

- Patches the **real** `openai.OpenAI` class (not any proxy/wrapper).
- Patched headers: `User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ...`
- `max_retries` forced to `0` — retry is delegated to the pool-router (`localhost:9998`).

## Known Caveats

- Must be imported **before** any `OpenAI()` instantiation.
- If `openai` changes its `__init__` signature, the `@functools.wraps` wrapper may miss new parameters.
- Only patches the `OpenAI` class, not `AsyncOpenAI` or Azure variants (unless they share the same `__init__`).
