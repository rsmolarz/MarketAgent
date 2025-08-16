
import requests

ETHERSCAN_API_KEY = "YourApiKeyHere"

def get_large_eth_transfers(min_eth=100):
    # Simulated large transfers (in real use, use Etherscan API)
    # Replace this function with actual API logic if key is provided
    # Example endpoint: https://api.etherscan.io/api?module=account&action=txlist&address=...&apikey=...
    return [{"wallet": "0x123...", "amount": 25000, "asset": "ETH"}]
