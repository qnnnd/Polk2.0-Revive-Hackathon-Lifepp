#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

echo "[OK] environment ready"
echo "Run: source .venv/bin/activate && python backend/main.py"
