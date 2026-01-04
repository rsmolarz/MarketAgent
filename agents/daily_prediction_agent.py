"""
Daily Prediction Agent

Generates daily price predictions for futures and equities using modular
forecaster, regime detector, and ensemble components.

Features:
- Multi-model forecasting (trend, mean reversion, momentum, volatility)
- Regime-aware predictions (bull/bear/range/volatile)
- Macro risk gating
- Confidence calibration with actionability assessment
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

from .base_agent import BaseAgent
from .analyzers.forecaster import ForecasterAnalyzer
from .analyzers.regime_detector import RegimeDetector
from .analyzers.ensemble import EnsemblePredictor
from data_sources.yahoo_finance_client import YahooFinanceClient

logger = logging.getLogger(__name__)


class DailyPredictionAgent(BaseAgent):
    """
    Daily Prediction Agent for futures and equity price forecasting.
    
    Generates actionable predictions with confidence levels and 
    regime-aware risk adjustments.
    """
    
    def __init__(self):
        super().__init__()
        
        self.yahoo_client = YahooFinanceClient()
        self.forecaster = ForecasterAnalyzer()
        self.regime_detector = RegimeDetector()
        self.ensemble = EnsemblePredictor()
        
        self.instruments = {
            'equity_indices': ['SPY', 'QQQ', 'IWM', 'DIA'],
            'mega_caps': ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA'],
            'futures_proxies': ['ES=F', 'NQ=F', 'YM=F', 'GC=F', 'CL=F'],
            'crypto': ['BTC-USD', 'ETH-USD']
        }
        
        self.severity_thresholds = {
            'high_confidence': 0.75,
            'medium_confidence': 0.55,
            'strong_move': 1.5,
            'moderate_move': 0.75
        }
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Generate daily predictions for monitored instruments.
        
        Returns:
            List of prediction findings
        """
        findings = []
        
        for category, symbols in self.instruments.items():
            for symbol in symbols:
                try:
                    prediction = self._generate_prediction(symbol, category)
                    if prediction:
                        finding = self._create_prediction_finding(prediction, category)
                        if finding:
                            findings.append(finding)
                except Exception as e:
                    self.logger.error(f"Error generating prediction for {symbol}: {e}")
        
        self._log_prediction_summary(findings)
        
        return findings
    
    def _generate_prediction(self, symbol: str, category: str) -> Dict[str, Any]:
        """Generate prediction for a single symbol"""
        price_data = self.yahoo_client.get_price_data(symbol, period='60d')
        
        if price_data is None or len(price_data) < 20:
            self.logger.warning(f"Insufficient data for {symbol}")
            return None
        
        forecast = self.forecaster.generate_forecast(symbol, price_data)
        
        regime = self.regime_detector.detect_regime(price_data)
        
        macro_conditions = self._get_macro_conditions()
        
        ensemble_prediction = self.ensemble.generate_ensemble_prediction(
            forecast, regime, macro_conditions
        )
        
        ensemble_prediction['category'] = category
        
        return ensemble_prediction
    
    def _get_macro_conditions(self) -> Dict[str, Any]:
        """Get current macro conditions for risk gating"""
        try:
            vix_data = self.yahoo_client.get_price_data('^VIX', period='5d')
            current_vix = float(vix_data['Close'].iloc[-1]) if vix_data is not None and len(vix_data) > 0 else 20
        except Exception:
            current_vix = 20
        
        return {
            'vix': current_vix,
            'fed_meeting_today': False,
            'major_earnings': False,
            'geopolitical_risk': 'low'
        }
    
    def _create_prediction_finding(self, prediction: Dict[str, Any], category: str) -> Dict[str, Any]:
        """Convert prediction to finding format"""
        if prediction.get('status') == 'error':
            return None
        
        pred_data = prediction.get('prediction', {})
        confidence_data = prediction.get('confidence', {})
        actionability = prediction.get('actionability', {})
        regime_context = prediction.get('regime_context', {})
        
        direction = pred_data.get('direction', 'neutral')
        expected_move = pred_data.get('expected_move_pct', 0)
        overall_confidence = confidence_data.get('overall', 0)
        action_level = actionability.get('level', 'low')
        
        if action_level == 'low' and abs(expected_move) < 0.5:
            return None
        
        severity = self._determine_severity(overall_confidence, expected_move, action_level)
        
        symbol = prediction.get('symbol', 'UNKNOWN')
        target_price = pred_data.get('target_price')
        stop_loss = pred_data.get('stop_loss_pct')
        take_profit = pred_data.get('take_profit_pct')
        current_regime = regime_context.get('current_regime', 'unknown')
        
        direction_emoji = '📈' if direction == 'bullish' else ('📉' if direction == 'bearish' else '➡️')
        direction_word = direction.title()
        
        description = (
            f"{direction_emoji} {direction_word} prediction for {symbol}. "
            f"Expected move: {expected_move:+.2f}% "
        )
        
        if target_price:
            description += f"(target: ${target_price:.2f}). "
        
        description += f"Confidence: {overall_confidence*100:.0f}%. "
        description += f"Market regime: {current_regime}. "
        description += f"Actionability: {action_level}. "
        
        if stop_loss and take_profit:
            description += f"Suggested stop: {stop_loss:.1f}%, target: {take_profit:.1f}%."
        
        market_type = 'crypto' if category == 'crypto' else 'equity'
        if 'futures' in category.lower():
            market_type = 'futures'
        
        return self.create_finding(
            title=f"Daily Prediction: {symbol} {direction_word}",
            description=description,
            severity=severity,
            confidence=overall_confidence,
            symbol=symbol,
            market_type=market_type,
            metadata={
                'prediction_type': 'daily_forecast',
                'direction': direction,
                'expected_move_pct': expected_move,
                'target_price': target_price,
                'stop_loss_pct': stop_loss,
                'take_profit_pct': take_profit,
                'confidence_breakdown': confidence_data,
                'regime': current_regime,
                'regime_bias': regime_context.get('regime_bias'),
                'position_multiplier': regime_context.get('position_multiplier'),
                'actionability': actionability,
                'model_contributions': prediction.get('model_contributions', []),
                'category': category,
                'forecast_horizon': prediction.get('forecast_horizon', '1 day')
            }
        )
    
    def _determine_severity(self, confidence: float, expected_move: float, action_level: str) -> str:
        """Determine finding severity based on prediction strength"""
        abs_move = abs(expected_move)
        
        if action_level == 'high' and confidence >= self.severity_thresholds['high_confidence']:
            if abs_move >= self.severity_thresholds['strong_move']:
                return 'high'
            else:
                return 'medium'
        elif action_level == 'medium' and confidence >= self.severity_thresholds['medium_confidence']:
            if abs_move >= self.severity_thresholds['moderate_move']:
                return 'medium'
            else:
                return 'low'
        else:
            return 'low'
    
    def _log_prediction_summary(self, findings: List[Dict[str, Any]]):
        """Log summary of predictions generated"""
        if not findings:
            self.logger.info("No actionable predictions generated this run")
            return
        
        bullish = sum(1 for f in findings if 'bullish' in f.get('title', '').lower())
        bearish = sum(1 for f in findings if 'bearish' in f.get('title', '').lower())
        neutral = len(findings) - bullish - bearish
        
        high_conf = sum(1 for f in findings if f.get('confidence', 0) >= 0.7)
        
        self.logger.info(
            f"Generated {len(findings)} predictions: "
            f"{bullish} bullish, {bearish} bearish, {neutral} neutral. "
            f"{high_conf} high-confidence signals."
        )
