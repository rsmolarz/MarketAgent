"""
Crypto VWAP Analyzer

Volume Weighted Average Price analysis for cryptocurrency.
Calculates VWAP, standard deviation bands, and price positioning signals.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CryptoVWAPAnalyzer:
    """
    VWAP analysis for cryptocurrency markets.
    
    Calculates:
    - Rolling VWAP (Volume Weighted Average Price)
    - VWAP standard deviation bands
    - Price position relative to VWAP
    - VWAP trend signals
    """
    
    def __init__(self):
        self.lookback_periods = 24
    
    def analyze(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate VWAP analysis.
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            Dictionary with VWAP metrics
        """
        try:
            if price_data is None or len(price_data) < 5:
                return self._empty_result()
            
            close = price_data['Close'].values
            high = price_data['High'].values
            low = price_data['Low'].values
            volume = price_data['Volume'].values if 'Volume' in price_data.columns else np.ones(len(close))
            
            typical_price = (high + low + close) / 3
            
            vwap = self._calculate_vwap(typical_price, volume)
            vwap_std = self._calculate_vwap_std(typical_price, volume, vwap)
            
            current_price = close[-1]
            vwap_z = (current_price - vwap) / vwap_std if vwap_std > 0 else 0
            
            bias = self._calculate_vwap_bias(current_price, vwap, vwap_std, close)
            
            return {
                'rth_vwap': round(vwap, 2),
                'rth_vwap_std': round(vwap_std, 4),
                'rth_close': round(current_price, 2),
                'vwap_z': round(vwap_z, 2),
                'upper_band_1': round(vwap + vwap_std, 2),
                'lower_band_1': round(vwap - vwap_std, 2),
                'upper_band_2': round(vwap + 2 * vwap_std, 2),
                'lower_band_2': round(vwap - 2 * vwap_std, 2),
                'price_position': self._get_price_position(vwap_z),
                'bias': bias,
                'raw_score': self._calculate_raw_score(vwap_z),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"VWAP analysis error: {e}")
            return self._empty_result()
    
    def _calculate_vwap(self, typical_price: np.ndarray, volume: np.ndarray) -> float:
        """Calculate Volume Weighted Average Price"""
        lookback = min(self.lookback_periods, len(typical_price))
        
        tp = typical_price[-lookback:]
        vol = volume[-lookback:]
        
        total_volume = np.sum(vol)
        if total_volume == 0:
            return float(np.mean(tp))
        
        vwap = np.sum(tp * vol) / total_volume
        return float(vwap)
    
    def _calculate_vwap_std(self, typical_price: np.ndarray, volume: np.ndarray, 
                            vwap: float) -> float:
        """Calculate VWAP standard deviation"""
        lookback = min(self.lookback_periods, len(typical_price))
        
        tp = typical_price[-lookback:]
        vol = volume[-lookback:]
        
        total_volume = np.sum(vol)
        if total_volume == 0:
            return float(np.std(tp))
        
        squared_deviation = (tp - vwap) ** 2
        variance = np.sum(squared_deviation * vol) / total_volume
        std = np.sqrt(variance)
        
        return float(max(std, 0.0001))
    
    def _get_price_position(self, vwap_z: float) -> str:
        """Get descriptive price position relative to VWAP"""
        if vwap_z > 2:
            return "strongly_above"
        elif vwap_z > 1:
            return "above"
        elif vwap_z > 0:
            return "slightly_above"
        elif vwap_z > -1:
            return "slightly_below"
        elif vwap_z > -2:
            return "below"
        else:
            return "strongly_below"
    
    def _calculate_vwap_bias(self, current_price: float, vwap: float, 
                             vwap_std: float, close: np.ndarray) -> float:
        """
        Calculate VWAP-based bias.
        
        Mean reversion signal when price is extended from VWAP.
        Trend confirmation when price holds above/below VWAP.
        """
        if vwap_std <= 0:
            return 0.0
        
        vwap_z = (current_price - vwap) / vwap_std
        
        if abs(vwap_z) > 2.5:
            bias = np.sign(vwap_z) * -0.4
        elif abs(vwap_z) > 2:
            bias = np.sign(vwap_z) * 0.1
        elif abs(vwap_z) > 1:
            bias = np.sign(vwap_z) * 0.3
        else:
            bias = vwap_z * 0.2
        
        if len(close) >= 5:
            recent_trend = close[-1] - close[-5]
            trend_aligned = np.sign(recent_trend) == np.sign(vwap_z)
            
            if trend_aligned and abs(vwap_z) <= 2:
                bias += np.sign(vwap_z) * 0.2
        
        return round(max(-1.0, min(1.0, bias)), 3)
    
    def _calculate_raw_score(self, vwap_z: float) -> float:
        """Calculate raw VWAP score for ensemble"""
        if abs(vwap_z) > 2.5:
            return round(-np.sign(vwap_z) * 0.8, 3)
        else:
            return round(np.tanh(vwap_z * 0.5), 3)
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'rth_vwap': None,
            'rth_vwap_std': None,
            'rth_close': None,
            'vwap_z': None,
            'upper_band_1': None,
            'lower_band_1': None,
            'upper_band_2': None,
            'lower_band_2': None,
            'price_position': 'unknown',
            'bias': 0.0,
            'raw_score': 0.0,
            'status': 'error'
        }
