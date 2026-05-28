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

    def save(self):
        """Speichert den Pool in die JSON-Datei."""
        try:
            with open(self.pool_path, "w") as f:
                json.dump(self.keys, f, indent=2)
            logger.info(f"Pool gespeichert: {len(self.keys)} Keys")
        except Exception as e:
            logger.error(f"Pool-Speichern fehlgeschlagen: {e}")

    def add_key(self, api_key: str, alias_email: str, key_name: str = "sinator-key") -> Dict[str, Any]:
        """
        Fügt einen neuen API-Key zum Pool hinzu.

        Args:
            api_key: Fireworks API-Key
            alias_email: Zugehörige GMX Alias-Email
            key_name: Name des Keys

        Returns:
            Dict mit status und key_id
        """
        key_entry = {
            "id": str(uuid.uuid4()),
            "api_key": api_key,
            "alias_email": alias_email,
            "key_name": key_name,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "used": False,
            "used_at": None,
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
            "available": available,
            "keys": keys_list,
        }

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
