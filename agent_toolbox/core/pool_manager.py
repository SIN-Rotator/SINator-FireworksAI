import json
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

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
        """Lädt den Pool aus der JSON-Datei."""
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
            logger.info("Kein Pool gefunden, erstelle neuen")
            self.keys = []

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
        key_entry = {
            "id": str(uuid.uuid4()),
            "api_key": api_key,
            "alias_email": alias_email,
            "key_name": key_name,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "used": False,
            "used_at": None,
            "credits_initial": credits_initial,
            "credits_remaining": credits_initial,
            "credits_checked_at": None,
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
        Liefert den nächsten unverwendeten und nicht-geleasten API-Key.
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        for key in self.keys:
            if not key.get("used", False):
                leased_until = key.get("leased_until")
                if leased_until is not None and leased_until > now:
                    continue
                return key
        return None

    def mark_used(self, key_id: str) -> bool:
        """
        Markiert einen API-Key als verwendet.

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
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        total = len(self.keys)
        used = sum(1 for k in self.keys if k.get("used", False))
        leased = sum(1 for k in self.keys if not k.get("used", False)
                     and k.get("leased_until") is not None and k["leased_until"] > now)
        available = total - used - leased

        keys_list = []
        for k in self.keys:
            leased_until = k.get("leased_until")
            is_leased = (not k.get("used", False) and leased_until is not None and leased_until > now)
            keys_list.append({
                "id": k["id"],
                "alias_email": k["alias_email"],
                "key_name": k["key_name"],
                "api_key": k.get("api_key", ""),
                "created_at": k["created_at"],
                "used": k.get("used", False),
                "used_at": k.get("used_at"),
                "credits_initial": k.get("credits_initial", 6.0),
                "credits_remaining": k.get("credits_remaining", 6.0),
                "credits_checked_at": k.get("credits_checked_at"),
                "leased": is_leased,
                "leased_to": k.get("leased_to") if is_leased else None,
                "leased_until": leased_until if is_leased else None,
                "lease_id": k.get("lease_id") if is_leased else None,
            })

        return {
            "total": total,
            "used": used,
            "leased": leased,
            "available": available,
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
                    key["used"] = True
                    key["used_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    self.save()
                    logger.warning(f"Key automatisch als used markiert (0 Credits): {key_id[:8]}...")
                return True
        return False

    def delete_key(self, key_id: str) -> bool:
        """
        Löscht einen API-Key aus dem Pool.

        Args:
            key_id: ID des Keys

        Returns:
            True wenn Key gefunden und gelöscht
        """
        self.reload()
        initial_len = len(self.keys)
        self.keys = [k for k in self.keys if k["id"] != key_id]
        if len(self.keys) < initial_len:
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
            if not key.get("used", False):
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
                result = {
                    "api_key": key["api_key"],
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
            leased_until = key.get("leased_until")
            if not key.get("used", False) and leased_until is not None and leased_until > now:
                leased.append({
                    "id": key["id"],
                    "alias_email": key["alias_email"],
                    "key_name": key.get("key_name", ""),
                    "api_key": key.get("api_key", ""),
                    "leased_to": key.get("leased_to"),
                    "lease_id": key.get("lease_id"),
                    "leased_at": key.get("leased_at"),
                    "leased_until": leased_until,
                })
        return leased

    def report_key(self, api_key: Optional[str] = None, key_id: Optional[str] = None,
                   reason: str = "unknown") -> Optional[Dict[str, Any]]:
        """
        Report a key as bad (suspended/rate-limited/invalid). Marks it as used
        and returns a new available key.

        Args:
            api_key: API key string to find (alternative to key_id)
            key_id: Key ID to find
            reason: Why the key was reported (suspended, rate_limited, unauthorized, etc.)

        Returns:
            Dict with new_key info or None
        """
        self.reload()
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
        self.mark_used(found_id)
        _emit_event("key_swapped", {
            "old_key_id": found_id,
            "old_alias": old_alias,
            "reason": reason,
        })
        logger.info(f"Key reported as {reason}: {found_id[:8]}...")
        new_key = self.get_available_key()
        if new_key:
            return {
                "status": "swapped",
                "new_api_key": new_key.get("api_key"),
                "new_key_id": new_key.get("id"),
                "new_alias": new_key.get("alias_email"),
            }
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
