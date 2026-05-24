#!/usr/bin/env python3
"""
Fireworks Key Watchdog — überwacht den aktiven API-Key und swapped bei 402/429.

Liest den aktuellen Key aus OpenCode auth.json, pingt Fireworks API,
und bei Suspension/Rate-Limit: automatisch neuen Key aus Pool holen,
auth.json updaten, loggen. Läuft als Daemon im Hintergrund.

Usage:
    python tools/key_watchdog.py              # Default: alle 60s checken
    python tools/key_watchdog.py --interval 30  # Alle 30s
    python tools/key_watchdog.py --once         # Einmalig checken + swap
"""
import json
import time
import sys
import logging
import urllib.request
import urllib.error
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | FW-WATCHDOG | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "key_watchdog.log"),
    ],
)
logger = logging.getLogger("key-watchdog")

AUTH_FILE = Path.home() / ".local/share/opencode/auth.json"
POOL_API = "http://localhost:8000/api/v1"
FIREWORKS_API = "https://api.fireworks.ai/inference/v1"
CHECK_INTERVAL = 60

# Pool API Auth Token — aus .env oder fix
_POOL_TOKEN = ""
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        if _line.startswith("SINATOR_AUTH_TOKEN="):
            _POOL_TOKEN = _line.split("=", 1)[1].strip()
            break


def _get_active_key() -> str | None:
    """Read current Fireworks key from auth.json."""
    if not AUTH_FILE.exists():
        return None
    try:
        auth = json.loads(AUTH_FILE.read_text())
        # OpenCode speichert den Key entweder unter "fireworks-ai" (neu) oder "fireworks" (alt)
        if "fireworks-ai" in auth and isinstance(auth["fireworks-ai"], dict):
            return auth["fireworks-ai"].get("key")
        return auth.get("fireworks")
    except (json.JSONDecodeError, KeyError):
        return None


def _update_auth(new_key: str) -> bool:
    """Write new key into auth.json. Handles both old and new format."""
    try:
        auth = json.loads(AUTH_FILE.read_text()) if AUTH_FILE.exists() else {}

        # Update both formats for compatibility
        auth["fireworks-ai"] = {"type": "api", "key": new_key}
        auth["fireworks"] = new_key

        AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTH_FILE.write_text(json.dumps(auth, indent=2))
        return True
    except Exception as e:
        logger.error(f"Failed to update auth.json: {e}")
        return False


def _report_key(bad_key: str) -> dict:
    """Call /pool/report to mark key as used and get a new one."""
    url = f"{POOL_API}/pool/report"
    body = json.dumps({"api_key": bad_key}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if _POOL_TOKEN:
        req.add_header("Authorization", f"Bearer {_POOL_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        logger.warning(f"Pool report HTTP {e.code}: {body[:200]}")
        return {}
    except Exception as e:
        logger.warning(f"Pool report error: {e}")
        return {}


def _check_key_via_inference(api_key: str) -> dict:
    """
    Check key health via a minimal inference call.
    Costs ~0.001¢ per check but is the ONLY reliable way to detect 402/suspended.

    Returns {'healthy': bool, 'status': int, 'body': str}
    """
    url = "https://api.fireworks.ai/inference/v1/chat/completions"
    payload = json.dumps({
        "model": "accounts/fireworks/models/deepseek-v4-pro",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }).encode()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "OpenCode/1.0",
        "Accept": "application/json",
    }
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"healthy": True, "status": r.status, "body": ""}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:800]
        return {"healthy": False, "status": e.code, "body": body}
    except Exception as e:
        return {"healthy": False, "status": 0, "body": str(e)}


def _is_suspended(result: dict) -> bool:
    """Check if the result indicates a rate-limited or suspended key."""
    status = result["status"]
    body = result["body"].lower()

    if status in (402, 429, 412):
        return True
    if status in (401, 403) and ("suspended" in body or "rate limit" in body or "spending limit" in body or "precondition_failed" in body):
        return True
    return False


def check_and_swap() -> bool:
    """
    Ein Check-Durchlauf:
    1. Aktiven Key lesen
    2. Health check via minimaler Inference-Call
    3. Bei 402/429/403/401 → report + swap + auth update
    Returns True wenn swapped, False wenn alles OK
    """
    current_key = _get_active_key()
    if not current_key:
        logger.warning("No active key in auth.json")
        return False

    result = _check_key_via_inference(current_key)
    truncated_key = f"{current_key[:20]}..."
    logger.info(f"Key {truncated_key} → inference HTTP {result['status']}")

    if result["healthy"]:
        return False

    if not _is_suspended(result):
        logger.info(f"HTTP {result['status']} — not a rate-limit error, skipping")
        return False

    logger.warning(f"SUSPENDED (HTTP {result['status']}) — swapping key...")
    logger.info(f"   Response: {result['body'][:300]}")

    # Key reporten und neuen holen
    report_result = _report_key(current_key)
    new_key = report_result.get("new_key")

    if not new_key:
        logger.error("No replacement key available from pool!")
        return False

    if new_key == current_key:
        logger.warning("Pool returned the same key — something wrong")
        return False

    # Auth.json updaten
    if _update_auth(new_key):
        logger.info(f"✅ SWAPPED: {current_key[:20]}... → {new_key[:20]}...")
        logger.info(f"   New alias: {report_result.get('new_alias', '?')}")
        return True
    else:
        logger.error("Key swapped but failed to update auth.json!")
        return False


def run_once():
    """Single check-and-swap pass."""
    swapped = check_and_swap()
    if swapped:
        print(f"✅ Key swapped successfully")
    else:
        print(f"ℹ️  Current key is healthy, no swap needed")


def run_daemon():
    """Run as daemon, checking every CHECK_INTERVAL seconds."""
    logger.info(f"🔥 Key Watchdog started (interval={CHECK_INTERVAL}s)")
    logger.info(f"   Monitoring: {AUTH_FILE}")
    logger.info(f"   Pool API: {POOL_API}")

    while True:
        try:
            check_and_swap()
        except Exception as e:
            logger.error(f"Check failed: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    elif "--interval" in sys.argv:
        idx = sys.argv.index("--interval")
        CHECK_INTERVAL = int(sys.argv[idx + 1])
        run_daemon()
    else:
        run_daemon()
