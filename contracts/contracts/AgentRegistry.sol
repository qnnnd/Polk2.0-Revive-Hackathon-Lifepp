// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title AgentRegistry
 * @notice On-chain registry for Life++ AI agents.
 *         Stores agent metadata hashes and owner mapping.
 */
contract AgentRegistry {
    struct AgentInfo {
        address owner;
        string  agentId;       // off-chain UUID
        string  name;
        string  metadataURI;   // IPFS or HTTP link to full metadata
        uint256 registeredAt;
        bool    active;
    }

    mapping(string => AgentInfo) public agents;   // agentId => info
    string[] public agentIds;

    event AgentRegistered(string indexed agentId, address indexed owner, string name);
    event AgentDeactivated(string indexed agentId);

    function register(
        string calldata agentId,
        string calldata name,
        string calldata metadataURI
    ) external {
        require(agents[agentId].registeredAt == 0, "Agent already registered");
        agents[agentId] = AgentInfo({
            owner: msg.sender,
            agentId: agentId,
            name: name,
            metadataURI: metadataURI,
            registeredAt: block.timestamp,
            active: true
        });
        agentIds.push(agentId);
        emit AgentRegistered(agentId, msg.sender, name);
    }

    function deactivate(string calldata agentId) external {
        require(agents[agentId].owner == msg.sender, "Not owner");
        agents[agentId].active = false;
        emit AgentDeactivated(agentId);
    }

    function getAgent(string calldata agentId) external view returns (AgentInfo memory) {
        return agents[agentId];
    }

    function totalAgents() external view returns (uint256) {
        return agentIds.length;
    }
}
