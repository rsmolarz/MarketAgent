#!/usr/bin/env python3

import os
import sys
sys.path.append('.')

from data_sources.coinbase_client import CoinbaseClient
from data_sources.etherscan_client import EtherscanClient
from data_sources.github_client import GitHubClient

def test_coinbase():
    print("Testing Coinbase API...")
    try:
        client = CoinbaseClient()
        ticker = client.get_ticker('BTC/USD')
        if ticker:
            print(f"✓ Coinbase API working: BTC price = ${ticker.get('last', 'N/A')}")
            return True
        else:
            print("✗ Coinbase API returned no data")
            return False
    except Exception as e:
        print(f"✗ Coinbase API error: {e}")
        return False

def test_etherscan():
    print("Testing Etherscan API...")
    try:
        client = EtherscanClient()
        balance = client.get_eth_balance('0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045')  # Vitalik's address
        if balance is not None:
            print(f"✓ Etherscan API working: ETH balance = {balance}")
            return True
        else:
            print("✗ Etherscan API returned no data")
            return False
    except Exception as e:
        print(f"✗ Etherscan API error: {e}")
        return False

def test_github():
    print("Testing GitHub API...")
    try:
        client = GitHubClient()
        repo_info = client.get_repository_info('ethereum', 'go-ethereum')
        if repo_info:
            print(f"✓ GitHub API working: repo stars = {repo_info.get('stargazers_count', 'N/A')}")
            return True
        else:
            print("✗ GitHub API returned no data")
            return False
    except Exception as e:
        print(f"✗ GitHub API error: {e}")
        return False

def test_environment():
    print("Testing environment variables...")
    keys = ['COINBASE_API_KEY', 'COINBASE_SECRET', 'COINBASE_PASSPHRASE', 'ETHERSCAN_API_KEY', 'GITHUB_TOKEN']
    
    for key in keys:
        value = os.getenv(key)
        if value:
            print(f"✓ {key}: {'*' * min(len(value), 8)}...")
        else:
            print(f"✗ {key}: Not set")

if __name__ == "__main__":
    test_environment()
    print("\n" + "="*50)
    test_coinbase()
    print()
    test_etherscan()
    print()
    test_github()