#!/usr/bin/env bash
set -euo pipefail
REPO="https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

echo "Installing SIN-Hermes-Provider-Bundle..."
echo ""
echo "This bundle installs:"
echo "  - Pool Router (localhost:9998) with auto-failover across sinatorpool1/2/3"
echo "  - Fireworks Config pointing to local router"
echo "  - 412 PRECONDITION_FAILED retry patch"
echo "  - User-Agent spoof patch"
echo "  - Unlimited max_turns"
echo ""

# 1. Router Config (localhost:9998)
curl -fsSL "$REPO/config/fireworks-router.yaml" -o "$HERMES_HOME/config.yaml"

# 2. Download and start pool-router
mkdir -p "$HERMES_HOME/scripts" "$HERMES_HOME/logs"
curl -fsSL "$REPO/scripts/pool-router.py" -o "$HERMES_HOME/scripts/pool-router.py"
chmod +x "$HERMES_HOME/scripts/pool-router.py"

if pgrep -f "pool-router.py" > /dev/null 2>&1; then
  echo "Pool-router already running."
else
  echo "Starting pool-router on localhost:9998..."
  nohup python3 "$HERMES_HOME/scripts/pool-router.py" > "$HERMES_HOME/logs/pool-router.log" 2>&1 &
  sleep 1
  if pgrep -f "pool-router.py" > /dev/null 2>&1; then
    echo "Pool-router started."
  else
    echo "WARNING: Pool-router failed to start. Check $HERMES_HOME/logs/pool-router.log"
  fi
fi

# 3. 412 Patch
if [ -f "$HERMES_HOME/hermes-agent/agent/error_classifier.py" ]; then
  echo "Applying 412 retry patch..."
  curl -fsSL "$REPO/patches/error_classifier_412.patch" -o /tmp/error_classifier_412.patch
  cd "$HERMES_HOME/hermes-agent"
  git apply /tmp/error_classifier_412.patch 2>/dev/null || echo "Patch may already be applied"
fi

# 4. UA-Spoof Patch
echo "Applying User-Agent spoof patch..."
curl -fsSL "$REPO/_ua_patch.py" -o "$HERMES_HOME/hermes-agent/_ua_patch.py"
if ! grep -q "import _ua_patch" "$HERMES_HOME/hermes-agent/run_agent.py" 2>/dev/null; then
  sed -i '' 's/^import os$/import os\nimport _ua_patch  # noqa/' "$HERMES_HOME/hermes-agent/run_agent.py" 2>/dev/null || true
  echo "UA-Spoof patch applied."
fi

# 5. Set unlimited max_turns
if ! grep -q "max_turns" "$HERMES_HOME/config.yaml"; then
  printf '\nagent:\n  max_turns: 999999\n  max_iterations: 999999\n' >> "$HERMES_HOME/config.yaml"
  echo "Set max_turns=999999 (unlimited)"
fi

echo ""
echo "=========================================="
echo " SIN-Hermes-Provider-Bundle installed!"
echo "=========================================="
echo ""
echo "Pool Router: localhost:9998 -> sinatorpool1/2/3 (auto-failover)"
echo ""
echo "Next step:"
echo "  hermes auth add custom:fireworks --type api-key --api-key \"\$FIREWORKS_AI_API_KEY\""
echo ""
echo "Docs: https://github.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/blob/main/docs/"
echo ""
echo "Done!"
