"""
Binance API Client

Provides access to Binance cryptocurrency exchange data including
prices, funding rates, and other market data.
"""

import ccxt
import logging
from typing import Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)

class BinanceClient:
    """
    Client for Binance API data
    """
    
    def __init__(self):
        self.api_key = Config.BINANCE_API_KEY
        self.secret = Config.BINANCE_SECRET
        self.exchange = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Binance client"""
        try:
            self.exchange = ccxt.binance({
                'apiKey': self.api_key,
                'secret': self.secret,
                'sandbox': False,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # Use futures for funding rates
                }
            })
            
        except Exception as e:
            logger.error(f"Error initializing Binance client: {e}")
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Get ticker data for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            
        Returns:
            Ticker data dictionary or None
        """
        if not self.exchange:
            return None
            
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
            
        except Exception as e:
            logger.error(f"Error getting ticker for {symbol}: {e}")
            return None
    
    def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        Get current funding rate for a futures symbol
        
        Args:
            symbol: Futures symbol (e.g., 'BTCUSDT')
            
        Returns:
            Funding rate data or None
        """
        if not self.exchange:
            return None
            
        try:
            # Get funding rate info
            funding_rate = self.exchange.fetch_funding_rate(symbol)
            return funding_rate
            
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            return None
    
    def get_funding_rate_history(self, symbol: str, limit: int = 100) -> Optional[List[Dict]]:
        """
        Get funding rate history for a symbol
        
        Args:
            symbol: Futures symbol
            limit: Number of records to fetch
            
        Returns:
            List of funding rate records or None
        """
        if not self.exchange:
            return None
            
        try:
            history = self.exchange.fetch_funding_rate_history(symbol, limit=limit)
            return history
            
        except Exception as e:
            logger.error(f"Error getting funding rate history for {symbol}: {e}")
            return None
    
    def get_orderbook(self, symbol: str, limit: int = 100) -> Optional[Dict]:
        """
        Get order book for a symbol
        
        Args:
            symbol: Trading pair symbol
            limit: Depth of order book
            
        Returns:
            Order book data or None
        """
        if not self.exchange:
            return None
            
        try:
            orderbook = self.exchange.fetch_order_book(symbol, limit)
            return orderbook
            
        except Exception as e:
            logger.error(f"Error getting orderbook for {symbol}: {e}")
            return None
    
    def get_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Optional[List]:
        """
        Get OHLCV data for a symbol
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (1m, 5m, 1h, 1d, etc.)
            limit: Number of candles
            
        Returns:
            OHLCV data or None
        """
        if not self.exchange:
            return None
            
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
            
        except Exception as e:
            logger.error(f"Error getting OHLCV for {symbol}: {e}")
            return None
    
    def get_24hr_stats(self, symbol: str) -> Optional[Dict]:
        """
        Get 24-hour ticker statistics
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            24-hour stats or None
        """
        if not self.exchange:
            return None
            
        try:
            stats = self.exchange.fetch_ticker(symbol)
            
            return {
                'symbol': symbol,
                'price_change_24h': stats.get('change'),
                'price_change_percent_24h': stats.get('percentage'),
                'volume_24h': stats.get('baseVolume'),
                'high_24h': stats.get('high'),
                'low_24h': stats.get('low'),
                'last_price': stats.get('last')
            }
            
        except Exception as e:
            logger.error(f"Error getting 24hr stats for {symbol}: {e}")
            return None
    
    def get_exchange_info(self) -> Optional[Dict]:
        """
        Get exchange information including trading pairs
        
        Returns:
            Exchange info or None
        """
        if not self.exchange:
            return None
            
        try:
            markets = self.exchange.load_markets()
            
            return {
                'symbols': list(markets.keys()),
                'markets': markets
            }
            
        except Exception as e:
            logger.error(f"Error getting exchange info: {e}")
            return None
