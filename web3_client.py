import os
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
USDC_ADDRESS = os.getenv("USDC_CONTRACT_ADDRESS")

web3 = Web3(Web3.HTTPProvider(RPC_URL))

# Standard ERC-20 Transfer ABI
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

def generate_wallet():
    """Generates a new EVM wallet and returns (address, private_key)"""
    account = Account.create()
    return account.address, account.key.hex()

def get_usdc_balance(address: str) -> float:
    """Gets the USDC balance of an address"""
    if not USDC_ADDRESS:
        return 0.0
    
    try:
        contract = web3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
        balance_raw = contract.functions.balanceOf(Web3.to_checksum_address(address)).call()
        decimals = contract.functions.decimals().call()
        return balance_raw / (10 ** decimals)
    except Exception as e:
        print(f"Error fetching balance: {e}")
        return 0.0

def send_usdc(private_key: str, to_address: str, amount: float) -> str:
    """
    Sends USDC on the Arc network.
    Returns the transaction hash or raises an exception.
    """
    if not USDC_ADDRESS:
        raise ValueError("USDC_CONTRACT_ADDRESS not configured in .env")

    account = Account.from_key(private_key)
    contract = web3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
    
    # Get decimals to format amount correctly
    decimals = contract.functions.decimals().call()
    amount_raw = int(amount * (10 ** decimals))
    
    to_address_checksum = Web3.to_checksum_address(to_address)
    
    # Build transaction
    tx = contract.functions.transfer(to_address_checksum, amount_raw).build_transaction({
        'chainId': web3.eth.chain_id,
        'gas': 100000,
        'gasPrice': web3.eth.gas_price,
        'nonce': web3.eth.get_transaction_count(account.address),
    })
    
    # Sign transaction
    signed_tx = web3.eth.account.sign_transaction(tx, private_key=private_key)
    
    # Broadcast transaction (web3 v6 uses raw_transaction, v5 used rawTransaction)
    raw = getattr(signed_tx, 'raw_transaction', None) or getattr(signed_tx, 'rawTransaction', None)
    tx_hash = web3.eth.send_raw_transaction(raw)
    return web3.to_hex(tx_hash)

