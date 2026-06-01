#!/bin/bash
# Updates ~/.sin-pool/ and ~/.hermes/scripts/ from repo WITHOUT reconfiguring
# Usage: ./update-installed.sh
#
# Issue #26: Keeps installed version in sync with repo
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL_DIR="$HOME/.sin-pool"
HERMES_SCRIPTS="$HOME/.hermes/scripts"

echo "=== SINator Update Installed ==="
echo "Repo: $REPO_ROOT"
echo ""

# Check if installed
if [ ! -d "$INSTALL_DIR" ]; then
    echo "ERROR: $INSTALL_DIR not found. Run setup.sh first."
    exit 1
fi

# Stop services first
echo "[1/4] Stopping services..."
launchctl unload ~/Library/LaunchAgents/com.sin.pool-proxy.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.sin.pool-router.plist 2>/dev/null || true
pkill -9 -f "\.sin-pool/server\.py" 2>/dev/null || true
pkill -9 -f "\.hermes/scripts/pool-router\.py" 2>/dev/null || true
sleep 1

# Sync proxy files
echo "[2/4] Syncing proxy files..."
for f in server.py pool_client.py key_cache.py config.py __init__.py; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/"
        echo "  - ~/.sin-pool/$f"
    fi
done

# Sync pool-router
echo "[3/4] Syncing pool-router..."
if [ -d "$HERMES_SCRIPTS" ]; then
    cp "$REPO_ROOT/scripts/pool-router.py" "$HERMES_SCRIPTS/"
    echo "  - ~/.hermes/scripts/pool-router.py"
fi

# Write version marker
echo "$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'unknown') $(date +%Y-%m-%d_%H:%M)" > "$INSTALL_DIR/.version"
echo "[4/4] Version: $(cat "$INSTALL_DIR/.version")"

echo ""
echo "=== Update Complete ==="
echo ""
echo "To restart services:"
echo "  launchctl load ~/Library/LaunchAgents/com.sin.pool-proxy.plist"
echo "  launchctl load ~/Library/LaunchAgents/com.sin.pool-router.plist"
echo ""
echo "Or use start-multi.sh to start from repo directly."
