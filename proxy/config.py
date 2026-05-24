import os
import json
from pathlib import Path

DEFAULT_PROXY_PORT = int(os.getenv("SIN_PROXY_PORT", "8888"))
DEFAULT_POOL_API_URL = os.getenv("SIN_POOL_API_URL", "http://localhost:8000/api/v1")
FIREWORKS_BASE = "https://api.fireworks.ai/inference/v1"
LEASE_TTL_SECONDS = int(os.getenv("SIN_LEASE_TTL", "1800"))
LEASE_BACKUP = os.getenv("SIN_LEASE_BACKUP", "true").lower() == "true"
MAX_RETRIES = int(os.getenv("SIN_MAX_RETRIES", "3"))
CACHE_DIR = Path(os.getenv("SIN_CACHE_DIR", str(Path.home() / ".sin-pool")))
CONFIG_FILE = CACHE_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "proxy_port": DEFAULT_PROXY_PORT,
        "pool_api_url": DEFAULT_POOL_API_URL,
        "fireworks_base": FIREWORKS_BASE,
        "lease_ttl_seconds": LEASE_TTL_SECONDS,
        "lease_backup": LEASE_BACKUP,
        "max_retries": MAX_RETRIES,
    }


def save_config(cfg: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
