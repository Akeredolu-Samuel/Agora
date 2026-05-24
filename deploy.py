import os
from web3 import Web3
from eth_account import Account
import solcx
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
web3 = Web3(Web3.HTTPProvider(RPC_URL))

# Path to the manually downloaded solc binary
SOLC_BINARY = os.path.join(os.path.expanduser("~"), ".solcx", "solc-v0.8.19.exe")

def deploy_contract():
    print(f"Using solc binary: {SOLC_BINARY}")
    if not os.path.exists(SOLC_BINARY):
        raise FileNotFoundError(f"solc binary not found at {SOLC_BINARY}. Please download it manually.")

    print("Compiling AgoraPay.sol...")
    with open("AgoraPay.sol", "r") as file:
        source_code = file.read()

    compiled_sol = solcx.compile_standard(
        {
            "language": "Solidity",
            "sources": {"AgoraPay.sol": {"content": source_code}},
            "settings": {
                "outputSelection": {
                    "*": {
                        "*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]
                    }
                }
            },
        },
        solc_binary=SOLC_BINARY,
    )

    bytecode = compiled_sol["contracts"]["AgoraPay.sol"]["AgoraPay"]["evm"]["bytecode"]["object"]
    abi = compiled_sol["contracts"]["AgoraPay.sol"]["AgoraPay"]["abi"]

    print("Loading deployer wallet...")
    deployer_key = os.getenv("DEPLOYER_PRIVATE_KEY")
    
    if deployer_key:
        account = Account.from_key(deployer_key)
        print(f"Using provided Deployer Wallet Address: {account.address}")
    else:
        print("No DEPLOYER_PRIVATE_KEY found in .env. Generating a new wallet...")
        account = Account.create()
        print(f"Deployer Wallet Address: {account.address}")
        print(f"Deployer Private Key: {account.key.hex()}")
        print("\n🚨 Please fund this Deployer Wallet with native Arc tokens to pay for gas, then press Enter to deploy...")
        input()

    AgoraPay = web3.eth.contract(abi=abi, bytecode=bytecode)

    print("Building deployment transaction...")
    nonce = web3.eth.get_transaction_count(account.address)
    tx = AgoraPay.constructor().build_transaction(
        {
            "chainId": web3.eth.chain_id,
            "gasPrice": web3.eth.gas_price,
            "from": account.address,
            "nonce": nonce,
        }
    )

    print("Signing and sending transaction...")
    signed_tx = web3.eth.account.sign_transaction(tx, private_key=account.key.hex())
    raw = getattr(signed_tx, 'raw_transaction', None) or getattr(signed_tx, 'rawTransaction', None)
    tx_hash = web3.eth.send_raw_transaction(raw)
    
    print(f"Deployment Tx Hash: https://testnet.arcscan.app/tx/{web3.to_hex(tx_hash)}")
    
    print("Waiting for receipt...")
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    print("\n[OK] Contract Deployed Successfully!")
    print(f"Contract Address: {tx_receipt.contractAddress}")
    print("\nNext Steps:")
    print(f"If you want the bot to use this contract, replace USDC_CONTRACT_ADDRESS in .env with {tx_receipt.contractAddress} (though currently the bot transfers USDC directly).")

if __name__ == "__main__":
    deploy_contract()
