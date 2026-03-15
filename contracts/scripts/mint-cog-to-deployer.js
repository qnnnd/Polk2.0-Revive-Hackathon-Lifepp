/**
 * Mint COG to the deployer (COGToken owner). Use when deployer needs more COG for task rewards.
 * Run: npx hardhat run scripts/mint-cog-to-deployer.js --network revive-local
 * Or:  pnpm run mint:cog (if script added to package.json)
 */
const fs = require("fs");
const path = require("path");
const { ethers } = require("hardhat");

const MINT_AMOUNT = ethers.parseEther("1000000"); // 1M COG

async function main() {
  const [deployer] = await ethers.getSigners();
  const deploymentsPath = path.join(__dirname, "..", "deployments.json");
  if (!fs.existsSync(deploymentsPath)) {
    console.error("Run deploy first: pnpm run deploy:revive-local");
    process.exitCode = 1;
    return;
  }
  const deployments = JSON.parse(fs.readFileSync(deploymentsPath, "utf8"));
  const cogAddr = deployments.COGToken;
  if (!cogAddr) {
    console.error("deployments.json missing COGToken");
    process.exitCode = 1;
    return;
  }

  const COGToken = await ethers.getContractFactory("COGToken");
  const cog = COGToken.attach(cogAddr);
  const balanceBefore = await cog.balanceOf(deployer.address);
  console.log("Deployer:", deployer.address);
  console.log("COG balance before:", ethers.formatEther(balanceBefore));

  console.log("Minting", ethers.formatEther(MINT_AMOUNT), "COG to deployer...");
  const tx = await cog.mint(deployer.address, MINT_AMOUNT);
  await tx.wait();
  const balanceAfter = await cog.balanceOf(deployer.address);
  console.log("COG balance after:", ethers.formatEther(balanceAfter));
  console.log("Done.");
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
