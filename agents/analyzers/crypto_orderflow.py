"""
Crypto Orderflow Analyzer

Analyzes order flow metrics for cryptocurrency prediction.
Monitors funding rates, open interest, and volume patterns.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


class CryptoOrderflowAnalyzer:
    """
    Order flow analysis for cryptocurrency markets.
    
    Analyzes:
    - Funding rates (perpetual futures premium)
    - Open interest changes
    - Volume profile
    - Buy/sell pressure
    """
    
    def __init__(self):
        self.extreme_funding_threshold = 0.01
        self.high_funding_threshold = 0.005
        self.oi_change_threshold = 10.0
    
    def analyze(self, price_data: pd.DataFrame, 
                funding_rate: Optional[float] = None,
                open_interest: Optional[float] = None,
                oi_change_pct: Optional[float] = None) -> Dict[str, Any]:
        """
        Analyze order flow metrics.
        
        Args:
            price_data: DataFrame with OHLCV data
            funding_rate: Current funding rate (if available)
            open_interest: Current open interest value
            oi_change_pct: Percent change in open interest
            
        Returns:
            Dictionary with orderflow analysis
        """
        try:
            if price_data is None or len(price_data) < 10:
                return self._empty_result()
            
            volume = price_data['Volume'].values if 'Volume' in price_data.columns else None
            close = price_data['Close'].values
            high = price_data['High'].values
            low = price_data['Low'].values
            
            volume_analysis = self._analyze_volume(volume, close) if volume is not None else {}
            
            buying_pressure = self._estimate_buying_pressure(close, high, low, volume)
            
            funding_signal = self._analyze_funding(funding_rate)
            oi_signal = self._analyze_open_interest(oi_change_pct)
            
            bias = self._calculate_orderflow_bias(
                volume_analysis.get('volume_trend', 0),
                buying_pressure,
                funding_signal,
                oi_signal
            )
            
            return {
                'funding_rate': funding_rate,
                'open_interest': open_interest,
                'oi_change_pct': oi_change_pct,
                'funding_signal': funding_signal,
                'oi_signal': oi_signal,
                'volume_trend': volume_analysis.get('volume_trend', 0),
                'buying_pressure': round(buying_pressure, 3),
                'volume_spike': volume_analysis.get('volume_spike', False),
                'bias': bias,
                'raw_score': self._calculate_raw_score(buying_pressure, funding_signal, oi_signal),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Orderflow analysis error: {e}")
            return self._empty_result()
    
    def _analyze_volume(self, volume: np.ndarray, close: np.ndarray) -> Dict[str, Any]:
        """Analyze volume patterns"""
        if volume is None or len(volume) < 5:
            return {}
        
        recent_vol = np.mean(volume[-5:])
        historical_vol = np.mean(volume[-20:]) if len(volume) >= 20 else np.mean(volume)
        
        volume_trend = 0.0
        if historical_vol > 0:
            volume_trend = (recent_vol - historical_vol) / historical_vol
        
        vol_std = np.std(volume[-20:]) if len(volume) >= 20 else np.std(volume)
        volume_spike = recent_vol > historical_vol + 2 * vol_std
        
        return {
            'volume_trend': round(volume_trend, 3),
            'volume_spike': volume_spike,
            'recent_volume': recent_vol,
            'avg_volume': historical_vol
        }
    
    def _estimate_buying_pressure(self, close: np.ndarray, high: np.ndarray, 
                                   low: np.ndarray, volume: Optional[np.ndarray]) -> float:
        """Estimate buying vs selling pressure using price action"""
        if len(close) < 5:
            return 0.0
        
        buying_scores = []
        for i in range(-5, 0):
            candle_range = high[i] - low[i]
            if candle_range > 0:
                close_position = (close[i] - low[i]) / candle_range
                buying_scores.append(close_position * 2 - 1)
            else:
                buying_scores.append(0)
        
        avg_pressure = np.mean(buying_scores)
        
        if volume is not None and len(volume) >= 5:
            recent_vol = volume[-5:]
            vol_weights = recent_vol / np.sum(recent_vol) if np.sum(recent_vol) > 0 else np.ones(5) / 5
            weighted_pressure = np.sum(np.array(buying_scores) * vol_weights)
            return float(weighted_pressure)
        
        return float(avg_pressure)
    
    def _analyze_funding(self, funding_rate: Optional[float]) -> float:
        """
        Analyze funding rate signal.
        Extreme positive funding = crowded long (bearish signal)
        Extreme negative funding = crowded short (bullish signal)
        """
        if funding_rate is None:
            return 0.0
        
        if abs(funding_rate) > self.extreme_funding_threshold:
            return -np.sign(funding_rate) * 1.0
        elif abs(funding_rate) > self.high_funding_threshold:
            return -np.sign(funding_rate) * 0.5
        else:
            return -np.sign(funding_rate) * 0.2 * abs(funding_rate) / self.high_funding_threshold
    
    def _analyze_open_interest(self, oi_change_pct: Optional[float]) -> float:
        """
        Analyze open interest changes.
        Rising OI with price = trend confirmation
        Falling OI = position unwinding
        """
        if oi_change_pct is None:
            return 0.0
        
        if abs(oi_change_pct) > self.oi_change_threshold:
            return np.sign(oi_change_pct) * 0.5
        else:
            return np.sign(oi_change_pct) * 0.3 * abs(oi_change_pct) / self.oi_change_threshold
    
    def _calculate_orderflow_bias(self, volume_trend: float, buying_pressure: float,
                                   funding_signal: float, oi_signal: float) -> float:
        """Calculate overall orderflow bias"""
        volume_component = np.tanh(volume_trend) * 0.2
        pressure_component = buying_pressure * 0.4
        funding_component = funding_signal * 0.25
        oi_component = oi_signal * 0.15
        
        combined = volume_component + pressure_component + funding_component + oi_component
        return round(max(-1.0, min(1.0, combined)), 3)
    
    def _calculate_raw_score(self, buying_pressure: float, funding_signal: float,
                             oi_signal: float) -> float:
        """Calculate raw orderflow score for ensemble"""
        return round(
            buying_pressure * 0.5 + funding_signal * 0.3 + oi_signal * 0.2,
            3
        )
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'funding_rate': None,
            'open_interest': None,
            'oi_change_pct': None,
            'funding_signal': 0.0,
            'oi_signal': 0.0,
            'volume_trend': 0.0,
            'buying_pressure': 0.0,
            'volume_spike': False,
            'bias': 0.0,
            'raw_score': 0.0,
            'status': 'error'
        }
