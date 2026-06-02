# Batch Rotate (`batch_rotate.py`)

Runs `rotate.py` in a loop to generate N new keys (default 69) until the target is reached or 3 consecutive failures occur.

## Dependencies

- **Imported by:** (standalone CLI)
- **Imports:** `asyncio`, `json`, `time`, `sys`, `subprocess`, `pathlib.Path`, `http.client`, `agent_toolbox.core.config_manager`

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `log(msg)` | Timestamped logging to both stdout and `data/batch-rotate.log` |
| `count_available()` | GET `/api/v1/pool/stats` to check current pool state |
| `rotate_one()` | Spawns `rotate.py` as subprocess with config credentials, captures output |
| `main()` | Loop: rotate → check success → retry with 30s backoff after failures |

## Important Config/Limits

| Setting | Value |
|---------|-------|
| `TARGET` | 69 (hardcoded) |
| Max consecutive failures | 3 → abort |
| Checkpoint every | 5 successes |

## Known Caveats

- **Chrome + GMX session must be alive** — each rotation expects CDP port 9222 with a valid session.
- If no session backup is available, the batch may fail after the first rotation (GMX session expires).
- The subprocess approach means each rotation is isolated; if Chrome crashes, the entire batch stops.
- **BlockingIOError (FIXED V19.5)**: previously crashed on long runs when child wrote more than the pipe buffer could hold, or when `print(flush=True)` hit a non-blocking stdout. Fixed via `await proc.communicate()` + `try/except` on every log call. See `v19.5-blockingio-fixed` tag.
- **No real-time output** (V19.5 trade-off) — using `communicate()` means you only see output AFTER each rotation completes. Use `tail -f tools/batch-rotate.log` for progress.
