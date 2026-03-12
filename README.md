# Life++ Local MVP (Hackathon Delivery)

This repository now includes a runnable local MVP backend aligned with `source-file/技术方案.md`.

## Quick Start

```bash
./scripts/dev-setup.sh
source .venv/bin/activate
python backend/main.py
```

API docs: http://127.0.0.1:8000/docs

## Run Tests

```bash
source .venv/bin/activate
PYTHONPATH=backend pytest -q backend/tests
# or
./scripts/run-smoke-tests.sh
```

## Implemented P0 API

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/agents`
- `GET /api/v1/agents`
- `POST /api/v1/agents/{id}/memories`
- `POST /api/v1/agents/{id}/memories/search`
- `POST /api/v1/agents/{id}/chat`
- `POST /api/v1/tasks`
- `POST /api/v1/tasks/{id}/accept`
- `POST /api/v1/tasks/{id}/complete`
- `GET /api/v1/network/agents`
- `GET /api/v1/network/connections`
- `POST /api/v1/network/connections`
