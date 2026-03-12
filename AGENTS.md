# Life++ Development Guide

## Cursor Cloud specific instructions

### Services

| Service | Command | Port |
|---------|---------|------|
| PostgreSQL+pgvector | `docker compose up -d postgres` (or `sudo docker start lpp-postgres`) | 5432 |
| Redis | `docker compose up -d redis` (or `sudo docker start lpp-redis`) | 6379 |
| Backend | `cd backend && source .venv/bin/activate && python main.py` | 8000 |
| Frontend | `cd frontend && pnpm dev` | 3000 |

### Quick Start

```bash
chmod +x scripts/dev-setup.sh && ./scripts/dev-setup.sh
```

Then start backend and frontend in separate terminals (see table above).

### Key Points

- **Docker required**: PostgreSQL 16 + pgvector and Redis 7 run as Docker containers.
- **Database migration**: Auto-loaded from `database/migrations/001_initial_schema.sql` when containers start. To manually re-apply: `docker exec -i lpp-postgres psql -U lifeplusplus -d lifeplusplus < database/migrations/001_initial_schema.sql`
- **Demo mode**: Without `ANTHROPIC_API_KEY`, chat returns mock responses. Full API flow still works.
- **Lint/Build/Test**: See `docs/test-report.md` for all commands.
- **API docs**: http://localhost:8000/docs (Swagger UI)
- **Demo flow**: See `docs/demo-runbook.md` for the 8-step demo loop.
