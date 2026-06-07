// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IERC20 {
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
}

/**
 * @title AgoraPay
 * @notice Central payment router for the Agora Telegram Bot.
 * All bot-processed payments go through this contract, emitting
 * PaymentProcessed events that act as an on-chain transaction ledger.
 */
contract AgoraPay {

    address public owner;

    // Emitted on every bot-routed payment — your on-chain transaction log
    event PaymentProcessed(
        address indexed from,
        address indexed to,
        uint256 amount,
        address indexed token,
        string memo        // optional label e.g. "tip", "send", "swap"
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice Route a token payment through the contract so it is logged on-chain.
     * Caller must have approved this contract to spend `amount` of `token` first.
     * @param token   ERC-20 token address (e.g. USDC)
     * @param to      Recipient address
     * @param amount  Raw token amount (already adjusted for decimals)
     * @param memo    Short label for the payment type ("send", "tip", "swap")
     */
    function processPayment(
        address token,
        address to,
        uint256 amount,
        string calldata memo
    ) external {
        require(to != address(0), "Invalid recipient");
        require(amount > 0, "Amount must be greater than 0");

        bool success = IERC20(token).transferFrom(msg.sender, to, amount);
        require(success, "Token transfer failed");

        emit PaymentProcessed(msg.sender, to, amount, token, memo);
    }
}
