#!/usr/bin/env bash
# OpenCode Config Repair — Fixes broken opencode.json after failed installer
# Usage: curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/opencode-config-repair.sh | bash

set -euo pipefail

OPENCODE_DIR="${HOME}/.config/opencode"
CONFIG_FILE="${OPENCODE_DIR}/opencode.json"
BACKUP_DIR="${OPENCODE_DIR}/backups"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'

log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

API_KEY="${1:-${FIREWORKS_AI_API_KEY:-<DEIN_API_KEY>}}"

echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  OpenCode Config Repair — Emergency Fix${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
echo ""

# Backup
mkdir -p "$BACKUP_DIR"
if [ -f "$CONFIG_FILE" ]; then
    BACKUP_FILE="${BACKUP_DIR}/opencode-broken-$(date +%Y%m%d-%H%M%S).json"
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    log_info "Broken config backed up: ${BACKUP_FILE}"
fi

# Check if current config is valid JSON
if [ -f "$CONFIG_FILE" ]; then
    if python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
        log_ok "Existing config is valid JSON — will preserve settings"
        REPAIR_MODE="merge"
    else
        log_warn "Existing config is BROKEN JSON — will recreate"
        REPAIR_MODE="replace"
    fi
else
    log_info "No config found — creating new"
    REPAIR_MODE="replace"
fi

# Repair
if [ "$REPAIR_MODE" = "merge" ]; then
    log_info "Merging Fireworks provider into existing config..."
    python3 << 'PYEOF'
import json, os

config_path = os.path.expanduser("~/.config/opencode/opencode.json")
api_key = os.environ.get('REPAIR_API_KEY', '<DEIN_API_KEY>')

with open(config_path, 'r') as f:
    cfg = json.load(f)

# Ensure critical structure exists
if "$schema" not in cfg:
    cfg["$schema"] = "https://opencode.ai/config.json"

if "permission" not in cfg:
    cfg["permission"] = "allow"

if "skills" not in cfg:
    cfg["skills"] = {"paths": [os.path.expanduser("~/.config/opencode/skills")]}

if "command" not in cfg:
    cfg["command"] = {}

if "mcp" not in cfg:
    cfg["mcp"] = {}

# Fireworks Provider with Reasoning
fireworks = {
    "npm": "@ai-sdk/fireworks",
    "name": "Fireworks AI",
    "models": {
        "deepseek-v4-pro": {
            "id": "fireworks/deepseek-v4-pro",
            "name": "DeepSeek V4 Pro (SIN)",
            "options": {"thinking": {"type": "enabled", "budgetTokens": 64000}},
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
            "options": {"thinking": {"type": "enabled", "budgetTokens": 32000}},
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
            "options": {"thinking": {"type": "enabled", "budgetTokens": 32000}},
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
            "options": {"thinking": {"type": "enabled", "budgetTokens": 32000}},
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
            "options": {"thinking": {"type": "enabled", "budgetTokens": 32000}},
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
        "apiKey": api_key
    }
}

cfg.setdefault("provider", {})["fireworks-ai"] = fireworks

# Default agent
if "agent" not in cfg:
    cfg["agent"] = {
        "SIN-Zeus": {"model": "fireworks-ai/deepseek-v4-pro"}
    }

if "defaultAgent" not in cfg:
    cfg["defaultAgent"] = "SIN-Zeus"

if "defaultModel" not in cfg:
    cfg["defaultModel"] = "fireworks-ai/deepseek-v4-pro"

with open(config_path, 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')

print("✅ Config repaired and merged")
PYEOF
else
    log_info "Creating fresh config..."
    python3 << 'PYEOF'
import json, os

config_path = os.path.expanduser("~/.config/opencode/opencode.json")
api_key = os.environ.get('REPAIR_API_KEY', '<DEIN_API_KEY>')

cfg = {
    "$schema": "https://opencode.ai/config.json",
    "permission": "allow",
    "skills": {
        "paths": [os.path.expanduser("~/.config/opencode/skills")]
    },
    "command": {},
    "mcp": {},
    "provider": {
        "fireworks-ai": {
            "npm": "@ai-sdk/fireworks",
            "name": "Fireworks AI",
            "models": {
                "deepseek-v4-pro": {
                    "id": "fireworks/deepseek-v4-pro",
                    "name": "DeepSeek V4 Pro (SIN)",
                    "options": {"thinking": {"type": "enabled", "budgetTokens": 64000}},
                    "variants": {
                        "off": {"thinking": {"type": "disabled"}},
                        "low": {"thinking": {"type": "enabled", "budgetTokens": 4000}},
                        "medium": {"thinking": {"type": "enabled", "budgetTokens": 16000}},
                        "high": {"thinking": {"type": "enabled", "budgetTokens": 64000}},
                        "max": {"thinking": {"type": "enabled", "budgetTokens": 128000}}
                    },
                    "limit": {"context": 1048576, "output": 65536}
                }
            },
            "options": {
                "baseURL": "https://sinatorpool-router.delqhi.com/inference/v1",
                "apiKey": api_key
            }
        }
    },
    "agent": {
        "SIN-Zeus": {"model": "fireworks-ai/deepseek-v4-pro"}
    },
    "defaultModel": "fireworks-ai/deepseek-v4-pro",
    "defaultAgent": "SIN-Zeus"
}

with open(config_path, 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')

print("✅ Fresh config created")
PYEOF
fi

log_ok "Config repaired!"

# Verify
if python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
    log_ok "JSON is valid"
    
    # Check if provider exists
    HAS_PROVIDER=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); print('yes' if 'fireworks-ai' in d.get('provider', {}) else 'no')")
    if [ "$HAS_PROVIDER" = "yes" ]; then
        log_ok "Fireworks provider present"
    else
        log_warn "Fireworks provider missing"
    fi
    
    # Check if reasoning exists
    HAS_REASONING=$(python3 -c "import json; d=json.load(open('$CONFIG_FILE')); p=d.get('provider',{}).get('fireworks-ai',{}); print('yes' if 'thinking' in str(p) else 'no')")
    if [ "$HAS_REASONING" = "yes" ]; then
        log_ok "Reasoning configs present"
    else
        log_warn "Reasoning configs missing"
    fi
else
    log_error "Config is still broken!"
    exit 1
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ OpenCode Config Repaired!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Test: ${CYAN}opencode --version${NC}"
echo -e "  Chat: ${CYAN}opencode chat --provider fireworks-ai --model deepseek-v4-pro${NC}"
echo ""
