"""
Etherscan API Client

Provides access to Ethereum blockchain data including transactions,
wallet balances, and smart contract information.
"""

import requests
import logging
from typing import Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)

class EtherscanClient:
    """
    Client for Etherscan API data
    """
    
    def __init__(self):
        self.api_key = Config.ETHERSCAN_API_KEY
        self.base_url = "https://api.etherscan.io/api"
        self.session = requests.Session()
    
    def get_account_balance(self, address: str) -> Optional[float]:
        """
        Get ETH balance for an address
        
        Args:
            address: Ethereum address
            
        Returns:
            Balance in ETH or None
        """
        try:
            params = {
                'module': 'account',
                'action': 'balance',
                'address': address,
                'tag': 'latest',
                'apikey': self.api_key
            }
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == '1':
                # Convert wei to ETH
                balance_wei = int(data.get('result', '0'))
                balance_eth = balance_wei / 1e18
                return balance_eth
                
        except Exception as e:
            logger.error(f"Error getting balance for {address}: {e}")
            
        return None
    
    def get_transactions(self, address: str, limit: int = 10) -> Optional[List[Dict]]:
        """
        Get recent transactions for an address
        
        Args:
            address: Ethereum address
            limit: Number of transactions to fetch
            
        Returns:
            List of transaction data or None
        """
        try:
            params = {
                'module': 'account',
                'action': 'txlist',
                'address': address,
                'startblock': 0,
                'endblock': 99999999,
                'page': 1,
                'offset': limit,
                'sort': 'desc',
                'apikey': self.api_key
            }
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == '1':
                return data.get('result', [])
                
        except Exception as e:
            logger.error(f"Error getting transactions for {address}: {e}")
            
        return None
    
    def get_internal_transactions(self, address: str, limit: int = 10) -> Optional[List[Dict]]:
        """
        Get internal transactions for an address
        
        Args:
            address: Ethereum address
            limit: Number of transactions to fetch
            
        Returns:
            List of internal transaction data or None
        """
        try:
            params = {
                'module': 'account',
                'action': 'txlistinternal',
                'address': address,
                'startblock': 0,
                'endblock': 99999999,
                'page': 1,
                'offset': limit,
                'sort': 'desc',
                'apikey': self.api_key
            }
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == '1':
                return data.get('result', [])
                
        except Exception as e:
            logger.error(f"Error getting internal transactions for {address}: {e}")
            
        return None
    
    def get_token_transfers(self, address: str, contract_address: str = None, limit: int = 10) -> Optional[List[Dict]]:
        """
        Get ERC-20 token transfers for an address
        
        Args:
            address: Ethereum address
            contract_address: Token contract address (optional)
            limit: Number of transfers to fetch
            
        Returns:
            List of token transfer data or None
        """
        try:
            params = {
                'module': 'account',
                'action': 'tokentx',
                'address': address,
                'startblock': 0,
                'endblock': 99999999,
                'page': 1,
                'offset': limit,
                'sort': 'desc',
                'apikey': self.api_key
            }
            
            if contract_address:
                params['contractaddress'] = contract_address
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == '1':
                return data.get('result', [])
                
        except Exception as e:
            logger.error(f"Error getting token transfers for {address}: {e}")
            
        return None
    
    def get_transaction_details(self, tx_hash: str) -> Optional[Dict]:
        """
        Get details for a specific transaction
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Transaction details or None
        """
        try:
            params = {
                'module': 'proxy',
                'action': 'eth_getTransactionByHash',
                'txhash': tx_hash,
                'apikey': self.api_key
            }
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            return data.get('result')
                
        except Exception as e:
            logger.error(f"Error getting transaction details for {tx_hash}: {e}")
            
        return None
    
    def get_gas_price(self) -> Optional[float]:
        """
        Get current gas price
        
        Returns:
            Gas price in Gwei or None
        """
        try:
            params = {
                'module': 'gastracker',
                'action': 'gasoracle',
                'apikey': self.api_key
            }
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == '1':
                result = data.get('result', {})
                return float(result.get('ProposeGasPrice', 0))
                
        except Exception as e:
            logger.error(f"Error getting gas price: {e}")
            
        return None
    
    def get_contract_abi(self, contract_address: str) -> Optional[str]:
        """
        Get ABI for a verified contract
        
        Args:
            contract_address: Contract address
            
        Returns:
            Contract ABI or None
        """
        try:
            params = {
                'module': 'contract',
                'action': 'getabi',
                'address': contract_address,
                'apikey': self.api_key
            }
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == '1':
                return data.get('result')
                
        except Exception as e:
            logger.error(f"Error getting contract ABI for {contract_address}: {e}")
            
        return None
