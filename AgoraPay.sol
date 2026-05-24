// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IERC20 {
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract AgoraPay {
    event PaymentProcessed(address indexed from, address indexed to, uint256 amount, address token);

    // This function allows users to send USDC via the AgoraPay contract.
    // The user MUST have approved the AgoraPay contract to spend their USDC first.
    function processPayment(address token, address to, uint256 amount) external {
        require(to != address(0), "Invalid recipient");
        require(amount > 0, "Amount must be greater than 0");

        // Transfer funds from sender to recipient
        bool success = IERC20(token).transferFrom(msg.sender, to, amount);
        require(success, "Token transfer failed");

        emit PaymentProcessed(msg.sender, to, amount, token);
    }
}
