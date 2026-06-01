# File: `cua_helper.py`

CUA (Computer Use Agent) window detection and interaction helper. Finds Chrome windows by title keywords and provides click/type/get-state via `cua-driver` CLI.

## Dependencies

- **Imported by:** `agent_toolbox/core/fireworks_service.py`, `tests/conftest.py`, `tests/test_cua_helper.py`
- **Imports:** `subprocess`, `json`, `os`, `time`, `logging`

## Key Functions

| Symbol | Purpose |
|--------|---------|
| `find_cua_window()` | Find a CUA-accessible window by app name + title keywords (2-pass + activate retry) |
| `cua_click()` | Click an element by its AX tree index via CUA driver |
| `cua_type_text()` | Type text via macOS CGEvent keystrokes (does NOT work on React controlled inputs) |
| `cua_get_window_state()` | Get AX tree markdown for a window |

## Known Caveats

- `cua_type_text()` does NOT work for React controlled inputs — use Playwright `fill()` instead
- Requires `cua-driver` CLI installed and running
- `find_cua_window()` retries by activating Chrome if first pass finds nothing (can be disruptive)
- Accepts `SINATOR_CHROME_PID` env var for PID targeting
