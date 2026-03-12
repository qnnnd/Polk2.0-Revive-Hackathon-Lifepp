// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title Reputation
 * @notice On-chain reputation tracking for Life++ agents.
 *         Records task completion events and computes aggregate scores.
 */
contract Reputation {
    struct AgentRep {
        uint256 tasksCompleted;
        uint256 tasksFailed;
        uint256 totalCogEarned;
        uint256 endorsements;
        uint256 lastUpdated;
    }

    mapping(string => AgentRep) public reputations;  // agentId => rep

    event ReputationUpdated(string indexed agentId, string eventType, int256 delta);

    function recordTaskComplete(string calldata agentId, uint256 cogEarned) external {
        AgentRep storage rep = reputations[agentId];
        rep.tasksCompleted += 1;
        rep.totalCogEarned += cogEarned;
        rep.lastUpdated = block.timestamp;
        emit ReputationUpdated(agentId, "task_complete", int256(cogEarned));
    }

    function recordTaskFailed(string calldata agentId) external {
        AgentRep storage rep = reputations[agentId];
        rep.tasksFailed += 1;
        rep.lastUpdated = block.timestamp;
        emit ReputationUpdated(agentId, "task_failed", -1);
    }

    function endorse(string calldata agentId) external {
        AgentRep storage rep = reputations[agentId];
        rep.endorsements += 1;
        rep.lastUpdated = block.timestamp;
        emit ReputationUpdated(agentId, "endorsement", 1);
    }

    function getReputation(string calldata agentId) external view returns (AgentRep memory) {
        return reputations[agentId];
    }

    function getScore(string calldata agentId) external view returns (uint256) {
        AgentRep storage rep = reputations[agentId];
        uint256 total = rep.tasksCompleted + rep.tasksFailed;
        if (total == 0) return 100;
        return (rep.tasksCompleted * 100) / total;
    }
}
