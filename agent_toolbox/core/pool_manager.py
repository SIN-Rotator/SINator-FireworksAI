"""API Key pool manager — add, lease, return, mark, report, stats, SSE events.

Docs: pool_manager.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from agent_toolbox.core.keychain_store import (
    store_key as _store_to_keychain,
    retrieve_key as _retrieve_from_keychain,
    delete_key as _delete_from_keychain,
    SENTINEL as _KEYCHAIN_SENTINEL,
)

logger = logging.getLogger(__name__)

UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.I,
)

DEFAULT_POOL_PATH = Path(__file__).parent.parent.parent / "data" / "fireworksai-pool.json"


class PoolManager:
    """
    Verwaltet den API-Key-Pool: Hinzufügen, Abrufen, Markieren, Statistiken.
    """

    def __init__(self, pool_path: Optional[Path] = None):
        """
        Initialisiert den Pool-Manager.

        Args:
            pool_path: Pfad zur Pool-JSON-Datei
        """
        self.pool_path = pool_path or DEFAULT_POOL_PATH
        self.pool_path.parent.mkdir(parents=True, exist_ok=True)
        self.keys: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """Lädt den Pool aus der JSON-Datei.

        Auto-Recovery (V19.8): Wenn die JSON-Datei fehlt aber das macOS
        Keychain Einträge hat, wird der Pool aus dem Keychain rekonstruiert
        (siehe tools/recover_pool.py). Verhindert "Pool tot" Dashboard-Fehler
        wenn ein Sync-Tool die JSON-Datei löscht.
        """
        if self.pool_path.exists():
            try:
                with open(self.pool_path, "r") as f:
                    raw = json.load(f)
                # Handle both formats: {"accounts": [...]} (old) or [...] (new)
                if isinstance(raw, list):
                    self.keys = raw
                elif isinstance(raw, dict) and "accounts" in raw:
                    self.keys = raw["accounts"]
                else:
                    self.keys = []
                logger.info(f"{len(self.keys)} API-Keys aus Pool geladen")
            except Exception as e:
                logger.error(f"Pool-Laden fehlgeschlagen: {e}")
                self.keys = []
        else:
            # V19.8: Try auto-recovery from macOS Keychain
            recovered = self._try_recover_from_keychain()
            if recovered is not None:
                self.keys = recovered
            else:
                logger.info("Kein Pool gefunden, erstelle neuen")
                self.keys = []

    def _try_recover_from_keychain(self) -> Optional[List[Dict[str, Any]]]:
        """V19.8: Reconstruct pool entries from macOS Keychain if possible.

        Returns:
            List of recovered key entries, or None if recovery failed.
        Side effect: writes the recovered pool to disk.
        """
        try:
            import subprocess
            result = subprocess.run(
                ["security", "dump-keychain"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return None

            accounts: List[str] = []
            capture_next = False
            for line in result.stdout.splitlines():
                if '"svce"<blob>="com.sinator.pool"' in line:
                    capture_next = True
                    continue
                if capture_next and '"acct"<blob>=' in line:
                    start = line.index('"acct"<blob>="') + len('"acct"<blob>="')
                    end = line.index('"', start)
                    accounts.append(line[start:end])
                    capture_next = False

            if not accounts:
                return None

            # V19.13: Reject non-UUID entries (ghost IDs from botched recovery)
            filtered = [aid for aid in accounts if UUID_RE.match(aid)]
            if len(filtered) != len(accounts):
                rejected_count = len(accounts) - len(filtered)
                logger.warning(
                    f"V19.13: Filtered out {rejected_count} non-UUID ghost IDs "
                    f"from keychain recovery"
                )
                for aid in accounts:
                    if not UUID_RE.match(aid):
                        logger.warning(f"  -> rejected: {aid[:60]}")
                accounts = filtered

            if not accounts:
                return None

            now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            entries: List[Dict[str, Any]] = []
            for aid in accounts:
                short = aid.split("-")[0] if "-" in aid else aid[:8]
                entries.append({
                    "id": aid,
                    "api_key": _KEYCHAIN_SENTINEL,
                    "alias_email": f"recovered-{short}@unknown.local",
                    "key_name": "recovered-from-keychain",
                    "created_at": now,
                    "used": False,
                    "used_at": None,
                    "credits_initial": 6.0,
                    "credits_remaining": 6.0,
                    "credits_checked_at": None,
                    "suspended": False,
                    "recovered": True,
                    "recovery_note": "Auto-recovered from macOS Keychain (V19.8)",
                })

            self.pool_path.parent.mkdir(parents=True, exist_ok=True)
            self.pool_path.write_text(json.dumps(entries, indent=2))
            logger.warning(
                f"🚨 AUTO-RECOVERY: Pool-JSON fehlte, {len(entries)} Keys aus "
                f"macOS Keychain rekonstruiert. Original-Metadaten verloren. "
                f"Siehe tools/recover_pool.py"
            )
            return entries
        except Exception as e:
            logger.error(f"Keychain-Recovery fehlgeschlagen: {e}")
            return None

    def reload(self):
        """Lädt den Pool frisch von Disk (sync mit externen Änderungen)."""
        self._load()

    def save(self):
        """Speichert den Pool in die JSON-Datei."""
        try:
            with open(self.pool_path, "w") as f:
                json.dump(self.keys, f, indent=2)
            logger.info(f"Pool gespeichert: {len(self.keys)} Keys")
        except Exception as e:
            logger.error(f"Pool-Speichern fehlgeschlagen: {e}")

    def add_key(self, api_key: str, alias_email: str, key_name: str = "sinator-key",
                credits_initial: float = 6.0) -> Dict[str, Any]:
        """
        Fügt einen neuen API-Key zum Pool hinzu.

        Args:
            api_key: Fireworks API-Key
            alias_email: Zugehörige GMX Alias-Email
            key_name: Name des Keys
            credits_initial: Startguthaben in USD (default 6.0 = $6 Free Credits)

        Returns:
            Dict mit status und key_id
        """
        self.reload()
        key_id = str(uuid.uuid4())
        now_ts = time.time()
        _store_to_keychain(key_id, api_key)
        key_entry = {
            "id": key_id,
            "api_key": _KEYCHAIN_SENTINEL,
            "alias_email": alias_email,
            "key_name": key_name,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "used": False,
            "used_at": None,
            "credits_initial": credits_initial,
            "credits_remaining": credits_initial,
            "credits_checked_at": None,
            "assigned_to": None,
            "active_consumers": [],
            "shared_count": 0,
            "last_heartbeat": now_ts,
        }

        self.keys.append(key_entry)
        self.save()

        logger.info(f"Neuer API-Key hinzugefügt: {key_entry['id'][:8]}...")
        return {
            "status": "success",
            "key_id": key_entry["id"],
        }

    def get_available_key(self) -> Optional[Dict[str, Any]]:
        """
        Liefert den nächsten unverwendeten, nicht-suspended und nicht-geleasten API-Key.
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        for key in self.keys:
            if key.get("used", False) or key.get("suspended", False):
                continue
            leased_until = key.get("leased_until")
            if leased_until is not None and leased_until > now:
                continue
            return self._hydrate_key(key)
        return None

    def _hydrate_key(self, key: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of the key dict with api_key hydrated from Keychain."""
        out = dict(key)
        api_key = out.get("api_key", "")
        if api_key == _KEYCHAIN_SENTINEL:
            real = _retrieve_from_keychain(out["id"])
            out["api_key"] = real or ""
        return out

    def mark_suspended(self, key_id: str, reason: str = "unknown") -> bool:
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                key["suspended"] = True
                key["suspended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                key["suspended_reason"] = reason
                # V19.11: Clear lease fields — a suspended key can never be
                # "actively leased". Before this fix, get_stats() excluded
                # suspended keys from the leased count (because `not suspended`
                # in the AND chain), so the stats were correct. BUT the raw JSON
                # still had `leased_until` etc. set, which:
                #   1. Confused debugging (looked like the key was still leased)
                #   2. Could cause issues if unsuspend_key() (V19.9) was called
                #      — the stale lease fields would make it look actively leased
                # Setting them to None keeps the JSON state consistent.
                key["leased_until"] = None
                key["leased_to"] = None
                key["lease_id"] = None
                key["leased_at"] = None
                self.save()
                logger.info(f"Key suspended ({reason}): {key_id[:8]}...")
                return True
        return False

    def unsuspend_key(self, key_id: str, reason: str = "test_verified_alive") -> bool:
        """
        Re-aktiviert einen suspended Key (false-positive recovery).

        Wird von tools/test_keys.py genutzt um Keys die als suspended markiert wurden
        (z.B. transient 412) aber tatsächlich noch alive sind, zurück in den Pool
        zu holen.
        """
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                key["suspended"] = False
                key["suspended_at"] = None
                key["suspended_reason"] = None
                key["reactivated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                key["reactivation_reason"] = reason
                self.save()
                logger.info(f"Key reactivated ({reason}): {key_id[:8]}...")
                return True
        return False

    def mark_used(self, key_id: str) -> bool:
        """
        Markiert einen API-Key als verwendet (manuell, z.B. nach Rotation).

        Args:
            key_id: ID des Keys

        Returns:
            True wenn Key gefunden und markiert
        """
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                key["used"] = True
                key["used_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.save()
                logger.info(f"API-Key markiert als verwendet: {key_id[:8]}...")
                return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Generiert Pool-Statistiken.
        available = total - used - suspended - leased (nur nicht-geleaste Keys)
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        total = len(self.keys)
        used = sum(1 for k in self.keys if k.get("used", False))
        suspended = sum(1 for k in self.keys if k.get("suspended") is True and not k.get("used", False))
        leased = sum(1 for k in self.keys
                     if not k.get("used", False)
                     and not k.get("suspended", False)
                     and k.get("leased_until") is not None
                     and k.get("leased_until") > now)
        available = total - used - suspended - leased

        keys_list = []
        for k in self.keys:
            is_leased = (not k.get("used", False)
                         and not k.get("suspended", False)
                         and k.get("leased_until") is not None
                         and k.get("leased_until") > now)
            keys_list.append({
                "id": k["id"],
                "alias_email": k["alias_email"],
                "key_name": k["key_name"],
                "api_key": "",
                "created_at": k["created_at"],
                "used": k.get("used", False),
                "used_at": k.get("used_at"),
                "suspended": k.get("suspended", False),
                "suspended_at": k.get("suspended_at"),
                "suspended_reason": k.get("suspended_reason"),
                "leased": is_leased,
                "leased_to": k.get("leased_to"),
                "credits_initial": k.get("credits_initial", 6.0),
                "credits_remaining": k.get("credits_remaining", 6.0),
                "credits_checked_at": k.get("credits_checked_at"),
                "assigned_to": k.get("assigned_to"),
                "active_consumers": k.get("active_consumers", []),
                "shared_count": k.get("shared_count", 0),
            })

        return {
            "total": total,
            "used": used,
            "suspended": suspended,
            "leased": leased,
            "available": available,
            "assigned": sum(1 for k in self.keys if k.get("assigned_to") and not k.get("used") and not k.get("suspended")),
            "shared": sum(1 for k in self.keys if len(k.get("active_consumers", [])) > 1 and not k.get("used") and not k.get("suspended")),
            "keys": keys_list,
        }

    def update_credits(self, key_id: str, credits_remaining: float) -> bool:
        """
        Aktualisiert das verbleibende Guthaben eines Keys.

        Args:
            key_id: ID des Keys
            credits_remaining: Verbleibendes Guthaben in USD

        Returns:
            True wenn Key gefunden und aktualisiert
        """
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                key["credits_remaining"] = round(credits_remaining, 2)
                key["credits_checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.save()
                logger.info(f"Credits aktualisiert: {key_id[:8]}... = ${credits_remaining:.2f}")
                if credits_remaining <= 0.01:
                    key["suspended"] = True
                    key["suspended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    key["suspended_reason"] = "credits_exhausted"
                    self.save()
                    logger.warning(f"Key suspended (0 Credits): {key_id[:8]}...")
                return True
        return False

    def delete_key(self, key_id: str) -> bool:
        """
        Löscht einen API-Key aus dem Pool und aus der Keychain.
        """
        self.reload()
        initial_len = len(self.keys)
        self.keys = [k for k in self.keys if k["id"] != key_id]
        if len(self.keys) < initial_len:
            _delete_from_keychain(key_id)
            self.save()
            logger.info(f"API-Key gelöscht: {key_id[:8]}...")
            return True
        return False

    def lease_key(self, ttl_seconds: int = 1800, leased_to: str = "proxy",
                  lease_backup: bool = False) -> Optional[Dict[str, Any]]:
        """
        Leases an available key atomically. Key becomes unavailable to other
        consumers until the lease expires or is returned.

        Args:
            ttl_seconds: Lease duration in seconds (default 30min)
            leased_to: Identifier of the lessee (e.g. "proxy-macbook-1")
            lease_backup: If True, also lease a second key as backup

        Returns:
            Dict with api_key, key_id, lease_id, expires_at or None
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        expires_at = now + ttl_seconds
        for key in self.keys:
            if key.get("used", False) or key.get("suspended", False):
                continue
            leased_until = key.get("leased_until")
            if leased_until is not None and leased_until > now:
                continue
            lease_id = uuid.uuid4().hex[:12]
            key["leased_until"] = expires_at
            key["leased_to"] = leased_to
            key["lease_id"] = lease_id
            key["leased_at"] = now
            self.save()
            _emit_event("key_leased", {
                "key_id": key["id"],
                "lease_id": lease_id,
                "leased_to": leased_to,
                "expires_at": expires_at,
            })
            logger.info(f"Key leased: {key['id'][:8]}... → {leased_to} (TTL={ttl_seconds}s)")
            hydrated = self._hydrate_key(key)
            result = {
                "api_key": hydrated["api_key"],
                "key_id": key["id"],
                "lease_id": lease_id,
                "expires_at": expires_at,
                "alias_email": key["alias_email"],
                "key_name": key.get("key_name", ""),
            }
            if lease_backup:
                backup = self.lease_key(ttl_seconds=ttl_seconds, leased_to=leased_to + "-backup")
                if backup:
                    result["backup"] = backup
            return result
        logger.warning("No available keys to lease")
        return None

    def get_key_for_agent(self, agent_id: str, preferred_key_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """V19.14: Soft-ownership key assignment. Never blocks.

        Priority:
          1. preferred_key_id (sticky — agent requests its known key)
          2. assigned_to == agent_id (agent's own key)
          3. assigned_to is None (unassigned → assign now)
          4. Least-shared key (min active_consumers) as fallback sharing

        Returns None only if ALL keys are suspended/used.
        """
        self.reload()
        now = time.time()
        active = [k for k in self.keys if not k.get("used") and not k.get("suspended")]
        if not active:
            return None

        if preferred_key_id:
            for k in active:
                if k["id"] == preferred_key_id:
                    return self._register_consumer(k, agent_id)

        for k in active:
            if k.get("assigned_to") == agent_id:
                return self._register_consumer(k, agent_id)

        for k in active:
            if not k.get("assigned_to"):
                k["assigned_to"] = agent_id
                self.save()
                return self._register_consumer(k, agent_id)

        best = min(active, key=lambda k: len(k.get("active_consumers", [])))
        best.setdefault("shared_count", 0)
        best["shared_count"] += 1
        logger.info(f"V19.14: Key {best['id'][:8]} SHARED ({agent_id} joins {len(best.get('active_consumers',[]))} existing consumers)")
        return self._register_consumer(best, agent_id)

    def _register_consumer(self, key: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
        """V19.14: Register an agent as active consumer of a key, hydrate, save."""
        consumers = key.setdefault("active_consumers", [])
        if agent_id not in consumers:
            consumers.append(agent_id)
        key["last_heartbeat"] = time.time()
        self.save()
        hydrated = self._hydrate_key(key)
        return {
            "api_key": hydrated["api_key"],
            "key_id": key["id"],
            "alias_email": key.get("alias_email", ""),
            "key_name": key.get("key_name", ""),
            "shared": len(consumers) > 1,
            "active_consumers": consumers.copy(),
            "assigned_to": key.get("assigned_to"),
            "shared_count": key.get("shared_count", 0),
        }

    def release_key_for_agent(self, agent_id: str, key_id: str) -> bool:
        """V19.14: Agent releases a key. Removes from active_consumers only."""
        self.reload()
        for k in self.keys:
            if k["id"] == key_id:
                consumers = k.get("active_consumers", [])
                if agent_id in consumers:
                    consumers.remove(agent_id)
                k["active_consumers"] = consumers
                self.save()
                logger.info(f"V19.14: Agent {agent_id} released key {key_id[:8]} (remaining consumers: {len(consumers)})")
                return True
        return False

    def cleanup_stale_consumers(self, timeout_seconds: int = 300) -> int:
        """V19.14: Remove consumers that haven't sent a heartbeat in timeout_seconds.

        Called periodically by the backend lifespan task.

        Returns: number of consumers cleaned up.
        """
        self.reload()
        now = time.time()
        cleaned = 0
        for k in self.keys:
            last_hb = k.get("last_heartbeat", 0)
            consumers = k.get("active_consumers", [])
            if consumers and now - last_hb > timeout_seconds:
                k["active_consumers"] = []
                cleaned += len(consumers)
        if cleaned > 0:
            self.save()
            logger.info(f"V19.14: Cleaned {cleaned} stale consumers (timeout={timeout_seconds}s)")
        return cleaned

    def return_key(self, key_id: str, lease_id: Optional[str] = None) -> bool:
        """
        Returns a leased key, making it available again.

        Args:
            key_id: ID of the key to return
            lease_id: Optional lease_id for verification

        Returns:
            True if key was found and returned
        """
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                if lease_id and key.get("lease_id") != lease_id:
                    logger.warning(f"Lease ID mismatch for key {key_id[:8]}...")
                    return False
                key["leased_until"] = None
                key["leased_to"] = None
                key["lease_id"] = None
                key["leased_at"] = None
                self.save()
                _emit_event("key_returned", {
                    "key_id": key_id,
                    "from": key.get("leased_to", "unknown"),
                })
                logger.info(f"Key returned: {key_id[:8]}...")
                return True
        return False

    def expire_leases(self) -> int:
        """
        Expires all leases whose TTL has passed. Called automatically
        before lease_key() and in get_stats().

        Returns:
            Number of leases expired
        """
        now = time.time()
        expired = 0
        for key in self.keys:
            leased_until = key.get("leased_until")
            if leased_until is not None and leased_until <= now:
                key["leased_until"] = None
                key["leased_to"] = None
                key["lease_id"] = None
                key["leased_at"] = None
                expired += 1
        if expired > 0:
            self.save()
            logger.info(f"Expired {expired} lease(s)")
        return expired

    def get_leased_keys(self) -> List[Dict[str, Any]]:
        """
        Returns all currently leased keys (active leases only).

        Returns:
            List of leased key dicts
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        leased = []
        for key in self.keys:
            if key.get("used", False) or key.get("suspended", False):
                continue
            leased_until = key.get("leased_until")
            if not key.get("used", False) and leased_until is not None and leased_until > now:
                hydrated = self._hydrate_key(key)
                leased.append({
                    "id": key["id"],
                    "alias_email": key["alias_email"],
                    "key_name": key.get("key_name", ""),
                    "api_key": hydrated["api_key"],
                    "leased_to": key.get("leased_to"),
                    "lease_id": key.get("lease_id"),
                    "leased_at": key.get("leased_at"),
                    "leased_until": leased_until,
                })
        return leased

    def report_key(self, api_key: Optional[str] = None, key_id: Optional[str] = None,
                   reason: str = "unknown", leased_to: str = "proxy",
                   ttl_seconds: int = 1800) -> Optional[Dict[str, Any]]:
        """
        Report a key as bad (suspended/rate-limited/invalid). Marks it as suspended
        (NOT used!), leases a replacement key atomically, and returns the new key.

        This replaces the old pattern of report() + separate lease() which caused
        double-key waste (2 keys touched per swap).

        Args:
            api_key: API key string to find (alternative to key_id)
            key_id: Key ID to find
            reason: Why the key was reported
            leased_to: Identifier for the lease (e.g. "proxy-8888")
            ttl_seconds: Lease TTL (default 30min)

        Returns:
            Dict with new_key info (including lease_id, expires_at) or None
        """
        import uuid as _uuid
        self.reload()
        self.expire_leases()
        found_id = key_id
        if not found_id and api_key:
            for k in self.keys:
                if k.get("api_key") == api_key:
                    found_id = k["id"]
                    break
        if not found_id:
            return None
        old_alias = ""
        for k in self.keys:
            if k["id"] == found_id:
                old_alias = k.get("alias_email", "")
                break

        # Suspend the old key
        self.mark_suspended(found_id, reason=reason)
        _emit_event("key_swapped", {
            "old_key_id": found_id,
            "old_alias": old_alias,
            "reason": reason,
        })
        logger.info(f"Key reported as {reason}: {found_id[:8]}...")

        # Atomically lease a replacement key (same logic as lease_key)
        now = time.time()
        expires_at = now + ttl_seconds
        for key in self.keys:
            if key.get("used", False) or key.get("suspended", False):
                continue
            leased_until = key.get("leased_until")
            if leased_until is not None and leased_until > now:
                continue
            lease_id = _uuid.uuid4().hex[:12]
            key["leased_until"] = expires_at
            key["leased_to"] = leased_to
            key["lease_id"] = lease_id
            key["leased_at"] = now
            self.save()
            _emit_event("key_leased", {
                "key_id": key["id"],
                "lease_id": lease_id,
                "leased_to": leased_to,
                "expires_at": expires_at,
            })
            logger.info(f"Replacement key leased: {key['id'][:8]}... → {leased_to} (TTL={ttl_seconds}s)")
            hydrated = self._hydrate_key(key)
            return {
                "status": "swapped",
                "new_api_key": hydrated["api_key"],
                "new_key_id": key["id"],
                "new_alias": key.get("alias_email", ""),
                "new_key_name": key.get("key_name", ""),
                "lease_id": lease_id,
                "expires_at": expires_at,
            }

        logger.warning("No replacement key available after report")
        return {"status": "no_keys_available", "swapped": False}


_SSE_LISTENERS: List = []


def _emit_event(event_type: str, data: Dict[str, Any]):
    """
    Emits an SSE event to all registered listeners.
    Thread-safe — safe to call from any PoolManager method.
    """
    import asyncio as _asyncio
    payload = {"event": event_type, "data": data}
    dead = []
    for q in _SSE_LISTENERS:
        try:
            q.put_nowait(payload)
        except Exception:
            dead.append(q)
    for q in dead:
        _SSE_LISTENERS.remove(q)


def register_sse_listener() -> "asyncio.Queue":
    """
    Register a new SSE listener queue. Returns an asyncio.Queue
    that will receive event payloads.
    """
    import asyncio as _asyncio
    q = _asyncio.Queue()
    _SSE_LISTENERS.append(q)
    return q


def unregister_sse_listener(q: "asyncio.Queue"):
    """Remove an SSE listener queue."""
    if q in _SSE_LISTENERS:
        _SSE_LISTENERS.remove(q)


_pool_manager: Optional[PoolManager] = None


def get_pool_manager(pool_path: Optional[Path] = None) -> PoolManager:
    """
    Liefert die Singleton-Instanz des Pool-Managers.

    Args:
        pool_path: Optionaler Pfad zur Pool-Datei

    Returns:
        PoolManager-Instanz
    """
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = PoolManager(pool_path)
    return _pool_manager
