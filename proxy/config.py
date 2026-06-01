"""
Proxy configuration — environment-driven, persisted to ~/.sin-pool/config.json.

Docs: config.doc.md
"""
import os
import json
from pathlib import Path

DEFAULT_PROXY_PORT = int(os.getenv("SIN_PROXY_PORT", "8888"))
FIREWORKS_BASE = "https://api.fireworks.ai/inference/v1"
LEASE_TTL_SECONDS = int(os.getenv("SIN_LEASE_TTL", "1800"))
LEASE_BACKUP = os.getenv("SIN_LEASE_BACKUP", "false").lower() == "true"
MAX_RETRIES = int(os.getenv("SIN_MAX_RETRIES", "3"))

# Issue #24 — Cloudflare Worker fallback + D1 sync (consumed by pool-router.py
# and scripts/sync_to_cf.py). Empty by default → fallback disabled.
CF_WORKER_URL = os.getenv("CF_WORKER_URL", "").rstrip("/")
CF_SYNC_TOKEN = os.getenv("CF_SYNC_TOKEN", "").strip()
CACHE_DIR = Path(os.getenv("SIN_CACHE_DIR", str(Path.home() / ".sin-pool")))
CONFIG_FILE = CACHE_DIR / "config.json"
TUNNEL_URL_FILE = CACHE_DIR / "tunnel-url.txt"

_proxy_project_root = Path(__file__).parent.parent if "__file__" in dir() else Path(os.getcwd())
SHARED_TUNNEL_URL_FILE = _proxy_project_root.parent / ".sin-pool" / "tunnel-url.txt"


def _resolve_pool_api_url() -> str:
    if os.getenv("SIN_POOL_API_URL"):
        return os.getenv("SIN_POOL_API_URL")
    for f in (TUNNEL_URL_FILE, SHARED_TUNNEL_URL_FILE):
        if f.exists():
            url = f.read_text().strip()
            if url:
                return f"{url}/api/v1"
    return "http://localhost:8000/api/v1"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "proxy_port": DEFAULT_PROXY_PORT,
        "pool_api_url": _resolve_pool_api_url(),
        "fireworks_base": FIREWORKS_BASE,
        "lease_ttl_seconds": LEASE_TTL_SECONDS,
        "lease_backup": LEASE_BACKUP,
        "max_retries": MAX_RETRIES,
        "cf_worker_url": CF_WORKER_URL,
        "cf_sync_token": CF_SYNC_TOKEN,
    }


def save_config(cfg: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
