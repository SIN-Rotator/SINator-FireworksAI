#!/bin/bash
# Cloudflare Tunnel Wrapper — Named Tunnel sinator.delqhi.com → localhost:8000
set -e

TUNNEL_LOG="/tmp/sinator-tunnel.log"
URL_FILE="$HOME/.sin-pool/tunnel-url.txt"
CLOUDFLARED="/opt/homebrew/bin/cloudflared"
CONFIG="$HOME/.cloudflared/config-sinator.yml"

echo "Starting Cloudflare Named Tunnel sinator → sinator.delqhi.com → localhost:8000" | tee "$TUNNEL_LOG"
mkdir -p "$HOME/.sin-pool"
echo "https://sinator.delqhi.com" > "$URL_FILE"

exec $CLOUDFLARED tunnel --config "$CONFIG" run sinator 2>&1 | tee -a "$TUNNEL_LOG"
