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

        # 4. Pool Router (ThreadingMixIn :9998)
        mkdir -p "${HOME}/.sin-pool"
        cat > "$LA/com.sinator.pool-router.plist" << EOF
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

        # 5. Pool Proxys (10 Instanzen :8888-:8897)
        for port in $(seq 8888 8897); do
            cat > "$LA/com.sinator.pool-proxy-${port}.plist" << EOF
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
        <string>http://localhost:8000/api/v1</string>
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
        launchctl load "$LA/com.sinator.chrome.plist" 2>/dev/null || true
        launchctl load "$LA/com.sinator.cua-driver.plist" 2>/dev/null || true
        launchctl load "$LA/com.sinator.backend.plist" 2>/dev/null || true
        launchctl load "$LA/com.sinator.pool-router.plist" 2>/dev/null || true
        for port in $(seq 8888 8897); do
            launchctl load "$LA/com.sinator.pool-proxy-${port}.plist" 2>/dev/null || true
        done
        echo ""
        echo "✅ All SINator services installed and loaded!"
        echo "   They will auto-start on next login/boot."
        ;;

    start)
        echo "→ Starting all SINator services..."
        launchctl kickstart "gui/$(id -u)/com.sinator.chrome" 2>/dev/null || true
        launchctl kickstart "gui/$(id -u)/com.sinator.cua-driver" 2>/dev/null || true
        launchctl kickstart "gui/$(id -u)/com.sinator.backend" 2>/dev/null || true
        launchctl kickstart "gui/$(id -u)/com.sinator.pool-router" 2>/dev/null || true
        for port in $(seq 8888 8897); do
            launchctl kickstart "gui/$(id -u)/com.sinator.pool-proxy-${port}" 2>/dev/null || true
        done
        echo "✅ Started"
        ;;

    stop)
        echo "→ Stopping all SINator services..."
        for port in $(seq 8897 -1 8888); do
            launchctl bootout "gui/$(id -u)/com.sinator.pool-proxy-${port}" 2>/dev/null || true
        done
        launchctl bootout "gui/$(id -u)/com.sinator.pool-router" 2>/dev/null || true
        launchctl bootout "gui/$(id -u)/com.sinator.backend" 2>/dev/null || true
        launchctl bootout "gui/$(id -u)/com.sinator.cua-driver" 2>/dev/null || true
        launchctl bootout "gui/$(id -u)/com.sinator.chrome" 2>/dev/null || true
        echo "✅ Stopped"
        ;;

    status)
        echo "╔══════════════════════════════════════╗"
        echo "║       SINator Service Status         ║"
        echo "╠══════════════════════════════════════╣"
        for svc in chrome cua-driver backend pool-router; do
            if launchctl print "gui/$(id -u)/com.sinator.${svc}" 2>/dev/null | grep -q "state = running"; then
                echo "║  ✅ com.sinator.${svc}"
            else
                echo "║  ❌ com.sinator.${svc}"
            fi
        done
        for port in $(seq 8888 8897); do
            if launchctl print "gui/$(id -u)/com.sinator.pool-proxy-${port}" 2>/dev/null | grep -q "state = running"; then
                echo "║  ✅ com.sinator.pool-proxy-${port}"
            else
                echo "║  ❌ com.sinator.pool-proxy-${port}"
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

        if curl -s http://localhost:9998/health &>/dev/null; then
            echo "║  🌐 Router:      http://localhost:9998 ✅"
        else
            echo "║  🌐 Router:      not reachable ❌"
        fi

        for port in $(seq 8888 8897); do
            if curl -s --max-time 1 "http://localhost:${port}/health" &>/dev/null; then
                echo "║  🌐 Proxy :${port}  ✅"
            else
                echo "║  🌐 Proxy :${port}  ❌"
            fi
        done
        echo "╚══════════════════════════════════════╝"
        ;;

    uninstall)
        echo "→ Uninstalling all SINator LaunchAgents..."
        for port in $(seq 8897 -1 8888); do
            launchctl bootout "gui/$(id -u)/com.sinator.pool-proxy-${port}" 2>/dev/null || true
            rm -f "$LA/com.sinator.pool-proxy-${port}.plist"
        done
        for svc in pool-router backend cua-driver chrome; do
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
