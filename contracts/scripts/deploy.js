const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying contracts with:", deployer.address);
  console.log("Balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)));

  // 1. Deploy COGToken
  const COGToken = await ethers.getContractFactory("COGToken");
  const cogToken = await COGToken.deploy();
  await cogToken.waitForDeployment();
  const cogAddr = await cogToken.getAddress();
  console.log("COGToken deployed to:", cogAddr);

  // 2. Deploy AgentRegistry
  const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
  const registry = await AgentRegistry.deploy();
  await registry.waitForDeployment();
  const regAddr = await registry.getAddress();
  console.log("AgentRegistry deployed to:", regAddr);

  // 3. Deploy TaskMarket
  const TaskMarket = await ethers.getContractFactory("TaskMarket");
  const taskMarket = await TaskMarket.deploy(cogAddr);
  await taskMarket.waitForDeployment();
  const tmAddr = await taskMarket.getAddress();
  console.log("TaskMarket deployed to:", tmAddr);

  // 4. Deploy Reputation
  const Reputation = await ethers.getContractFactory("Reputation");
  const reputation = await Reputation.deploy();
  await reputation.waitForDeployment();
  const repAddr = await reputation.getAddress();
  console.log("Reputation deployed to:", repAddr);

  // Save deployment addresses
  const addresses = {
    COGToken: cogAddr,
    AgentRegistry: regAddr,
    TaskMarket: tmAddr,
    Reputation: repAddr,
    deployer: deployer.address,
    network: (await ethers.provider.getNetwork()).name,
    timestamp: new Date().toISOString(),
  };

  const outPath = path.join(__dirname, "..", "deployments.json");
  fs.writeFileSync(outPath, JSON.stringify(addresses, null, 2));
  console.log("\nDeployment addresses saved to:", outPath);
  console.log(JSON.stringify(addresses, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
