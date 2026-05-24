"""
cua_helper.py — CUA Window Detection Helper

Shared across fireworks_service.py and gmx_service.py.
Provides dynamic PID/WID detection to replace hardcoded values.

Usage:
    from cua_helper import find_cua_window

    result = find_cua_window(title_keywords=["fireworks"])
    if result:
        pid, wid = result
        # use pid, wid for CUA calls
    else:
        # handle not found
"""
import subprocess
import json
import logging
import time

logger = logging.getLogger(__name__)


def _activate_chrome():
    try:
        subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'],
                       capture_output=True, timeout=5)
        time.sleep(1.5)
    except Exception:
        pass


def find_cua_window(
    title_keywords=None,
    app_name="Google Chrome",
    include_minimized_fallback=True,
) -> tuple:
    """Find a CUA-accessible window by title keywords.

    Scans all Chrome windows via cua-driver list_windows and returns
    the first match. Case-insensitive matching for both app_name and title.

    Args:
        title_keywords: List of strings to match in window title
                        (case-insensitive). If None, returns first on-screen
                        Chrome window.
        app_name: Application name filter (default: "Google Chrome").
                  Case-insensitive.
        include_minimized_fallback: If no on-screen match found, also check
                                    off-screen/minimized windows.

    Returns:
        (pid, window_id) tuple, or None if no window matches.
    """
    try:
        res = subprocess.run(
            ["cua-driver", "call", "list_windows"],
            capture_output=True,
            text=True,
            timeout=10,
            input=json.dumps({"query": "Chrome"}),
        )
        windows = json.loads(res.stdout).get("windows", [])

        def _match(w):
            if w.get("app_name", "").lower() != app_name.lower():
                return False
            title = w.get("title", "")
            if title_keywords:
                title_lower = title.lower()
                if not any(kw.lower() in title_lower for kw in title_keywords):
                    return False
            return True

        # First pass: on-screen windows only (fast path)
        for w in windows:
            if w.get("is_on_screen") and _match(w):
                logger.debug(
                    "CUA window found: pid=%s wid=%s title=%s",
                    w["pid"], w["window_id"], w.get("title", "")[:60]
                )
                return w["pid"], w["window_id"]

        # Second pass: include minimized/offscreen windows (fallback)
        if include_minimized_fallback:
            for w in windows:
                if _match(w):
                    logger.debug(
                        "CUA window found (fallback): pid=%s wid=%s title=%s",
                        w["pid"], w["window_id"], w.get("title", "")[:60]
                    )
                    return w["pid"], w["window_id"]

        # Activate Chrome and retry
        logger.info("Activating Chrome and retrying...")
        _activate_chrome()
        time.sleep(1)
        res2 = subprocess.run(
            ["cua-driver", "call", "list_windows"],
            capture_output=True, text=True, timeout=10,
            input=json.dumps({"query": "Chrome"}),
        )
        windows2 = json.loads(res2.stdout).get("windows", [])
        for w in windows2:
            if _match(w):
                logger.info("CUA window found after activate: pid=%s wid=%s", w["pid"], w["window_id"])
                return w["pid"], w["window_id"]

        logger.warning(
            "CUA window not found: app=%s keywords=%s",
            app_name, title_keywords
        )
        return None

    except subprocess.TimeoutExpired:
        logger.error("cua-driver list_windows timed out")
        return None
    except json.JSONDecodeError as e:
        logger.error("cua-driver output parse error: %s", e)
        return None
    except FileNotFoundError:
        logger.error("cua-driver not found — is it installed and running?")
        return None
    except Exception as e:
        logger.warning("CUA window detection error: %s", e)
        return None


def cua_click(pid, wid, element_index, timeout=10) -> bool:
    """Click an element via CUA driver.

    Returns True if the command was sent (no error), False on failure.
    """
    try:
        subprocess.run(
            ["cua-driver", "call", "click"],
            capture_output=True,
            text=True,
            timeout=timeout,
            input=json.dumps({
                "pid": pid,
                "window_id": wid,
                "element_index": element_index,
            }),
        )
        return True
    except Exception as e:
        logger.warning("CUA click error: %s", e)
        return False


def cua_type_text(pid, text, timeout=5) -> bool:
    """Type text via CUA driver (macOS CGEvent keystrokes).

    Note: Does NOT work for React controlled inputs.
          Use Playwright fill() for those.
    """
    try:
        subprocess.run(
            ["cua-driver", "call", "type_text"],
            capture_output=True,
            text=True,
            timeout=timeout,
            input=json.dumps({"pid": pid, "text": text}),
        )
        return True
    except Exception as e:
        logger.warning("CUA type_text error: %s", e)
        return False


def cua_get_window_state(pid, wid, timeout=15) -> str:
    """Get AX tree markdown for a window.

    Returns the tree_markdown string, or empty string on failure.
    """
    try:
        r = subprocess.run(
            ["cua-driver", "call", "get_window_state"],
            capture_output=True,
            text=True,
            timeout=timeout,
            input=json.dumps({"pid": pid, "window_id": wid}),
        )
        return json.loads(r.stdout).get("tree_markdown", "")
    except Exception as e:
        logger.warning("CUA get_window_state error: %s", e)
        return ""
