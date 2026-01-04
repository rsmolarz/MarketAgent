"""
Regime Detector Module for Daily Prediction Agent

Detects market regimes (bull/bear/range) for regime-aware predictions.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Market regime detection using multiple indicators.
    
    Regimes:
    - BULL: Strong uptrend with positive momentum
    - BEAR: Strong downtrend with negative momentum  
    - RANGE: Sideways consolidation with low directional bias
    - VOLATILE: High volatility regime requiring caution
    """
    
    REGIME_BULL = 'bull'
    REGIME_BEAR = 'bear'
    REGIME_RANGE = 'range'
    REGIME_VOLATILE = 'volatile'
    
    def __init__(self):
        self.regime_thresholds = {
            'trend_strength': 0.02,
            'volatility_high': 1.5,
            'volatility_low': 0.7,
            'adx_trending': 25
        }
    
    def detect_regime(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect the current market regime.
        
        Args:
            price_data: DataFrame with OHLCV data
            
        Returns:
            Dict with regime classification and supporting metrics
        """
        if price_data is None or len(price_data) < 20:
            return self._default_regime("Insufficient data")
        
        try:
            trend = self._analyze_trend(price_data)
            volatility = self._analyze_volatility(price_data)
            breadth = self._analyze_price_structure(price_data)
            
            regime = self._classify_regime(trend, volatility, breadth)
            
            return {
                'regime': regime,
                'timestamp': datetime.utcnow().isoformat(),
                'trend_analysis': trend,
                'volatility_analysis': volatility,
                'structure_analysis': breadth,
                'regime_confidence': self._calculate_regime_confidence(trend, volatility, breadth),
                'risk_adjustment': self._get_risk_adjustment(regime),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Regime detection error: {e}")
            return self._default_regime(str(e))
    
    def _analyze_trend(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze price trend using moving averages"""
        close = data['Close']
        
        ma_20 = close.rolling(window=20).mean()
        ma_50 = close.rolling(window=50).mean() if len(close) >= 50 else ma_20
        
        current_price = close.iloc[-1]
        current_ma20 = ma_20.iloc[-1]
        current_ma50 = ma_50.iloc[-1]
        
        returns_20d = (current_price - close.iloc[-20]) / close.iloc[-20] if len(close) >= 20 else 0
        
        slope_20 = (ma_20.iloc[-1] - ma_20.iloc[-5]) / ma_20.iloc[-5] if len(ma_20) >= 5 else 0
        
        if current_price > current_ma20 > current_ma50:
            alignment = 'bullish'
            alignment_score = 1.0
        elif current_price < current_ma20 < current_ma50:
            alignment = 'bearish'
            alignment_score = -1.0
        elif current_price > current_ma20:
            alignment = 'mixed_bullish'
            alignment_score = 0.5
        elif current_price < current_ma20:
            alignment = 'mixed_bearish'
            alignment_score = -0.5
        else:
            alignment = 'neutral'
            alignment_score = 0
        
        return {
            'direction': 'up' if returns_20d > 0.02 else ('down' if returns_20d < -0.02 else 'sideways'),
            'strength': abs(returns_20d),
            'ma_alignment': alignment,
            'alignment_score': alignment_score,
            'slope': slope_20,
            'price_vs_ma20': (current_price - current_ma20) / current_ma20 * 100,
            'return_20d': returns_20d * 100
        }
    
    def _analyze_volatility(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze volatility regime"""
        close = data['Close']
        returns = close.pct_change().dropna()
        
        current_vol = returns.tail(10).std() * np.sqrt(252) * 100
        historical_vol = returns.std() * np.sqrt(252) * 100
        
        vol_ratio = current_vol / historical_vol if historical_vol > 0 else 1
        
        if vol_ratio > self.regime_thresholds['volatility_high']:
            vol_regime = 'high'
        elif vol_ratio < self.regime_thresholds['volatility_low']:
            vol_regime = 'low'
        else:
            vol_regime = 'normal'
        
        if 'High' in data.columns and 'Low' in data.columns:
            tr1 = data['High'] - data['Low']
            tr2 = abs(data['High'] - close.shift(1))
            tr3 = abs(data['Low'] - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            atr_pct = (atr / close.iloc[-1]) * 100
        else:
            atr_pct = current_vol / np.sqrt(252)
        
        return {
            'regime': vol_regime,
            'current_vol': current_vol,
            'historical_vol': historical_vol,
            'vol_ratio': vol_ratio,
            'atr_pct': atr_pct,
            'is_expanding': vol_ratio > 1.2
        }
    
    def _analyze_price_structure(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze price structure for range detection"""
        close = data['Close']
        
        high_20d = close.tail(20).max()
        low_20d = close.tail(20).min()
        range_pct = (high_20d - low_20d) / low_20d * 100
        
        current_price = close.iloc[-1]
        range_position = (current_price - low_20d) / (high_20d - low_20d) if high_20d != low_20d else 0.5
        
        higher_highs = 0
        lower_lows = 0
        for i in range(-10, -1):
            if len(close) > abs(i) + 5:
                if close.iloc[i] > close.iloc[i-5:i].max():
                    higher_highs += 1
                if close.iloc[i] < close.iloc[i-5:i].min():
                    lower_lows += 1
        
        if higher_highs > lower_lows + 1:
            structure = 'uptrend'
        elif lower_lows > higher_highs + 1:
            structure = 'downtrend'
        else:
            structure = 'range'
        
        return {
            'structure': structure,
            'range_pct': range_pct,
            'range_position': range_position,
            'higher_highs': higher_highs,
            'lower_lows': lower_lows,
            'is_near_high': range_position > 0.8,
            'is_near_low': range_position < 0.2
        }
    
    def _classify_regime(self, trend: Dict, volatility: Dict, structure: Dict) -> str:
        """Classify overall market regime"""
        if volatility['regime'] == 'high' and volatility['vol_ratio'] > 2:
            return self.REGIME_VOLATILE
        
        if (trend['alignment_score'] > 0.5 and 
            structure['structure'] == 'uptrend' and
            trend['direction'] == 'up'):
            return self.REGIME_BULL
        
        if (trend['alignment_score'] < -0.5 and 
            structure['structure'] == 'downtrend' and
            trend['direction'] == 'down'):
            return self.REGIME_BEAR
        
        if (structure['structure'] == 'range' and 
            abs(trend['alignment_score']) < 0.5 and
            volatility['regime'] != 'high'):
            return self.REGIME_RANGE
        
        if trend['alignment_score'] > 0:
            return self.REGIME_BULL
        elif trend['alignment_score'] < 0:
            return self.REGIME_BEAR
        else:
            return self.REGIME_RANGE
    
    def _calculate_regime_confidence(self, trend: Dict, volatility: Dict, structure: Dict) -> float:
        """Calculate confidence in regime classification"""
        trend_conf = min(abs(trend['alignment_score']), 1.0)
        vol_conf = 0.8 if volatility['regime'] != 'high' else 0.5
        structure_conf = 0.8 if structure['structure'] != 'range' else 0.6
        
        return (trend_conf * 0.4 + vol_conf * 0.3 + structure_conf * 0.3)
    
    def _get_risk_adjustment(self, regime: str) -> Dict[str, Any]:
        """Get risk adjustment factors based on regime"""
        adjustments = {
            self.REGIME_BULL: {
                'position_size_multiplier': 1.0,
                'confidence_adjustment': 0.1,
                'stop_loss_buffer': 1.0,
                'bias': 'long'
            },
            self.REGIME_BEAR: {
                'position_size_multiplier': 0.8,
                'confidence_adjustment': 0.0,
                'stop_loss_buffer': 0.8,
                'bias': 'short'
            },
            self.REGIME_RANGE: {
                'position_size_multiplier': 0.7,
                'confidence_adjustment': -0.1,
                'stop_loss_buffer': 1.2,
                'bias': 'neutral'
            },
            self.REGIME_VOLATILE: {
                'position_size_multiplier': 0.5,
                'confidence_adjustment': -0.2,
                'stop_loss_buffer': 1.5,
                'bias': 'reduce_exposure'
            }
        }
        return adjustments.get(regime, adjustments[self.REGIME_RANGE])
    
    def _default_regime(self, reason: str) -> Dict[str, Any]:
        """Return default regime on error"""
        return {
            'regime': self.REGIME_RANGE,
            'timestamp': datetime.utcnow().isoformat(),
            'trend_analysis': {},
            'volatility_analysis': {},
            'structure_analysis': {},
            'regime_confidence': 0.3,
            'risk_adjustment': self._get_risk_adjustment(self.REGIME_RANGE),
            'status': 'error',
            'error': reason
        }
