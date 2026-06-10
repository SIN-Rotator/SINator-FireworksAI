"""Tests for cua_helper module — dynamic CUA window detection.

Purpose: Verify CUA window detection works on macOS with cua-driver.
Docs: tests/test_cua_helper.doc.md
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))

from cua_helper import find_cua_window, cua_get_window_state


class TestFindWindow:
    """Dynamic CUA window detection."""

    def test_find_any_chrome(self, chrome_ok, cua_ok):
        """Should find the first on-screen Chrome window."""
        cua = find_cua_window()
        assert cua is not None, "No Chrome window found"
        pid, wid = cua
        assert isinstance(pid, int), f"pid should be int, got {type(pid)}"
        assert isinstance(wid, int), f"wid should be int, got {type(wid)}"
        assert pid > 0, f"pid should be > 0, got {pid}"
        print(f"  Chrome window: pid={pid} wid={wid}")

    def test_find_gmx(self, chrome_ok, cua_ok):
        """Should find a GMX window if one is open."""
        cua = find_cua_window(title_keywords=["GMX", "gmx", "freemail", "E-Mail"])
        if cua:
            pid, wid = cua
            tree = cua_get_window_state(pid, wid)
            assert "GMX" in tree or "gmx" in tree or "E-Mail" in tree, \
                "GMX window tree should contain GMX or E-Mail"
            print(f"  GMX window: pid={pid} wid={wid}")
        else:
            print("  No GMX window open (skipping content check)")

    def test_find_fireworks(self, chrome_ok, cua_ok):
        """Should find a Fireworks window if one is open."""
        cua = find_cua_window(title_keywords=["fireworks"])
        if cua:
            pid, wid = cua
            tree = cua_get_window_state(pid, wid)
            assert "fireworks" in tree.lower(), \
                "Fireworks window tree should contain 'fireworks'"
            print(f"  Fireworks window: pid={pid} wid={wid}")
        else:
            print("  No Fireworks window open (skipping content check)")

    def test_find_nonexistent(self, chrome_ok, cua_ok):
        """Should return None for non-existent window."""
        cua = find_cua_window(title_keywords=["XYZZYX_NONEXISTENT_12345"])
        assert cua is None, "Should return None for non-matching keywords"

    def test_include_minimized_fallback(self, chrome_ok, cua_ok):
        """Fallback should find a window even if is_on_screen=False."""
        cua = find_cua_window(include_minimized_fallback=True)
        assert cua is not None, "Fallback should find a window"
        print(f"  Fallback found: pid={cua[0]} wid={cua[1]}")


class TestGetWindowState:
    """CUA get_window_state."""

    def test_get_state(self, chrome_ok, cua_ok):
        """Should return non-empty AX tree for any Chrome window."""
        cua = find_cua_window()
        assert cua is not None, "Need a Chrome window"
        tree = cua_get_window_state(cua[0], cua[1])
        assert len(tree) > 100, f"AX tree too short: {len(tree)} chars"
        assert "AXWindow" in tree, "Should contain AXWindow element"
        print(f"  AX tree: {len(tree)} chars")

    def test_get_state_invalid_wid(self, chrome_ok, cua_ok):
        """Should return empty string for invalid window_id."""
        tree = cua_get_window_state(999999, 999999)
        assert tree == "", "Should return empty string for invalid window"
