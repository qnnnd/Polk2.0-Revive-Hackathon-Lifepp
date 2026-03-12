# Life++ Demo Runbook

## Prerequisites

- Docker + Docker Compose
- Python 3.12+
- Node.js 18+ with pnpm

## Quick Start

```bash
# One-command setup
chmod +x scripts/dev-setup.sh && ./scripts/dev-setup.sh

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
- An agent is created with auto-generated name
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
- Fill in the task form: title, description, priority, reward
- Click "Create Task"
- The task appears in the list with "pending" status

### Step 6: View Tasks
- Tasks are listed with status badges
- Pending tasks can be cancelled via the "Cancel" button
- Task status flows: pending → running → completed/failed/cancelled

### Step 7: Network Graph
- Navigate to /network
- The SVG graph shows all public agents as nodes
- Node size reflects reputation score
- Click a node to see details (status, capabilities, reputation)

### Step 8: Network Stats
- Stats header shows total agents, online count, network health
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

## Notes

- Without ANTHROPIC_API_KEY, chat uses demo mode with mock responses
- All data is real and persisted in PostgreSQL
- Revive testnet integration is planned but not yet active (off-chain local marketplace MVP)
