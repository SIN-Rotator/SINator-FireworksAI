# Rotation Routes (`rotation.py`)

FastAPI router for the full GMX+Fireworks account rotation flow — spawns `rotate.py` as a subprocess.

## Dependencies

- **Imported by:** `agent_toolbox/start_toolbox.py`
- **Imports:** `fastapi.APIRouter`, `agent_toolbox.api.schemas`, `asyncio.subprocess`, `osascript` (AppleScript)

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/rotation/full` | POST | Execute full rotation: GMX alias → Fireworks signup/login → API key → pool |

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `full_rotation()` | Orchestrate subprocess call to `tools/rotate.py`, parse stdout for results |

## Important Config/Limits

- **ROTATE_SCRIPT:** `tools/rotate.py` (resolved relative to project root)
- Opens a second Chrome window via AppleScript for visual feedback
- Passes `--gmx-email`, `--gmx-password`, `--password`, `--cdp-port 9222` to the script
- Reads credentials from `config_manager` config

## Known Caveats

- **Pre-existing Python indentation bug on lines 40-49** — the subprocess command assembly block uses 2-space indent instead of 4-space, causing `IndentationError`. The fallback/error path below is unaffected.
- Uses blocking subprocess — the response waits for the full rotation to complete
- AppleScript window manipulation is macOS-only
- No timeout protection on the subprocess
