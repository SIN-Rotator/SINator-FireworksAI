#!/usr/bin/env bash
# One-Liner OpenCode CLI Fireworks Config Installer
# Mit Reasoning-Configs (thinking: enabled, budgetTokens)
# 
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/opencode-config-install.sh | bash
#   curl -fsSL ... | bash -s -- --api-key fw_xxx
#   curl -fsSL ... | bash -s -- --dry-run

set -euo pipefail

OPENCODE_DIR="${HOME}/.config/opencode"
CONFIG_FILE="${OPENCODE_DIR}/opencode.json"
BACKUP_DIR="${OPENCODE_DIR}/backups"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'

log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

API_KEY=""
DRY_RUN=false

# Parse args
while [ $# -gt 0 ]; do
    case "$1" in
        --api-key) API_KEY="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) shift ;;
    esac
done

echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  OpenCode CLI — Fireworks AI Config + Reasoning Installer${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

# API Key abfragen wenn nicht via Argument
if [ -z "$API_KEY" ]; then
    if [ -n "${FIREWORKS_AI_API_KEY:-}" ]; then
        API_KEY="$FIREWORKS_AI_API_KEY"
        log_info "Using FIREWORKS_AI_API_KEY from environment"
    else
        echo -n "Enter your Fireworks API Key (fw_... or press Enter for placeholder): "
        read -r API_KEY
        if [ -z "$API_KEY" ]; then
            API_KEY="<DEIN_API_KEY>"
            log_warn "No API key provided — using placeholder"
        fi
    fi
fi

mkdir -p "$OPENCODE_DIR"

# Backup erstellen
if [ -f "$CONFIG_FILE" ]; then
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="${BACKUP_DIR}/opencode-$(date +%Y%m%d-%H%M%S).json"
    if [ "$DRY_RUN" = false ]; then
        cp "$CONFIG_FILE" "$BACKUP_FILE"
    fi
    log_info "Backup created: ${BACKUP_FILE}"
fi

# Fireworks Provider Config mit Reasoning
if [ "$DRY_RUN" = false ]; then
    INSTALLER_API_KEY="${API_KEY}" python3 << 'PYEOF'
import json, os

config_path = os.path.expanduser("~/.config/opencode/opencode.json")

# Neues oder bestehendes Config laden
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        cfg = json.load(f)
else:
    cfg = {
        "$schema": "https://opencode.ai/config.json",
        "permission": "allow",
        "skills": {"paths": [os.path.expanduser("~/.config/opencode/skills")]},
        "command": {},
        "mcp": {}
    }

# Fireworks Provider mit Reasoning-Configs
fireworks_provider = {
    "npm": "@ai-sdk/fireworks",
    "name": "Fireworks AI",
    "models": {
        "deepseek-v4-pro": {
            "id": "fireworks/deepseek-v4-pro",
            "name": "DeepSeek V4 Pro (SIN)",
            "options": {
                "thinking": {"type": "enabled", "budgetTokens": 64000}
            },
            "variants": {
                "off": {"thinking": {"type": "disabled"}},
                "low": {"thinking": {"type": "enabled", "budgetTokens": 4000}},
                "medium": {"thinking": {"type": "enabled", "budgetTokens": 16000}},
                "high": {"thinking": {"type": "enabled", "budgetTokens": 64000}},
                "max": {"thinking": {"type": "enabled", "budgetTokens": 128000}}
            },
            "limit": {"context": 1048576, "output": 65536}
        },
        "glm-5p1": {
            "id": "fireworks/glm-5p1",
            "name": "GLM 5.1 (SIN)",
            "options": {
                "thinking": {"type": "enabled", "budgetTokens": 32000}
            },
            "variants": {
                "off": {"thinking": {"type": "disabled"}},
                "low": {"thinking": {"type": "enabled", "budgetTokens": 4000}},
                "medium": {"thinking": {"type": "enabled", "budgetTokens": 16000}},
                "high": {"thinking": {"type": "enabled", "budgetTokens": 32000}},
                "max": {"thinking": {"type": "enabled", "budgetTokens": 64000}}
            },
            "limit": {"context": 202752, "output": 32768}
        },
        "kimi-k2p6": {
            "id": "fireworks/kimi-k2p6",
            "name": "Kimi K2.6 (SIN)",
            "options": {
                "thinking": {"type": "enabled", "budgetTokens": 32000}
            },
            "variants": {
                "off": {"thinking": {"type": "disabled"}},
                "low": {"thinking": {"type": "enabled", "budgetTokens": 4000}},
                "medium": {"thinking": {"type": "enabled", "budgetTokens": 16000}},
                "high": {"thinking": {"type": "enabled", "budgetTokens": 32000}},
                "max": {"thinking": {"type": "enabled", "budgetTokens": 64000}}
            },
            "limit": {"context": 262144, "output": 32768},
            "modalities": {"input": ["text", "image"], "output": ["text"]}
        },
        "qwen3p6-plus": {
            "id": "accounts/fireworks/models/qwen3p6-plus",
            "name": "Qwen3.6 Plus (SIN)",
            "options": {
                "thinking": {"type": "enabled", "budgetTokens": 32000}
            },
            "variants": {
                "off": {"thinking": {"type": "disabled"}},
                "low": {"thinking": {"type": "enabled", "budgetTokens": 4000}},
                "medium": {"thinking": {"type": "enabled", "budgetTokens": 16000}},
                "high": {"thinking": {"type": "enabled", "budgetTokens": 32000}},
                "max": {"thinking": {"type": "enabled", "budgetTokens": 64000}}
            },
            "limit": {"context": 131072, "output": 32768},
            "modalities": {"input": ["text", "image"], "output": ["text"]}
        },
        "minimax-m2p7": {
            "id": "fireworks/minimax-m2p7",
            "name": "MiniMax M2.7 (SIN)",
            "options": {
                "thinking": {"type": "enabled", "budgetTokens": 32000}
            },
            "variants": {
                "off": {"thinking": {"type": "disabled"}},
                "low": {"thinking": {"type": "enabled", "budgetTokens": 4000}},
                "medium": {"thinking": {"type": "enabled", "budgetTokens": 16000}},
                "high": {"thinking": {"type": "enabled", "budgetTokens": 32000}},
                "max": {"thinking": {"type": "enabled", "budgetTokens": 64000}}
            },
            "limit": {"context": 196608, "output": 32768}
        }
    },
    "options": {
        "baseURL": "https://sinatorpool-router.delqhi.com/inference/v1",
        "apiKey": os.environ.get('INSTALLER_API_KEY', '<DEIN_API_KEY>')
    }
}

# Provider setzen
providers = cfg.setdefault("provider", {})
providers["fireworks-ai"] = fireworks_provider

# Default model setzen (wenn nicht vorhanden)
if "defaultModel" not in cfg:
    cfg["defaultModel"] = "fireworks-ai/deepseek-v4-pro"

# Default agent setzen (wenn nicht vorhanden)
if "defaultAgent" not in cfg:
    cfg["defaultAgent"] = "SIN-Zeus"

with open(config_path, 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')

print(f"Fireworks provider configured with {len(fireworks_provider['models'])} models")
print(f"Base URL: {fireworks_provider['options']['baseURL']}")
print(f"Reasoning: enabled (off/low/medium/high/max variants)")
PYEOF

    log_ok "opencode.json updated with Fireworks AI + Reasoning"
else
    log_info "DRY RUN — Would create/update opencode.json"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ OpenCode Fireworks Config Complete!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Models:     ${CYAN}5 reasoning models (off/low/medium/high/max)${NC}"
echo -e "  Base URL:   ${CYAN}https://sinatorpool-router.delqhi.com/inference/v1${NC}"
echo -e "  Config:     ${CYAN}${CONFIG_FILE}${NC}"
if [ -f "$BACKUP_FILE" ]; then
    echo -e "  Backup:     ${CYAN}${BACKUP_FILE}${NC}"
fi
echo ""
echo -e "  ${YELLOW}Usage:${NC}"
echo -e "    ${CYAN}opencode chat --provider fireworks-ai --model deepseek-v4-pro${NC}"
echo -e "    ${CYAN}opencode chat --provider fireworks-ai --model deepseek-v4-pro --variant high${NC}"
echo ""
echo -e "  ${YELLOW}Test:${NC}"
echo -e "    ${CYAN}curl -s https://sinatorpool-router.delqhi.com/inference/v1/models | head -5${NC}"
echo ""
