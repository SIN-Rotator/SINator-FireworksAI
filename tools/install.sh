#!/bin/bash
# SINator Install Script — one command to rule them all
# curl -fsSL https://sinator.pages.dev/install | bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${CYAN}══════════════════════════════════════${NC}"
echo -e "${CYAN}  SINator Fireworks AI — Installer   ${NC}"
echo -e "${CYAN}══════════════════════════════════════${NC}"
echo ""

SINATOR_DIR="${HOME}/sinator-fireworksai"

# 1. Clone repo
if [ ! -d "$SINATOR_DIR" ]; then
    echo -e "${GREEN}→${NC} Cloning SINator-FireworksAI..."
    git clone https://github.com/SIN-Rotator/SINator-FireworksAI "$SINATOR_DIR"
else
    echo -e "${GREEN}→${NC} SINator exists, updating..."
    cd "$SINATOR_DIR" && git pull
fi

cd "$SINATOR_DIR"

# 2. Python deps
echo -e "${GREEN}→${NC} Installing Python dependencies..."
pip3 install -q fastapi uvicorn httpx playwright 2>/dev/null
python3 -m playwright install chromium 2>/dev/null || true

# 3. Set password
if [ -z "$SINATOR_PASSWORD" ]; then
    SINATOR_PASSWORD=$(openssl rand -hex 12)
    echo -e "${YELLOW}→${NC} Generated password: ${SINATOR_PASSWORD}"
fi

# 4. Create .env
if [ ! -f ".env" ]; then
    cat > .env << EOF
SINATOR_PASSWORD=${SINATOR_PASSWORD}
GMX_EMAIL=
GMX_PASSWORD=
FIREWORKS_PASSWORD=ZOE.jerry2024
CDP_PORT=9222
EOF
fi

# 5. Start backend
echo -e "${GREEN}→${NC} Starting backend on port 8000..."
SINATOR_PASSWORD="${SINATOR_PASSWORD}" nohup python3 agent_toolbox/start_toolbox.py > /tmp/sinator-backend.log 2>&1 &
sleep 4

# 6. Start watchdog
echo -e "${GREEN}→${NC} Starting key watchdog..."
nohup python3 tools/key_watchdog.py --interval 120 > /tmp/sinator-watchdog.log 2>&1 &

echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ SINator ist bereit!              ${NC}"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo ""
echo -e "  Dashboard: ${CYAN}http://localhost:8000/dashboard${NC}"
echo -e "  Login:     ${CYAN}SINATOR_PASSWORD = ${SINATOR_PASSWORD}${NC}"
echo -e "  API Docs:  ${CYAN}http://localhost:8000/docs${NC}"
echo ""
echo -e "  ${YELLOW}Wichtige Schritte nach dem Login:${NC}"
echo -e "  1. Dashboard öffnen → Setup → GMX Credentials eintragen"
echo -e "  2. Chrome starten (siehe AGENTS.md)"
echo -e "  3. 'API Key holen' klicken für ersten Key"
echo ""

# 7. Optional: Cloudflare tunnel
if command -v cloudflared &>/dev/null; then
    echo -e "${GREEN}→${NC} Cloudflare Tunnel starten? (y/N)"
    read -t 5 -r START_TUNNEL || START_TUNNEL="n"
    if [ "$START_TUNNEL" = "y" ] || [ "$START_TUNNEL" = "Y" ]; then
        echo -e "${GREEN}→${NC} Starting Cloudflare Tunnel..."
        nohup cloudflared tunnel --url http://localhost:8000 > /tmp/sinator-tunnel.log 2>&1 &
        sleep 5
        TUNNEL_URL=$(grep -o 'https://.*trycloudflare.com' /tmp/sinator-tunnel.log | head -1)
        if [ -n "$TUNNEL_URL" ]; then
            echo -e "  Public URL: ${CYAN}${TUNNEL_URL}${NC}"
            echo -e "  Dashboard:  ${CYAN}${TUNNEL_URL}/dashboard${NC}"
        fi
    fi
fi

echo ""
echo -e "${CYAN}══════════════════════════════════════${NC}"
