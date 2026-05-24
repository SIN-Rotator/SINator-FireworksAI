#!/bin/bash
# SINator Auto-Start Setup — makes everything launch on boot
# Usage: ./tools/autostart.sh {install|start|stop|status|uninstall}
set -e

SINATOR_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON=$(which python3)
LA=~/Library/LaunchAgents

case "${1:-status}" in

    install)
        echo "→ Installing all SINator LaunchAgents..."

        # 1. Chrome — starts with Profile 901 + CDP port 9222
        cat > "$LA/com.sinator.chrome.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.chrome</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Google Chrome.app/Contents/MacOS/Google Chrome</string>
        <string>--user-data-dir=/Users/jeremy/Library/Application Support/Google Chrome</string>
        <string>--profile-directory=Profile 901</string>
        <string>--remote-debugging-port=9222</string>
        <string>--no-first-run</string>
        <string>--no-default-browser-check</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/sinator-chrome.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/sinator-chrome.err</string>
</dict>
</plist>
EOF

        # 2. cua-driver daemon
        cat > "$LA/com.sinator.cua-driver.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.cua-driver</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/jeremy/.local/bin/cua-driver</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/sinator-cua-driver.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/sinator-cua-driver.err</string>
    <key>ThrottleInterval</key>
    <integer>5</integer>
</dict>
</plist>
EOF

        # 3. Backend (FastAPI :8000)
        cat > "$LA/com.sinator.backend.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.backend</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SINATOR_DIR}/agent_toolbox/start_toolbox.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${SINATOR_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${SINATOR_DIR}/agent_toolbox/core</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/sinator-backend.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/sinator-backend.err</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

        # 4. Pool Proxy (aiohttp :8888)
        mkdir -p "${HOME}/.sin-pool"
        cat > "$LA/com.sinator.pool-proxy.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.pool-proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SINATOR_DIR}/proxy/server.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${SINATOR_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${SINATOR_DIR}</string>
        <key>SIN_CACHE_DIR</key>
        <string>${HOME}/.sin-pool</string>
        <key>SIN_POOL_API_URL</key>
        <string>http://localhost:8000/api/v1</string>
        <key>SIN_PROXY_PORT</key>
        <string>8888</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/pool-proxy.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/pool-proxy.err</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

        # 5. Cloudflare Tunnel
        cat > "$LA/com.sinator.tunnel.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SINATOR_DIR}/tools/sinator_tunnel.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/sinator-tunnel.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/sinator-tunnel.log</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

        echo "→ Loading services..."
        for svc in chrome cua-driver backend pool-proxy tunnel; do
            launchctl load "$LA/com.sinator.${svc}.plist" 2>/dev/null || true
        done
        echo ""
        echo "✅ All SINator services installed and loaded!"
        echo "   They will auto-start on next login/boot."
        echo ""
        echo "   Start order: Chrome → cua-driver → backend → pool-proxy → tunnel"
        echo "   Chrome + cua-driver start first (no deps)"
        echo "   Backend waits 8s for Chrome (CDP port 9222)"
        echo "   Pool-proxy waits 3s for backend (:8000)"
        echo "   Tunnel waits for pool-proxy (:8888)"
        ;;

    start)
        echo "→ Starting all SINator services..."
        for svc in chrome cua-driver backend pool-proxy tunnel; do
            launchctl kickstart "gui/$(id -u)/com.sinator.${svc}" 2>/dev/null || \
                launchctl start "com.sinator.${svc}" 2>/dev/null || true
        done
        echo "✅ Started"
        ;;

    stop)
        echo "→ Stopping all SINator services..."
        for svc in tunnel pool-proxy backend cua-driver chrome; do
            launchctl bootout "gui/$(id -u)/com.sinator.${svc}" 2>/dev/null || true
        done
        echo "✅ Stopped"
        ;;

    status)
        echo "╔══════════════════════════════════════╗"
        echo "║       SINator Service Status         ║"
        echo "╠══════════════════════════════════════╣"
        for svc in chrome cua-driver backend pool-proxy tunnel; do
            if launchctl print "gui/$(id -u)/com.sinator.${svc}" 2>/dev/null | grep -q "state = running"; then
                echo "║  ✅ com.sinator.${svc}"
            else
                echo "║  ❌ com.sinator.${svc}"
            fi
        done
        echo "╠══════════════════════════════════════╣"

        if curl -s http://127.0.0.1:9222/json/version &>/dev/null; then
            echo "║  🌐 Chrome CDP:  http://localhost:9222 ✅"
        else
            echo "║  🌐 Chrome CDP:  not reachable ❌"
        fi

        if curl -s http://localhost:8000/docs &>/dev/null; then
            echo "║  🌐 Backend:     http://localhost:8000 ✅"
        else
            echo "║  🌐 Backend:     not reachable ❌"
        fi

        if curl -s http://localhost:8888/health &>/dev/null; then
            echo "║  🌐 Proxy:       http://localhost:8888 ✅"
        else
            echo "║  🌐 Proxy:       not reachable ❌"
        fi

        TUNNEL_URL=$(grep -o 'https://.*trycloudflare.com' /tmp/sinator-tunnel.log 2>/dev/null | tail -1)
        if [ -n "$TUNNEL_URL" ]; then
            echo "║  🌐 Tunnel:      ${TUNNEL_URL} ✅"
        else
            echo "║  🌐 Tunnel:      not connected ❌"
        fi
        echo "╚══════════════════════════════════════╝"
        ;;

    uninstall)
        echo "→ Uninstalling all SINator LaunchAgents..."
        for svc in tunnel pool-proxy backend cua-driver chrome; do
            launchctl bootout "gui/$(id -u)/com.sinator.${svc}" 2>/dev/null || true
            rm -f "$LA/com.sinator.${svc}.plist"
        done
        echo "✅ Uninstalled"
        ;;

    *)
        echo "Usage: $0 {install|start|stop|status|uninstall}"
        echo ""
        echo "  install   — Create LaunchAgents + load (auto-starts on boot)"
        echo "  start     — Start all services now"
        echo "  stop      — Stop all services now"
        echo "  status    — Show service status + health"
        echo "  uninstall — Remove all LaunchAgents"
        ;;
esac
