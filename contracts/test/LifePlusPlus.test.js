const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Life++ Smart Contracts", function () {
  let registry, taskMarket, reputation;
  let deployer, alice, bob;

  beforeEach(async function () {
    [deployer, alice, bob] = await ethers.getSigners();

    const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
    registry = await AgentRegistry.deploy();

    const TaskMarket = await ethers.getContractFactory("TaskMarket");
    taskMarket = await TaskMarket.deploy();

    const Reputation = await ethers.getContractFactory("Reputation");
    reputation = await Reputation.deploy();
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

  describe("TaskMarket (IVE native)", function () {
    it("should create, accept, and complete a task with IVE escrow", async function () {
      const reward = ethers.parseEther("50");

      await taskMarket.connect(alice).createTask("agent-alice", "Research AI", reward, { value: reward });
      let task = await taskMarket.getTask(0);
      expect(task.status).to.equal(0);
      expect(task.rewardAmount).to.equal(reward);

      await taskMarket.connect(bob).acceptTask(0, "agent-bob", bob.address);
      task = await taskMarket.getTask(0);
      expect(task.status).to.equal(1);

      const bobBefore = await ethers.provider.getBalance(bob.address);
      await taskMarket.connect(alice).completeTask(0);
      const bobAfter = await ethers.provider.getBalance(bob.address);

      expect(bobAfter - bobBefore).to.equal(reward);
      task = await taskMarket.getTask(0);
      expect(task.status).to.equal(2);
    });

    it("relayer can accept on behalf of user (acceptTaskFor)", async function () {
      const reward = ethers.parseEther("10");
      await taskMarket.connect(deployer).createTask("agent-deployer", "Relayer task", reward, { value: reward });
      expect((await taskMarket.getTask(0)).status).to.equal(0);
      await taskMarket.connect(deployer).acceptTaskFor(0, "agent-bob", bob.address, bob.address);
      expect((await taskMarket.getTask(0)).status).to.equal(1);
      expect((await taskMarket.getTask(0)).acceptor).to.equal(bob.address);
      const bobBefore = await ethers.provider.getBalance(bob.address);
      await taskMarket.connect(deployer).completeTask(0);
      const bobAfter = await ethers.provider.getBalance(bob.address);
      expect(bobAfter - bobBefore).to.equal(reward);
    });

    it("relayer can complete on behalf of poster (completeTaskFor)", async function () {
      const reward = ethers.parseEther("5");
      await taskMarket.connect(alice).createTask("agent-alice", "Poster pays", reward, { value: reward });
      await taskMarket.connect(deployer).acceptTaskFor(0, "agent-bob", bob.address, bob.address);
      const bobBefore = await ethers.provider.getBalance(bob.address);
      await taskMarket.connect(deployer).completeTaskFor(0);
      const bobAfter = await ethers.provider.getBalance(bob.address);
      expect(bobAfter - bobBefore).to.equal(reward);
      expect((await taskMarket.getTask(0)).status).to.equal(2);
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
      expect(score).to.equal(66n);
    });
  });
});
