"""
Whale Wallet Watcher Agent

Monitors large cryptocurrency wallets for significant movements
that could indicate insider activity or market manipulation.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.etherscan_client import EtherscanClient
from config import Config

class WhaleWalletWatcherAgent(BaseAgent):
    """
    Monitors whale wallets for large transactions and movements
    """
    
    def __init__(self):
        super().__init__()
        self.etherscan_client = EtherscanClient()
        
        # Known whale addresses to monitor
        self.whale_addresses = [
            '0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a',  # Binance Cold Wallet
            '0x28C6c06298d514Db089934071355E5743bf21d60',  # Binance Hot Wallet
            '0x2FAF487A4414Fe77e2327F0bf4AE2a264a776AD2',  # FTX Cold Wallet
            '0x9696f59E4d72E237BE84fFD425DCaD154Bf96976',  # Coinbase Wallet
            '0x503828976D22510aad0201ac7EC88293211D23Da',  # Coinbase Wallet 2
        ]
        
        self.min_whale_amount = Config.WHALE_WALLET_THRESHOLD  # ETH
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze whale wallet activities for suspicious patterns
        """
        from services.api_toggle import api_guard
        if not api_guard("etherscan", "whale wallet Etherscan data"):
            return []

        findings = []
        
        if not self.validate_config(['ETHERSCAN_API_KEY']):
            self.logger.warning("Etherscan API key not configured")
            return findings
        
        for address in self.whale_addresses:
            try:
                # Get recent transactions
                transactions = self.etherscan_client.get_transactions(address, limit=10)
                if not transactions:
                    continue
                
                # Analyze transaction patterns
                findings.extend(self._analyze_large_transfers(address, transactions))
                findings.extend(self._analyze_unusual_activity(address, transactions))
                
            except Exception as e:
                self.logger.error(f"Error analyzing whale address {address}: {e}")
                
        return findings
    
    def _analyze_large_transfers(self, address: str, transactions: List[Dict]) -> List[Dict[str, Any]]:
        """Analyze for unusually large transfers"""
        findings = []
        
        for tx in transactions:
            try:
                # Convert wei to ETH
                value_eth = float(tx.get('value', '0')) / 1e18
                
                if value_eth >= self.min_whale_amount:
                    # Determine severity based on amount
                    if value_eth >= self.min_whale_amount * 10:
                        severity = 'critical'
                        confidence = 0.9
                    elif value_eth >= self.min_whale_amount * 5:
                        severity = 'high'
                        confidence = 0.8
                    else:
                        severity = 'medium'
                        confidence = 0.7
                    
                    # Check if it's incoming or outgoing
                    is_outgoing = tx.get('from', '').lower() == address.lower()
                    direction = 'outgoing' if is_outgoing else 'incoming'
                    
                    findings.append(self.create_finding(
                        title=f"Large Whale Transaction Detected",
                        description=f"Whale wallet moved {value_eth:,.2f} ETH ({direction}). "
                                   f"Hash: {tx.get('hash', 'unknown')}",
                        severity=severity,
                        confidence=confidence,
                        symbol='ETH',
                        market_type='crypto',
                        metadata={
                            'whale_address': address,
                            'amount_eth': value_eth,
                            'direction': direction,
                            'tx_hash': tx.get('hash'),
                            'gas_price': tx.get('gasPrice'),
                            'to_address': tx.get('to'),
                            'from_address': tx.get('from')
                        }
                    ))
                    
            except Exception as e:
                self.logger.error(f"Error analyzing transaction: {e}")
                
        return findings
    
    def _analyze_unusual_activity(self, address: str, transactions: List[Dict]) -> List[Dict[str, Any]]:
        """Analyze for unusual activity patterns"""
        findings = []
        
        if len(transactions) < 3:
            return findings
        
        try:
            # Calculate transaction frequency
            timestamps = []
            for tx in transactions:
                try:
                    timestamp = int(tx.get('timeStamp', 0))
                    timestamps.append(timestamp)
                except (ValueError, TypeError):
                    continue
            
            if len(timestamps) < 2:
                return findings
                
            timestamps.sort()
            
            # Check for rapid-fire transactions (multiple tx in short time)
            rapid_count = 0
            for i in range(1, len(timestamps)):
                time_diff = timestamps[i] - timestamps[i-1]
                if time_diff < 300:  # Less than 5 minutes apart
                    rapid_count += 1
            
            if rapid_count >= 3:
                findings.append(self.create_finding(
                    title="Rapid Whale Transactions Detected",
                    description=f"Whale wallet executed {rapid_count + 1} transactions "
                               f"within short time periods. This could indicate coordinated activity.",
                    severity='medium',
                    confidence=0.6,
                    symbol='ETH',
                    market_type='crypto',
                    metadata={
                        'whale_address': address,
                        'rapid_tx_count': rapid_count + 1,
                        'analysis_window': '10 recent transactions'
                    }
                ))
            
            # Check for consistent amounts (possible automation/bots)
            amounts = []
            for tx in transactions:
                try:
                    value_eth = float(tx.get('value', '0')) / 1e18
                    if value_eth > 0:
                        amounts.append(value_eth)
                except (ValueError, TypeError):
                    continue
            
            if len(amounts) >= 3:
                # Check if amounts are suspiciously similar
                avg_amount = sum(amounts) / len(amounts)
                similar_count = sum(1 for amt in amounts if abs(amt - avg_amount) / avg_amount < 0.1)
                
                if similar_count >= 3 and avg_amount > 10:  # 3+ similar amounts > 10 ETH
                    findings.append(self.create_finding(
                        title="Suspicious Uniform Whale Transactions",
                        description=f"Whale wallet executed {similar_count} transactions "
                                   f"with similar amounts (~{avg_amount:.2f} ETH). "
                                   f"This pattern suggests automated or coordinated activity.",
                        severity='medium',
                        confidence=0.7,
                        symbol='ETH',
                        market_type='crypto',
                        metadata={
                            'whale_address': address,
                            'similar_tx_count': similar_count,
                            'average_amount': avg_amount,
                            'amounts': amounts[:5]  # First 5 amounts for reference
                        }
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error analyzing activity patterns: {e}")
            
        return findings
