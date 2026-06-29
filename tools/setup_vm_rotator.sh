#!/bin/bash
# SINator-Fireworks VM Setup — installiert kompletten Rotator-Stack auf sin-supabase
# Xvfb + Chromium + Playwright + Rotator + noVNC + systemd Services
# Keys werden zu Mac Backend (sinator.delqhi.com) gepusht
set -e

VM_SSH="sin-supabase"
ROTATOR_DIR="/opt/sinator-fireworks"
V2_REPO="https://github.com/SIN-Rotator/SINator-Fireworks-Rotator-v2.git"

echo "========================================"
echo "  SINator-Fireworks VM Setup"
echo "  VM: sin-supabase (24GB RAM, ARM)"
echo "========================================"

# ── 1. System-Pakete ──────────────────────────────────────────────────
echo "→ [1/7] Installing system packages..."
ssh $VM_SSH 'sudo apt-get update -qq && sudo apt-get install -y -qq \
    chromium-browser \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    python3 \
    python3-pip \
    python3-venv \
    git \
    jq \
    2>&1 | tail -5'

echo "  ✅ System packages installed"

# ── 2. Rotator Repo klonen ────────────────────────────────────────────
echo "→ [2/7] Cloning rotator repo..."
ssh $VM_SSH "if [ ! -d $ROTATOR_DIR ]; then
    sudo mkdir -p $ROTATOR_DIR
    sudo chown ubuntu:ubuntu $ROTATOR_DIR
    git clone $V2_REPO $ROTATOR_DIR 2>&1 | tail -3
else
    cd $ROTATOR_DIR && git pull 2>&1 | tail -3
fi"
echo "  ✅ Rotator repo ready"

# ── 3. Python venv + Playwright ───────────────────────────────────────
echo "→ [3/7] Setting up Python environment..."
ssh $VM_SSH "cd $ROTATOR_DIR && \
    python3 -m venv .venv && \
    .venv/bin/pip install --quiet --upgrade pip && \
    .venv/bin/pip install --quiet playwright httpx aiohttp 2>&1 | tail -3 && \
    .venv/bin/playwright install chromium 2>&1 | tail -3 && \
    .venv/bin/playwright install-deps 2>&1 | tail -3"
echo "  ✅ Python + Playwright ready"

# ── 4. GMX Config sicher übertragen ───────────────────────────────────
echo "→ [4/7] Transferring GMX config (secure)..."
# Read config from shared location, transfer via stdin (no chat leak)
CONFIG_FILE="$HOME/dev/data/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    CONFIG_FILE="$HOME/dev/SINator-Fireworks-Rotator-v2/data/config.json"
fi
if [ -f "$CONFIG_FILE" ]; then
    cat "$CONFIG_FILE" | ssh $VM_SSH "sudo mkdir -p $ROTATOR_DIR/data && \
        sudo chown ubuntu:ubuntu $ROTATOR_DIR/data && \
        cat > $ROTATOR_DIR/data/config.json && \
        chmod 600 $ROTATOR_DIR/data/config.json"
    echo "  ✅ GMX config transferred (chmod 600)"
else
    echo "  ⚠️  Config file not found — will need manual setup"
fi

# ── 5. VM-spezifisches rotate_sync Script ─────────────────────────────
echo "→ [5/7] Creating VM rotator scripts..."
ssh $VM_SSH "cat > $ROTATOR_DIR/tools/rotate_vm.py" << 'PYEOF'
#!/usr/bin/env python3
"""SINator-Fireworks VM Rotator — generates keys and pushes to Mac backend.
Runs on Xvfb :99 with Chromium CDP :9222.
"""
import asyncio
import json
import logging
import os
import sys
import time
import subprocess
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rotate_vm")

ROTATOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAC_BACKEND = os.environ.get("MAC_BACKEND_URL", "https://sinator.delqhi.com")
CDP_PORT = 9222
DISPLAY = ":99"

