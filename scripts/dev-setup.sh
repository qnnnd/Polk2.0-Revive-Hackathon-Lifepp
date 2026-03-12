#!/bin/bash
# Life++ — One-command development environment setup
# Usage: chmod +x scripts/dev-setup.sh && ./scripts/dev-setup.sh

set -e

echo "============================================"
echo "  Life++ Development Environment Setup"
echo "============================================"
echo ""

# ── Backend ──────────────────────────────────────────────
echo "[1/4] Setting up Python backend..."
cd backend

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  Created virtual environment"
fi

source .venv/bin/activate
pip install -q -r requirements.txt
echo "  Backend dependencies installed"

if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
SECRET_KEY=dev-secret-change-in-production
JWT_SECRET=dev-jwt-secret
ENVIRONMENT=development
DEBUG=true
REVIVE_RPC_URL=http://127.0.0.1:8545
EOF
    echo "  Created .env file"
fi

cd ..

# ── Frontend ─────────────────────────────────────────────
echo "[2/4] Setting up Next.js frontend..."
cd frontend
pnpm install --silent 2>/dev/null || npm install --silent
echo "  Frontend dependencies installed"

if [ ! -f ".env.local" ]; then
    echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
    echo "  Created .env.local"
fi
cd ..

# ── Smart Contracts ──────────────────────────────────────
echo "[3/4] Setting up Hardhat contracts..."
cd contracts
pnpm install --silent 2>/dev/null || npm install --silent
npx hardhat compile --quiet
echo "  Contracts compiled"
cd ..

# ── Done ─────────────────────────────────────────────────
echo "[4/4] Setup complete!"
echo ""
echo "============================================"
echo "  Start services:"
echo ""
echo "  Terminal 1 (Backend):"
echo "    cd backend && source .venv/bin/activate && python main.py"
echo ""
echo "  Terminal 2 (Frontend):"
echo "    cd frontend && pnpm dev"
echo ""
echo "  Terminal 3 (Hardhat node — optional):"
echo "    cd contracts && npx hardhat node"
echo ""
echo "  Then deploy contracts:"
echo "    cd contracts && npx hardhat run scripts/deploy.js --network localhost"
echo ""
echo "  Open: http://localhost:3000 (frontend)"
echo "  API:  http://localhost:8000/docs (backend)"
echo "============================================"
