"""Stores SINator runtime configuration (GMX + Fireworks credentials)."""
import json, logging, os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"

class Config:
    def __init__(self):
        self.gmx_email: str = "delqhi@gmx.de"
        self.gmx_password: str = "ZOE.jerry2024"
        self.fireworks_password: str = "ZOE.jerry2024!"
        self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                self.gmx_email = data.get("gmx_email", self.gmx_email)
                self.gmx_password = data.get("gmx_password", self.gmx_password)
                self.fireworks_password = data.get("fireworks_password", self.fireworks_password)
            except Exception as e:
                logger.warning(f"Config load failed: {e}")

    def save(self, gmx_email=None, gmx_password=None, fireworks_password=None):
        if gmx_email is not None: self.gmx_email = gmx_email
        if gmx_password is not None: self.gmx_password = gmx_password
        if fireworks_password is not None: self.fireworks_password = fireworks_password
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "gmx_email": self.gmx_email,
                "gmx_password": self.gmx_password,
                "fireworks_password": self.fireworks_password,
            }, f, indent=2)
        logger.info(f"Config saved to {CONFIG_FILE}")

_config: Optional[Config] = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config