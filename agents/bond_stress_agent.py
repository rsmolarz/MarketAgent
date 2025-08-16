"""
Bond Stress Agent

Monitors bond markets for stress signals that could indicate
broader financial market instability.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.yahoo_finance_client import YahooFinanceClient
import numpy as np

class BondStressAgent(BaseAgent):
    """
    Monitors bond markets for stress signals
    """
    
    def __init__(self):
        super().__init__()
        self.yahoo_client = YahooFinanceClient()
        
        # Bond instruments to monitor
        self.bond_instruments = {
            '^TNX': {'name': '10Y Treasury', 'type': 'treasury'},
            '^FVX': {'name': '5Y Treasury', 'type': 'treasury'}, 
            '^IRX': {'name': '3M Treasury', 'type': 'treasury'},
            'HYG': {'name': 'High Yield Corp', 'type': 'corporate'},
            'LQD': {'name': 'Investment Grade Corp', 'type': 'corporate'},
            'TLT': {'name': '20Y Treasury Bond', 'type': 'treasury'},
            'IEF': {'name': '7-10Y Treasury', 'type': 'treasury'}
        }
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze bond markets for stress signals
        """
        findings = []
        
        # Get all bond data first
        bond_data = {}
        for symbol, info in self.bond_instruments.items():
            try:
                data = self.yahoo_client.get_price_data(symbol, period='30d')
                if data is not None and len(data) > 5:
                    bond_data[symbol] = {'data': data, 'info': info}
            except Exception as e:
                self.logger.error(f"Error getting data for {symbol}: {e}")
        
        # Analyze individual bonds
        for symbol, bond_info in bond_data.items():
            findings.extend(self._analyze_bond_stress(symbol, bond_info))
        
        # Analyze cross-bond relationships
        findings.extend(self._analyze_yield_curve(bond_data))
        findings.extend(self._analyze_credit_spreads(bond_data))
        
        return findings
    
    def _analyze_bond_stress(self, symbol: str, bond_info: Dict) -> List[Dict[str, Any]]:
        """Analyze individual bond for stress signals"""
        findings = []
        
        try:
            data = bond_info['data']
            info = bond_info['info']
            
            # Calculate recent volatility
            returns = data['Close'].pct_change().dropna()
            recent_vol = returns.tail(5).std()
            historical_vol = returns.std()
            
            # Check for volatility spikes
            if recent_vol > historical_vol * 2:
                findings.append(self.create_finding(
                    title=f"High Volatility in {info['name']}",
                    description=f"Recent volatility ({recent_vol:.4f}) is {recent_vol/historical_vol:.1f}x "
                               f"higher than historical average. This could indicate market stress.",
                    severity='medium',
                    confidence=0.7,
                    symbol=symbol,
                    market_type='bond',
                    metadata={
                        'recent_volatility': recent_vol,
                        'historical_volatility': historical_vol,
                        'volatility_ratio': recent_vol / historical_vol,
                        'bond_type': info['type']
                    }
                ))
            
            # Check for unusual price movements
            recent_change = (data['Close'].iloc[-1] - data['Close'].iloc[-5]) / data['Close'].iloc[-5]
            
            if abs(recent_change) > 0.05:  # 5% move in bonds is significant
                severity = 'high' if abs(recent_change) > 0.1 else 'medium'
                direction = 'increased' if recent_change > 0 else 'decreased'
                
                findings.append(self.create_finding(
                    title=f"Significant Price Movement in {info['name']}",
                    description=f"Bond price {direction} {abs(recent_change)*100:.1f}% "
                               f"over recent period. Large bond moves can signal "
                               f"changing market expectations or stress.",
                    severity=severity,
                    confidence=0.8,
                    symbol=symbol,
                    market_type='bond',
                    metadata={
                        'price_change': recent_change,
                        'direction': direction,
                        'bond_type': info['type']
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Error analyzing bond stress for {symbol}: {e}")
            
        return findings
    
    def _analyze_yield_curve(self, bond_data: Dict) -> List[Dict[str, Any]]:
        """Analyze yield curve for inversions and unusual shapes"""
        findings = []
        
        try:
            # Get current yields (for ETFs, price down = yield up)
            yields = {}
            
            for symbol, bond_info in bond_data.items():
                if bond_info['info']['type'] == 'treasury':
                    current_price = bond_info['data']['Close'].iloc[-1]
                    prev_price = bond_info['data']['Close'].iloc[-30] if len(bond_info['data']) >= 30 else bond_info['data']['Close'].iloc[0]
                    
                    # For treasury securities, approximate yield movement (inverse to price)
                    # This is simplified - actual implementation would use real yield data
                    yield_change = -(current_price - prev_price) / prev_price
                    yields[symbol] = {
                        'yield_change': yield_change,
                        'name': bond_info['info']['name']
                    }
            
            # Check for yield curve flattening/inversion signals
            if '^TNX' in yields and '^IRX' in yields:
                ten_year_change = yields['^TNX']['yield_change']
                three_month_change = yields['^IRX']['yield_change']
                
                # If short rates rising faster than long rates
                if three_month_change > ten_year_change + 0.02:
                    findings.append(self.create_finding(
                        title="Yield Curve Flattening Signal",
                        description=f"3-month rates rising faster than 10-year rates "
                                   f"(3M change: {three_month_change*100:.2f}%, "
                                   f"10Y change: {ten_year_change*100:.2f}%). "
                                   f"This could indicate Fed tightening stress.",
                        severity='medium',
                        confidence=0.6,
                        symbol='YIELD_CURVE',
                        market_type='bond',
                        metadata={
                            'three_month_change': three_month_change,
                            'ten_year_change': ten_year_change,
                            'spread_change': three_month_change - ten_year_change
                        }
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error analyzing yield curve: {e}")
            
        return findings
    
    def _analyze_credit_spreads(self, bond_data: Dict) -> List[Dict[str, Any]]:
        """Analyze credit spreads for stress signals"""
        findings = []
        
        try:
            # Compare corporate bonds to treasuries
            if 'HYG' in bond_data and 'LQD' in bond_data:
                hyg_data = bond_data['HYG']['data']
                lqd_data = bond_data['LQD']['data']
                
                # Calculate recent performance
                hyg_change = (hyg_data['Close'].iloc[-1] - hyg_data['Close'].iloc[-5]) / hyg_data['Close'].iloc[-5]
                lqd_change = (lqd_data['Close'].iloc[-1] - lqd_data['Close'].iloc[-5]) / lqd_data['Close'].iloc[-5]
                
                # High yield underperforming investment grade significantly
                if hyg_change < lqd_change - 0.03:  # 3% underperformance
                    findings.append(self.create_finding(
                        title="Credit Spread Widening Signal",
                        description=f"High yield bonds underperforming investment grade "
                                   f"(HYG: {hyg_change*100:.1f}%, LQD: {lqd_change*100:.1f}%). "
                                   f"This could indicate credit stress or risk-off sentiment.",
                        severity='medium',
                        confidence=0.7,
                        symbol='CREDIT_SPREAD',
                        market_type='bond',
                        metadata={
                            'hyg_change': hyg_change,
                            'lqd_change': lqd_change,
                            'spread_widening': lqd_change - hyg_change
                        }
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error analyzing credit spreads: {e}")
            
        return findings
