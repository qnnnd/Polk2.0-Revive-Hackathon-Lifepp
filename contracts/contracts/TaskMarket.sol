// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title TaskMarket
 * @notice Marketplace for agent tasks with native IVE token escrow.
 *         Flow: create (send IVE) → accept → complete (release IVE to rewardRecipient).
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
        address    rewardRecipient;
        uint256    createdAt;
        uint256    completedAt;
    }

    uint256 public nextTaskId;
    mapping(uint256 => TaskInfo) public tasks;

    /// @dev Relayer (e.g. backend) can accept on behalf of users so backend can submit accept tx without user signing.
    address public relayer;

    constructor() {
        relayer = msg.sender;
    }

    event TaskCreated(uint256 indexed taskId, address indexed poster, uint256 reward);
    event TaskAccepted(uint256 indexed taskId, address indexed acceptor, string acceptorAgentId);
    event TaskCompleted(uint256 indexed taskId, uint256 reward);
    event TaskCancelled(uint256 indexed taskId);

    function createTask(
        string calldata posterAgentId,
        string calldata title,
        uint256 rewardAmount
    ) external payable returns (uint256) {
        require(rewardAmount > 0, "Reward must be > 0");
        require(msg.value == rewardAmount, "Send exact reward amount as IVE");

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

    /// @notice Relayer (backend) accepts the task on behalf of acceptorAddress. Caller must be relayer.
    function acceptTaskFor(
        uint256 taskId,
        string calldata acceptorAgentId,
        address rewardRecipient,
        address acceptorAddress
    ) external {
        require(msg.sender == relayer, "Only relayer");
        TaskInfo storage t = tasks[taskId];
        require(t.status == TaskStatus.Open, "Task not open");
        require(acceptorAddress != address(0) && acceptorAddress != t.poster, "Invalid acceptor");
        require(rewardRecipient != address(0), "Reward recipient required");

        t.status = TaskStatus.Accepted;
        t.acceptor = acceptorAddress;
        t.acceptorAgentId = acceptorAgentId;
        t.rewardRecipient = rewardRecipient;

        emit TaskAccepted(taskId, acceptorAddress, acceptorAgentId);
    }

    function completeTask(uint256 taskId) external {
        TaskInfo storage t = tasks[taskId];
        require(t.status == TaskStatus.Accepted, "Task not accepted");
        require(t.poster == msg.sender, "Only poster can confirm completion");

        _completeTaskLogic(taskId, t);
    }

    /// @notice Relayer can complete on behalf of the poster (e.g. when poster is a frontend user and backend submits).
    function completeTaskFor(uint256 taskId) external {
        require(msg.sender == relayer, "Only relayer");
        TaskInfo storage t = tasks[taskId];
        require(t.status == TaskStatus.Accepted, "Task not accepted");

        _completeTaskLogic(taskId, t);
    }

    function _completeTaskLogic(uint256 taskId, TaskInfo storage t) internal {
        t.status = TaskStatus.Completed;
        t.completedAt = block.timestamp;

        address payoutTo = t.rewardRecipient != address(0) ? t.rewardRecipient : t.acceptor;
        (bool ok, ) = payable(payoutTo).call{ value: t.rewardAmount }("");
        require(ok, "Reward transfer failed");

        emit TaskCompleted(taskId, t.rewardAmount);
    }

    function cancelTask(uint256 taskId) external {
        TaskInfo storage t = tasks[taskId];
        require(t.status == TaskStatus.Open, "Can only cancel open tasks");
        require(t.poster == msg.sender, "Only poster can cancel");

        t.status = TaskStatus.Cancelled;
        (bool ok, ) = payable(t.poster).call{ value: t.rewardAmount }("");
        require(ok, "Refund failed");

        emit TaskCancelled(taskId);
    }

    function getTask(uint256 taskId) external view returns (TaskInfo memory) {
        return tasks[taskId];
    }
}
