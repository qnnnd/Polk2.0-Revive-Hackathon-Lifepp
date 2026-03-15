#!/bin/bash
set -e

echo "============================================"
echo "  Life++ Development Environment Setup"
echo "============================================"

echo "[1/4] Starting Docker services..."
docker compose up -d postgres redis
echo "  Waiting for PostgreSQL..."
until docker exec lpp-postgres pg_isready -U lifeplusplus -q 2>/dev/null; do sleep 1; done
echo "  PostgreSQL ready"

echo "[2/4] Running database migration..."
docker exec -i lpp-postgres psql -U lifeplusplus -d lifeplusplus < database/migrations/001_initial_schema.sql 2>/dev/null || true
echo "  Migration complete"

echo "[3/4] Setting up Python backend..."
cd backend
if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q -r requirements.txt
if [ ! -f ".env" ]; then cp .env.example .env; fi
cd ..

echo "[4/4] Setting up Next.js frontend..."
cd frontend
pnpm install --silent 2>/dev/null || npm install --silent
if [ ! -f ".env.local" ]; then cp .env.local.example .env.local; fi
cd ..

echo ""
echo "============================================"
echo "  Setup complete! Start services:"
echo ""
echo "  Backend:  cd backend && source .venv/bin/activate && python main.py"
echo "  Frontend: cd frontend && pnpm dev"
echo ""
echo "  Or: docker compose up -d"
echo ""
echo "  Frontend: http://localhost:3001"
echo "  Backend:  http://localhost:8002/docs"
echo "============================================"
