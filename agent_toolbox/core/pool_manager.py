"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Pool Manager (Core)                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ZWECK:                                                                      ║
║  API-Key-Pool-Speicherung und -Verwaltung.                                   ║
║                                                                              ║
║  ARCHITEKTUR:                                                                 ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │ PoolManager                                                          │    ║
║  │ ├── add_key() → Fügt neuen API-Key zum Pool hinzu                   │    ║
║  │ ├── get_available_key() → Liefert nächsten unverwendeten Key        │    ║
║  │ ├── mark_used() → Markiert Key als verwendet                        │    ║
║  │ ├── get_stats() → Pool-Statistiken                                  │    ║
║  │ └── save() → Speichert Pool in JSON-Datei                           │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
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

=======
    def reload(self):
        """Lädt den Pool frisch von Disk (sync mit externen Änderungen)."""
        self._load()

>>>>>>> upstream/main
    def save(self):
        """Speichert den Pool in die JSON-Datei."""
        try:
            with open(self.pool_path, "w") as f:
                json.dump(self.keys, f, indent=2)
            logger.info(f"Pool gespeichert: {len(self.keys)} Keys")
        except Exception as e:
            logger.error(f"Pool-Speichern fehlgeschlagen: {e}")

<<<<<<< HEAD
    def add_key(self, api_key: str, alias_email: str, key_name: str = "sinator-key") -> Dict[str, Any]:
        """
        Fügt einen neuen API-Key zum Pool hinzu.

        Args:
            api_key: Fireworks API-Key
            alias_email: Zugehörige GMX Alias-Email
            key_name: Name des Keys
=======
            credits_initial: Startguthaben in USD (default 6.0 = $6 Free Credits)
>>>>>>> upstream/main

        Returns:
            Dict mit status und key_id
        """
<<<<<<< HEAD
        key_entry = {
            "id": str(uuid.uuid4()),
            "api_key": api_key,
            "alias_email": alias_email,
            "key_name": key_name,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "used": False,
            "used_at": None,
=======
            "credits_initial": credits_initial,
            "credits_remaining": credits_initial,
            "credits_checked_at": None,
>>>>>>> upstream/main
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
<<<<<<< HEAD
        Liefert den nächsten unverwendeten API-Key.

        Returns:
            Dict mit api_key, alias_email, key_name oder None
        """
        for key in self.keys:
            if not key.get("used", False):
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
=======
        self.reload()
>>>>>>> upstream/main
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
<<<<<<< HEAD

        Returns:
            Dict mit total, used, available, keys
        """
        total = len(self.keys)
        used = sum(1 for k in self.keys if k.get("used", False))
        available = total - used

        keys_list = []
        for k in self.keys:
            keys_list.append({
                "id": k["id"],
                "alias_email": k["alias_email"],
                "key_name": k["key_name"],
                "created_at": k["created_at"],
                "used": k.get("used", False),
                "used_at": k.get("used_at"),
            })

        return {
            "total": total,
            "used": used,
=======
            "suspended": suspended,
>>>>>>> upstream/main
            "available": available,
            "keys": keys_list,
        }

<<<<<<< HEAD
    def delete_key(self, key_id: str) -> bool:
        """
        Löscht einen API-Key aus dem Pool.

        Args:
            key_id: ID des Keys

        Returns:
            True wenn Key gefunden und gelöscht
        """
        initial_len = len(self.keys)
        self.keys = [k for k in self.keys if k["id"] != key_id]
        if len(self.keys) < initial_len:
            self.save()
            logger.info(f"API-Key gelöscht: {key_id[:8]}...")
            return True
        return False

<<<<<<< HEAD
=======
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

>>>>>>> upstream/main

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
