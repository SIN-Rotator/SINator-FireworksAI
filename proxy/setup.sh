#!/bin/bash
# Pool Proxy Installer for Miner MacBooks
# Usage: ./setup.sh [tunnel_url]
set -e

TUNNEL_URL="${1:-}"
INSTALL_DIR="$HOME/.sin-pool"
PLIST_NAME="com.sin.pool-proxy"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
OPENCODE_CONFIG="$HOME/.config/opencode/opencode.json"

echo "=== SINator Pool Proxy Setup ==="
echo ""

# 1. Create install directory
mkdir -p "$INSTALL_DIR"
echo "[1/6] Install dir: $INSTALL_DIR"

# 2. Copy proxy files
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for f in server.py pool_client.py key_cache.py config.py __init__.py; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        cp "$SCRIPT_DIR/$f" "$INSTALL_DIR/"
    fi
done
echo "[2/6] Proxy files copied"

# 3. Ask for tunnel URL if not provided
if [ -z "$TUNNEL_URL" ]; then
    echo ""
    echo "Enter SINator tunnel URL (e.g. https://xxx.trycloudflare.com):"
    read -r TUNNEL_URL
fi

# Write config
python3 -c "
import json, sys
cfg = {
    'pool_api_url': '${TUNNEL_URL}/api/v1',
    'proxy_port': 8888,
    'fireworks_base': 'https://api.fireworks.ai/inference/v1',
    'lease_ttl_seconds': 1800,
    'lease_backup': True,
    'max_retries': 3,
}
with open('${INSTALL_DIR}/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
print(f'Config written to ${INSTALL_DIR}/config.json')
"
echo "[3/6] Config saved (pool_api_url: $TUNNEL_URL/api/v1)"

# 4. Create LaunchAgent (runs server.py from install dir)
cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${INSTALL_DIR}/server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${INSTALL_DIR}</string>
        <key>SIN_CACHE_DIR</key>
        <string>${INSTALL_DIR}</string>
        <key>SIN_POOL_API_URL</key>
        <string>${TUNNEL_URL}/api/v1</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${INSTALL_DIR}/proxy.log</string>
    <key>StandardErrorPath</key>
    <string>${INSTALL_DIR}/proxy-error.log</string>
</dict>
</plist>
PLIST
echo "[4/6] LaunchAgent installed: $PLIST_PATH"

# 5. Patch opencode config
if [ -f "$OPENCODE_CONFIG" ]; then
    echo "[5/6] Patching opencode config..."
    python3 -c "
import json
with open('${OPENCODE_CONFIG}') as f:
    cfg = json.load(f)
for provider_name, provider in cfg.get('provider', {}).items():
    if 'fireworks' in provider_name.lower():
        provider.setdefault('options', {})['baseURL'] = 'http://localhost:8888/inference/v1'
        print(f'  Patched {provider_name}: baseURL → http://localhost:8888/inference/v1')
with open('${OPENCODE_CONFIG}', 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>/dev/null || echo "  (opencode config patch skipped — no fireworks provider found)"
else
    echo "[5/6] No opencode config found at $OPENCODE_CONFIG (skip patching)"
fi

# 6. Load LaunchAgent
launchctl load "$PLIST_PATH" 2>/dev/null || true
echo "[6/6] LaunchAgent loaded"
echo ""
echo "=== Setup Complete ==="
echo "  Proxy:     http://localhost:8888"
echo "  Health:    http://localhost:8888/health"
echo "  Pool API:  $TUNNEL_URL/api/v1"
echo "  Log:       $INSTALL_DIR/proxy.log"
echo ""
echo "To test: curl http://localhost:8888/health"
echo "To stop:  launchctl unload $PLIST_PATH"
echo "To start: launchctl load $PLIST_PATH"
