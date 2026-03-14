# Life++ Demo Runbook

## Prerequisites

- Docker + Docker Compose
- Python 3.12+
- Node.js 18+ with pnpm
- **Revive testnet**: RPC URL and deployer wallet with COG for on-chain flows (required for 13.4 / "必须使用 Revive")

## Deploy contracts to Revive (required for full demo)

1. In `contracts/`, set env:
   - `REVIVE_RPC_URL` (default: https://rpc.revive.network)
   - `DEPLOYER_PRIVATE_KEY` (testnet wallet with funds for gas)
2. Run: `pnpm install && pnpm deploy:revive`
3. Copy addresses from `contracts/deployments.json` into backend `.env` (see below).

## Backend env (Revive)

In `backend/.env` add (from deployments.json after deploy):

- `REVIVE_RPC_URL` — Revive RPC URL
- `COG_TOKEN_ADDRESS` — COGToken contract
- `AGENT_REGISTRY_ADDRESS` — AgentRegistry contract
- `TASK_MARKET_ADDRESS` — TaskMarket contract
- `REPUTATION_ADDRESS` — Reputation contract
- `REVIVE_DEPLOYER_PRIVATE_KEY` — same key used to deploy (for agent register + marketplace escrow)

## Quick Start

```bash
# One-command setup
chmod +x scripts/dev-setup.sh && ./scripts/dev-setup.sh

# Apply DB migration for Revive fields (chain_task_id, wallet_address, chain_registered_tx_hash)
docker exec -i lpp-postgres psql -U lifeplusplus -d lifeplusplus < database/migrations/002_revive_chain.sql

# Start backend
cd backend && source .venv/bin/activate && python main.py

# Start frontend (new terminal)
cd frontend && pnpm dev
```

## Demo Flow (8-step main loop)

### Step 1: Register & Login
- Open http://localhost:3000/dashboard
- Enter a username (e.g. "alice") in the login form
- Click "Enter Life++"
- You are now authenticated with a JWT token

### Step 2: Create Agent
- On the dashboard, click "+ New Agent"
- An agent is created with auto-generated name and registered on Revive (AgentRegistry) when chain is configured
- The agent appears in the sidebar list

### Step 3: Chat with Agent
- Click the agent card to open /agents/[id]
- The "Chat" tab is shown by default
- Type a message like "Remember that I enjoy AI research"
- The agent responds (demo mode if no ANTHROPIC_API_KEY)
- Messages are persisted in the database

### Step 4: Memory Write & Recall
- Switch to the "Memories" tab
- Memories from the chat are automatically stored
- Use the search box to search "AI research"
- Verify semantic search returns relevant memories
- Click "Consolidate" to run memory decay

### Step 5: Create Task
- Navigate to /marketplace
- Fill in the task form: title, description, reward (COG)
- Click "Publish Task"
- When Revive is configured, the task is created on-chain (TaskMarket) with COG escrow and appears with chain tx_hash

### Step 6: View Tasks
- Tasks are listed with status badges
- Pending tasks can be cancelled via the "Cancel" button
- Task status flows: pending → running → completed/failed/cancelled

### Step 7: Network Graph
- Navigate to /network
- The SVG graph shows all public agents as nodes
- Node size reflects reputation score (from Revive Reputation contract when configured)
- Click a node to see details (status, capabilities, reputation)

### Step 8: Network Stats & Revive status
- Dashboard "Revive Testnet Status" shows Revive connection and agents on chain (from AgentRegistry)
- Stats header shows total agents, online count
- Data refreshes automatically via React Query polling

## API Documentation

Interactive Swagger UI: http://localhost:8000/docs

## Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/register | Create user account |
| POST | /api/v1/auth/token | Get JWT token |
| POST | /api/v1/agents | Create agent |
| GET | /api/v1/agents | List my agents |
| POST | /api/v1/agents/{id}/chat | Chat with agent |
| POST | /api/v1/agents/{id}/memories | Store memory |
| POST | /api/v1/agents/{id}/memories/search | Semantic search |
| POST | /api/v1/agents/{id}/tasks | Create task |
| GET | /api/v1/network/graph | Network graph |
| GET | /api/v1/network/stats | Network stats |
| GET | /api/v1/chain/config | Revive contract addresses (public) |
| GET | /api/v1/chain/stats | Revive chain stats (agents on chain, block) |
| GET | /api/v1/chain/balance | Current user COG balance from chain (auth) |

## Verify chain data in UI (13.4)

- **Marketplace**: "Contract" and "Recent TX" come from API (no hardcoded values). Task tx_hash is set only from real Revive txs.
- **Dashboard**: "Revive Testnet Status" shows Revive connection and "Agents on chain" from AgentRegistry.
- **Agent detail & Network**: Reputation (score, tasks completed) is from Revive Reputation contract when configured.
- **COG balance**: GET /api/v1/chain/balance returns chain-derived balance when user has wallet_address set.

## Notes

- Without ANTHROPIC_API_KEY, chat uses demo mode with mock responses
- All app data is persisted in PostgreSQL; chain-related data (task status, reputation, balance) comes from Revive when configured (13.4: no fake chain data)
- **Must use Revive**: Deploy contracts to Revive and set backend env so that agent registration, task marketplace, and reputation use the testnet
