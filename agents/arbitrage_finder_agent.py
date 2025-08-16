"""
Arbitrage Finder Agent

Detects arbitrage opportunities across cryptocurrency exchanges
by comparing prices for the same assets.
"""

import ccxt
from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.binance_client import BinanceClient
from config import Config

class ArbitrageFinderAgent(BaseAgent):
    """
    Finds arbitrage opportunities across crypto exchanges
    """
    
    def __init__(self):
        super().__init__()
        self.binance_client = BinanceClient()
        
        # Initialize exchanges
        self.exchanges = self._initialize_exchanges()
        
        # Common trading pairs to check
        self.trading_pairs = [
            'BTC/USDT',
            'ETH/USDT', 
            'BNB/USDT',
            'ADA/USDT',
            'SOL/USDT',
            'MATIC/USDT'
        ]
        
        self.min_profit_threshold = Config.ARBITRAGE_PROFIT_THRESHOLD
    
    def _initialize_exchanges(self) -> Dict[str, ccxt.Exchange]:
        """Initialize exchange connections"""
        exchanges = {}
        
        try:
            # Binance
            exchanges['binance'] = ccxt.binance({
                'apiKey': Config.BINANCE_API_KEY,
                'secret': Config.BINANCE_SECRET,
                'sandbox': False,
                'enableRateLimit': True,
            })
            
            # Public-only exchanges (no API keys needed)
            exchanges['coinbase'] = ccxt.coinbasepro({
                'sandbox': False,
                'enableRateLimit': True,
            })
            
            exchanges['kraken'] = ccxt.kraken({
                'sandbox': False,
                'enableRateLimit': True,
            })
            
            exchanges['kucoin'] = ccxt.kucoin({
                'sandbox': False,
                'enableRateLimit': True,
            })
            
        except Exception as e:
            self.logger.error(f"Error initializing exchanges: {e}")
            
        return exchanges
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Find arbitrage opportunities across exchanges
        """
        findings = []
        
        for pair in self.trading_pairs:
            try:
                # Get prices from all exchanges
                prices = self._get_prices_for_pair(pair)
                
                if len(prices) < 2:
                    continue
                
                # Find arbitrage opportunities
                opportunities = self._find_arbitrage_opportunities(pair, prices)
                findings.extend(opportunities)
                
            except Exception as e:
                self.logger.error(f"Error analyzing pair {pair}: {e}")
                
        return findings
    
    def _get_prices_for_pair(self, pair: str) -> Dict[str, Dict]:
        """Get current prices for a trading pair from all exchanges"""
        prices = {}
        
        for exchange_name, exchange in self.exchanges.items():
            try:
                # Get ticker data
                ticker = exchange.fetch_ticker(pair)
                
                if ticker and ticker.get('bid') and ticker.get('ask'):
                    prices[exchange_name] = {
                        'bid': ticker['bid'],
                        'ask': ticker['ask'],
                        'last': ticker.get('last'),
                        'volume': ticker.get('baseVolume', 0),
                        'timestamp': ticker.get('timestamp')
                    }
                    
            except Exception as e:
                # Some exchanges might not have this pair
                self.logger.debug(f"Could not get {pair} from {exchange_name}: {e}")
                continue
                
        return prices
    
    def _find_arbitrage_opportunities(self, pair: str, prices: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """Find arbitrage opportunities for a trading pair"""
        findings = []
        
        if len(prices) < 2:
            return findings
        
        # Find highest bid and lowest ask
        highest_bid = {'exchange': None, 'price': 0}
        lowest_ask = {'exchange': None, 'price': float('inf')}
        
        for exchange_name, price_data in prices.items():
            bid = price_data.get('bid', 0)
            ask = price_data.get('ask', float('inf'))
            
            if bid > highest_bid['price']:
                highest_bid = {'exchange': exchange_name, 'price': bid}
                
            if ask < lowest_ask['price']:
                lowest_ask = {'exchange': exchange_name, 'price': ask}
        
        # Calculate potential profit
        if (highest_bid['price'] > 0 and 
            lowest_ask['price'] < float('inf') and 
            highest_bid['exchange'] != lowest_ask['exchange']):
            
            profit_percent = (highest_bid['price'] - lowest_ask['price']) / lowest_ask['price']
            
            if profit_percent > self.min_profit_threshold:
                # Determine severity based on profit potential
                if profit_percent > 0.05:  # 5%
                    severity = 'high'
                    confidence = 0.9
                elif profit_percent > 0.03:  # 3%
                    severity = 'medium'
                    confidence = 0.8
                else:
                    severity = 'low'
                    confidence = 0.7
                
                # Calculate volumes for analysis
                buy_volume = prices[lowest_ask['exchange']].get('volume', 0)
                sell_volume = prices[highest_bid['exchange']].get('volume', 0)
                min_volume = min(buy_volume, sell_volume)
                
                findings.append(self.create_finding(
                    title=f"Arbitrage Opportunity: {pair}",
                    description=f"Buy {pair} on {lowest_ask['exchange']} at ${lowest_ask['price']:.4f}, "
                               f"sell on {highest_bid['exchange']} at ${highest_bid['price']:.4f}. "
                               f"Potential profit: {profit_percent*100:.2f}%",
                    severity=severity,
                    confidence=confidence,
                    symbol=pair.split('/')[0],
                    market_type='crypto',
                    metadata={
                        'trading_pair': pair,
                        'buy_exchange': lowest_ask['exchange'],
                        'sell_exchange': highest_bid['exchange'],
                        'buy_price': lowest_ask['price'],
                        'sell_price': highest_bid['price'],
                        'profit_percent': profit_percent,
                        'profit_absolute': highest_bid['price'] - lowest_ask['price'],
                        'min_volume': min_volume,
                        'all_prices': prices
                    }
                ))
                
        return findings
