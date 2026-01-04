"""
Forecaster Module for Daily Prediction Agent

Technical and AI-based price forecasting using multiple models.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ForecasterAnalyzer:
    """
    Multi-model price forecaster combining technical analysis with statistical methods.
    
    Models:
    - Trend Following: MA crossover signals
    - Mean Reversion: Bollinger band positions
    - Momentum: RSI-based directional bias
    - Volatility Regime: ATR-adjusted predictions
    """
    
    def __init__(self):
        self.models = ['trend', 'mean_reversion', 'momentum', 'volatility']
        self.lookback_periods = {
            'short': 5,
            'medium': 20,
            'long': 50
        }
    
    def generate_forecast(self, symbol: str, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate a price forecast for the given symbol.
        
        Args:
            symbol: Ticker symbol
            price_data: DataFrame with OHLCV data
            
        Returns:
            Dict with forecast details including direction, magnitude, and confidence
        """
        if price_data is None or len(price_data) < 20:
            return self._empty_forecast(symbol, "Insufficient data")
        
        try:
            forecasts = {
                'trend': self._trend_forecast(price_data),
                'mean_reversion': self._mean_reversion_forecast(price_data),
                'momentum': self._momentum_forecast(price_data),
                'volatility': self._volatility_forecast(price_data)
            }
            
            combined = self._combine_forecasts(forecasts)
            current_price = float(price_data['Close'].iloc[-1])
            
            return {
                'symbol': symbol,
                'timestamp': datetime.utcnow().isoformat(),
                'current_price': current_price,
                'direction': combined['direction'],
                'expected_move_pct': combined['expected_move'],
                'target_price': current_price * (1 + combined['expected_move'] / 100),
                'confidence': combined['confidence'],
                'model_signals': forecasts,
                'forecast_horizon': '1 day',
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Forecast error for {symbol}: {e}")
            return self._empty_forecast(symbol, str(e))
    
    def _trend_forecast(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Trend-following model using MA crossovers"""
        try:
            close = data['Close']
            ma_short = close.rolling(window=5).mean()
            ma_medium = close.rolling(window=20).mean()
            ma_long = close.rolling(window=50).mean() if len(close) >= 50 else ma_medium
            
            current_price = close.iloc[-1]
            short_ma = ma_short.iloc[-1]
            medium_ma = ma_medium.iloc[-1]
            
            trend_score = 0
            if current_price > short_ma:
                trend_score += 1
            if short_ma > medium_ma:
                trend_score += 1
            if current_price > medium_ma:
                trend_score += 1
            
            direction = 'bullish' if trend_score >= 2 else ('bearish' if trend_score <= 1 else 'neutral')
            signal_strength = abs(trend_score - 1.5) / 1.5
            
            price_vs_ma = (current_price - medium_ma) / medium_ma * 100
            
            return {
                'direction': direction,
                'signal_strength': signal_strength,
                'expected_move': price_vs_ma * 0.1 if direction == 'bullish' else -abs(price_vs_ma) * 0.1,
                'confidence': 0.5 + signal_strength * 0.3,
                'metrics': {
                    'price_vs_20ma': price_vs_ma,
                    'ma_alignment': trend_score
                }
            }
        except Exception as e:
            logger.error(f"Trend forecast error: {e}")
            return {'direction': 'neutral', 'signal_strength': 0, 'expected_move': 0, 'confidence': 0.3}
    
    def _mean_reversion_forecast(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Mean reversion model using Bollinger Bands"""
        try:
            close = data['Close']
            period = 20
            
            ma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            
            upper_band = ma + (2 * std)
            lower_band = ma - (2 * std)
            
            current_price = close.iloc[-1]
            current_ma = ma.iloc[-1]
            current_upper = upper_band.iloc[-1]
            current_lower = lower_band.iloc[-1]
            
            band_width = current_upper - current_lower
            position = (current_price - current_lower) / band_width if band_width > 0 else 0.5
            
            if position > 0.8:
                direction = 'bearish'
                expected_move = -(position - 0.5) * 2
            elif position < 0.2:
                direction = 'bullish'
                expected_move = (0.5 - position) * 2
            else:
                direction = 'neutral'
                expected_move = 0
            
            signal_strength = abs(position - 0.5) * 2
            
            return {
                'direction': direction,
                'signal_strength': signal_strength,
                'expected_move': expected_move,
                'confidence': 0.4 + signal_strength * 0.4,
                'metrics': {
                    'bollinger_position': position,
                    'distance_from_mean_pct': (current_price - current_ma) / current_ma * 100
                }
            }
        except Exception as e:
            logger.error(f"Mean reversion forecast error: {e}")
            return {'direction': 'neutral', 'signal_strength': 0, 'expected_move': 0, 'confidence': 0.3}
    
    def _momentum_forecast(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Momentum model using RSI"""
        try:
            close = data['Close']
            rsi = self._calculate_rsi(close)
            current_rsi = rsi.iloc[-1]
            
            rsi_change = rsi.iloc[-1] - rsi.iloc[-5] if len(rsi) >= 5 else 0
            
            if current_rsi > 70:
                direction = 'bearish'
                signal_strength = (current_rsi - 70) / 30
                expected_move = -signal_strength * 1.5
            elif current_rsi < 30:
                direction = 'bullish'
                signal_strength = (30 - current_rsi) / 30
                expected_move = signal_strength * 1.5
            elif current_rsi > 50:
                direction = 'bullish'
                signal_strength = (current_rsi - 50) / 20
                expected_move = signal_strength * 0.5
            else:
                direction = 'bearish'
                signal_strength = (50 - current_rsi) / 20
                expected_move = -signal_strength * 0.5
            
            return {
                'direction': direction,
                'signal_strength': min(signal_strength, 1.0),
                'expected_move': expected_move,
                'confidence': 0.4 + min(signal_strength, 1.0) * 0.35,
                'metrics': {
                    'rsi': current_rsi,
                    'rsi_change_5d': rsi_change
                }
            }
        except Exception as e:
            logger.error(f"Momentum forecast error: {e}")
            return {'direction': 'neutral', 'signal_strength': 0, 'expected_move': 0, 'confidence': 0.3}
    
    def _volatility_forecast(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Volatility-adjusted forecast using ATR"""
        try:
            high = data['High'] if 'High' in data.columns else data['Close'] * 1.01
            low = data['Low'] if 'Low' in data.columns else data['Close'] * 0.99
            close = data['Close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean()
            
            current_atr = atr.iloc[-1]
            current_price = close.iloc[-1]
            atr_pct = (current_atr / current_price) * 100
            
            historical_atr_pct = (atr / close * 100).rolling(window=50).mean()
            avg_atr_pct = historical_atr_pct.iloc[-1] if len(historical_atr_pct) >= 50 else atr_pct
            
            volatility_regime = 'high' if atr_pct > avg_atr_pct * 1.5 else ('low' if atr_pct < avg_atr_pct * 0.7 else 'normal')
            
            returns = close.pct_change().dropna()
            recent_return = returns.tail(5).mean() * 100
            
            if volatility_regime == 'high':
                direction = 'neutral'
                expected_move = recent_return * 0.5
                confidence = 0.35
            else:
                direction = 'bullish' if recent_return > 0 else 'bearish'
                expected_move = recent_return
                confidence = 0.5
            
            return {
                'direction': direction,
                'signal_strength': abs(recent_return) / atr_pct if atr_pct > 0 else 0.5,
                'expected_move': expected_move,
                'confidence': confidence,
                'metrics': {
                    'atr_pct': atr_pct,
                    'volatility_regime': volatility_regime,
                    'recent_5d_return': recent_return
                }
            }
        except Exception as e:
            logger.error(f"Volatility forecast error: {e}")
            return {'direction': 'neutral', 'signal_strength': 0, 'expected_move': 0, 'confidence': 0.3}
    
    def _combine_forecasts(self, forecasts: Dict[str, Dict]) -> Dict[str, Any]:
        """Combine individual model forecasts into ensemble prediction"""
        weights = {
            'trend': 0.30,
            'mean_reversion': 0.25,
            'momentum': 0.25,
            'volatility': 0.20
        }
        
        weighted_move = 0
        weighted_confidence = 0
        bullish_votes = 0
        bearish_votes = 0
        
        for model, forecast in forecasts.items():
            weight = weights.get(model, 0.25)
            weighted_move += forecast.get('expected_move', 0) * weight
            weighted_confidence += forecast.get('confidence', 0.5) * weight
            
            direction = forecast.get('direction', 'neutral')
            if direction == 'bullish':
                bullish_votes += weight
            elif direction == 'bearish':
                bearish_votes += weight
        
        if bullish_votes > bearish_votes + 0.1:
            direction = 'bullish'
        elif bearish_votes > bullish_votes + 0.1:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        agreement = max(bullish_votes, bearish_votes) / (bullish_votes + bearish_votes + 0.001)
        confidence_boost = (agreement - 0.5) * 0.2
        
        return {
            'direction': direction,
            'expected_move': weighted_move,
            'confidence': min(weighted_confidence + confidence_boost, 0.95),
            'model_agreement': agreement,
            'bullish_weight': bullish_votes,
            'bearish_weight': bearish_votes
        }
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _empty_forecast(self, symbol: str, reason: str) -> Dict[str, Any]:
        """Return empty forecast structure"""
        return {
            'symbol': symbol,
            'timestamp': datetime.utcnow().isoformat(),
            'current_price': None,
            'direction': 'neutral',
            'expected_move_pct': 0,
            'target_price': None,
            'confidence': 0,
            'model_signals': {},
            'forecast_horizon': '1 day',
            'status': 'error',
            'error': reason
        }
