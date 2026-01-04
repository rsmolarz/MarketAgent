"""
Crypto Technical Analyzer

Analyzes technical indicators for cryptocurrency price prediction.
Calculates RSI, MACD, ADX and other momentum/trend indicators.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CryptoTechnicalAnalyzer:
    """
    Technical analysis for cryptocurrency markets.
    
    Calculates:
    - RSI (Relative Strength Index)
    - MACD (Moving Average Convergence Divergence)
    - ADX (Average Directional Index)
    - Trend bias and momentum signals
    """
    
    def __init__(self):
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.adx_period = 14
    
    def analyze(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate technical analysis signals.
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            Dictionary with technical indicators and bias
        """
        try:
            if price_data is None or len(price_data) < self.macd_slow + 10:
                return self._empty_result()
            
            close = price_data['Close'].values
            high = price_data['High'].values
            low = price_data['Low'].values
            
            rsi = self._calculate_rsi(close)
            macd, macd_signal_line, macd_hist = self._calculate_macd(close)
            adx = self._calculate_adx(high, low, close)
            
            bias = self._calculate_technical_bias(rsi, macd_hist, adx)
            
            return {
                'rsi': round(rsi, 2) if rsi is not None else None,
                'macd': round(macd, 4) if macd is not None else None,
                'macd_signal': round(macd_signal_line, 4) if macd_signal_line is not None else None,
                'macd_hist': round(macd_hist, 4) if macd_hist is not None else None,
                'adx': round(adx, 2) if adx is not None else None,
                'bias': bias,
                'raw_score': self._calculate_raw_score(rsi, macd_hist, adx),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Technical analysis error: {e}")
            return self._empty_result()
    
    def _calculate_rsi(self, close: np.ndarray) -> Optional[float]:
        """Calculate RSI"""
        if len(close) < self.rsi_period + 1:
            return None
            
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-self.rsi_period:])
        avg_loss = np.mean(losses[-self.rsi_period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _calculate_macd(self, close: np.ndarray) -> tuple:
        """Calculate MACD, signal line, and histogram"""
        if len(close) < self.macd_slow + self.macd_signal:
            return None, None, None
        
        ema_fast = self._ema(close, self.macd_fast)
        ema_slow = self._ema(close, self.macd_slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(np.array([macd_line[-1]] * len(close)), self.macd_signal)
        
        macd_series = []
        for i in range(len(close)):
            fast = self._ema(close[:i+1], self.macd_fast) if i >= self.macd_fast else 0
            slow = self._ema(close[:i+1], self.macd_slow) if i >= self.macd_slow else 0
            macd_series.append(fast - slow)
        
        macd_arr = np.array(macd_series[-self.macd_signal:])
        signal = self._ema(macd_arr, self.macd_signal) if len(macd_arr) >= self.macd_signal else macd_arr[-1]
        
        current_macd = macd_series[-1]
        hist = current_macd - signal
        
        return float(current_macd), float(signal), float(hist)
    
    def _ema(self, data: np.ndarray, period: int) -> float:
        """Calculate exponential moving average"""
        if len(data) < period:
            return float(np.mean(data))
        
        multiplier = 2 / (period + 1)
        ema = data[-period]
        
        for price in data[-period+1:]:
            ema = (price - ema) * multiplier + ema
            
        return float(ema)
    
    def _calculate_adx(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> Optional[float]:
        """Calculate Average Directional Index"""
        if len(close) < self.adx_period + 1:
            return None
        
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []
        
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
            tr_list.append(tr)
            
            plus_dm = high[i] - high[i-1] if high[i] - high[i-1] > low[i-1] - low[i] else 0
            plus_dm = max(plus_dm, 0)
            plus_dm_list.append(plus_dm)
            
            minus_dm = low[i-1] - low[i] if low[i-1] - low[i] > high[i] - high[i-1] else 0
            minus_dm = max(minus_dm, 0)
            minus_dm_list.append(minus_dm)
        
        tr_arr = np.array(tr_list[-self.adx_period:])
        plus_dm_arr = np.array(plus_dm_list[-self.adx_period:])
        minus_dm_arr = np.array(minus_dm_list[-self.adx_period:])
        
        atr = np.mean(tr_arr)
        if atr == 0:
            return 0.0
        
        plus_di = 100 * np.mean(plus_dm_arr) / atr
        minus_di = 100 * np.mean(minus_dm_arr) / atr
        
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 0.0
            
        dx = 100 * abs(plus_di - minus_di) / di_sum
        
        return float(dx)
    
    def _calculate_technical_bias(self, rsi: Optional[float], macd_hist: Optional[float], 
                                   adx: Optional[float]) -> float:
        """Calculate overall technical bias (-1 to +1)"""
        if rsi is None or macd_hist is None:
            return 0.0
        
        rsi_bias = 0.0
        if rsi > 70:
            rsi_bias = -0.5 * (rsi - 70) / 30
        elif rsi < 30:
            rsi_bias = 0.5 * (30 - rsi) / 30
        elif rsi > 50:
            rsi_bias = 0.3 * (rsi - 50) / 20
        else:
            rsi_bias = -0.3 * (50 - rsi) / 20
        
        macd_bias = np.tanh(macd_hist * 10)
        
        trend_strength = min((adx or 25) / 50, 1.0)
        
        combined = (rsi_bias * 0.4 + macd_bias * 0.6) * (0.5 + 0.5 * trend_strength)
        
        return round(max(-1.0, min(1.0, combined)), 3)
    
    def _calculate_raw_score(self, rsi: Optional[float], macd_hist: Optional[float],
                             adx: Optional[float]) -> float:
        """Calculate raw technical score for ensemble"""
        if rsi is None or macd_hist is None:
            return 0.0
        
        rsi_score = (rsi - 50) / 50
        macd_score = np.tanh(macd_hist * 5)
        trend_mult = 1.0 + 0.5 * min((adx or 0) / 50, 1.0)
        
        return round((rsi_score * 0.4 + macd_score * 0.6) * trend_mult, 3)
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'rsi': None,
            'macd': None,
            'macd_signal': None,
            'macd_hist': None,
            'adx': None,
            'bias': 0.0,
            'raw_score': 0.0,
            'status': 'error'
        }
