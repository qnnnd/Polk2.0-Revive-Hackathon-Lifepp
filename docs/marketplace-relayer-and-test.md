# Why Backend Must Use the TaskMarket Deployer Account

## Contract design

In `contracts/contracts/TaskMarket.sol`:

- The contract has a **relayer** address: `address public relayer;`
- It is set **once** in the constructor: `relayer = msg.sender;` (i.e. the deployer).
- **acceptTaskFor** and **completeTaskFor** both enforce: `require(msg.sender == relayer, "Only relayer");`

So only the **relayer** (the address that deployed the contract) is allowed to:

- Call **acceptTaskFor** (backend accepts on behalf of the user who clicked “Accept”).
- Call **completeTaskFor** (backend completes on behalf of the publisher who clicked “Complete”).

There is no setter to change `relayer`; it is fixed at deployment. Therefore the backend **must** send these two functions from the **same account that deployed TaskMarket** (the deployer). If it uses any other account, the transactions will revert with "Only relayer" and reward will never be sent.

Summary: **Backend must use the deployer account for accept/complete because the contract only allows that single address (the relayer = deployer) to call `acceptTaskFor` and `completeTaskFor`.**

---

# How to Test So That Reward Works

## 1. Use one key for deploy and backend

When you deploy the contracts (e.g. `cd contracts && pnpm run deploy:revive-local`), you use a **deployer private key** (often Alith in dev). That address becomes the **relayer** in TaskMarket.

The backend must use **that same private key** so that accept/complete transactions are sent from the relayer.

## 2. Set backend env from deploy

After deploying:

```bash
# If you have DEPLOYER_PRIVATE_KEY in your environment (same key you used to deploy):
export DEPLOYER_PRIVATE_KEY=0x...   # e.g. Alith key for revive-local

./scripts/apply-revive-local-env.sh
```

This writes `backend/.env` with:

- `REVIVE_RPC_URL=http://127.0.0.1:8545`
- `TASK_MARKET_ADDRESS`, `AGENT_REGISTRY_ADDRESS`, `REPUTATION_ADDRESS` from `contracts/deployments.json`
- **`REVIVE_DEPLOYER_PRIVATE_KEY`** from `DEPLOYER_PRIVATE_KEY` (if set)

If you did **not** set `DEPLOYER_PRIVATE_KEY` when running the script, you must **manually** set in `backend/.env`:

```bash
REVIVE_DEPLOYER_PRIVATE_KEY=0x...   # same key used to deploy TaskMarket (see deployments.json "deployer" address)
```

The address in `contracts/deployments.json` under `"deployer"` must correspond to this key.

## 3. Start services and run E2E

1. Start Revive local node and RPC (e.g. port 8545).
2. Start backend (so it loads `backend/.env`):

   ```bash
   cd backend && source .venv/bin/activate && python main.py
   ```

3. Run the full E2E (publish → accept → complete with IVE):

   ```bash
   cd backend && .venv/bin/python ../scripts/e2e_task_cog_test.py
   ```

   The script will use `REVIVE_DEPLOYER_PRIVATE_KEY` from `backend/.env` as publisher A’s key if `E2E_PUBLISHER_A_PRIVATE_KEY` is not set, and will call the API for accept/complete. The backend will send accept/complete from the same deployer key, so the relayer checks pass and the acceptor receives the reward.

## 4. Quick checklist

- [ ] TaskMarket deployed with key **K** (address in `deployments.json` → `deployer`).
- [ ] `backend/.env` has **`REVIVE_DEPLOYER_PRIVATE_KEY`** = **K** (same key).
- [ ] Backend was **restarted** after changing `.env`.
- [ ] Revive RPC is up (e.g. `http://127.0.0.1:8545`).
- [ ] Run E2E: `cd backend && .venv/bin/python ../scripts/e2e_task_cog_test.py`.

If complete still returns 503, check backend logs for `complete_task_on_chain: sender=0x...` and confirm that address is the same as `deployments.json`’s `deployer`.
