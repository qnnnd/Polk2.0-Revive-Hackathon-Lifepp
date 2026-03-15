#!/bin/bash
# Write Revive local (127.0.0.1:8545) and contract addresses from contracts/deployments.json
# into backend/.env. Uses native IVE for rewards (no COG token).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTRACTS_JSON="$REPO_ROOT/contracts/deployments.json"
BACKEND_ENV="$REPO_ROOT/backend/.env"

if [ ! -f "$CONTRACTS_JSON" ]; then
  echo "Run contracts deploy first: cd contracts && pnpm run deploy:revive-local"
  exit 1
fi

if command -v jq &>/dev/null; then
  REGISTRY=$(jq -r '.AgentRegistry' "$CONTRACTS_JSON")
  TASK_MARKET=$(jq -r '.TaskMarket' "$CONTRACTS_JSON")
  REPUTATION=$(jq -r '.Reputation' "$CONTRACTS_JSON")
elif command -v python3 &>/dev/null; then
  read -r REGISTRY TASK_MARKET REPUTATION <<< $(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
print(d.get('AgentRegistry',''), d.get('TaskMarket',''), d.get('Reputation',''))
" "$CONTRACTS_JSON")
else
  echo "Need jq or python3 to read deployments.json"
  exit 1
fi

if [ "$REGISTRY" = "null" ] || [ -z "$REGISTRY" ] || [ "$TASK_MARKET" = "null" ] || [ -z "$TASK_MARKET" ]; then
  echo "Invalid deployments.json (missing AgentRegistry or TaskMarket)"
  exit 1
fi

if [ ! -f "$BACKEND_ENV" ]; then
  cp "$REPO_ROOT/backend/.env.example" "$BACKEND_ENV"
fi

set_env_var() {
  local key="$1"
  local val="$2"
  if grep -q "^${key}=" "$BACKEND_ENV" 2>/dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i '' "s|^${key}=.*|${key}=${val}|" "$BACKEND_ENV"
    else
      sed -i "s|^${key}=.*|${key}=${val}|" "$BACKEND_ENV"
    fi
  else
    echo "${key}=${val}" >> "$BACKEND_ENV"
  fi
}

set_env_var "REVIVE_RPC_URL" "http://127.0.0.1:8545"
set_env_var "AGENT_REGISTRY_ADDRESS" "$REGISTRY"
set_env_var "TASK_MARKET_ADDRESS" "$TASK_MARKET"
set_env_var "REPUTATION_ADDRESS" "$REPUTATION"

if [ -n "$DEPLOYER_PRIVATE_KEY" ]; then
  set_env_var "REVIVE_DEPLOYER_PRIVATE_KEY" "$DEPLOYER_PRIVATE_KEY"
  echo "REVIVE_DEPLOYER_PRIVATE_KEY set from DEPLOYER_PRIVATE_KEY"
else
  echo "Optional: set REVIVE_DEPLOYER_PRIVATE_KEY in backend/.env (same as deploy key for agent register + marketplace)"
fi

echo "Backend .env updated for local Revive (http://127.0.0.1:8545), native IVE rewards."