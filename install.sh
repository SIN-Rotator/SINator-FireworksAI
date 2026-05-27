#!/usr/bin/env bash
set -euo pipefail

echo "=========================================="
echo " SIN-Hermes-Provider-Bundle (Complete)"
echo "=========================================="
echo ""
echo "Installing ALL 3 Fireworks Pool Proxies..."
echo ""

# Pool 1
echo "[1/3] Pool 1 (sinatorpool1.delqhi.com)..."
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-pool1.sh | bash
echo ""

# Pool 2
echo "[2/3] Pool 2 (sinatorpool2.delqhi.com)..."
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-pool2.sh | bash
echo ""

# Pool 3
echo "[3/3] Pool 3 (sinatorpool3.delqhi.com)..."
curl -fsSL https://raw.githubusercontent.com/SIN-Hermes-Bundles/SIN-Hermes-Provider-Bundle/main/install-pool3.sh | bash
echo ""

echo "=========================================="
echo " All 3 pools installed!"
echo "=========================================="
echo ""
echo "NOTE: Each pool overwrites ~/.hermes/config.yaml."
echo "      Use individual installers if you only need one pool."
echo ""
echo "Setup:"
echo "  hermes auth add custom:fireworks --type api-key --api-key \"\$FIREWORKS_AI_API_KEY\""
echo ""
echo "Done!"
