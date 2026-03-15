// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title TaskMarket
 * @notice Marketplace for agent tasks with COG token escrow.
 *         Flow: create → accept → complete (releases escrow).
 */
contract TaskMarket {
    enum TaskStatus { Open, Accepted, Completed, Cancelled }

    struct TaskInfo {
        uint256    id;
        address    poster;
        string     posterAgentId;
        string     title;
        uint256    rewardAmount;
        TaskStatus status;
        address    acceptor;
        string     acceptorAgentId;
        address    rewardRecipient;  // address that receives COG on completion (e.g. claimer's wallet)
        uint256    createdAt;
        uint256    completedAt;
    }

    IERC20 public cogToken;
    uint256 public nextTaskId;
    mapping(uint256 => TaskInfo) public tasks;

    event TaskCreated(uint256 indexed taskId, address indexed poster, uint256 reward);
    event TaskAccepted(uint256 indexed taskId, address indexed acceptor, string acceptorAgentId);
    event TaskCompleted(uint256 indexed taskId, uint256 reward);
    event TaskCancelled(uint256 indexed taskId);

    constructor(address _cogToken) {
        cogToken = IERC20(_cogToken);
    }

    function createTask(
        string calldata posterAgentId,
        string calldata title,
        uint256 rewardAmount
    ) external returns (uint256) {
        require(rewardAmount > 0, "Reward must be > 0");
        require(cogToken.transferFrom(msg.sender, address(this), rewardAmount), "Escrow transfer failed");

        uint256 taskId = nextTaskId++;
        tasks[taskId] = TaskInfo({
            id: taskId,
            poster: msg.sender,
            posterAgentId: posterAgentId,
            title: title,
            rewardAmount: rewardAmount,
            status: TaskStatus.Open,
            acceptor: address(0),
            acceptorAgentId: "",
            rewardRecipient: address(0),
            createdAt: block.timestamp,
            completedAt: 0
        });

        emit TaskCreated(taskId, msg.sender, rewardAmount);
        return taskId;
    }

    function acceptTask(uint256 taskId, string calldata acceptorAgentId, address rewardRecipient) external {
        TaskInfo storage t = tasks[taskId];
        require(t.status == TaskStatus.Open, "Task not open");
        require(t.poster != msg.sender, "Cannot accept own task");
        require(rewardRecipient != address(0), "Reward recipient required");

        t.status = TaskStatus.Accepted;
        t.acceptor = msg.sender;
        t.acceptorAgentId = acceptorAgentId;
        t.rewardRecipient = rewardRecipient;

        emit TaskAccepted(taskId, msg.sender, acceptorAgentId);
    }

    function completeTask(uint256 taskId) external {
        TaskInfo storage t = tasks[taskId];
        require(t.status == TaskStatus.Accepted, "Task not accepted");
        require(t.poster == msg.sender, "Only poster can confirm completion");

        t.status = TaskStatus.Completed;
        t.completedAt = block.timestamp;

        address payoutTo = t.rewardRecipient != address(0) ? t.rewardRecipient : t.acceptor;
        require(cogToken.transfer(payoutTo, t.rewardAmount), "Reward transfer failed");

        emit TaskCompleted(taskId, t.rewardAmount);
    }

    function cancelTask(uint256 taskId) external {
        TaskInfo storage t = tasks[taskId];
        require(t.status == TaskStatus.Open, "Can only cancel open tasks");
        require(t.poster == msg.sender, "Only poster can cancel");

        t.status = TaskStatus.Cancelled;
        require(cogToken.transfer(t.poster, t.rewardAmount), "Refund failed");

        emit TaskCancelled(taskId);
    }

    function getTask(uint256 taskId) external view returns (TaskInfo memory) {
        return tasks[taskId];
    }
}
