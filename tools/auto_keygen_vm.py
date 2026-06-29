#!/usr/bin/env python3
"""Auto-keygen for VM — checks Mac pool stats, generates keys if low."""
import json
import logging
import os
import subprocess
import sys
import fcntl

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("auto-keygen-vm")

MAC_BACKEND = os.environ.get("MAC_BACKEND_URL", "https://sinator.delqhi.com")
THRESHOLD = int(os.environ.get("KEYGEN_THRESHOLD", "5"))
BATCH_SIZE = int(os.environ.get("KEYGEN_BATCH", "10"))
LOCKFILE = "/tmp/sinator-auto-keygen.lock"
LOG = "/tmp/sinator-auto-keygen.log"

def check_pool():
    """Check Mac pool available keys."""
    try:
        import httpx
        with httpx.Client(timeout=10) as c:
            r = c.get(f"{MAC_BACKEND}/api/v1/pool/stats")
            if r.status_code == 200:
                return r.json().get("available", 0)
    except Exception as e:
        logger.error(f"Pool check failed: {e}")
    return 999  # On error, don't trigger

def main():
    # Lock
    try:
        lock = open(LOCKFILE, "w")
        os.chmod(LOCKFILE, 0o666)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, BlockingIOError):
        logger.info("Already running, skipping")
        return

    available = check_pool()
    logger.info(f"Pool available={available} threshold={THRESHOLD}")

    if available < THRESHOLD:
        logger.info(f"Below threshold → generating {BATCH_SIZE} keys...")
        rotator = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rotate_vm.py")
        venv_python = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin", "python3")
        proc = subprocess.run(
            [venv_python, "-u", rotator, str(BATCH_SIZE)],
            capture_output=True,
            text=True,
            timeout=3600,
            env={**os.environ, "DISPLAY": ":99", "MAC_BACKEND_URL": MAC_BACKEND},
        )
        # Log output
        with open(LOG, "a") as f:
            f.write(proc.stdout + "\n" + proc.stderr + "\n")
        logger.info(f"Generation complete (rc={proc.returncode})")
    else:
        logger.info("Sufficient keys, skipping")

    fcntl.flock(lock, fcntl.LOCK_UN)

if __name__ == "__main__":
    main()
