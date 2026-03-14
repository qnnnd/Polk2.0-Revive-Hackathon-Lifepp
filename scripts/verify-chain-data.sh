#!/bin/bash
# Verify chain data after demo: backend must connect to Revive and read real contract state.
# Run from repo root. Requires backend .venv and Revive configured in backend/.env.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT/backend"

if [ ! -d ".venv" ]; then
  echo "Run dev-setup first or create backend .venv"
  exit 1
fi

source .venv/bin/activate

echo "Running chain verification tests (no fake data)..."
python -m pytest tests/test_chain_verification.py -v

echo "Chain data verification passed."
