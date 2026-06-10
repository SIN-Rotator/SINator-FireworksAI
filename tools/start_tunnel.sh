#!/bin/bash
# SINator Cloudflare Tunnel — start or install as launchd service
# Usage:
#   ./start_tunnel.sh              # start tunnel once
#   ./start_tunnel.sh --install    # install as persistent launchd service
#   ./start_tunnel.sh --stop       # stop tunnel
#   ./start_tunnel.sh --status     # show tunnel URL

TUNNEL_LOG="/tmp/sinator-tunnel.log"
BACKEND_PORT=8100
SERVICE_NAME="com.sinator.tunnel"

start_tunnel() {
    echo "→ Starting Cloudflare Tunnel (port ${BACKEND_PORT})..."
    nohup cloudflared tunnel --url "http://localhost:${BACKEND_PORT}" \
        > "${TUNNEL_LOG}" 2>&1 &
    sleep 5
    TUNNEL_URL=$(grep -o 'https://.*trycloudflare.com' "${TUNNEL_LOG}" | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        echo "✅ Public URL: ${TUNNEL_URL}"
        echo "   Dashboard:  ${TUNNEL_URL}/dashboard"
    else
        echo "⚠️  Tunnel URL not found yet. Check: tail -20 ${TUNNEL_LOG}"
    fi
}

stop_tunnel() {
    echo "→ Stopping Cloudflare Tunnel..."
    pkill -f "cloudflared tunnel" 2>/dev/null || true
    rm -f "${TUNNEL_LOG}"
    echo "✅ Tunnel stopped"
}

show_status() {
    if pgrep -f "cloudflared tunnel" &>/dev/null; then
        TUNNEL_URL=$(grep -o 'https://.*trycloudflare.com' "${TUNNEL_LOG}" 2>/dev/null | head -1)
        echo "✅ Tunnel is running"
        [ -n "$TUNNEL_URL" ] && echo "   URL: ${TUNNEL_URL}"
    else
        echo "❌ Tunnel is not running"
    fi
}

install_service() {
    # Create launchd plist
    PLIST="${HOME}/Library/LaunchAgents/${SERVICE_NAME}.plist"
    mkdir -p "${HOME}/Library/LaunchAgents"

    cat > "${PLIST}" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which cloudflared)</string>
        <string>tunnel</string>
        <string>--url</string>
        <string>http://localhost:${BACKEND_PORT}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${TUNNEL_LOG}</string>
    <key>StandardErrorPath</key>
    <string>${TUNNEL_LOG}</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

    launchctl load "${PLIST}"
    sleep 5
    echo "✅ Cloudflare Tunnel installed as launchd service (${SERVICE_NAME})"
    show_status
}

case "${1:-}" in
    --install)
        install_service
        ;;
    --stop)
        stop_tunnel
        launchctl unload "${HOME}/Library/LaunchAgents/${SERVICE_NAME}.plist" 2>/dev/null || true
        ;;
    --status)
        show_status
        ;;
    *)
        start_tunnel
        ;;
esac
