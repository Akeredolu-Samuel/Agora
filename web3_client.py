import os
import requests
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

RPC_URL             = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
USDC_ADDRESS        = os.getenv("USDC_CONTRACT_ADDRESS")
EURC_ADDRESS        = os.getenv("EURC_CONTRACT_ADDRESS", "0x89B50855Aa3bE2F677cD6303Cec089B5F319D72a")
AGORAPAY_ADDRESS    = os.getenv("AGORAPAY_CONTRACT_ADDRESS")   # set after deploying AgoraPay.sol
ARCSCAN_API         = "https://testnet.arcscan.app/api"

web3 = Web3(Web3.HTTPProvider(RPC_URL))

# ---------------------------------------------------------------------------
# ABIs
# ---------------------------------------------------------------------------

ERC20_ABI = [
    {"constant": False,
     "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": False,
     "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True,
     "inputs": [{"name": "_owner", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True,
     "inputs": [],
     "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
]

AGORAPAY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "token",  "type": "address"},
            {"internalType": "address", "name": "to",     "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "string",  "name": "memo",   "type": "string"},
        ],
        "name": "processPayment",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "internalType": "address", "name": "from",   "type": "address"},
            {"indexed": True,  "internalType": "address", "name": "to",     "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
            {"indexed": True,  "internalType": "address", "name": "token",  "type": "address"},
            {"indexed": False, "internalType": "string",  "name": "memo",   "type": "string"},
        ],
        "name": "PaymentProcessed",
        "type": "event",
    },
]

TOKEN_MAP = {
    "usdc": USDC_ADDRESS,
    "eurc": EURC_ADDRESS,
}

# ---------------------------------------------------------------------------
# Wallet generation
# ---------------------------------------------------------------------------

def generate_wallet() -> tuple[str, str]:
    """Return (address, private_key) for a brand-new EVM wallet."""
    account = Account.create()
    return account.address, account.key.hex()


# ---------------------------------------------------------------------------
# Balances
# ---------------------------------------------------------------------------

def get_usdc_balance(address: str) -> float:
    """USDC ERC-20 balance (6 decimals on Arc)."""
    return _erc20_balance(USDC_ADDRESS, address)

def get_eurc_balance(address: str) -> float:
    """EURC ERC-20 balance."""
    return _erc20_balance(EURC_ADDRESS, address)

def get_native_balance(address: str) -> float:
    """Native Arc gas balance in USDC (18-decimal native token)."""
    try:
        raw = web3.eth.get_balance(Web3.to_checksum_address(address))
        return raw / (10 ** 18)
    except Exception as e:
        print(f"Error fetching native balance: {e}")
        return 0.0

def _erc20_balance(contract_address: str, wallet: str) -> float:
    if not contract_address:
        return 0.0
    try:
        contract = web3.eth.contract(
            address=Web3.to_checksum_address(contract_address), abi=ERC20_ABI
        )
        raw      = contract.functions.balanceOf(Web3.to_checksum_address(wallet)).call()
        decimals = contract.functions.decimals().call()
        return raw / (10 ** decimals)
    except Exception as e:
        print(f"Error fetching ERC-20 balance for {contract_address}: {e}")
        return 0.0


# ---------------------------------------------------------------------------
# Approve helper
# ---------------------------------------------------------------------------

def approve_token(private_key: str, token_address: str, spender: str, amount_raw: int) -> str:
    """Grant `spender` an allowance of `amount_raw` for `token_address`. Returns tx hash."""
    account  = Account.from_key(private_key)
    contract = web3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
    tx = contract.functions.approve(
        Web3.to_checksum_address(spender), amount_raw
    ).build_transaction({
        'chainId':  web3.eth.chain_id,
        'gas':      80_000,
        'gasPrice': web3.eth.gas_price,
        'nonce':    web3.eth.get_transaction_count(account.address),
    })
    signed = web3.eth.account.sign_transaction(tx, private_key=private_key)
    raw    = getattr(signed, 'raw_transaction', None) or signed.rawTransaction
    tx_hash = web3.eth.send_raw_transaction(raw)
    # Wait for confirmation
    web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    return web3.to_hex(tx_hash)


