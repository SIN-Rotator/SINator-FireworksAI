#!/usr/bin/env python3
"""SINator-Fireworks VM Rotator — generates keys and pushes to Mac backend.
Runs on Xvfb :99 with Chromium CDP :9222.
Uses synchronous subprocess for rotate.py (avoids event loop issues).
File-lock protected: prevents concurrent runs from auto-rotator + manual batches.
"""
import fcntl
import json
import logging
import os
import re
import subprocess
import sys
import time
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rotate_vm")

ROTATOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAC_BACKEND = os.environ.get("MAC_BACKEND_URL", "https://sinator.delqhi.com")
CDP_PORT = 9222
DISPLAY = ":99"
LOCK_FILE = "/tmp/sinator-rotate.lock"
LOCK_FD = None

def push_key_to_mac(api_key, alias_email, key_name):
    """Push generated key to Mac backend pool via API."""
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(
                f"{MAC_BACKEND}/api/v1/pool/add",
                json={"api_key": api_key, "alias_email": alias_email, "key_name": key_name},
            )
            if r.status_code == 200:
                logger.info(f"Key pushed to Mac backend: {r.json().get('key_id','?')[:8]}...")
                return True
            else:
                logger.error(f"Mac backend returned {r.status_code}: {r.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"Failed to push key to Mac: {e}")
        return False

def ensure_chrome():
    """Ensure Chromium is running on CDP :9222."""
    try:
        result = subprocess.run(["pgrep", "-f", "remote-debugging-port=9222"],
                              capture_output=True)
        if result.returncode == 0:
            return True
    except Exception:
        pass
    
    logger.info("Starting Chromium on Xvfb :99 with CDP :9222...")
    subprocess.Popen(
        ["chromium-browser",
         f"--remote-debugging-port={CDP_PORT}",
         "--remote-allow-origins=*",
         "--no-first-run",
         "--no-default-browser-check",
         "--disable-gpu",
         "--no-sandbox",
         "--user-data-dir=/opt/sinator-fireworks/chrome-profile",
         "about:blank"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "DISPLAY": DISPLAY},
    )
    time.sleep(3)
    return True

def generate_one_key():
    """Generate a single Fireworks API key using the rotator."""
    ensure_chrome()
    
    logger.info("Running rotate.py via CDP...")
    env = {**os.environ, "DISPLAY": DISPLAY, "PYTHONPATH": ROTATOR_DIR}
    
    result = subprocess.run(
        [sys.executable, "-u", os.path.join(ROTATOR_DIR, "tools", "rotate.py"),
         "--cdp-port", str(CDP_PORT), "--debug"],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        cwd=ROTATOR_DIR,
    )
    
    output = result.stdout + "\n" + result.stderr
    
    # Parse API key
    api_key = None
    alias = None
    for line in output.split("\n"):
        if "API Key: fw_" in line:
            idx = line.find("fw_")
            api_key = line[idx:].strip().split()[0].rstrip(".")
        if "GMX Alias:" in line:
            idx = line.find("Alias:") + 7
            alias = line[idx:].strip()
    
    if not api_key:
        m = re.search(r'(fw_[A-Za-z0-9]{20,})', output)
        if m:
            api_key = m.group(1)
    
    if api_key:
        key_name = (alias or "vm-key").split("@")[0].split("-")[0] if alias else "vm-key"
        logger.info(f"✓ API Key: {api_key[:20]}...")
        if alias:
            logger.info(f"  Alias: {alias}")
        pushed = push_key_to_mac(api_key, alias or "unknown@gmx.de", key_name)
        if pushed:
            logger.info("✓ Key synced to Mac backend")
        else:
            logger.warning("⚠ Key NOT synced — saving locally")
            pool_file = os.path.join(ROTATOR_DIR, "data", "fireworksai-pool.json")
            keys = []
            if os.path.exists(pool_file):
                with open(pool_file) as f:
                    try: keys = json.load(f)
                    except: keys = []
            import uuid
            keys.append({"id": str(uuid.uuid4()), "api_key": api_key,
                         "alias_email": alias or "unknown@gmx.de", "key_name": key_name,
                         "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "suspended": False, "used": False})
            with open(pool_file, "w") as f:
                json.dump(keys, f, indent=2)
        return True
    else:
        logger.error("✗ No API key generated")
        for line in output.split("\n")[-10:]:
            if line.strip():
                logger.error(f"  {line.strip()}")
        return False

def acquire_lock():
    """Acquire exclusive file lock. Returns True if acquired, False if another process holds it."""
    global LOCK_FD
    LOCK_FD = open(LOCK_FILE, "w")
    os.chmod(LOCK_FILE, 0o666)  # world-writable so root + ubuntu can share
    try:
        fcntl.flock(LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
        LOCK_FD.write(f"{os.getpid()}\n")
        LOCK_FD.flush()
        logger.info(f"Lock acquired: {LOCK_FILE} (pid={os.getpid()})")
        return True
    except (IOError, OSError):
        existing_pid = LOCK_FD.read().strip()
        logger.warning(f"Lock held by pid={existing_pid} — another rotate_vm.py is running. Exiting.")
        LOCK_FD.close()
        LOCK_FD = None
        return False

def release_lock():
    """Release the file lock."""
    global LOCK_FD
    if LOCK_FD:
        try:
            fcntl.flock(LOCK_FD, fcntl.LOCK_UN)
            LOCK_FD.close()
            os.unlink(LOCK_FILE)
            logger.info("Lock released")
        except Exception:
            pass
        LOCK_FD = None

def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    logger.info(f"=== SINator-Fireworks VM: generating {count} key(s) ===")
    logger.info(f"Mac backend: {MAC_BACKEND}")
    logger.info(f"Display: {DISPLAY}, CDP: {CDP_PORT}")

    if not acquire_lock():
        sys.exit(1)

    success = 0
    failed = 0
    t_start = time.time()
    try:
        for i in range(1, count + 1):
            logger.info(f"\n--- Key {i}/{count} ---")
            t0 = time.time()
            try:
                ok = generate_one_key()
                elapsed = time.time() - t0
                if ok:
                    success += 1
                    logger.info(f"Key {i} took {elapsed:.1f}s")
                else:
                    failed += 1
                    logger.error(f"Key {i} failed after {elapsed:.1f}s")
            except Exception as e:
                logger.error(f"Key {i} failed: {e}")
                failed += 1
            if i < count:
                time.sleep(15)  # Bug 6 fix: 15s delay to avoid GMX rate limiting
    finally:
        release_lock()

    total_elapsed = time.time() - t_start
    logger.info(f"\n=== DONE: {success}/{count} keys generated ({failed} failed) in {total_elapsed:.1f}s ===")
    if success > 0:
        logger.info(f"Average: {total_elapsed / success:.1f}s per key")

if __name__ == "__main__":
    main()
