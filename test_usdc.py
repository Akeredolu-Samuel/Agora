import os
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
USDC_ADDRESS = os.getenv("USDC_CONTRACT_ADDRESS", "0x3600000000000000000000000000000000000000")

web3 = Web3(Web3.HTTPProvider(RPC_URL))

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

try:
    contract = web3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
    decimals = contract.functions.decimals().call()
    print("Decimals:", decimals)
except Exception as e:
    print("Error calling decimals:", e)
