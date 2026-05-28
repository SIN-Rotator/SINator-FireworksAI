"""
Unit tests for PoolManager lease/return/expire/report logic.
Pure logic tests — no network, no real pool data.
"""
import json
import time
import tempfile
from pathlib import Path

import pytest

from agent_toolbox.core.pool_manager import PoolManager


@pytest.fixture
def temp_pool():
    """Create a PoolManager backed by a temp file with sample data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([
            {
                "id": "key-001", "api_key": "fw_aaa111", "alias_email": "alpha@gmx.de",
                "key_name": "alpha", "created_at": "2026-01-01T00:00:00Z",
                "used": False, "used_at": None, "credits_initial": 6.0, "credits_remaining": 6.0,
                "leased_until": None, "leased_to": None, "lease_id": None, "leased_at": None,
            },
            {
                "id": "key-002", "api_key": "fw_bbb222", "alias_email": "beta@gmx.de",
                "key_name": "beta", "created_at": "2026-01-01T00:00:00Z",
                "used": False, "used_at": None, "credits_initial": 6.0, "credits_remaining": 6.0,
                "leased_until": None, "leased_to": None, "lease_id": None, "leased_at": None,
            },
            {
                "id": "key-003", "api_key": "fw_ccc333", "alias_email": "gamma@gmx.de",
                "key_name": "gamma", "created_at": "2026-01-01T00:00:00Z",
                "used": True, "used_at": "2026-01-02T00:00:00Z", "credits_initial": 6.0, "credits_remaining": 0.0,
                "leased_until": None, "leased_to": None, "lease_id": None, "leased_at": None,
            },
            {
                "id": "key-004", "api_key": "fw_ddd444", "alias_email": "delta@gmx.de",
                "key_name": "delta", "created_at": "2026-01-01T00:00:00Z",
                "used": False, "used_at": None, "credits_initial": 6.0, "credits_remaining": 6.0,
                "leased_until": None, "leased_to": None, "lease_id": None, "leased_at": None,
            },
        ], f)
        pool_path = Path(f.name)
    pm = PoolManager(pool_path=pool_path)
    yield pm
    pool_path.unlink(missing_ok=True)


class TestLeaseKey:
    def test_basic_lease(self, temp_pool):
        result = temp_pool.lease_key(ttl_seconds=60, leased_to="test-proxy")
        assert result is not None
        assert result["api_key"] == "fw_aaa111"
        assert result["key_id"] == "key-001"
        assert result["lease_id"] is not None
        assert result["expires_at"] > time.time()
        assert result["alias_email"] == "alpha@gmx.de"

    def test_skip_leased_keys(self, temp_pool):
        r1 = temp_pool.lease_key(ttl_seconds=60, leased_to="proxy-1")
        r2 = temp_pool.lease_key(ttl_seconds=60, leased_to="proxy-2")
        assert r1["key_id"] == "key-001"
        assert r2["key_id"] == "key-002"

    def test_skip_used_keys(self, temp_pool):
        r1 = temp_pool.lease_key(ttl_seconds=60)
        r2 = temp_pool.lease_key(ttl_seconds=60)
        r3 = temp_pool.lease_key(ttl_seconds=60)
        assert r1["key_id"] == "key-001"
        assert r2["key_id"] == "key-002"
        assert r3["key_id"] == "key-004"

    def test_backup_lease(self, temp_pool):
        result = temp_pool.lease_key(ttl_seconds=60, leased_to="proxy", lease_backup=True)
        assert result is not None
        assert "backup" in result
        assert result["backup"]["key_id"] == "key-002"
        assert result["backup"]["api_key"] == "fw_bbb222"

    def test_no_available_keys(self, temp_pool):
        temp_pool.lease_key(ttl_seconds=60)  # key-001
        temp_pool.lease_key(ttl_seconds=60)  # key-002
        temp_pool.lease_key(ttl_seconds=60)  # key-004
        result = temp_pool.lease_key(ttl_seconds=60)
        assert result is None

    def test_expired_lease_becomes_available(self, temp_pool):
        r1 = temp_pool.lease_key(ttl_seconds=0, leased_to="proxy-1")
        assert r1["key_id"] == "key-001"
        time.sleep(0.1)
        r2 = temp_pool.lease_key(ttl_seconds=60, leased_to="proxy-2")
        assert r2["key_id"] == "key-001"


class TestReturnKey:
    def test_return_key_success(self, temp_pool):
        r = temp_pool.lease_key(ttl_seconds=60, leased_to="test")
        result = temp_pool.return_key(r["key_id"], r["lease_id"])
        assert result is True
        stats = temp_pool.get_stats()
        assert stats["leased"] == 0

    def test_return_wrong_lease_id_fails(self, temp_pool):
        r = temp_pool.lease_key(ttl_seconds=60, leased_to="test")
        result = temp_pool.return_key(r["key_id"], "wrong-lease-id")
        assert result is False
        stats = temp_pool.get_stats()
        assert stats["leased"] == 1

    def test_return_unknown_key(self, temp_pool):
        result = temp_pool.return_key("nonexistent")
        assert result is False


class TestExpireLeases:
    def test_expire_past_ttl(self, temp_pool):
        r = temp_pool.lease_key(ttl_seconds=0, leased_to="test")
        assert r is not None
        time.sleep(0.2)
        count = temp_pool.expire_leases()
        assert count == 1
        stats = temp_pool.get_stats()
        assert stats["leased"] == 0

    def test_no_expire_active_lease(self, temp_pool):
        r = temp_pool.lease_key(ttl_seconds=3600, leased_to="test")
        count = temp_pool.expire_leases()
        assert count == 0
        stats = temp_pool.get_stats()
        assert stats["leased"] == 1


class TestReportKey:
    def test_report_by_api_key(self, temp_pool):
        result = temp_pool.report_key(api_key="fw_aaa111", reason="suspended")
        assert result is not None
        assert result["status"] == "swapped"
        assert result["new_api_key"] == "fw_bbb222"

    def test_report_by_key_id(self, temp_pool):
        result = temp_pool.report_key(key_id="key-001", reason="unauthorized")
        assert result is not None
        assert result["status"] == "swapped"

    def test_reported_key_marked_used(self, temp_pool):
        temp_pool.report_key(key_id="key-001", reason="suspended")
        stats = temp_pool.get_stats()
        assert stats["used"] == 2  # key-001 + key-003 (pre-existing)
        assert stats["available"] == 2  # key-002 + key-004

    def test_report_nonexistent_key(self, temp_pool):
        result = temp_pool.report_key(api_key="fw_nonexistent")
        assert result is None

    def test_report_last_key(self, temp_pool):
        temp_pool.report_key(key_id="key-001", reason="suspended")
        temp_pool.report_key(key_id="key-002", reason="suspended")
        temp_pool.report_key(key_id="key-004", reason="suspended")
        stats = temp_pool.get_stats()
        assert stats["available"] == 0


class TestGetStats:
    def test_initial_stats(self, temp_pool):
        stats = temp_pool.get_stats()
        assert stats["total"] == 4
        assert stats["used"] == 1  # key-003
        assert stats["leased"] == 0
        assert stats["available"] == 3

    def test_stats_after_lease(self, temp_pool):
        temp_pool.lease_key(ttl_seconds=60, leased_to="test")
        stats = temp_pool.get_stats()
        assert stats["leased"] == 1
        assert stats["available"] == 2

    def test_stats_keys_detail(self, temp_pool):
        stats = temp_pool.get_stats()
        assert len(stats["keys"]) == 4
        for k in stats["keys"]:
            assert "id" in k
            assert "alias_email" in k
            assert "api_key" in k
            assert "used" in k
            assert "leased" in k
            assert "leased_to" in k


class TestGetLeasedKeys:
    def test_empty_initially(self, temp_pool):
        assert len(temp_pool.get_leased_keys()) == 0

    def test_one_leased(self, temp_pool):
        temp_pool.lease_key(ttl_seconds=3600, leased_to="proxy-a")
        leased = temp_pool.get_leased_keys()
        assert len(leased) == 1
        assert leased[0]["leased_to"] == "proxy-a"

    def test_expired_not_listed(self, temp_pool):
        temp_pool.lease_key(ttl_seconds=0, leased_to="old-proxy")
        time.sleep(0.2)
        assert len(temp_pool.get_leased_keys()) == 0


class TestGetAvailableKey:
    def test_skips_used(self, temp_pool):
        key = temp_pool.get_available_key()
        assert key is not None
        assert key["id"] not in ("key-003",)

    def test_skips_leased(self, temp_pool):
        temp_pool.lease_key(ttl_seconds=3600, leased_to="test")
        key = temp_pool.get_available_key()
        assert key["id"] == "key-002"

    def test_none_when_empty(self, temp_pool):
        for _ in range(3):
            temp_pool.lease_key(ttl_seconds=3600)
        assert temp_pool.get_available_key() is None


class TestRaceCondition:
    def test_double_lease_different_keys(self, temp_pool):
        r1 = temp_pool.lease_key(ttl_seconds=60, leased_to="proxy-1")
        r2 = temp_pool.lease_key(ttl_seconds=60, leased_to="proxy-2")
        assert r1["key_id"] != r2["key_id"]

    def test_return_then_release(self, temp_pool):
        r = temp_pool.lease_key(ttl_seconds=60, leased_to="proxy-1")
        temp_pool.return_key(r["key_id"], r["lease_id"])
        r2 = temp_pool.lease_key(ttl_seconds=60, leased_to="proxy-2")
        assert r2["key_id"] == r["key_id"]


class TestSSEEvents:
    def test_event_emitted_on_lease(self, temp_pool):
        from agent_toolbox.core.pool_manager import register_sse_listener, unregister_sse_listener
        q = register_sse_listener()
        try:
            temp_pool.lease_key(ttl_seconds=60, leased_to="test")
            event = q.get_nowait()
            assert event["event"] == "key_leased"
            assert event["data"]["key_id"] == "key-001"
            assert event["data"]["leased_to"] == "test"
        finally:
            unregister_sse_listener(q)

    def test_event_on_swap(self, temp_pool):
        from agent_toolbox.core.pool_manager import register_sse_listener, unregister_sse_listener
        q = register_sse_listener()
        try:
            temp_pool.report_key(key_id="key-001", reason="suspended")
            event = q.get_nowait()
            assert event["event"] == "key_swapped"
            assert event["data"]["reason"] == "suspended"
        finally:
            unregister_sse_listener(q)
