# Life++ Development Guide

## Overview

Life++ is a Peer-to-Peer Cognitive Agent Network for the Polkadot Solidity Hackathon 2026. It consists of:

- **Backend**: FastAPI (Python 3.12) with SQLite storage
- **Frontend**: Next.js 14 (TypeScript, TailwindCSS, React Query v5)
- **Smart Contracts**: Solidity 0.8.24 (Hardhat) — COGToken, AgentRegistry, TaskMarket, Reputation

## Cursor Cloud specific instructions

### Quick Start

```bash
chmod +x scripts/dev-setup.sh && ./scripts/dev-setup.sh
```

### Services

| Service | Command | Port |
|---------|---------|------|
| Backend | `cd backend && source .venv/bin/activate && python main.py` | 8000 |
| Frontend | `cd frontend && pnpm dev` | 3000 |
| Hardhat node | `cd contracts && npx hardhat node` | 8545 |
| Deploy contracts | `cd contracts && npx hardhat run scripts/deploy.js --network localhost` | — |

### Key Points

- **No Docker required**: Backend uses SQLite (file `backend/lifeplusplus.db`, auto-created on startup).
- **No external DB**: All data stored locally in SQLite. Delete `lifeplusplus.db` to reset.
- **Demo mode**: Without `ANTHROPIC_API_KEY`, chat returns mocked responses. Full API flow still works.
- **Contract tests**: `cd contracts && npx hardhat test` — runs 7 tests for all 4 contracts.
- **Lint**: `cd frontend && pnpm lint`
- **Build**: `cd frontend && pnpm build`

### API Docs

Backend Swagger UI: `http://localhost:8000/docs` (when backend is running).

### Demo Flow (Spec Section 2.3)

The 8-step demo loop can be exercised via the API:
1. Register user → `POST /api/v1/auth/register`
2. Create agent → `POST /api/v1/agents`
3. Chat with agent → `POST /api/v1/agents/{id}/chat`
4. Store + recall memory → `POST /api/v1/agents/{id}/memories` + `/memories/search`
5. Publish task → `POST /api/v1/tasks`
6. Accept task → `POST /api/v1/tasks/{id}/accept`
7. Complete task → `POST /api/v1/tasks/{id}/complete`
8. Orchestrate agents → `POST /api/v1/network/orchestrate`
