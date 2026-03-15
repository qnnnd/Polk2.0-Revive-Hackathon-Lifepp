/**
 * Claim local Revive dev-chain tokens into the deployer account.
 *
 * Uses the well-known Frontier/Substrate EVM dev account "Alith" (if pre-funded
 * by the chain) to send native token to the address derived from
 * DEPLOYER_PRIVATE_KEY in .env. Run with revive-dev-node + eth-rpc at 8545.
 *
 * Usage:
 *   cd contracts && pnpm run claim:revive-local
 *   or: npx hardhat run scripts/claim-local-tokens.js
 */
require("dotenv").config();
const { ethers } = require("hardhat");

const RPC = process.env.REVIVE_LOCAL_RPC_URL || "http://127.0.0.1:8545";

// Well-known Frontier/Substrate EVM dev account (Alith). Many dev chains pre-fund it.
// See: https://github.com/polkadot-sdk/pull/8103, substrate.stackexchange.com/questions/6674
const ALITH_PRIVATE_KEY = "0x5fb92d6e98884f76de468fa3f6278f8807c48bebc13595d45af5bdc4da702133";

async function main() {
  const deployerKey = process.env.DEPLOYER_PRIVATE_KEY;
  if (!deployerKey || !deployerKey.startsWith("0x")) {
    console.error("Set DEPLOYER_PRIVATE_KEY in contracts/.env (the account you want to fund).");
    process.exitCode = 1;
    return;
  }

  const provider = new ethers.JsonRpcProvider(RPC);
  const alith = new ethers.Wallet(ALITH_PRIVATE_KEY, provider);
  const recipient = new ethers.Wallet(deployerKey, provider);

  const alithAddress = alith.address;
  const recipientAddress = recipient.address;

  const balAlith = await provider.getBalance(alithAddress);
  const balRecipient = await provider.getBalance(recipientAddress);

  console.log("RPC:", RPC);
  console.log("Alith (faucet):", alithAddress, "balance:", ethers.formatEther(balAlith));
  console.log("Recipient (deployer):", recipientAddress, "balance:", ethers.formatEther(balRecipient));

  if (balAlith === 0n) {
    console.error("\nFaucet (Alith) has 0 balance. This Revive dev node may not pre-fund Alith.");
    console.error("Options: (1) Use a chain spec that endows Alith / mapped EVM accounts.");
    console.error("        (2) Use Alith as deployer: set DEPLOYER_PRIVATE_KEY to Alith key in .env and run deploy:revive-local.");
    process.exitCode = 1;
    return;
  }

  // Leave a bit for gas on Alith; send the rest (or cap at 1000 ETH)
  const reserve = ethers.parseEther("10");
  const toSend = balAlith - reserve > 0n ? balAlith - reserve : balAlith;
  const cap = ethers.parseEther("10000");
  const amount = toSend > cap ? cap : toSend;

  if (amount <= 0n) {
    console.error("Nothing to send (balance too low after reserve).");
    process.exitCode = 1;
    return;
  }

  console.log("\nSending", ethers.formatEther(amount), "to", recipientAddress, "...");
  try {
    const tx = await alith.sendTransaction({
      to: recipientAddress,
      value: amount,
      gasLimit: 21000,
    });
    console.log("Tx hash:", tx.hash);
    await tx.wait();
    const newBal = await provider.getBalance(recipientAddress);
    console.log("Recipient new balance:", ethers.formatEther(newBal));
    console.log("Done. You can run: pnpm run deploy:revive-local");
  } catch (err) {
    if (err && (err.error || err.message) && String(err.error || err.message).includes("Invalid Transaction")) {
      console.error("\nTransfer failed: this Revive dev node may require EVM accounts to be 'mapped'.");
      console.error("Use Alith as deployer instead: set in contracts/.env");
      console.error("  DEPLOYER_PRIVATE_KEY=0x5fb92d6e98884f76de468fa3f6278f8807c48bebc13595d45af5bdc4da702133");
      console.error("Then run: pnpm run deploy:revive-local");
    } else {
      throw err;
    }
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
