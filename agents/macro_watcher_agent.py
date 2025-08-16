"""
Macro Watcher Agent

Monitors macroeconomic indicators for anomalies that could signal
market inefficiencies or regime changes.
"""

import yfinance as yf
from typing import List, Dict, Any
from datetime import datetime, timedelta
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient

class MacroWatcherAgent(BaseAgent):
    """
    Monitors macro indicators like VIX, DXY, yield curves for anomalies
    """
    
    def __init__(self):
        super().__init__()
        self.yahoo_client = YahooFinanceClient()
        
        # Key macro indicators to monitor
        self.indicators = {
            '^VIX': {'name': 'VIX', 'high_threshold': 30, 'critical_threshold': 40},
            'DX-Y.NYB': {'name': 'Dollar Index', 'volatility_threshold': 0.02},
            '^TNX': {'name': '10Y Treasury', 'volatility_threshold': 0.1},
            '^IRX': {'name': '3M Treasury', 'volatility_threshold': 0.05},
            'SPY': {'name': 'S&P 500', 'volatility_threshold': 0.03}
        }
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze macro indicators for anomalies
        """
        findings = []
        
        for symbol, config in self.indicators.items():
            try:
                # Get recent data
                data = self.yahoo_client.get_price_data(symbol, period='5d')
                if data is None or len(data) < 2:
                    continue
                
                current_price = data['Close'].iloc[-1]
                previous_price = data['Close'].iloc[-2]
                
                # Calculate metrics
                daily_change = (current_price - previous_price) / previous_price
                volatility = data['Close'].pct_change().std()
                
                # Check for anomalies
                findings.extend(self._check_vix_spike(symbol, config, current_price, daily_change))
                findings.extend(self._check_volatility_spike(symbol, config, volatility, daily_change))
                findings.extend(self._check_yield_curve_inversion(symbol, config, data))
                
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")
                
        return findings
    
    def _check_vix_spike(self, symbol: str, config: Dict, price: float, daily_change: float) -> List[Dict[str, Any]]:
        """Check for VIX spikes indicating fear"""
        findings = []
        
        if symbol == '^VIX':
            if price > config.get('critical_threshold', 40):
                findings.append(self.create_finding(
                    title="Critical VIX Spike Detected",
                    description=f"VIX at {price:.2f}, indicating extreme market fear. "
                               f"Daily change: {daily_change*100:.2f}%",
                    severity='critical',
                    confidence=0.9,
                    symbol='VIX',
                    market_type='macro',
                    metadata={
                        'vix_level': price,
                        'daily_change': daily_change,
                        'threshold': config.get('critical_threshold')
                    }
                ))
            elif price > config.get('high_threshold', 30):
                findings.append(self.create_finding(
                    title="Elevated VIX Detected",
                    description=f"VIX at {price:.2f}, indicating increased market uncertainty. "
                               f"Daily change: {daily_change*100:.2f}%",
                    severity='high',
                    confidence=0.8,
                    symbol='VIX',
                    market_type='macro',
                    metadata={
                        'vix_level': price,
                        'daily_change': daily_change,
                        'threshold': config.get('high_threshold')
                    }
                ))
                
        return findings
    
    def _check_volatility_spike(self, symbol: str, config: Dict, volatility: float, daily_change: float) -> List[Dict[str, Any]]:
        """Check for unusual volatility spikes"""
        findings = []
        
        threshold = config.get('volatility_threshold', 0.02)
        
        if abs(daily_change) > threshold * 2:  # 2x normal volatility
            severity = 'high' if abs(daily_change) > threshold * 3 else 'medium'
            
            findings.append(self.create_finding(
                title=f"High Volatility in {config['name']}",
                description=f"{config['name']} moved {daily_change*100:.2f}% today, "
                           f"significantly above normal volatility of {threshold*100:.2f}%",
                severity=severity,
                confidence=0.7,
                symbol=symbol,
                market_type='macro',
                metadata={
                    'daily_change': daily_change,
                    'volatility': volatility,
                    'threshold': threshold,
                    'indicator_name': config['name']
                }
            ))
            
        return findings
    
    def _check_yield_curve_inversion(self, symbol: str, config: Dict, data) -> List[Dict[str, Any]]:
        """Check for yield curve inversions"""
        findings = []
        
        # This is a simplified check - in practice you'd compare multiple yield points
        if symbol == '^TNX':  # 10-year
            try:
                # Get 2-year data for comparison
                two_year_data = self.yahoo_client.get_price_data('^IRX', period='2d')
                if two_year_data is not None and len(two_year_data) > 0:
                    ten_year_yield = data['Close'].iloc[-1]
                    two_year_yield = two_year_data['Close'].iloc[-1]
                    
                    if two_year_yield > ten_year_yield:
                        spread = two_year_yield - ten_year_yield
                        findings.append(self.create_finding(
                            title="Yield Curve Inversion Detected",
                            description=f"2Y yield ({two_year_yield:.2f}%) > 10Y yield ({ten_year_yield:.2f}%), "
                                       f"spread: {spread:.2f}bp. This often precedes recessions.",
                            severity='high',
                            confidence=0.8,
                            symbol='YIELD_CURVE',
                            market_type='macro',
                            metadata={
                                'two_year_yield': two_year_yield,
                                'ten_year_yield': ten_year_yield,
                                'spread_bp': spread * 100
                            }
                        ))
                        
            except Exception as e:
                self.logger.error(f"Error checking yield curve: {e}")
                
        return findings
