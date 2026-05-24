import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from .config import CACHE_DIR

logger = logging.getLogger(__name__)

CURRENT_KEY_FILE = CACHE_DIR / "current-key.json"
BACKUP_KEY_FILE = CACHE_DIR / "backup-key.json"


class KeyCache:
    def __init__(self):
        self.primary: Optional[Dict[str, Any]] = None
        self.backup: Optional[Dict[str, Any]] = None
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

    def set_primary(self, key_info: Dict[str, Any]):
        self.primary = key_info
        self.request_count = 0
        self.last_used_at = time.time()
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
                self.primary = None
                CURRENT_KEY_FILE.unlink(missing_ok=True)
                return None
            self.request_count += 1
            self.last_used_at = time.time()
            return self.primary
        return None

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
