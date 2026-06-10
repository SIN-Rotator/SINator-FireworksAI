# SINator CLI (`sinator-cli.py`)

Legacy CLI for generating Fireworks AI API keys directly via
`GmxService` + `FireworksService` + `PoolManager`. Superseded by `rotate.py`.

## Dependencies

- **Imported by:** (standalone CLI)
- **Imports:** `sys`, `os`, `json`, `asyncio`, `argparse`, `pathlib.Path`, `agent_toolbox.core.*`

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `generate_key(password, alias_name)` | Register Fireworks account with given alias+password, save key to pool |
| `main()` | CLI entry — supports `--password`, `--alias`, `--count`, `--json` flags |

## Important Config/Limits

Requires Chrome + CUA-Driver + GMX session. No OTP polling — accounts may remain unverified.

## Known Caveats

- **Legacy tool** — superseded by the `rotate.py` orchestrated flow which handles OTP, onboarding, and session recovery.
- No OTP polling: registration may create unverified accounts that block API key generation.
- Count flag generates sequentially; if any registration fails, the loop breaks early.
