"""
Data Sources Module

Contains clients for various external data sources including
market data, blockchain data, and alternative data sources.
"""

from .coinbase_client import CoinbaseClient
from .etherscan_client import EtherscanClient
from .github_client import GitHubClient
from .yahoo_finance_client import YahooFinanceClient

__all__ = [
    'CoinbaseClient',
    'EtherscanClient', 
    'GitHubClient',
    'YahooFinanceClient'
]
