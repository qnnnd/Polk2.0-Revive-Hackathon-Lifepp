# Life++ Development Guide

## Overview

Life++ is a Peer-to-Peer Cognitive Agent Network for the Polkadot Solidity Hackathon 2026. It consists of:

- **Backend**: FastAPI (Python 3.12) with PostgreSQL+pgvector
- **Frontend**: Next.js 14 (TypeScript, TailwindCSS, React Query v5)
- **Smart Contracts**: Solidity 0.8.24 (Hardhat) — COGToken, AgentRegistry, TaskMarket, Reputation

## Cursor Cloud specific instructions

### Prerequisites

PostgreSQL 16 with pgvector and Redis must be running. They are started via Docker Compose:

```bash
sudo docker compose up -d postgres redis
```

The database resets cleanly via SQLAlchemy `Base.metadata.create_all()` on backend startup (the `lifespan` handler calls `init_db()`). No manual migration is needed for dev.

### Services

| Service | Command | Port |
|---------|---------|------|
| Backend | `cd backend && source .venv/bin/activate && python main.py` | 8000 |
| Frontend | `cd frontend && pnpm dev` | 3000 |

### Key Points

- **Docker required**: PostgreSQL (pgvector/pgvector:pg16) and Redis (redis:7-alpine) run in Docker containers.
- **Backend venv**: Python dependencies are installed in `backend/.venv`. Always activate it before running backend commands.
- **Demo mode**: Without `ANTHROPIC_API_KEY`, chat returns mocked responses. Full API flow still works.
- **Tests**: `cd backend && source .venv/bin/activate && python -m pytest tests/test_smoke.py -v` — runs 5 async smoke tests against the live PostgreSQL database. Tests use `loop_scope="session"` to share the asyncpg connection pool across tests.
- **Lint**: `cd frontend && pnpm lint`
- **Build**: `cd frontend && pnpm build`
- **pgvector gotcha**: If the database was previously initialized with the SQL migration (which uses PostgreSQL ENUM types for status fields), you must drop and recreate the schema before the SQLAlchemy ORM models (which use `String(20)`) can create tables. The `init_db()` function handles table creation but will fail if conflicting ENUM types exist.
- **API docs**: `http://localhost:8000/docs` (Swagger UI when backend is running).

### Demo Flow

1. Register user → `POST /api/v1/auth/register`
2. Login → `POST /api/v1/auth/token?username=...`
3. Create agent → `POST /api/v1/agents`
4. Chat with agent → `POST /api/v1/agents/{id}/chat`
5. Store memory → `POST /api/v1/agents/{id}/memories`
6. Search memory → `POST /api/v1/agents/{id}/memories/search`
7. Create task → `POST /api/v1/agents/{id}/tasks`
8. View network → `GET /api/v1/network/graph`
