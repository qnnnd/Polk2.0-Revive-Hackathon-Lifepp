# Life++ Development Guide

## Cursor Cloud specific instructions

### Services

| Service | Command | Port |
|---------|---------|------|
| PostgreSQL+pgvector | `docker compose up -d postgres` (or `sudo docker start lpp-postgres`) | 5432 |
| Redis | `docker compose up -d redis` (or `sudo docker start lpp-redis`) | 6379 |
| Backend | `cd backend && source .venv/bin/activate && python main.py` | 8002 |
| Frontend | `cd frontend && pnpm dev` | 3001 |

### Quick Start

```bash
chmod +x scripts/dev-setup.sh && ./scripts/dev-setup.sh
```

Then start backend and frontend in separate terminals (see table above).

### Key Points

- **Docker required**: PostgreSQL 16 + pgvector and Redis 7 run as Docker containers.
- **Local Revive (required for “本地必须使用 Revive”)**: See `docs/revive-local-setup.md` — run revive-dev-node + eth-rpc, then `pnpm run deploy:revive-local`, `./scripts/apply-revive-local-env.sh`, and after demo run `./scripts/verify-chain-data.sh`.
- **Database migration**: Auto-loaded from `database/migrations/001_initial_schema.sql` when containers start. To manually re-apply: `docker exec -i lpp-postgres psql -U lifeplusplus -d lifeplusplus < database/migrations/001_initial_schema.sql`; also apply `database/migrations/002_revive_chain.sql` for chain fields.
- **Demo mode**: Without `ANTHROPIC_API_KEY`, chat returns mock responses. Full API flow still works.
- **Lint/Build/Test**: See `docs/test-report.md` for all commands.
- **API docs**: http://localhost:8002/docs (Swagger UI)
- **Demo flow**: See `docs/demo-runbook.md` for the 8-step demo loop. After demo, verify chain data with `./scripts/verify-chain-data.sh`.
