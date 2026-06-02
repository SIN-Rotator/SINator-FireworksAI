"""
Primary/backup key cache with on-disk persistence for pool proxy.

Purpose: Persist the proxy's leased primary + backup Fireworks API keys to
~/.sin-pool/ so they survive proxy restarts. V19.11 also tracks the "previous"
key (expired, pending return to pool) for crash-recovery.

Docs: key_cache.doc.md
"""
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from .config import CACHE_DIR
except ImportError:
    from config import CACHE_DIR

logger = logging.getLogger(__name__)

CURRENT_KEY_FILE = CACHE_DIR / "current-key.json"
BACKUP_KEY_FILE = CACHE_DIR / "backup-key.json"
PREVIOUS_KEY_FILE = CACHE_DIR / "previous-key.json"


class KeyCache:
    def __init__(self):
        self.primary: Optional[Dict[str, Any]] = None
        self.backup: Optional[Dict[str, Any]] = None
        self.previous: Optional[Dict[str, Any]] = None  # V19.11: Track expired key to return to pool
        self.request_count: int = 0
        self.last_used_at: float = 0
        self._load()

    def _load(self):
        if CURRENT_KEY_FILE.exists():
            try:
                with open(CURRENT_KEY_FILE) as f:
                    self.primary = json.load(f)
                logger.info(f"Loaded cached key: {self.primary.get('key_id', '?')[:8]}...")
            except Exception as e:
                logger.warning(f"Failed to load cached key: {e}")
                self.primary = None
        if BACKUP_KEY_FILE.exists():
            try:
                with open(BACKUP_KEY_FILE) as f:
                    self.backup = json.load(f)
                logger.info(f"Loaded backup key: {self.backup.get('key_id', '?')[:8]}...")
            except Exception as e:
                self.backup = None
        if PREVIOUS_KEY_FILE.exists():
            try:
                with open(PREVIOUS_KEY_FILE) as f:
                    self.previous = json.load(f)
                logger.info(f"Loaded previous key (pending return): {self.previous.get('key_id', '?')[:8]}...")
            except Exception as e:
                self.previous = None

    def _save(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if self.primary:
            with open(CURRENT_KEY_FILE, "w") as f:
                json.dump(self.primary, f, indent=2)
        else:
            CURRENT_KEY_FILE.unlink(missing_ok=True)
        if self.backup:
            with open(BACKUP_KEY_FILE, "w") as f:
                json.dump(self.backup, f, indent=2)
        else:
            BACKUP_KEY_FILE.unlink(missing_ok=True)
        if self.previous:
            with open(PREVIOUS_KEY_FILE, "w") as f:
                json.dump(self.previous, f, indent=2)
        else:
            PREVIOUS_KEY_FILE.unlink(missing_ok=True)

    def set_primary(self, key_info: Dict[str, Any]):
        self.primary = key_info
        self.request_count = 0
        self.last_used_at = time.time()
        # V19.11: Clear previous — a new primary means the expired one has been handled
        self.previous = None
        PREVIOUS_KEY_FILE.unlink(missing_ok=True)
        self._save()
        logger.info(f"Primary key set: {key_info.get('key_id', '?')[:8]}... ({key_info.get('alias_email', '')})")

    def set_backup(self, key_info: Dict[str, Any]):
        self.backup = key_info
        self._save()
        logger.info(f"Backup key set: {key_info.get('key_id', '?')[:8]}... ({key_info.get('alias_email', '')})")

    def get_primary(self) -> Optional[Dict[str, Any]]:
        if self.primary:
            expires = self.primary.get("expires_at", 0)
            if expires and time.time() > expires:
                logger.warning("Primary key lease expired")
                # V19.11: Save to `previous` (persisted to previous-key.json) so
                # the server's _ensure_key() can call /pool/return on the next
                # request. Without this, the key sits "leased" in the backend
                # until the 30-min TTL + V19.10 cleanup loop expires it.
                # CRITICAL: persist BEFORE clearing so a crash mid-return
                # still allows the next proxy start to recover the key.
                self.previous = self.primary
                self.primary = None
                self._save()
                CURRENT_KEY_FILE.unlink(missing_ok=True)
                return None
            self.request_count += 1
            self.last_used_at = time.time()
            return self.primary
        return None

    def pop_previous(self) -> Optional[Dict[str, Any]]:
        """V19.11: Atomically get and clear the previous (expired) key.

        Called by _ensure_key() in server.py BEFORE leasing a new key.
        Returns the key dict and clears it from disk so it's not returned twice.
        Returns None if there's no pending previous key.
        """
        prev = self.previous
        self.previous = None
        PREVIOUS_KEY_FILE.unlink(missing_ok=True)
        return prev

    def promote_backup(self) -> Optional[Dict[str, Any]]:
        if self.backup:
            expires = self.backup.get("expires_at", 0)
            if expires and time.time() > expires:
                logger.warning("Backup key lease also expired")
                self.backup = None
                BACKUP_KEY_FILE.unlink(missing_ok=True)
                return None
            self.primary = self.backup
            self.backup = None
            self.request_count = 0
            self.last_used_at = time.time()
            self._save()
            logger.info(f"Promoted backup → primary: {self.primary.get('key_id', '?')[:8]}...")
            return self.primary
        return None

    def clear_primary(self):
        self.primary = None
        CURRENT_KEY_FILE.unlink(missing_ok=True)

    def clear_backup(self):
        self.backup = None
        BACKUP_KEY_FILE.unlink(missing_ok=True)

    def clear_all(self):
        self.primary = None
        self.backup = None
        self.request_count = 0
        CURRENT_KEY_FILE.unlink(missing_ok=True)
        BACKUP_KEY_FILE.unlink(missing_ok=True)

    def status(self) -> Dict[str, Any]:
        return {
            "primary": {
                "key_id": self.primary.get("key_id", "")[:8] + "..." if self.primary else None,
                "alias": self.primary.get("alias_email", "") if self.primary else None,
                "expires_at": self.primary.get("expires_at") if self.primary else None,
                "requests": self.request_count,
            } if self.primary else None,
            "backup": {
                "key_id": self.backup.get("key_id", "")[:8] + "..." if self.backup else None,
                "alias": self.backup.get("alias_email", "") if self.backup else None,
            } if self.backup else None,
            "cache_dir": str(CACHE_DIR),
        }


class AgentKeyCache:
    """V19.14: Per-agent key cache with sticky preferred_key_id persistence."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.primary: Optional[Dict[str, Any]] = None
        self.preferred_key_id: Optional[str] = None
        self.request_count: int = 0
        self._load()

    def _cache_file(self) -> Path:
        return CACHE_DIR / f"agent-{self.agent_id}.json"

    def _load(self):
        cf = self._cache_file()
        if cf.exists():
            try:
                with open(cf) as f:
                    data = json.load(f)
                self.primary = data.get("primary")
                self.preferred_key_id = data.get("preferred_key_id")
                self.request_count = data.get("request_count", 0)
                if self.primary:
                    logger.info(f"AgentKeyCache loaded: preferred={self.preferred_key_id[:8] if self.preferred_key_id else 'none'}...")
            except Exception as e:
                logger.warning(f"Failed to load agent cache: {e}")

    def _save(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "primary": self.primary,
            "preferred_key_id": self.preferred_key_id,
            "request_count": self.request_count,
        }
        with open(self._cache_file(), "w") as f:
            json.dump(data, f, indent=2)

    def get_primary(self) -> Optional[Dict[str, Any]]:
        """V19.14: No TTL check — soft-ownership keys don't expire."""
        if self.primary:
            self.request_count += 1
            return self.primary
        return None

    def set_primary(self, key_info: Dict[str, Any]):
        self.primary = key_info
        self.request_count = 0
        if key_info.get("key_id"):
            self.preferred_key_id = key_info["key_id"]
        self._save()
        logger.info(f"AgentKeyCache primary: {key_info.get('key_id', '?')[:8]}...")

    @property
    def backup(self) -> Optional[Dict[str, Any]]:
        return None

    def set_backup(self, key_info: Dict[str, Any]):
        pass

    def promote_backup(self) -> Optional[Dict[str, Any]]:
        return None

    def pop_previous(self) -> Optional[Dict[str, Any]]:
        return None

    def clear_primary(self):
        self.primary = None
        self._save()

    def clear_backup(self):
        pass

    def clear_all(self):
        self.primary = None
        self._save()
        self._cache_file().unlink(missing_ok=True)

    def status(self) -> Dict[str, Any]:
        return {
            "primary": {
                "key_id": self.primary.get("key_id", "")[:8] + "..." if self.primary else None,
                "alias": self.primary.get("alias_email", "") if self.primary else None,
                "expires_at": self.primary.get("expires_at") if self.primary else None,
                "requests": self.request_count,
            } if self.primary else None,
            "backup": None,
            "cache_dir": str(CACHE_DIR),
        }
