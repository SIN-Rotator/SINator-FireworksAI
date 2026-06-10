#!/bin/bash
# SINator Service Manager — start|stop|restart|status for all services
# Usage: ./tools/manage_services.sh {start|stop|restart|status|install|uninstall}
set -e

SINATOR_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON=$(which python3)

case "${1:-status}" in

    install)
        echo "→ Creating SINator LaunchAgents..."
        $0 uninstall 2>/dev/null || true

        # Backend (:8100)
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

        # Pool Router (:9998)
        cat > ~/Library/LaunchAgents/com.sinator.pool-router.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.pool-router</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${SINATOR_DIR}/scripts/pool-router.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${SINATOR_DIR}</string>
    <key>StandardOutPath</key>
    <string>/tmp/pool-router-launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/pool-router-launchd.log</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

        # 10 Pool Proxys (:8888-:8897)
        for port in $(seq 8888 8897); do
            cat > ~/Library/LaunchAgents/com.sinator.pool-proxy-${port}.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sinator.pool-proxy-${port}</string>
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
        <string>http://localhost:8100/api/v1</string>
        <key>SIN_PROXY_PORT</key>
        <string>${port}</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/pool-proxy-${port}.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/pool-proxy-${port}.err</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF
        done

        echo "→ Loading services..."
        launchctl load ~/Library/LaunchAgents/com.sinator.backend.plist 2>/dev/null || true
        launchctl load ~/Library/LaunchAgents/com.sinator.pool-router.plist 2>/dev/null || true
        for port in $(seq 8888 8897); do
            launchctl load ~/Library/LaunchAgents/com.sinator.pool-proxy-${port}.plist 2>/dev/null || true
        done
        echo "✅ Services installed and loaded"
        ;;

    start)
        launchctl kickstart gui/$(id -u)/com.sinator.backend 2>/dev/null || \
            launchctl start com.sinator.backend 2>/dev/null || true
        launchctl kickstart gui/$(id -u)/com.sinator.pool-router 2>/dev/null || \
            launchctl start com.sinator.pool-router 2>/dev/null || true
        for port in $(seq 8888 8897); do
            launchctl kickstart gui/$(id -u)/com.sinator.pool-proxy-${port} 2>/dev/null || true
        done
        echo "✅ Started"
        ;;

    stop)
        for port in $(seq 8897 -1 8888); do
            launchctl bootout gui/$(id -u)/com.sinator.pool-proxy-${port} 2>/dev/null || true
        done
        launchctl bootout gui/$(id -u)/com.sinator.pool-router 2>/dev/null || true
        launchctl bootout gui/$(id -u)/com.sinator.backend 2>/dev/null || true
        echo "✅ Stopped"
        ;;

    restart)
        $0 stop
        sleep 2
        $0 start
        ;;

    status)
        echo "=== SINator Services ==="
        for svc in backend pool-router; do
            if launchctl list | grep -q "com.sinator.${svc}"; then
                echo "  ✅ com.sinator.${svc}"
            else
                echo "  ❌ com.sinator.${svc}"
            fi
        done
        for port in $(seq 8888 8897); do
            if launchctl list | grep -q "com.sinator.pool-proxy-${port}"; then
                echo "  ✅ com.sinator.pool-proxy-${port}"
            else
                echo "  ❌ com.sinator.pool-proxy-${port}"
            fi
        done
        echo ""
        echo "=== Health ==="
        curl -s --max-time 2 http://localhost:8100/health 2>/dev/null \
            && echo "  :8100 ✅" || echo "  :8100 ❌"
        curl -s --max-time 2 http://localhost:9998/health 2>/dev/null \
            && echo "  :9998 ✅" || echo "  :9998 ❌"
        for port in $(seq 8888 8897); do
            curl -s --max-time 1 http://localhost:${port}/health >/dev/null 2>&1 \
                && echo "  :${port} ✅" || echo "  :${port} ❌"
        done
        ;;

    uninstall)
        echo "→ Uninstalling SINator LaunchAgents..."
        for port in $(seq 8897 -1 8888); do
            launchctl bootout gui/$(id -u)/com.sinator.pool-proxy-${port} 2>/dev/null || true
            rm -f ~/Library/LaunchAgents/com.sinator.pool-proxy-${port}.plist
        done
        for svc in pool-router backend; do
            launchctl bootout gui/$(id -u)/com.sinator.${svc} 2>/dev/null || true
            rm -f ~/Library/LaunchAgents/com.sinator.${svc}.plist
        done
        echo "✅ Uninstalled"
        ;;

    *)
        echo "Usage: $0 {install|start|stop|restart|status|uninstall}"
        ;;
esac
