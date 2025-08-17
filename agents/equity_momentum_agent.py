"""
Equity Momentum Agent

Monitors equity markets for momentum anomalies and unusual patterns.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
import numpy as np

class EquityMomentumAgent(BaseAgent):
    """
    Monitors equity momentum for anomalies
    """
    
    def __init__(self):
        super().__init__()
        self.yahoo_client = YahooFinanceClient()
        
        # Key equity instruments to monitor
        self.instruments = [
            'SPY',   # S&P 500
            'QQQ',   # NASDAQ
            'IWM',   # Russell 2000
            'VTI',   # Total Stock Market
            'TSLA',  # Tesla (momentum stock)
            'NVDA',  # NVIDIA (AI momentum)
            'AAPL',  # Apple
            'MSFT'   # Microsoft
        ]
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze equity momentum for anomalies
        """
        findings = []
        
        for symbol in self.instruments:
            try:
                # Get price data
                data = self.yahoo_client.get_price_data(symbol, period='30d')
                if data is None or len(data) < 20:
                    continue
                
                # Calculate momentum indicators
                findings.extend(self._check_momentum_divergence(symbol, data))
                findings.extend(self._check_volume_price_divergence(symbol, data))
                findings.extend(self._check_momentum_exhaustion(symbol, data))
                
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")
                
        return findings
    
    def _check_momentum_divergence(self, symbol: str, data) -> List[Dict[str, Any]]:
        """Check for momentum divergences"""
        findings = []
        
        try:
            # Calculate RSI
            rsi = self._calculate_rsi(data['Close'])
            
            # Get recent prices
            recent_prices = data['Close'].tail(5)
            recent_rsi = rsi.tail(5)
            
            if len(recent_prices) < 5 or len(recent_rsi) < 5:
                return findings
            
            # Check for bearish divergence (price up, RSI down)
            price_trend = recent_prices.iloc[-1] - recent_prices.iloc[0]
            rsi_trend = recent_rsi.iloc[-1] - recent_rsi.iloc[0]
            
            if price_trend > 0 and rsi_trend < -5:  # Price up, RSI down
                findings.append(self.create_finding(
                    title=f"Bearish RSI Divergence in {symbol}",
                    description=f"Price increased while RSI declined over recent period. "
                               f"Current RSI: {recent_rsi.iloc[-1]:.1f}. "
                               f"This could signal momentum weakness.",
                    severity='medium',
                    confidence=0.7,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'current_rsi': recent_rsi.iloc[-1],
                        'rsi_change': rsi_trend,
                        'price_change': price_trend,
                        'divergence_type': 'bearish'
                    }
                ))
                
            elif price_trend < 0 and rsi_trend > 5:  # Price down, RSI up
                findings.append(self.create_finding(
                    title=f"Bullish RSI Divergence in {symbol}",
                    description=f"Price decreased while RSI increased over recent period. "
                               f"Current RSI: {recent_rsi.iloc[-1]:.1f}. "
                               f"This could signal momentum reversal.",
                    severity='medium',
                    confidence=0.7,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'current_rsi': recent_rsi.iloc[-1],
                        'rsi_change': rsi_trend,
                        'price_change': price_trend,
                        'divergence_type': 'bullish'
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error checking momentum divergence for {symbol}: {e}")
            
        return findings
    
    def _check_volume_price_divergence(self, symbol: str, data) -> List[Dict[str, Any]]:
        """Check for volume-price divergences"""
        findings = []
        
        try:
            if 'Volume' not in data.columns:
                return findings
            
            # Get recent data
            recent_data = data.tail(10)
            
            # Calculate price and volume trends
            price_change = (recent_data['Close'].iloc[-1] - recent_data['Close'].iloc[0]) / recent_data['Close'].iloc[0]
            avg_volume_recent = recent_data['Volume'].tail(5).mean()
            avg_volume_earlier = recent_data['Volume'].head(5).mean()
            
            volume_change = (avg_volume_recent - avg_volume_earlier) / avg_volume_earlier if avg_volume_earlier > 0 else 0
            
            # Check for divergences with more sensitive thresholds  
            if price_change > 0.01 and volume_change < -0.1:  # Price up 1%+, volume down 10%+ (more sensitive)
                findings.append(self.create_finding(
                    title=f"Volume Divergence in {symbol}",
                    description=f"Price increased {price_change*100:.1f}% while volume "
                               f"decreased {abs(volume_change)*100:.1f}%. "
                               f"This could indicate weak buying interest or distribution.",
                    severity='medium',
                    confidence=0.7,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'price_change': price_change,
                        'volume_change': volume_change,
                        'avg_volume_recent': avg_volume_recent,
                        'avg_volume_earlier': avg_volume_earlier
                    }
                ))
            elif price_change < -0.01 and volume_change > 0.1:  # Price down, volume up 
                findings.append(self.create_finding(
                    title=f"Selling Pressure in {symbol}",
                    description=f"Price decreased {abs(price_change)*100:.1f}% while volume "
                               f"increased {volume_change*100:.1f}%. "
                               f"This indicates strong selling pressure or institutional distribution.",
                    severity='high',
                    confidence=0.8,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'price_change': price_change,
                        'volume_change': volume_change,
                        'avg_volume_recent': avg_volume_recent,
                        'avg_volume_earlier': avg_volume_earlier
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error checking volume divergence for {symbol}: {e}")
            
        return findings
    
    def _check_momentum_exhaustion(self, symbol: str, data) -> List[Dict[str, Any]]:
        """Check for momentum exhaustion signals"""
        findings = []
        
        try:
            # Calculate RSI
            rsi = self._calculate_rsi(data['Close'])
            current_rsi = rsi.iloc[-1]
            
            # Check for overbought/oversold conditions
            if current_rsi > 80:
                findings.append(self.create_finding(
                    title=f"Overbought Condition in {symbol}",
                    description=f"RSI at {current_rsi:.1f}, indicating overbought conditions. "
                               f"Momentum may be exhausted and reversal could occur.",
                    severity='medium',
                    confidence=0.6,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'rsi': current_rsi,
                        'condition': 'overbought',
                        'threshold': 80
                    }
                ))
                
            elif current_rsi < 20:
                findings.append(self.create_finding(
                    title=f"Oversold Condition in {symbol}",
                    description=f"RSI at {current_rsi:.1f}, indicating oversold conditions. "
                               f"Bounce or reversal could occur.",
                    severity='medium',
                    confidence=0.6,
                    symbol=symbol,
                    market_type='equity',
                    metadata={
                        'rsi': current_rsi,
                        'condition': 'oversold',
                        'threshold': 20
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error checking momentum exhaustion for {symbol}: {e}")
            
        return findings
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI (Relative Strength Index)"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except Exception as e:
            self.logger.error(f"Error calculating RSI: {e}")
            return prices * 0 + 50  # Return neutral RSI on error
