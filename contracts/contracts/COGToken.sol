// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title COGToken
 * @notice ERC-20 utility token for the Life++ Agent Economy.
 *         Fixed supply minted to deployer; used for task rewards & escrow.
 */
contract COGToken is ERC20, Ownable {
    uint256 public constant INITIAL_SUPPLY = 1_000_000 * 1e18;

    constructor() ERC20("Cognitive Token", "COG") Ownable(msg.sender) {
        _mint(msg.sender, INITIAL_SUPPLY);
    }

    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }
}
