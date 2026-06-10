# browser_utils.py — Browser Utility Helpers

## Purpose
Legacy browser utility functions for SPA interaction: CookieYes removal, React input fill, React checkbox click, SPA transition detection. Being superseded by direct SIN-Browser-Tools usage.

## Dependencies
- **Imports from:** Nothing (standalone utilities)
- **Imported by:** `fireworks_service.py` (legacy, now replaced by SIN-Browser-Tools)
- **Reads:** Nothing from disk

## Functions

### `accept_cookieyes_via_js(page)`
Removes CookieYes consent overlays via JS API or localStorage manipulation. Returns True if any method succeeded.

### `wait_for_spa_transition(page, target_text, timeout)`
MutationObserver-based等待 for text to appear in DOM. Used for SPA page transitions where URL doesn't change.

### `fill_react_input(page, selector, value)`
Native React value setter pattern. Sets input value + dispatches `input`/`change` events. Works for React controlled components.

### `click_react_checkbox(page, label_text)`
Finds checkbox by label text (supports `for` attribute, nested checkbox, aria-label). Falls back through multiple strategies.

### `wait_for_url_change(page, target_substring, timeout)`
Polling-based URL change detection. Simpler but less efficient than MutationObserver.

### `scan_main_frame_only(page, pattern)`
Regex scan of main frame's `innerText`. Used for OTP extraction when frame isolation is needed.

## Status
**DEPRECATED** — `fireworks_service.py` now uses SIN-Browser-Tools directly. These utilities remain for backward compatibility but new code should use `sin_browser_tools.tools.*`.
