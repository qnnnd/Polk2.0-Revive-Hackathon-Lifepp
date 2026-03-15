# Local Revive Quick Start

Your **revive-dev-node** and **eth-rpc** are already running (9944 + 8545). The project is configured to use them.

## What’s already done

- **contracts/.env** — `DEPLOYER_PRIVATE_KEY` set (Hardhat-style dev key). Deploy will only succeed once this account has balance on your local Revive (see below).
- **contracts/hardhat.config.js** — loads `dotenv` so `contracts/.env` is used for `deploy:revive-local`.
- **backend/.env** — `REVIVE_RPC_URL=http://127.0.0.1:8545`; contract addresses left empty until you deploy.
- **frontend/.env.local** — `NEXT_PUBLIC_API_URL=http://localhost:8002`.

## 1. Get token + deploy contracts (optional; needed for full chain features)

Your deployer account needs **native token** on the local Revive chain. Easiest:

**Step 1 — Claim tokens (if your dev node pre-funds Alith):**

```bash
cd contracts
pnpm install   # or: npm install
pnpm run claim:revive-local   # sends from Alith to your DEPLOYER_PRIVATE_KEY address
```

If the script reports "Faucet (Alith) has 0 balance", your chain does not pre-fund Alith; use [Option B in revive-local-setup.md](revive-local-setup.md) (e.g. set Alith as deployer, or use a custom chain spec).

**Step 2 — Deploy:**

```bash
pnpm run deploy:revive-local   # or: npx hardhat run scripts/deploy.js --network revive-local
cd ..
./scripts/apply-revive-local-env.sh   # writes contract addresses into backend/.env
```

## 2. Start app (Docker: Postgres + Redis already up)

**Terminal 1 – Backend**

```bash
cd backend
source .venv/bin/activate   # or: python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Terminal 2 – Frontend**

```bash
cd frontend
pnpm install && pnpm dev   # or: npm install && npm run dev
```

- Frontend: http://localhost:3001  
- Backend API docs: http://localhost:8002/docs  

Without a successful contract deploy, chain-related features (agents on chain, task market, etc.) will show as “not configured” until you deploy and run `./scripts/apply-revive-local-env.sh`.
