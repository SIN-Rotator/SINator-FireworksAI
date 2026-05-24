#!/bin/bash
# SINator Service Manager — install/start/stop all launchd services
# Usage: ./manage_services.sh {install|start|stop|status|logs}
set -e

SINATOR_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON=$(which python3)

case "${1:-status}" in
    install)
        echo "→ Installing all SINator launchd services..."

        # Backend service
        cat > ~/Library/LaunchAgents/com.sinator.backend.plist << EOF
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
    <key>StandardOutPath</key>
    <string>/tmp/sinator-backend.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/sinator-backend.err</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

        # Pool Proxy service (replaces deprecated watchdog)
        cat > ~/Library/LaunchAgents/com.sinator.pool-proxy.plist << EOF
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

        # Tunnel service
        cat > ~/Library/LaunchAgents/com.sinator.tunnel.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which cloudflared)</string>
        <string>tunnel</string>
        <string>--url</string>
        <string>http://localhost:8000</string>
    </array>
    <key>RunAtLoad</key>
    <false/>
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
        for svc in backend pool-proxy tunnel; do
            launchctl load ~/Library/LaunchAgents/com.sinator.${svc}.plist 2>/dev/null || true
        done
        echo "✅ All services installed"
        ;;

    start)
        for svc in backend pool-proxy tunnel; do
            launchctl kickstart gui/$(id -u)/com.sinator.${svc} 2>/dev/null || \
                launchctl start com.sinator.${svc} 2>/dev/null || true
        done
        echo "✅ Services started"
        ;;

    stop)
        for svc in backend pool-proxy tunnel; do
            launchctl bootout gui/$(id -u)/com.sinator.${svc} 2>/dev/null || true
        done
        echo "✅ Services stopped"
        ;;

    status)
        echo "=== SINator Services ==="
        for svc in backend pool-proxy tunnel; do
            if launchctl print gui/$(id -u)/com.sinator.${svc} 2>/dev/null | grep -q "state = running"; then
                echo "  ✅ com.sinator.${svc} — running"
            else
                echo "  ❌ com.sinator.${svc} — not running"
            fi
        done
        if pgrep -f cloudflared &>/dev/null; then
            TUNNEL_URL=$(grep -o 'https://.*trycloudflare.com' /tmp/sinator-tunnel.log 2>/dev/null | head -1)
            echo ""
            echo "  Tunnel URL: ${TUNNEL_URL:-checking...}"
        fi
        ;;

    logs)
        echo "=== Backend ==="
        tail -5 /tmp/sinator-backend.log 2>/dev/null || echo "  (no log)"
        echo ""
        echo "=== Pool Proxy ==="
        tail -5 /tmp/pool-proxy.log 2>/dev/null || echo "  (no log)"
        echo ""
        echo "=== Tunnel ==="
        tail -3 /tmp/sinator-tunnel.log 2>/dev/null || echo "  (no log)"
        ;;

    *)
        echo "Usage: $0 {install|start|stop|status|logs}"
        ;;
esac
