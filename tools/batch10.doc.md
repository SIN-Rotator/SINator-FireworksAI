# Batch 10 (`batch10.py`)

Generate 10 fresh Fireworks API keys via sequential `rotate.py` calls. V19.4 wrapper created after the V19.3 GMX Delete Fix to validate end-to-end rotation throughput.

## Dependencies

- **Imported by:** (standalone CLI)
- **Imports:** `asyncio`, `json`, `time`, `subprocess`, `pathlib.Path`
- **Calls:** `python3 tools/rotate.py --cdp-port 9222` (subprocess)
- **Requires:** Running pool backend on `http://127.0.0.1:8100` (for stats check)
- **Requires:** Chrome with CDP port 9222 (User Chrome Profile 73 or bot)

## Key Classes/Functions

| Symbol | Purpose |
|--------|---------|
| `log(msg)` | Timestamped logging to stdout + `tools/batch10.log` (overwritten on each run) |
| `get_pool_stats()` | Curl `/api/v1/pool/stats`, returns `(available, total)` tuple |
| `rotate_one(idx)` | Spawns `rotate.py` as async subprocess, streams stdout, returns bool success |
| `main()` | Loop 1-10 rotations, 15s backoff after failure, abort on 3 consecutive fails |

## Important Config/Limits

| Setting | Value |
|---------|-------|
| Target rotations | 10 (hardcoded `for i in range(1, 11)`) |
| Max consecutive failures | 3 → abort |
| Retry backoff | 15s between failed attempts |
| Per-rotation timeout | None (waits for subprocess to exit, ~160s/rotation) |
| Subprocess cwd | Project root (`ROTATE.parent.parent`) |

## Known Caveats

- **BlockingIOError (FIXED V19.5)**: previously crashed on rotation 10 when `print(..., flush=True)` hit a non-blocking stdout under nohup redirect. Now uses `await proc.communicate()` to drain output in one shot + `try/except BlockingIOError` on every log call. See `v19.5-blockingio-fixed` tag.
- **Chrome session must be alive** — if GMX session expires mid-batch, all subsequent rotations fail.
- **No rate-limiting between rotations** — Fireworks may throttle if back-to-back signups from same IP. 160s/rotation provides natural pacing.
- **Subprocess approach means no shared state** — each rotation launches a fresh Python interpreter (~0.5s overhead per call).
- **Log file overwritten on each run** (`LOG.write_text("")` at start) — historical logs are lost.
- **No real-time output** (V19.5 trade-off) — using `communicate()` means you only see output AFTER each rotation completes, not streaming. Acceptable for batch.

## Usage

```bash
python3 tools/batch10.py        # foreground (~27 min for 10 rotations)
nohup python3 tools/batch10.py & # background, log to /tmp/batch10_console.log
```

## Verified Run (2026-06-02)

- Pool start: 245 keys, 4 available
- Pool end: 255 keys, 10 available
- Average rotation time: 159s
- Total runtime: ~28 min
- All 10 keys successfully generated via this script (rotation 10 ran manually after batch died on BlockingIOError)
