"""
Crypto Funding Rate Agent

Monitors cryptocurrency perpetual swap funding rates for anomalies
that could indicate market imbalances or excessive leverage.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.coinbase_client import CoinbaseClient

class CryptoFundingRateAgent(BaseAgent):
    """
    Monitors crypto funding rates for market imbalances
    Note: Coinbase doesn't offer futures/funding rates, so this agent
    will monitor spot price volatility instead.
    """
    
    def __init__(self):
        super().__init__()
        self.coinbase_client = CoinbaseClient()
        
        # Symbols to monitor
        self.symbols = [
            'BTCUSDT',
            'ETHUSDT',
            'BNBUSDT',
            'ADAUSDT',
            'SOLUSDT',
            'MATICUSDT',
            'AVAXUSDT',
            'DOTUSDT'
        ]
        
        # Funding rate thresholds
        self.high_funding_threshold = 0.01  # 1% (very high)
        self.medium_funding_threshold = 0.005  # 0.5% (high)
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze funding rates for anomalies
        """
        findings = []
        
        if not self.validate_config(['COINBASE_API_KEY']):
            self.logger.warning("Coinbase API key not configured")
            return findings
        
        # Convert symbols to Coinbase format
        coinbase_symbols = [symbol.replace('USDT', '/USD') for symbol in self.symbols]
        
        for symbol in coinbase_symbols:
            try:
                # Get current price and volatility data instead of funding rates
                ticker_data = self.coinbase_client.get_ticker(symbol)
                if not ticker_data:
                    continue
                
                # Analyze price volatility and volume
                findings.extend(self._analyze_price_volatility(symbol, ticker_data))
                
            except Exception as e:
                self.logger.error(f"Error analyzing funding rate for {symbol}: {e}")
                
        return findings
    
    def _analyze_price_volatility(self, symbol: str, ticker_data: Dict) -> List[Dict[str, Any]]:
        """Analyze price volatility and unusual trading activity"""
        findings = []
        
        try:
            # Get price change and volume data
            price_change_pct = float(ticker_data.get('percentage', 0))
            volume = float(ticker_data.get('baseVolume', 0))
            last_price = float(ticker_data.get('last', 0))
            
            # Check for extreme price movements (potential market stress)
            if abs(price_change_pct) > 10:  # 10% price change
                severity = 'high' if abs(price_change_pct) > 20 else 'medium'
                confidence = 0.8
                
                direction = "surge" if price_change_pct > 0 else "crash"
                interpretation = (f"Extreme price {direction} may indicate market stress, "
                                f"news events, or liquidation cascades.")
                
                findings.append(self.create_finding(
                    title=f"Extreme Price Movement: {symbol}",
                    description=f"Price {direction} of {abs(price_change_pct):.1f}%. {interpretation}",
                    severity=severity,
                    confidence=confidence,
                    symbol=symbol.split('/')[0],
                    market_type='crypto',
                    metadata={
                        'price_change_pct': price_change_pct,
                        'direction': direction,
                        'volume': volume,
                        'last_price': last_price,
                        'threshold': 10.0
                    }
                ))
                
            # Check for unusual volume spikes
            elif volume > 0:  # Only if volume data is available
                # Note: This is a simplified check - in production you'd compare to historical averages
                findings.append(self.create_finding(
                    title=f"Market Activity: {symbol}",
                    description=f"Current price: ${last_price:.4f}, 24h change: {price_change_pct:+.2f}%, "
                               f"Volume: {volume:,.0f}",
                    severity='low',
                    confidence=0.6,
                    symbol=symbol.split('/')[0],
                    market_type='crypto',
                    metadata={
                        'price_change_pct': price_change_pct,
                        'volume': volume,
                        'last_price': last_price
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error analyzing price volatility for {symbol}: {e}")
            
        return findings
