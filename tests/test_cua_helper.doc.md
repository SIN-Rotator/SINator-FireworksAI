# Test CUA Helper (`test_cua_helper.py`)

Tests for the `cua_helper` module — dynamic Computer Use API (CUA) window detection. Used to find Chrome windows on macOS for AX-tree-based automation (Fireworks onboarding, CUA fallback flows).

## Dependencies

- **Imported by:** (test runner only)
- **Imports:** `cua_helper` (the system under test)
- **External state:** Chrome with CDP port 9222 (required by `chrome_ok` fixture)
- **External state:** cua-driver daemon running (required by `cua_ok` fixture)
- **Platform:** macOS only (cua-driver is macOS-specific)

## Test Classes

| Class | Purpose |
|-------|---------|
| `TestFindWindow` | Dynamic CUA window detection by title keywords |
| `TestWindowState` | Get current state of a CUA window (position, size, focused, etc.) |

## Test Methods

| Test | Verifies |
|------|----------|
| `test_find_any_chrome` | `find_cua_window()` returns `(pid, wid)` tuple for first on-screen Chrome |
| `test_find_gmx` | `find_cua_window(title_keywords=["GMX", ...])` returns a GMX tab |
| `test_window_state` | `cua_get_window_state(pid, wid)` returns dict with `x`, `y`, `width`, `height`, `focused` |

## ⚠️ macOS Prerequisites

```bash
# cua-driver must be running
cua-driver serve &

# macOS Accessibility permissions required for the Terminal/IDE running the tests
# System Preferences → Security & Privacy → Privacy → Accessibility
```

## Important Config/Limits

| Setting | Value |
|---------|-------|
| cua-driver check | `cua-driver status` returns 0 (handled by `cua_ok` fixture) |
| Chrome CDP | port 9222 reachable (handled by `chrome_ok` fixture) |
| Window search | First matching window by title keyword |
| Title keyword matching | Case-insensitive substring match |

## Known Caveats

- **macOS-only** — tests will skip on Linux/Windows because cua-driver is not available.
- **Requires accessibility permissions** — the process running pytest must be granted accessibility access in macOS System Preferences.
- **Window state may be stale** — CUA returns cached state in some cases. Tests may fail intermittently if a window is rapidly moving.
- **Multiple Chrome windows cause ambiguity** — if multiple Chrome windows match the keyword, the first one is returned (undefined order).

## Usage

```bash
# All CUA tests (skip if cua-driver unavailable)
pytest tests/test_cua_helper.py -v

# Specific test
pytest tests/test_cua_helper.py::TestFindWindow::test_find_gmx -v
```

## See Also

- `agent_toolbox/core/cua_helper.py` — the system under test
- `agent_toolbox/core/cua_helper.doc.md` — CUA architecture and usage
- `skills/sinator-fireworks-flow/SKILL.md` — Fireworks flow uses CUA for onboarding
