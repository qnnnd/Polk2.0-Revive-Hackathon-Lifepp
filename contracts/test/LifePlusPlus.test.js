const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Life++ Smart Contracts", function () {
  let cogToken, registry, taskMarket, reputation;
  let deployer, alice, bob;

  beforeEach(async function () {
    [deployer, alice, bob] = await ethers.getSigners();

    const COGToken = await ethers.getContractFactory("COGToken");
    cogToken = await COGToken.deploy();

    const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
    registry = await AgentRegistry.deploy();

    const TaskMarket = await ethers.getContractFactory("TaskMarket");
    taskMarket = await TaskMarket.deploy(await cogToken.getAddress());

    const Reputation = await ethers.getContractFactory("Reputation");
    reputation = await Reputation.deploy();

    // Give Alice some COG tokens
    await cogToken.transfer(alice.address, ethers.parseEther("1000"));
  });

  describe("COGToken", function () {
    it("should have correct initial supply", async function () {
      const supply = await cogToken.totalSupply();
      expect(supply).to.equal(ethers.parseEther("1000000"));
    });

    it("should transfer tokens", async function () {
      const balance = await cogToken.balanceOf(alice.address);
      expect(balance).to.equal(ethers.parseEther("1000"));
    });
  });

  describe("AgentRegistry", function () {
    it("should register an agent", async function () {
      await registry.connect(alice).register("agent-1", "Nexus", "ipfs://meta");
      const info = await registry.getAgent("agent-1");
      expect(info.name).to.equal("Nexus");
      expect(info.owner).to.equal(alice.address);
      expect(info.active).to.be.true;
    });

    it("should not allow duplicate registration", async function () {
      await registry.connect(alice).register("agent-1", "Nexus", "ipfs://meta");
      await expect(
        registry.connect(bob).register("agent-1", "Dup", "ipfs://dup")
      ).to.be.revertedWith("Agent already registered");
    });
  });

  describe("TaskMarket", function () {
    it("should create, accept, and complete a task with escrow", async function () {
      const reward = ethers.parseEther("50");

      // Alice approves TaskMarket to spend COG
      await cogToken.connect(alice).approve(await taskMarket.getAddress(), reward);

      // Alice creates a task
      await taskMarket.connect(alice).createTask("agent-alice", "Research AI", reward);
      let task = await taskMarket.getTask(0);
      expect(task.status).to.equal(0); // Open
      expect(task.rewardAmount).to.equal(reward);

      // Bob accepts the task
      await taskMarket.connect(bob).acceptTask(0, "agent-bob");
      task = await taskMarket.getTask(0);
      expect(task.status).to.equal(1); // Accepted

      // Alice confirms completion → escrow released to Bob
      const bobBefore = await cogToken.balanceOf(bob.address);
      await taskMarket.connect(alice).completeTask(0);
      const bobAfter = await cogToken.balanceOf(bob.address);

      expect(bobAfter - bobBefore).to.equal(reward);
      task = await taskMarket.getTask(0);
      expect(task.status).to.equal(2); // Completed
    });
  });

  describe("Reputation", function () {
    it("should track task completions", async function () {
      await reputation.recordTaskComplete("agent-1", ethers.parseEther("50"));
      const rep = await reputation.getReputation("agent-1");
      expect(rep.tasksCompleted).to.equal(1);
      expect(rep.totalCogEarned).to.equal(ethers.parseEther("50"));
    });

    it("should compute score correctly", async function () {
      await reputation.recordTaskComplete("agent-1", 100);
      await reputation.recordTaskComplete("agent-1", 200);
      await reputation.recordTaskFailed("agent-1");
      const score = await reputation.getScore("agent-1");
      expect(score).to.equal(66n); // 2 completed / 3 total * 100
    });
  });
});
