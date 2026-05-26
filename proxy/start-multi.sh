#!/bin/bash
# Startet 3 Pool-Proxy Instanzen für Multi-Mac Load-Balancing
# Jede Instanz nutzt EINEN Key (kein Backup) aus dem gemeinsamen Pool
set -e

BASE_PORT=8888
INSTANCES=3
PROXY_DIR=~/dev/SINator-fireworksai/proxy

echo "🚀 SINator Multi-Pool Proxy — $INSTANCES Instanzen"
echo "================================================"
echo ""

# Kill old instances
for port in $(seq $BASE_PORT $((BASE_PORT + INSTANCES - 1))); do
  lsof -ti :$port 2>/dev/null | xargs kill -9 2>/dev/null || true
done
sleep 1

# Start instances
for i in $(seq 1 $INSTANCES); do
  PORT=$((BASE_PORT + i - 1))
  echo "[$i/$INSTANCES] Proxy → :$PORT"
  cd "$PROXY_DIR"
  SIN_PROXY_PORT=$PORT SIN_LEASE_BACKUP=false SIN_NO_BACKUP=true \
    nohup /opt/homebrew/bin/python3 server.py > /tmp/sinator-proxy-$PORT.log 2>&1 &
  echo "  PID: $!"
done

# Wait for all
echo ""
echo "⏳ Waiting for proxies to be ready..."
for i in $(seq 1 20); do
  ALL_OK=1
  for port in $(seq $BASE_PORT $((BASE_PORT + INSTANCES - 1))); do
    s=$(/usr/bin/curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null || echo "---")
    [ "$s" != "200" ] && ALL_OK=0
  done
  if [ "$ALL_OK" = "1" ]; then
    echo "✅ All $INSTANCES proxies ready!"
    break
  fi
  printf "  [%2d] " "$i"
  for port in $(seq $BASE_PORT $((BASE_PORT + INSTANCES - 1))); do
    s=$(/usr/bin/curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null || echo "-")
    printf ":%d=%s " "$port" "$s"
  done
  echo ""
  sleep 2
done

echo ""
echo "=== Proxy URLs ==="
for port in $(seq $BASE_PORT $((BASE_PORT + INSTANCES - 1))); do
  echo "  Pool $port: http://localhost:$port/inference/v1"
done
echo ""
echo "=== Mac-Zuweisung ==="
echo "  Mac 1 → :8888"
echo "  Mac 2 → :8889"
echo "  Mac 3 → :8890"
echo ""
echo "  baseURL: http://localhost:PORT/inference/v1   (PORT = zugewiesener Port)"
