-- Revive chain integration (13.4 compliance)
-- Adds chain_task_id to task_listings, wallet_address to users, chain_registered_tx_hash to agents.

ALTER TABLE task_listings
  ADD COLUMN IF NOT EXISTS chain_task_id BIGINT;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS wallet_address TEXT;

ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS chain_registered_tx_hash TEXT;

COMMENT ON COLUMN task_listings.chain_task_id IS 'TaskMarket task id on Revive';
COMMENT ON COLUMN users.wallet_address IS 'EVM address for COG balance / chain ops';
COMMENT ON COLUMN agents.chain_registered_tx_hash IS 'Tx hash from AgentRegistry.register on Revive';
