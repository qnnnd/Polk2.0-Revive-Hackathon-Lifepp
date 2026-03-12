# Life++ Development Guide

## Overview

Life++ is a Peer-to-Peer Cognitive Agent Network — a platform for building and networking persistent AI agents with long-term cognitive memory. It consists of a **FastAPI backend** (Python 3.12) and a **Next.js 14 frontend** (TypeScript), backed by PostgreSQL+pgvector and Redis.

## Cursor Cloud specific instructions

### Services

| Service | How to run | Port |
|---------|-----------|------|
| PostgreSQL+pgvector | `sudo docker start lpp-postgres` (container already created) | 5432 |
| Redis | `sudo docker start lpp-redis` (container already created) | 6379 |
| Backend (FastAPI) | `cd /workspace/backend && source .venv/bin/activate && python main.py` | 8000 |
| Frontend (Next.js) | `cd /workspace/frontend && pnpm dev` | 3000 |

### Important caveats

- **Docker daemon**: Must be started before containers: `sudo dockerd &>/tmp/dockerd.log &` — wait a few seconds before running `docker start`.
- **Database migration**: Run `sudo docker exec -i lpp-postgres psql -U lifeplusplus -d lifeplusplus < /workspace/database/migrations/001_initial_schema.sql` if the database is fresh (idempotent for first run, will error on duplicate types for reruns — safe to ignore).
- **ENUM types**: The PostgreSQL schema uses custom ENUM types (`agent_status`, `task_status`, `task_priority`, `memory_type`, `message_role`). The SQLAlchemy models must use `Enum(...)` with `create_type=False` to match. Do not use plain `String` columns for these fields.
- **Demo mode**: The backend runs in demo mode without `ANTHROPIC_API_KEY`. Chat responses are mocked but the full API flow (register, login, create agent, chat, memories, tasks, network) works.
- **Frontend static assets**: On first page load after starting `pnpm dev`, Next.js compiles pages on demand. The first load may briefly show unstyled content; a refresh resolves it.

### Lint / Test / Build

- **Frontend lint**: `cd /workspace/frontend && pnpm lint`
- **Frontend build**: `cd /workspace/frontend && pnpm build`
- **Backend import check**: `cd /workspace/backend && source .venv/bin/activate && python -c "import main"`
- **Backend API docs**: Available at `http://localhost:8000/docs` when the backend is running.

### Environment Variables

Backend config is in `/workspace/backend/.env`. Key variables:
- `DATABASE_URL` — async PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `ANTHROPIC_API_KEY` — optional, enables live AI agent responses
- `SECRET_KEY` / `JWT_SECRET` — app security (dev defaults set)

Frontend config is in `/workspace/frontend/.env.local`:
- `NEXT_PUBLIC_API_URL=http://localhost:8000`
