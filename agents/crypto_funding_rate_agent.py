"""
Crypto Funding Rate Agent

Monitors cryptocurrency perpetual swap funding rates for anomalies
that could indicate market imbalances or excessive leverage.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.binance_client import BinanceClient

class CryptoFundingRateAgent(BaseAgent):
    """
    Monitors crypto funding rates for market imbalances
    """
    
    def __init__(self):
        super().__init__()
        self.binance_client = BinanceClient()
        
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
        
        if not self.validate_config(['BINANCE_API_KEY']):
            self.logger.warning("Binance API key not configured")
            return findings
        
        for symbol in self.symbols:
            try:
                # Get current funding rate
                funding_data = self.binance_client.get_funding_rate(symbol)
                if not funding_data:
                    continue
                
                # Analyze funding rate
                findings.extend(self._analyze_funding_rate(symbol, funding_data))
                
            except Exception as e:
                self.logger.error(f"Error analyzing funding rate for {symbol}: {e}")
                
        return findings
    
    def _analyze_funding_rate(self, symbol: str, funding_data: Dict) -> List[Dict[str, Any]]:
        """Analyze funding rate for anomalies"""
        findings = []
        
        try:
            funding_rate = float(funding_data.get('lastFundingRate', 0))
            funding_time = funding_data.get('nextFundingTime')
            
            # Convert to percentage
            funding_rate_pct = funding_rate * 100
            
            # Check for extreme funding rates
            if abs(funding_rate) > self.high_funding_threshold:
                severity = 'high'
                confidence = 0.8
                
                if funding_rate > 0:
                    direction = "positive"
                    interpretation = ("Longs paying shorts heavily - excessive bullish leverage. "
                                    "Potential for long liquidations and price correction.")
                else:
                    direction = "negative"
                    interpretation = ("Shorts paying longs heavily - excessive bearish leverage. "
                                    "Potential for short liquidations and price pump.")
                
                findings.append(self.create_finding(
                    title=f"Extreme {direction.title()} Funding Rate: {symbol}",
                    description=f"Funding rate at {funding_rate_pct:.3f}%. {interpretation}",
                    severity=severity,
                    confidence=confidence,
                    symbol=symbol.replace('USDT', ''),
                    market_type='crypto',
                    metadata={
                        'funding_rate': funding_rate,
                        'funding_rate_pct': funding_rate_pct,
                        'direction': direction,
                        'next_funding_time': funding_time,
                        'threshold': self.high_funding_threshold
                    }
                ))
                
            elif abs(funding_rate) > self.medium_funding_threshold:
                severity = 'medium'
                confidence = 0.7
                
                direction = "positive" if funding_rate > 0 else "negative"
                
                findings.append(self.create_finding(
                    title=f"High {direction.title()} Funding Rate: {symbol}",
                    description=f"Funding rate at {funding_rate_pct:.3f}%, indicating "
                               f"elevated leverage on the {direction} side. "
                               f"Monitor for potential liquidation cascades.",
                    severity=severity,
                    confidence=confidence,
                    symbol=symbol.replace('USDT', ''),
                    market_type='crypto',
                    metadata={
                        'funding_rate': funding_rate,
                        'funding_rate_pct': funding_rate_pct,
                        'direction': direction,
                        'next_funding_time': funding_time,
                        'threshold': self.medium_funding_threshold
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error analyzing funding rate for {symbol}: {e}")
            
        return findings
