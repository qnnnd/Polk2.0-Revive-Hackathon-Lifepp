# Local Revive Node Setup

This guide gets you to **run a Revive node locally**, deploy Life++ contracts to it, and run the app + verification with **no fake data** (all chain data from local Revive).

Reference: [Polkadot — Local Development Node](https://docs.polkadot.com/smart-contracts/dev-environments/local-dev-node/).

## 1. Prerequisites

- Rust and [Polkadot SDK dependencies](https://docs.polkadot.com/parachains/install-polkadot-sdk/) installed
- Node.js 18+ and pnpm (for contracts)
- Docker (for Postgres/Redis/backend/frontend)

## 2. Build Revive Dev Node and ETH-RPC

Clone and build (first build can take ~30 minutes):

```bash
git clone https://github.com/paritytech/polkadot-sdk.git
cd polkadot-sdk

cargo build -p revive-dev-node --bin revive-dev-node --release
cargo build -p pallet-revive-eth-rpc --bin eth-rpc --release
```

Binaries:

- Node: `target/release/revive-dev-node`
- ETH-RPC (Ethereum JSON-RPC at 8545): `target/release/eth-rpc`

## 3. Run Local Revive (two terminals)

**Terminal 1 — Revive dev node (Substrate, ws://127.0.0.1:9944):**

```bash
/path/to/polkadot-sdk/target/release/revive-dev-node --dev
```

**Terminal 2 — ETH-RPC adapter (Ethereum API at http://127.0.0.1:8545):**

```bash
/path/to/polkadot-sdk/target/release/eth-rpc --dev
```

Or use the project script (after setting binary paths):

```bash
export REVIVE_DEV_NODE_BIN="/path/to/polkadot-sdk/target/release/revive-dev-node"
export ETH_RPC_BIN="/path/to/polkadot-sdk/target/release/eth-rpc"
./scripts/revive-local-node.sh
```

Leave both running. The dev node uses **pre-funded development accounts**; you need a private key that has balance on this chain for deploying contracts and for the backend (see step 5).

## 4. Deploy Contracts to Local Revive

In the Life++ repo:

```bash
cd contracts
pnpm install
```

Set a deployer key that has balance on your **local** Revive dev chain.

**Option A — Claim tokens into your deployer (recommended):** If your Revive dev node pre-funds the Alith account (many Substrate EVM dev chains do), run the claim script so that your deployer receives native token:

```bash
pnpm run claim:revive-local   # or: npm run claim:revive-local
```

This sends token from the well-known dev account "Alith" to the address derived from `DEPLOYER_PRIVATE_KEY` in `contracts/.env`. Then deploy:

```bash
pnpm run deploy:revive-local
```

**Option B — Use Alith as deployer:** If the chain funds Alith but you prefer not to use the Hardhat test key, set in `contracts/.env`:

```
DEPLOYER_PRIVATE_KEY=0x5fb92d6e98884f76de468fa3f6278f8807c48bebc13595d45af5bdc4da702133
```

Then run `pnpm run deploy:revive-local` (no claim step).

**If deploy still fails with "Balance: 0" or "Invalid Transaction"**: the Revive dev node has not funded that EVM account. You can: (1) Use a chain spec that endows and maps an EVM account (see [Polkadot SDK genesis config](https://github.com/paritytech/polkadot-sdk/pull/8103)); or (2) Fund an account via the node, then set that key in `contracts/.env` as `DEPLOYER_PRIVATE_KEY`.

This writes `contracts/deployments.json` with AgentRegistry, TaskMarket, Reputation addresses (rewards use native IVE).

## 5. Apply Addresses to Backend (local Revive)

From repo root:

```bash
./scripts/apply-revive-local-env.sh
```

This sets in `backend/.env`:

- `REVIVE_RPC_URL=http://127.0.0.1:8545`
- `AGENT_REGISTRY_ADDRESS`, `TASK_MARKET_ADDRESS`, `REPUTATION_ADDRESS` from `contracts/deployments.json`
- `REVIVE_DEPLOYER_PRIVATE_KEY` from your `DEPLOYER_PRIVATE_KEY` (so backend can register agents and run marketplace on local Revive)

Ensure the deployer account has enough native IVE on the local chain for task rewards and gas.

## 6. Start App and Run Demo

1. Start Postgres/Redis and run migrations (see main runbook):

   ```bash
   docker compose up -d postgres redis
   docker exec -i lpp-postgres psql -U lifeplusplus -d lifeplusplus < database/migrations/001_initial_schema.sql
   docker exec -i lpp-postgres psql -U lifeplusplus -d lifeplusplus < database/migrations/002_revive_chain.sql
   ```

2. Start backend and frontend:

   ```bash
   cd backend && source .venv/bin/activate && python main.py
   # New terminal:
   cd frontend && pnpm dev
   ```

3. Follow the [Demo Runbook](demo-runbook.md): register, create agent, chat, memory, **publish task (with COG reward)**, accept, complete. All chain data (agents on chain, tasks, reputation) comes from **local Revive** — no fake data.

## 7. Verify Chain Data After Demo

After completing the demo flow (at least one agent created, one task published and completed):

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_chain_verification.py -v
```

Or run the verification script:

```bash
./scripts/verify-chain-data.sh
```

This checks:

- Backend can connect to Revive (`/api/v1/chain/stats`).
- Contract addresses are set (`/api/v1/chain/config`).
- Agent count on chain (AgentRegistry) matches expectation.
- A task on chain (TaskMarket) and reputation (Reputation) are readable and consistent.

If any check fails, the script or test reports what is wrong so you can fix and re-run.

## Summary

| Step | What |
|------|------|
| 1 | Prerequisites (Rust, Node, Docker) |
| 2 | Build `revive-dev-node` and `eth-rpc` from polkadot-sdk |
| 3 | Run `revive-dev-node --dev` and `eth-rpc --dev` (local Revive at 8545) |
| 4 | Deploy contracts: `pnpm run deploy:revive-local` in `contracts/` |
| 5 | Apply addresses: `./scripts/apply-revive-local-env.sh` |
| 6 | Start app, run full demo (no fake data) |
| 7 | Run verification: `pytest tests/test_chain_verification.py` or `./scripts/verify-chain-data.sh` |

All displayed chain data (contract address, tx hashes, reputation, agents on chain) comes from your **local Revive** node; nothing is hardcoded or faked.
