#!/usr/bin/env bash
set -euo pipefail
REPO="https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

echo "Installing SIN-Hermes-Provider-Bundle (Pool 3)..."

# 1. Provider Config
curl -fsSL "$REPO/config/fireworks-pool3.yaml" -o "$HERMES_HOME/config.yaml"

# 2. 412 Patch
if [ -f "$HERMES_HOME/hermes-agent/agent/error_classifier.py" ]; then
  echo "Applying 412 retry patch..."
  curl -fsSL "$REPO/patches/error_classifier_412.patch" -o /tmp/error_classifier_412.patch
  cd "$HERMES_HOME/hermes-agent"
  git apply /tmp/error_classifier_412.patch 2>/dev/null || echo "Patch may already be applied"
fi

# 3. UA-Spoof Patch (all LLM calls via sinator proxy need real browser UA)
echo "Applying User-Agent spoof patch..."
curl -fsSL "$REPO/_ua_patch.py" -o "$HERMES_HOME/hermes-agent/_ua_patch.py"
if ! grep -q "import _ua_patch" "$HERMES_HOME/hermes-agent/run_agent.py" 2>/dev/null; then
  sed -i '' 's/^import os$/import os\nimport _ua_patch  # noqa/' "$HERMES_HOME/hermes-agent/run_agent.py" 2>/dev/null || true
  echo "UA-Spoof patch applied to run_agent.py"
fi

# 4. Set unlimited max_turns
if ! grep -q "max_turns" "$HERMES_HOME/config.yaml"; then
  printf '\nagent:\n  max_turns: 999999\n  max_iterations: 999999\n' >> "$HERMES_HOME/config.yaml"
  echo "Set max_turns=999999 (unlimited)"
fi

echo ""
echo "Pool 3 configured: sinatorpool3.delqhi.com"
echo ""
echo "Setup:"
echo "  hermes auth add custom:fireworks --type api-key --api-key \"\$FIREWORKS_AI_API_KEY\""
echo ""
echo "Done!"
