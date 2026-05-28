#!/bin/bash
# Startet 10 Pool-Proxy Instanzen (8888-8897) + Pool-Router (9998)
# Jeder Proxy nutzt EINEN Key aus dem gemeinsamen Pool
# Der Pool-Router verteilt Requests auf alle Proxys mit Auto-Failover
set -e

BASE_PORT=8888
INSTANCES=10
PROXY_DIR=~/dev/SINator-fireworksai/proxy

echo "🚀 SINator Pool — $INSTANCES Proxys + Router"
echo "============================================"
echo ""

# Kill old instances
for port in $(seq $BASE_PORT $((BASE_PORT + INSTANCES - 1))); do
  lsof -ti :$port 2>/dev/null | xargs kill -9 2>/dev/null || true
done
lsof -ti :9998 2>/dev/null | xargs kill -9 2>/dev/null || true
rm -f ~/.sin-pool/tunnel-url.txt
sleep 1

# Start proxy instances (ALWAYS use local backend — never stale tunnel URL)
for i in $(seq 1 $INSTANCES); do
  PORT=$((BASE_PORT + i - 1))
  echo "[$i/$INSTANCES] Proxy → :$PORT"
  cd "$PROXY_DIR"
  SIN_POOL_API_URL="http://localhost:8000/api/v1" \
    SIN_PROXY_PORT=$PORT SIN_LEASE_BACKUP=true \
    nohup /opt/homebrew/bin/python3 server.py > /tmp/sinator-proxy-$PORT.log 2>&1 &
  echo "  PID: $!"
done

# Start pool-router
echo ""
echo "[Router] Pool-Router → :9998"
cd ~/dev/SINator-fireworksai
nohup /opt/homebrew/bin/python3 scripts/pool-router.py > /tmp/pool-router.log 2>&1 &
echo "  PID: $!"

echo ""
echo "✅ $INSTANCES Proxys + Router gestartet"
echo "   Proxys:  http://localhost:{$BASE_PORT..$((BASE_PORT + INSTANCES - 1))}"
echo "   Router:  http://localhost:9998"
echo "   Health:  curl http://localhost:9998/health"
