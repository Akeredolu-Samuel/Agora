# Agora Arc Pay Bot 🚀

Agora Arc Pay Bot is a natural-language-powered Web3 payment assistant running on Telegram. It enables users to securely manage wallets, save contacts, and transfer USDC seamlessly across the **Arc Blockchain Network** using simple, everyday natural language.

---

## 🌟 Key Features

- **Instant Wallet Generation:** Creates a secure EVM-compatible wallet on the Arc testnet upon start.
- **Natural Language Parsing:** Powered by DeepSeek NLP, users can interact normally (e.g., *"pay 10 usdc to David"* or *"save address 0x... for Alice"*).
- **Secure Key Management:** Includes an interactive on-demand message deletion mechanism to hide private keys after saving them.
- **ERC-20 Compatibility:** Automated on-chain transfers targeting the official USDC contract address on Arc Testnet.
- **ArcScan Links:** Returns direct transaction tracking links for verified transparency.

---

## 🛠️ Tech Stack & Architecture

- **Runtime:** Python 3.13+
- **Smart Contract:** Solidity (compiled via `solc` 0.8.19)
- **Web3 Interface:** `Web3.py` v7.x (EVM connection, transaction signing, and execution)
- **AI Processing:** OpenAI SDK / OpenRouter API (`deepseek-chat` model)
- **Bot Engine:** `python-telegram-bot` (v21.1+)

---

## ⚙️ Configuration (.env)

The bot requires the following environment variables to run:
- `TELEGRAM_BOT_TOKEN`: The API token for your Telegram Bot.
- `OPENROUTER_API_KEY`: API Key for OpenRouter to access DeepSeek.
- `ARC_RPC_URL`: The RPC endpoint for the Arc Testnet (`https://rpc.testnet.arc.network`).
- `USDC_CONTRACT_ADDRESS`: The ERC-20 system address (`0x3600000000000000000000000000000000000000`).

---

## 📂 Project Structure

```
├── AgoraPay.sol          # Solidity Smart Contract
├── db.py                 # SQLite database layer (contacts & user wallets)
├── deploy.py             # Contract deployment script
├── main.py               # Main Telegram bot polling loop & callback handlers
├── nlp.py                # DeepSeek natural language engine
├── web3_client.py        # Web3 client for gas estimation & USDC transfers
├── requirements.txt      # Project dependencies
└── Procfile              # Heroku deployment configuration (worker process)
```

---

## 🔒 Security First

All sensitive environment configurations (such as `.env` and local database files `*.db`) are strictly protected via `.gitignore` to prevent any credentials leaking to public repositories.
