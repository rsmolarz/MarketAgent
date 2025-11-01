"""
Market Correction Agent

Monitors markets for correction signals (10%+ decline from peaks) using
technical indicators, valuation metrics, and market breadth analysis.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from datetime import datetime, timedelta
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient


class MarketCorrectionAgent(BaseAgent):
    """
    Detects early warning signals for potential market corrections
    """
    
    def __init__(self):
        super().__init__()
        self.yahoo_client = YahooFinanceClient()
        
        # Markets to monitor
        self.markets = {
            'SPY': {'name': 'S&P 500', 'type': 'equity_index'},
            'QQQ': {'name': 'NASDAQ-100', 'type': 'equity_index'},
            'IWM': {'name': 'Russell 2000', 'type': 'equity_index'},
            'DIA': {'name': 'Dow Jones', 'type': 'equity_index'},
            '^VIX': {'name': 'VIX', 'type': 'volatility'},
            'TLT': {'name': '20Y Treasury', 'type': 'bonds'},
            '^TNX': {'name': '10Y Yield', 'type': 'rates'}
        }
        
        # Read configuration
        self.correction_threshold = self.config.get('correction_threshold', 0.10)  # 10%
        self.rsi_overbought = self.config.get('rsi_overbought', 70)
        self.vix_warning = self.config.get('vix_warning', 25)
        self.vix_critical = self.config.get('vix_critical', 35)
        
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze markets for correction signals
        """
        findings = []
        
        # Get market data
        market_data = self._fetch_market_data()
        
        # Analyze each market
        for symbol, data in market_data.items():
            if data is None:
                continue
                
            info = self.markets[symbol]
            
            # Run various correction detection analyses
            findings.extend(self._check_decline_from_peak(symbol, data, info))
            findings.extend(self._check_technical_indicators(symbol, data, info))
            findings.extend(self._check_momentum_exhaustion(symbol, data, info))
            
        # Cross-market analysis
        findings.extend(self._check_vix_spike(market_data))
        findings.extend(self._check_breadth_deterioration(market_data))
        findings.extend(self._check_yield_curve(market_data))
        
        return findings
    
    def _fetch_market_data(self) -> Dict[str, Any]:
        """Fetch recent market data for all monitored instruments"""
        market_data = {}
        
        for symbol in self.markets.keys():
            try:
                data = self.yahoo_client.get_price_data(symbol, period='6mo')
                if data is not None and len(data) > 50:
                    market_data[symbol] = data
                else:
                    self.logger.warning(f"Insufficient data for {symbol}")
            except Exception as e:
                self.logger.error(f"Error fetching data for {symbol}: {e}")
                
        return market_data
    
    def _check_decline_from_peak(self, symbol: str, data: Any, info: Dict) -> List[Dict[str, Any]]:
        """Check if price has declined significantly from recent peak"""
        findings = []
        
        try:
            # Calculate 52-week high
            high_52w = data['Close'].tail(252).max()
            current_price = data['Close'].iloc[-1]
            
            # Calculate decline from peak
            decline_pct = (current_price - high_52w) / high_52w
            
            # Check if approaching correction territory
            warning_threshold = -self.correction_threshold * 0.7  # 70% of correction threshold
            if decline_pct <= warning_threshold:  # Warning level
                severity = 'critical' if decline_pct <= -self.correction_threshold else 'high'
                
                findings.append(self.create_finding(
                    title=f"{info['name']} Approaching Correction",
                    description=f"{info['name']} has declined {abs(decline_pct)*100:.1f}% from its "
                               f"52-week high of ${high_52w:.2f}. Current price: ${current_price:.2f}. "
                               f"A decline of {self.correction_threshold*100:.0f}% or more is typically considered a correction.",
                    severity=severity,
                    confidence=0.85,
                    symbol=symbol,
                    market_type=info['type'],
                    metadata={
                        'decline_from_peak': decline_pct,
                        'current_price': float(current_price),
                        'peak_price': float(high_52w),
                        'correction_threshold': -self.correction_threshold
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error checking decline from peak for {symbol}: {e}")
            
        return findings
    
    def _check_technical_indicators(self, symbol: str, data: Any, info: Dict) -> List[Dict[str, Any]]:
        """Check RSI and moving averages for overbought conditions"""
        findings = []
        
        try:
            # Skip VIX and rates for technical analysis
            if info['type'] in ['volatility', 'rates']:
                return findings
            
            # Calculate RSI
            rsi = self._calculate_rsi(data['Close'], period=14)
            current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
            
            # Calculate moving averages
            ma_50 = data['Close'].rolling(window=50).mean()
            ma_200 = data['Close'].rolling(window=200).mean()
            
            current_price = data['Close'].iloc[-1]
            current_ma50 = ma_50.iloc[-1]
            current_ma200 = ma_200.iloc[-1]
            
            # Death cross warning (50MA crosses below 200MA)
            if current_ma50 < current_ma200:
                prev_ma50 = ma_50.iloc[-5]
                prev_ma200 = ma_200.iloc[-5]
                
                # Check if this is a recent crossover
                if prev_ma50 >= prev_ma200:
                    findings.append(self.create_finding(
                        title=f"Death Cross Detected in {info['name']}",
                        description=f"The 50-day moving average (${current_ma50:.2f}) has crossed below "
                                   f"the 200-day moving average (${current_ma200:.2f}), a bearish signal "
                                   f"that often precedes market corrections.",
                        severity='high',
                        confidence=0.75,
                        symbol=symbol,
                        market_type=info['type'],
                        metadata={
                            'ma_50': float(current_ma50),
                            'ma_200': float(current_ma200),
                            'current_price': float(current_price),
                            'rsi': float(current_rsi)
                        }
                    ))
            
            # Extreme overbought condition
            extreme_threshold = self.rsi_overbought + 5  # 5 points above configured threshold
            if current_rsi > extreme_threshold:
                findings.append(self.create_finding(
                    title=f"{info['name']} Extremely Overbought",
                    description=f"RSI is at {current_rsi:.1f}, indicating extreme overbought conditions. "
                                f"Markets at these levels often experience pullbacks or corrections.",
                    severity='medium',
                    confidence=0.65,
                    symbol=symbol,
                    market_type=info['type'],
                    metadata={
                        'rsi': float(current_rsi),
                        'rsi_threshold': extreme_threshold,
                        'current_price': float(current_price)
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error checking technical indicators for {symbol}: {e}")
            
        return findings
    
    def _check_momentum_exhaustion(self, symbol: str, data: Any, info: Dict) -> List[Dict[str, Any]]:
        """Check for signs of momentum exhaustion"""
        findings = []
        
        try:
            if info['type'] in ['volatility', 'rates']:
                return findings
            
            # Calculate recent returns
            returns = data['Close'].pct_change()
            
            # Check for extended rally (20+ days of gains)
            recent_20d = returns.tail(20)
            positive_days = (recent_20d > 0).sum()
            
            if positive_days >= 16:  # 80% positive days
                cumulative_gain = (data['Close'].iloc[-1] / data['Close'].iloc[-20] - 1)
                
                findings.append(self.create_finding(
                    title=f"{info['name']} Shows Momentum Exhaustion",
                    description=f"{positive_days} out of the last 20 days were positive, with a "
                               f"cumulative gain of {cumulative_gain*100:.1f}%. Extended rallies "
                               f"without pullbacks often precede corrections.",
                    severity='medium',
                    confidence=0.60,
                    symbol=symbol,
                    market_type=info['type'],
                    metadata={
                        'positive_days_count': int(positive_days),
                        'period_days': 20,
                        'cumulative_gain': float(cumulative_gain)
                    }
                ))
            
            # Check for declining volume on rallies
            if 'Volume' in data.columns:
                recent_prices = data['Close'].tail(10)
                recent_volumes = data['Volume'].tail(10)
                
                price_trend = (recent_prices.iloc[-1] > recent_prices.iloc[0])
                volume_trend = recent_volumes.mean() < data['Volume'].tail(30).mean()
                
                if price_trend and volume_trend:
                    findings.append(self.create_finding(
                        title=f"Declining Volume on {info['name']} Rally",
                        description=f"Price is rising but volume is declining, suggesting weakening "
                                   f"conviction. This can signal an impending reversal.",
                        severity='low',
                        confidence=0.55,
                        symbol=symbol,
                        market_type=info['type'],
                        metadata={
                            'recent_volume_avg': float(recent_volumes.mean()),
                            'historical_volume_avg': float(data['Volume'].tail(30).mean())
                        }
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error checking momentum exhaustion for {symbol}: {e}")
            
        return findings
    
    def _check_vix_spike(self, market_data: Dict) -> List[Dict[str, Any]]:
        """Check for VIX spikes indicating fear"""
        findings = []
        
        try:
            if '^VIX' not in market_data:
                return findings
            
            vix_data = market_data['^VIX']
            current_vix = vix_data['Close'].iloc[-1]
            avg_vix = vix_data['Close'].tail(30).mean()
            
            # Critical VIX level
            if current_vix >= self.vix_critical:
                findings.append(self.create_finding(
                    title="VIX at Critical Levels - Market Fear Spiking",
                    description=f"VIX (fear index) is at {current_vix:.2f}, indicating extreme market "
                               f"fear and uncertainty. Historical corrections often coincide with VIX "
                               f"spikes above {self.vix_critical}.",
                    severity='critical',
                    confidence=0.85,
                    symbol='^VIX',
                    market_type='volatility',
                    metadata={
                        'current_vix': float(current_vix),
                        'avg_vix_30d': float(avg_vix),
                        'vix_critical_threshold': self.vix_critical
                    }
                ))
            
            # Warning VIX level
            elif current_vix >= self.vix_warning:
                findings.append(self.create_finding(
                    title="VIX Elevated - Increased Market Volatility",
                    description=f"VIX is at {current_vix:.2f}, above the warning threshold of "
                               f"{self.vix_warning}. Elevated VIX can signal market instability "
                               f"and potential correction risk.",
                    severity='high',
                    confidence=0.75,
                    symbol='^VIX',
                    market_type='volatility',
                    metadata={
                        'current_vix': float(current_vix),
                        'avg_vix_30d': float(avg_vix),
                        'vix_warning_threshold': self.vix_warning
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error checking VIX spike: {e}")
            
        return findings
    
    def _check_breadth_deterioration(self, market_data: Dict) -> List[Dict[str, Any]]:
        """Check if market breadth is deteriorating"""
        findings = []
        
        try:
            # Compare large-cap (SPY) vs small-cap (IWM) performance
            if 'SPY' in market_data and 'IWM' in market_data:
                spy_data = market_data['SPY']
                iwm_data = market_data['IWM']
                
                # Calculate 20-day returns
                spy_return = (spy_data['Close'].iloc[-1] / spy_data['Close'].iloc[-20] - 1)
                iwm_return = (iwm_data['Close'].iloc[-1] / iwm_data['Close'].iloc[-20] - 1)
                
                # Significant underperformance of small caps
                if iwm_return < spy_return - 0.05:  # 5% underperformance
                    findings.append(self.create_finding(
                        title="Market Breadth Deteriorating - Small Caps Lagging",
                        description=f"Russell 2000 is underperforming S&P 500 by "
                                   f"{abs(iwm_return - spy_return)*100:.1f}% over 20 days. "
                                   f"When small caps lag, it suggests narrowing market leadership "
                                   f"and potential correction risk.",
                        severity='medium',
                        confidence=0.70,
                        symbol='IWM',
                        market_type='breadth',
                        metadata={
                            'spy_return_20d': float(spy_return),
                            'iwm_return_20d': float(iwm_return),
                            'performance_gap': float(iwm_return - spy_return)
                        }
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error checking breadth deterioration: {e}")
            
        return findings
    
    def _check_yield_curve(self, market_data: Dict) -> List[Dict[str, Any]]:
        """Check for yield curve inversions"""
        findings = []
        
        try:
            # Note: This is a simplified check - real yield curve analysis would need more data points
            if '^TNX' in market_data and 'TLT' in market_data:
                tnx_data = market_data['^TNX']
                current_10y = tnx_data['Close'].iloc[-1]
                
                # Rapid rise in 10Y yield can signal trouble
                prev_10y = tnx_data['Close'].iloc[-20]
                yield_change = current_10y - prev_10y
                
                if yield_change > 0.5:  # 50 basis points in 20 days
                    findings.append(self.create_finding(
                        title="Rapid Treasury Yield Rise - Tightening Conditions",
                        description=f"10-year Treasury yield has risen {yield_change:.2f}% in 20 days "
                                   f"to {current_10y:.2f}%. Rapid yield increases can trigger equity "
                                   f"market corrections as borrowing costs rise.",
                        severity='high',
                        confidence=0.70,
                        symbol='^TNX',
                        market_type='rates',
                        metadata={
                            'current_yield': float(current_10y),
                            'yield_change_20d': float(yield_change),
                            'threshold_bps': 50
                        }
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error checking yield curve: {e}")
            
        return findings
    
    def _calculate_rsi(self, prices: Any, period: int = 14) -> Any:
        """Calculate Relative Strength Index"""
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