async def push_key_to_mac(api_key, alias_email, key_name):
    """Push generated key to Mac backend pool via API."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{MAC_BACKEND}/api/v1/pool/add",
                json={
                    "api_key": api_key,
                    "alias_email": alias_email,
                    "key_name": key_name,
                },
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

async def generate_one_key():
    """Generate a single Fireworks API key using the rotator."""
    # Set display for Chrome
    os.environ["DISPLAY"] = DISPLAY
    
    # Ensure Chrome is running on CDP :9222
    try:
        proc = await asyncio.create_subprocess_exec(
            "pgrep", "-f", "remote-debugging-port=9222",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        chrome_running = proc.returncode == 0
    except Exception:
        chrome_running = False

    if not chrome_running:
        logger.info("Starting Chromium on Xvfb :99 with CDP :9222...")
        # Start Chrome in background on virtual display
        chrome_proc = await asyncio.create_subprocess_exec(
            "chromium-browser",
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--no-sandbox",
            "--user-data-dir=/opt/sinator-fireworks/chrome-profile",
            "about:blank",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "DISPLAY": DISPLAY},
        )
        logger.info(f"Chromium started (PID {chrome_proc.pid})")
        await asyncio.sleep(3)
    
    # Run rotate.py with CDP
    logger.info("Running rotate.py via CDP...")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-u",
        os.path.join(ROTATOR_DIR, "tools", "rotate.py"),
        "--cdp-port", str(CDP_PORT),
        "--debug",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "DISPLAY": DISPLAY, "PYTHONPATH": ROTATOR_DIR},
        cwd=ROTATOR_DIR,
    )
    
    stdout, stderr = await proc.communicate()
    out = stdout.decode(errors="replace")
    err = stderr.decode(errors="replace")
    
    # Parse API key from output (rotate.py logs to stderr via logging module)
    api_key = None
    alias = None
    for line in (err + out).split("\n"):
        if "API Key: fw_" in line:
            # Extract key
            idx = line.find("fw_")
            api_key = line[idx:].strip().split()[0].rstrip(".")
        if "GMX Alias:" in line:
            idx = line.find("Alias:") + 7
            alias = line[idx:].strip()
    
    if not api_key:
        # Try regex
        import re
        m = re.search(r'(fw_[A-Za-z0-9]{20,})', err + out)
        if m:
            api_key = m.group(1)
    
    if api_key:
        key_name = (alias or "vm-key").split("@")[0].split("-")[0] if alias else "vm-key"
        logger.info(f"✓ API Key: {api_key[:20]}...")
        if alias:
            logger.info(f"  Alias: {alias}")
        # Push to Mac backend
        pushed = await push_key_to_mac(api_key, alias or "unknown@gmx.de", key_name)
        if pushed:
            logger.info("✓ Key synced to Mac backend")
        else:
            logger.warning("⚠ Key generated but NOT synced to Mac — saving locally")
            # Fallback: save locally
            pool_file = os.path.join(ROTATOR_DIR, "data", "fireworksai-pool.json")
            keys = []
            if os.path.exists(pool_file):
                with open(pool_file) as f:
                    try:
                        keys = json.load(f)
                    except:
                        keys = []
            import uuid
            keys.append({
                "id": str(uuid.uuid4()),
                "api_key": api_key,
                "alias_email": alias or "unknown@gmx.de",
                "key_name": key_name,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "suspended": False,
                "used": False,
            })
            with open(pool_file, "w") as f:
                json.dump(keys, f, indent=2)
        return True
    else:
        logger.error("✗ No API key generated")
        # Log last 10 lines for debugging
        for line in (err + out).split("\n")[-10:]:
            if line.strip():
                logger.error(f"  {line.strip()}")
        return False

async def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    logger.info(f"=== SINator-Fireworks VM: generating {count} key(s) ===")
    logger.info(f"Mac backend: {MAC_BACKEND}")
    logger.info(f"Display: {DISPLAY}, CDP: {CDP_PORT}")
    
    success = 0
    failed = 0
    for i in range(1, count + 1):
        logger.info(f"\n--- Key {i}/{count} ---")
        try:
            ok = await generate_one_key()
            if ok:
                success += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Key {i} failed: {e}")
            failed += 1
        if i < count:
            await asyncio.sleep(5)
    
    elapsed = 0
    logger.info(f"\n=== DONE: {success}/{count} keys generated ({failed} failed) ===")
    
    # Signal auto-keygen to restart Chrome if needed
    if failed > 0:
        logger.warning("Some keys failed — Chrome may need restart")

if __name__ == "__main__":
    asyncio.run(main())
PYEOF

ssh $VM_SSH "chmod +x $ROTATOR_DIR/tools/rotate_vm.py"
echo "  ✅ rotate_vm.py created"

# ── 6. systemd Services ───────────────────────────────────────────────
echo "→ [6/7] Creating systemd services..."

# Xvfb service
ssh $VM_SSH "sudo tee /etc/systemd/system/sinator-xvfb.service" << 'EOF'
[Unit]
Description=SINator Xvfb Virtual Display (:99)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Chromium service
ssh $VM_SSH "sudo tee /etc/systemd/system/sinator-chromium.service" << 'EOF'
[Unit]
Description=SINator Chromium (CDP :9222 on Xvfb :99)
After=sinator-xvfb.service
Requires=sinator-xvfb.service

[Service]
Type=simple
Environment=DISPLAY=:99
ExecStart=/usr/bin/chromium-browser \
    --remote-debugging-port=9222 \
    --remote-allow-origins=* \
    --no-first-run \
    --no-default-browser-check \
    --disable-gpu \
    --no-sandbox \
    --user-data-dir=/opt/sinator-fireworks/chrome-profile \
    about:blank
Restart=always
RestartSec=10
WorkingDirectory=/opt/sinator-fireworks

[Install]
WantedBy=multi-user.target
EOF

# noVNC service (web-based screen viewing)
ssh $VM_SSH "sudo tee /etc/systemd/system/sinator-novnc.service" << 'EOF'
[Unit]
Description=SINator noVNC Web Viewer (:6080)
After=sinator-xvfb.service
Requires=sinator-xvfb.service

[Service]
Type=simple
ExecStartPre=/usr/bin/x11vnc -display :99 -bg -forever -nopw -xkb
ExecStart=/usr/bin/websockify --web=/usr/share/novnc/ 6080 localhost:5900
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Auto-rotator service (runs every 10 minutes, checks Mac pool, generates if low)
ssh $VM_SSH "sudo tee /etc/systemd/system/sinator-auto-rotator.service" << 'EOF'
[Unit]
Description=SINator Auto Key Generator

[Service]
Type=oneshot
ExecStart=/opt/sinator-fireworks/.venv/bin/python3 /opt/sinator-fireworks/tools/auto_keygen_vm.py
Environment=DISPLAY=:99
Environment=MAC_BACKEND_URL=https://sinator.delqhi.com
WorkingDirectory=/opt/sinator-fireworks
EOF

ssh $VM_SSH "sudo tee /etc/systemd/system/sinator-auto-rotator.timer" << 'EOF'
[Unit]
Description=SINator Auto Key Generator (every 10 min)

[Timer]
OnBootSec=60
OnUnitActiveSec=600
AccuracySec=30

[Install]
WantedBy=timers.target
EOF

# Enable + start services
ssh $VM_SSH "sudo systemctl daemon-reload && \
    sudo systemctl enable --now sinator-xvfb && \
    sleep 2 && \
    sudo systemctl enable --now sinator-chromium && \
    sleep 3 && \
    sudo systemctl enable --now sinator-novnc && \
    sudo systemctl enable sinator-auto-rotator.timer && \
    sudo systemctl start sinator-auto-rotator.timer"
echo "  ✅ systemd services enabled"

# ── 7. auto_keygen_vm.py (Pool check + trigger generation) ────────────
echo "→ [7/7] Creating auto-keygen script..."
ssh $VM_SSH "cat > $ROTATOR_DIR/tools/auto_keygen_vm.py" << 'PYEOF'
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
PYEOF

ssh $VM_SSH "chmod +x $ROTATOR_DIR/tools/auto_keygen_vm.py"
echo "  ✅ auto_keygen_vm.py created"

# ── Verify ────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  Verifying setup..."
echo "========================================"

ssh $VM_SSH "echo '=== Services ===' && \
    systemctl is-active sinator-xvfb sinator-chromium sinator-novnc sinator-auto-rotator.timer 2>&1 && \
    echo '=== Chrome CDP ===' && \
    curl -s http://localhost:9222/json/version 2>/dev/null | jq -r '.Browser // \"FAIL\"' && \
    echo '=== noVNC ===' && \
    curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost:6080/ 2>/dev/null && echo && \
    echo '=== Mac Backend ===' && \
    curl -s -o /dev/null -w 'HTTP %{http_code}' $MAC_BACKEND/health 2>/dev/null && echo && \
    echo '=== Config ===' && \
    test -f $ROTATOR_DIR/data/config.json && echo 'config.json ✅' || echo 'config.json ❌'"

echo ""
echo "========================================"
echo "  SETUP COMPLETE"
echo "========================================"
echo ""
echo "  noVNC (live screen): http://92.5.60.87:6080"
echo "  Chrome CDP:          http://localhost:9222 (on VM)"
echo "  Mac Backend:         https://sinator.delqhi.com"
echo "  Auto-Rotator:        every 10 min (threshold: 5 keys)"
echo ""
echo "  Generate 1 key now:"
echo "    ssh sin-supabase '/opt/sinator-fireworks/.venv/bin/python3 -u /opt/sinator-fireworks/tools/rotate_vm.py 1'"
echo ""
echo "  Check auto-keygen log:"
echo "    ssh sin-supabase 'tail -20 /tmp/sinator-auto-keygen.log'"
echo ""
