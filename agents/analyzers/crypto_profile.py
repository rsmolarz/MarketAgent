"""
Crypto Profile Analyzer

Market profile analysis for cryptocurrency.
Calculates POC (Point of Control), Value Area High/Low, and auction signals.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class CryptoProfileAnalyzer:
    """
    Market profile analysis for crypto.
    
    Analyzes:
    - POC (Point of Control) - price with highest volume
    - VAH/VAL (Value Area High/Low) - 70% of volume range
    - Price position relative to value area
    - Auction market signals
    """
    
    def __init__(self):
        self.value_area_pct = 0.70
        self.num_bins = 50
    
    def analyze(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate market profile analysis.
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            Dictionary with profile metrics
        """
        try:
            if price_data is None or len(price_data) < 10:
                return self._empty_result()
            
            close = price_data['Close'].values
            high = price_data['High'].values
            low = price_data['Low'].values
            volume = price_data['Volume'].values if 'Volume' in price_data.columns else np.ones(len(close))
            
            poc, vah, val = self._calculate_value_area(close, volume, high, low)
            
            current_price = close[-1]
            in_value = val <= current_price <= vah
            
            position_signal = self._calculate_position_signal(current_price, poc, vah, val)
            
            auction_bias = self._calculate_auction_bias(current_price, close, poc, vah, val)
            
            return {
                'poc': round(poc, 2),
                'vah': round(vah, 2),
                'val': round(val, 2),
                'current_price': round(current_price, 2),
                'in_value': in_value,
                'position_signal': position_signal,
                'bias': auction_bias,
                'raw_score': self._calculate_raw_score(current_price, poc, vah, val),
                'value_area_width': round((vah - val) / poc * 100, 2) if poc > 0 else 0,
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Profile analysis error: {e}")
            return self._empty_result()
    
    def _calculate_value_area(self, close: np.ndarray, volume: np.ndarray,
                               high: np.ndarray, low: np.ndarray) -> Tuple[float, float, float]:
        """Calculate POC and Value Area"""
        price_min = np.min(low)
        price_max = np.max(high)
        
        if price_min == price_max:
            return float(close[-1]), float(close[-1]), float(close[-1])
        
        bin_edges = np.linspace(price_min, price_max, self.num_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        volume_profile = np.zeros(self.num_bins)
        
        for i in range(len(close)):
            for j in range(self.num_bins):
                if low[i] <= bin_centers[j] <= high[i]:
                    volume_profile[j] += volume[i] / max(1, (high[i] - low[i]) / (price_max - price_min) * self.num_bins)
        
        poc_idx = np.argmax(volume_profile)
        poc = float(bin_centers[poc_idx])
        
        total_volume = np.sum(volume_profile)
        target_volume = total_volume * self.value_area_pct
        
        current_volume = volume_profile[poc_idx]
        low_idx = poc_idx
        high_idx = poc_idx
        
        while current_volume < target_volume and (low_idx > 0 or high_idx < self.num_bins - 1):
            expand_up = high_idx < self.num_bins - 1 and (low_idx <= 0 or volume_profile[high_idx + 1] >= volume_profile[low_idx - 1])
            
            if expand_up:
                high_idx += 1
                current_volume += volume_profile[high_idx]
            else:
                low_idx -= 1
                current_volume += volume_profile[low_idx]
        
        vah = float(bin_centers[high_idx])
        val = float(bin_centers[low_idx])
        
        return poc, vah, val
    
    def _calculate_position_signal(self, price: float, poc: float, vah: float, val: float) -> str:
        """Determine price position relative to value area"""
        if price > vah:
            return "above_value"
        elif price < val:
            return "below_value"
        elif price >= poc:
            return "upper_value"
        else:
            return "lower_value"
    
    def _calculate_auction_bias(self, current_price: float, close: np.ndarray,
                                 poc: float, vah: float, val: float) -> float:
        """
        Calculate auction theory bias.
        
        Above value area = bullish continuation or exhaustion
        Below value area = bearish continuation or support
        In value = balanced/neutral
        """
        value_width = vah - val
        if value_width <= 0:
            return 0.0
        
        if current_price > vah:
            distance = (current_price - vah) / value_width
            bias = min(1.0, 0.3 + 0.4 * distance)
        elif current_price < val:
            distance = (val - current_price) / value_width
            bias = max(-1.0, -0.3 - 0.4 * distance)
        else:
            relative_pos = (current_price - poc) / (value_width / 2)
            bias = relative_pos * 0.2
        
        if len(close) >= 5:
            momentum = (close[-1] - close[-5]) / close[-5] if close[-5] > 0 else 0
            bias += np.sign(momentum) * min(abs(momentum) * 5, 0.3)
        
        return round(max(-1.0, min(1.0, bias)), 3)
    
    def _calculate_raw_score(self, price: float, poc: float, vah: float, val: float) -> float:
        """Calculate raw profile score for ensemble"""
        if poc <= 0:
            return 0.0
        
        value_mid = (vah + val) / 2
        value_width = vah - val
        
        if value_width <= 0:
            return 0.0
        
        deviation = (price - value_mid) / value_width
        
        return round(np.tanh(deviation), 3)
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'poc': None,
            'vah': None,
            'val': None,
            'current_price': None,
            'in_value': None,
            'position_signal': 'unknown',
            'bias': 0.0,
            'raw_score': 0.0,
            'value_area_width': 0.0,
            'status': 'error'
        }
