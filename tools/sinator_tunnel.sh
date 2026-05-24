#!/bin/bash
# Cloudflare Tunnel Wrapper — startet Tunnel und speichert URL
set -e

TUNNEL_LOG="/tmp/sinator-tunnel.log"
URL_FILE="$HOME/.sin-pool/tunnel-url.txt"
PORT="${1:-8000}"
CLOUDFLARED="/opt/homebrew/bin/cloudflared"

echo "Starting Cloudflare Tunnel → localhost:${PORT}" | tee "$TUNNEL_LOG"

mkdir -p "$HOME/.sin-pool"
$CLOUDFLARED tunnel --url "http://localhost:${PORT}" 2>&1 | tee -a "$TUNNEL_LOG" | while IFS= read -r line; do
    url=$(echo "$line" | grep -o 'https://[^ ]*trycloudflare.com' || true)
    if [ -n "$url" ]; then
        echo "Tunnel ready: $url" | tee -a "$TUNNEL_LOG"
        echo "$url" > "$URL_FILE"
    fi
done
