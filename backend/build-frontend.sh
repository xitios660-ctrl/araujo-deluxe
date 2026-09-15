#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python -m pip install -r backend/requirements-deploy.txt

cd frontend
npm install --legacy-peer-deps --no-audit --no-fund
REACT_APP_BACKEND_URL="" npm run build