# ---------------------------------------------------------------------------
# Send via AgoraPay contract (tracked on-chain)
# ---------------------------------------------------------------------------

def send_usdc(private_key: str, to_address: str, amount: float, memo: str = "send") -> str:
    """
    Route a USDC payment through the AgoraPay contract so it is logged on-chain.
    Falls back to a direct ERC-20 transfer if AGORAPAY_CONTRACT_ADDRESS is not set.
    """
    if not USDC_ADDRESS:
        raise ValueError("USDC_CONTRACT_ADDRESS not set in .env")

    usdc_contract = web3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI
    )
    decimals   = usdc_contract.functions.decimals().call()
    amount_raw = int(amount * (10 ** decimals))
    account    = Account.from_key(private_key)

    if AGORAPAY_ADDRESS:
        # Step 1: approve AgoraPay to spend
        approve_token(private_key, USDC_ADDRESS, AGORAPAY_ADDRESS, amount_raw)

        # Step 2: call processPayment
        agora = web3.eth.contract(
            address=Web3.to_checksum_address(AGORAPAY_ADDRESS), abi=AGORAPAY_ABI
        )
        tx = agora.functions.processPayment(
            Web3.to_checksum_address(USDC_ADDRESS),
            Web3.to_checksum_address(to_address),
            amount_raw,
            memo,
        ).build_transaction({
            'chainId':  web3.eth.chain_id,
            'gas':      200_000,
            'gasPrice': web3.eth.gas_price,
            'nonce':    web3.eth.get_transaction_count(account.address),
        })
    else:
        # Fallback: direct ERC-20 transfer
        tx = usdc_contract.functions.transfer(
            Web3.to_checksum_address(to_address), amount_raw
        ).build_transaction({
            'chainId':  web3.eth.chain_id,
            'gas':      100_000,
            'gasPrice': web3.eth.gas_price,
            'nonce':    web3.eth.get_transaction_count(account.address),
        })

    signed  = web3.eth.account.sign_transaction(tx, private_key=private_key)
    raw     = getattr(signed, 'raw_transaction', None) or signed.rawTransaction
    tx_hash = web3.eth.send_raw_transaction(raw)
    return web3.to_hex(tx_hash)


# ---------------------------------------------------------------------------
# Transaction history via ArcScan API
# ---------------------------------------------------------------------------

def get_transaction_history(wallet_address: str, limit: int = 10) -> list[dict]:
    """
    Fetch recent ERC-20 token transfers for the given wallet from ArcScan.
    Returns a list of dicts: {type, amount, symbol, counterparty, tx_hash, timestamp}
    """
    try:
        params = {
            "module":  "account",
            "action":  "tokentx",
            "address": wallet_address,
            "page":    1,
            "offset":  limit,
            "sort":    "desc",
        }
        resp = requests.get(ARCSCAN_API, params=params, timeout=10)
        data = resp.json()
        if data.get("status") != "1":
            return []

        history = []
        wallet_lower = wallet_address.lower()
        for tx in data.get("result", []):
            is_outgoing = tx["from"].lower() == wallet_lower
            decimals    = int(tx.get("tokenDecimal", 6))
            amount      = int(tx["value"]) / (10 ** decimals)
            symbol      = tx.get("tokenSymbol", "TOKEN")
            counterparty = tx["to"] if is_outgoing else tx["from"]
            # Shorten address for display
            short = counterparty[:6] + "..." + counterparty[-4:]
            history.append({
                "type":         "Sent" if is_outgoing else "Received",
                "amount":       round(amount, 4),
                "symbol":       symbol,
                "counterparty": short,
                "tx_hash":      tx["hash"],
            })
        return history
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []
