"""
Tests for auto-key-swap feature: POST /api/v1/pool/report + tools/swap_key.py

Requires: backend running on localhost:8000
Run: pytest tests/test_key_swap.py -v
"""
import sys
import json
import subprocess
from pathlib import Path

_project_root = str(Path(__file__).parent.parent)
_core_dir = str(Path(__file__).parent.parent / "agent_toolbox" / "core")
sys.path.insert(0, _project_root)
sys.path.insert(0, _core_dir)

import pytest
import pytest_asyncio
import httpx
import logging

logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v1"
AUTH_FILE = Path.home() / ".local/share/opencode/auth.json"


# ── Fixtures ──────────────────────────────────────────────────────────

def _get_pool_key():
    """Get an available key from the pool for testing."""
    resp = httpx.get(f"{BASE_URL}/pool/key", timeout=10)
    return resp.json() if resp.status_code == 200 else None


def _restore_auth(backup):
    """Restore auth.json from backup."""
    if backup:
        AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTH_FILE.write_text(backup)


@pytest.fixture
def auth_backup():
    """Backup auth.json before test, restore after."""
    if AUTH_FILE.exists():
        backup = AUTH_FILE.read_text()
    else:
        backup = None
    yield backup
    if backup:
        AUTH_FILE.write_text(backup)
    elif AUTH_FILE.exists():
        AUTH_FILE.unlink()


# ── API Endpoint Tests ───────────────────────────────────────────────

class TestPoolReport:
    """Tests for POST /api/v1/pool/report"""

    def test_report_by_api_key(self):
        """Report a key by api_key value, get new key back."""
        key_data = _get_pool_key()
        assert key_data, "No keys in pool"
        
        resp = httpx.post(
            f"{BASE_URL}/pool/report",
            json={"api_key": key_data["api_key"]},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["swapped"] is True
        assert data["new_key"].startswith("fw_")
        assert data["new_alias"].endswith("@gmx.de")

    def test_report_by_key_id(self):
        """Report a key by key_id, get new key back."""
        key_data = _get_pool_key()
        assert key_data, "No keys in pool"
        
        resp = httpx.post(
            f"{BASE_URL}/pool/report",
            json={"key_id": key_data["key_id"]},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["swapped"] is True
        assert data["new_key"] != key_data["api_key"]

    def test_report_unknown_key(self):
        """Reporting a non-existent key still returns a fresh key (best effort)."""
        resp = httpx.post(
            f"{BASE_URL}/pool/report",
            json={"api_key": "fw_nonexistent_key_12345"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        # Unknown key can't be marked, but we still try to give a new key
        if data.get("swapped"):
            assert data["new_key"].startswith("fw_")

    def test_report_empty_body(self):
        """Empty body should still return a valid response."""
        resp = httpx.post(
            f"{BASE_URL}/pool/report",
            json={},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_report_reported_key_not_in_new(self):
        """Reported key should NOT be the same as the new key returned."""
        key_data = _get_pool_key()
        assert key_data, "No keys in pool"
        
        resp = httpx.post(
            f"{BASE_URL}/pool/report",
            json={"api_key": key_data["api_key"]},
            timeout=10,
        )
        data = resp.json()
        if data["swapped"]:
            assert data["new_key"] != key_data["api_key"], \
                "Reported key should not be returned as new key"


# ── CLI Tool Tests ────────────────────────────────────────────────────

class TestSwapKeyCLI:
    """Tests for tools/swap_key.py"""

    def test_swap_with_explicit_key(self, auth_backup):
        """Swap a specific key via CLI argument."""
        key_data = _get_pool_key()
        assert key_data, "No keys in pool"
        
        result = subprocess.run(
            ["python3", "tools/swap_key.py", key_data["api_key"]],
            capture_output=True, text=True, timeout=15,
            cwd=_project_root,
        )
        assert result.returncode == 0, f"Stderr: {result.stderr}"
        assert "Key swapped" in result.stdout
        assert key_data["api_key"][:15] in result.stdout

    def test_swap_updates_auth_file(self, auth_backup):
        """swap_key should update auth.json with the new key."""
        key_data = _get_pool_key()
        assert key_data, "No keys in pool"
        
        result = subprocess.run(
            ["python3", "tools/swap_key.py", key_data["api_key"]],
            capture_output=True, text=True, timeout=15,
            cwd=_project_root,
        )
        assert result.returncode == 0
        
        assert AUTH_FILE.exists(), "auth.json should exist after swap"
        auth = json.loads(AUTH_FILE.read_text())
        assert "fireworks" in auth
        assert auth["fireworks"].startswith("fw_")
        assert auth["fireworks"] != key_data["api_key"], \
            "New key should be different from reported key"

    def test_swap_output_format(self, auth_backup):
        """Check swap_key output contains expected info."""
        key_data = _get_pool_key()
        assert key_data, "No keys in pool"
        
        result = subprocess.run(
            ["python3", "tools/swap_key.py", key_data["api_key"]],
            capture_output=True, text=True, timeout=15,
            cwd=_project_root,
        )
        assert "✅" in result.stdout
        assert "Key swapped" in result.stdout
        assert "New alias" in result.stdout
        assert "Updated:" in result.stdout
        assert str(AUTH_FILE) in result.stdout


# ── Integration Test ──────────────────────────────────────────────────

class TestIntegration:
    """End-to-end: report via API, verify via CLI"""

    def test_roundtrip(self, auth_backup):
        """Report via API, then verify key works and auth file updated."""
        key_data = _get_pool_key()
        assert key_data, "No keys in pool"
        
        # 1. Report key via API
        resp = httpx.post(
            f"{BASE_URL}/pool/report",
            json={"api_key": key_data["api_key"]},
            timeout=10,
        )
        assert resp.status_code == 200
        api_result = resp.json()
        assert api_result["swapped"]
        new_key_api = api_result["new_key"]
        
        # 2. Verify pool stats changed
        stats = httpx.get(f"{BASE_URL}/pool/stats", timeout=10).json()
        assert stats["used"] >= 1
        assert stats["available"] < stats["total"]
