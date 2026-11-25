#!/usr/bin/env bash
set -euo pipefail

# Run on the Nobus server from /opt/vio (or wherever the repo is cloned).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

git pull --ff-only

.venv/bin/pip install -e ./backend

npm --prefix frontend/frontend install --no-audit --no-fund
npm --prefix frontend/frontend run build

sudo systemctl restart vio-api
sudo systemctl reload nginx
