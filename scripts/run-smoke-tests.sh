#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate
PYTHONPATH=backend pytest -q backend/tests
