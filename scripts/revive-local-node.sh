#!/bin/bash
# Start local Revive dev node + eth-rpc (Ethereum RPC at 8545).
# Set REVIVE_DEV_NODE_BIN and ETH_RPC_BIN to your built binaries, or they default to env.
# Requires: both binaries built from polkadot-sdk (see docs/revive-local-setup.md).

set -e

REVIVE_BIN="${REVIVE_DEV_NODE_BIN:-}"
ETH_RPC_BIN="${ETH_RPC_BIN:-}"

if [ -z "$REVIVE_BIN" ] || [ -z "$ETH_RPC_BIN" ]; then
  echo "Set REVIVE_DEV_NODE_BIN and ETH_RPC_BIN to your polkadot-sdk build, e.g.:"
  echo "  export REVIVE_DEV_NODE_BIN=/path/to/polkadot-sdk/target/release/revive-dev-node"
  echo "  export ETH_RPC_BIN=/path/to/polkadot-sdk/target/release/eth-rpc"
  echo "See docs/revive-local-setup.md for building."
  exit 1
fi

if [ ! -x "$REVIVE_BIN" ]; then
  echo "Not found or not executable: $REVIVE_BIN"
  exit 1
fi
if [ ! -x "$ETH_RPC_BIN" ]; then
  echo "Not found or not executable: $ETH_RPC_BIN"
  exit 1
fi

echo "Starting Revive dev node in background..."
"$REVIVE_BIN" --dev &
REVIVE_PID=$!
echo "Revive dev node PID: $REVIVE_PID"

echo "Waiting for node (9944)..."
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9944 2>/dev/null | grep -q .; then
    break
  fi
  sleep 1
done
sleep 2

echo "Starting eth-rpc in background..."
"$ETH_RPC_BIN" --dev &
ETH_PID=$!
echo "eth-rpc PID: $ETH_PID"

echo "Waiting for eth-rpc (8545)..."
for i in $(seq 1 20); do
  if curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' http://127.0.0.1:8545 2>/dev/null | grep -q jsonrpc; then
    echo "Local Revive ready at http://127.0.0.1:8545"
    echo "To stop: kill $REVIVE_PID $ETH_PID"
    exit 0
  fi
  sleep 1
done

echo "eth-rpc did not become ready in time. Killing processes."
kill $REVIVE_PID $ETH_PID 2>/dev/null || true
exit 1
