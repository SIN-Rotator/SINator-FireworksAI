#!/bin/bash
# Startet 10 Pool-Proxy Instanzen (8888-8897) + Pool-Router (9998)
# Jeder Proxy nutzt EINEN Key aus dem gemeinsamen Pool
# Der Pool-Router verteilt Requests auf alle Proxys mit Auto-Failover
#
# Issue #26: Unloads LaunchAgents first to prevent respawn from ~/.sin-pool/
set -e

BASE_PORT=8888
INSTANCES=10
PROXY_DIR=~/dev/SINator-fireworksai/proxy
REPO_ROOT=~/dev/SINator-fireworksai

echo "SINator Pool — $INSTANCES Proxys + Router"
echo "=========================================="
echo ""

# ----------------------------------------------------------------
# Issue #26 FIX: Stop LaunchAgents BEFORE killing PIDs
# Otherwise KeepAlive respawns from stale ~/.sin-pool/ code
# ----------------------------------------------------------------
echo "[0] Stopping LaunchAgents (prevents respawn)..."
launchctl unload ~/Library/LaunchAgents/com.sin.pool-proxy.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.sin.pool-router.plist 2>/dev/null || true
# Kill any stray .sin-pool processes explicitly
pkill -9 -f "\.sin-pool/server\.py" 2>/dev/null || true
pkill -9 -f "\.hermes/scripts/pool-router\.py" 2>/dev/null || true
sleep 0.5

# Kill old instances by port
for port in $(seq $BASE_PORT $((BASE_PORT + INSTANCES - 1))); do
  lsof -ti :$port 2>/dev/null | xargs kill -9 2>/dev/null || true
done
lsof -ti :9998 2>/dev/null | xargs kill -9 2>/dev/null || true
rm -f ~/.sin-pool/tunnel-url.txt
sleep 1

# ----------------------------------------------------------------
# Issue #26 FIX: Sync ~/.sin-pool/ from repo before starting
# This ensures the installed version matches the repo
# ----------------------------------------------------------------
echo "[0.5] Syncing ~/.sin-pool/ from repo (Issue #26 fix)..."
mkdir -p ~/.sin-pool
for f in server.py pool_client.py key_cache.py config.py __init__.py; do
  if [ -f "$PROXY_DIR/$f" ]; then
    cp "$PROXY_DIR/$f" ~/.sin-pool/
  fi
done
# Also sync pool-router to ~/.hermes/scripts/ if it exists
if [ -d ~/.hermes/scripts ]; then
  cp "$REPO_ROOT/scripts/pool-router.py" ~/.hermes/scripts/ 2>/dev/null || true
fi
echo "  Synced: server.py, pool_client.py, config.py, pool-router.py"

# Start proxy instances (from REPO, not ~/.sin-pool/)
for i in $(seq 1 $INSTANCES); do
  PORT=$((BASE_PORT + i - 1))
  echo "[$i/$INSTANCES] Proxy → :$PORT (from repo)"
  cd "$PROXY_DIR"
  SIN_POOL_API_URL="http://localhost:8000/api/v1" \
    SIN_PROXY_PORT=$PORT SIN_LEASE_BACKUP=true \
    nohup /opt/homebrew/bin/python3 server.py > /tmp/sinator-proxy-$PORT.log 2>&1 &
  echo "  PID: $!"
done

# Start pool-router (from REPO, not ~/.hermes/)
echo ""
echo "[Router] Pool-Router → :9998 (from repo)"
cd "$REPO_ROOT"
nohup /opt/homebrew/bin/python3 scripts/pool-router.py > /tmp/pool-router.log 2>&1 &
echo "  PID: $!"

echo ""
echo "Done: $INSTANCES Proxys + Router gestartet"
echo "   Proxys:  http://localhost:{$BASE_PORT..$((BASE_PORT + INSTANCES - 1))}"
echo "   Router:  http://localhost:9998"
echo "   Health:  curl http://localhost:9998/health"
echo ""
echo "Note: LaunchAgents wurden gestoppt. Beim naechsten Reboot starten sie"
echo "      wieder von ~/.sin-pool/ — fuehre dann erneut start-multi.sh aus"
echo "      oder nutze 'proxy/setup.sh' um die installierte Version zu updaten."
