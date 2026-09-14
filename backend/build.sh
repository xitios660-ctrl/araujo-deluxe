#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pip install -r backend/requirements-deploy.txt
node -e 'if (Number(process.versions.node.split(".")[0]) < 20) throw new Error("Baileys requer Node.js 20 ou superior")'
npm --prefix whatsapp-bot ci --omit=dev --no-audit --no-fund
node --input-type=module -e 'await import("./whatsapp-bot/node_modules/baileys/lib/index.js")'
