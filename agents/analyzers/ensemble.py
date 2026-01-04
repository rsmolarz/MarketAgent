"""
Ensemble Module for Daily Prediction Agent

Combines multiple forecasts with regime awareness for final predictions.
"""

import logging
import numpy as np
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class EnsemblePredictor:
    """
    Regime-aware ensemble predictor that combines forecasts with macro gating.
    
    Features:
    - Weighted model combination
    - Regime-based weight adjustment
    - Macro risk gating
    - Confidence calibration
    """
    
    def __init__(self):
        self.base_weights = {
            'trend': 0.30,
            'mean_reversion': 0.25,
            'momentum': 0.25,
            'volatility': 0.20
        }
        
        self.regime_weight_adjustments = {
            'bull': {'trend': 1.3, 'momentum': 1.2, 'mean_reversion': 0.7},
            'bear': {'trend': 1.2, 'mean_reversion': 1.1, 'momentum': 0.8},
            'range': {'mean_reversion': 1.4, 'trend': 0.6, 'volatility': 1.2},
            'volatile': {'volatility': 1.5, 'trend': 0.5, 'mean_reversion': 0.5}
        }
    
    def generate_ensemble_prediction(self, 
                                     forecast: Dict[str, Any],
                                     regime: Dict[str, Any],
                                     macro_conditions: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate final ensemble prediction with regime awareness.
        
        Args:
            forecast: Output from ForecasterAnalyzer
            regime: Output from RegimeDetector
            macro_conditions: Optional macro risk indicators
            
        Returns:
            Final prediction with confidence and actionability
        """
        try:
            if forecast.get('status') == 'error':
                return self._error_prediction(forecast.get('symbol', 'UNKNOWN'), 
                                              forecast.get('error', 'Forecast error'))
            
            current_regime = regime.get('regime', 'range')
            regime_confidence = regime.get('regime_confidence', 0.5)
            risk_adjustment = regime.get('risk_adjustment', {})
            
            adjusted_weights = self._adjust_weights_for_regime(current_regime)
            
            model_signals = forecast.get('model_signals', {})
            if model_signals:
                ensemble_result = self._weighted_ensemble(model_signals, adjusted_weights)
            else:
                ensemble_result = {
                    'direction': forecast.get('direction', 'neutral'),
                    'expected_move': forecast.get('expected_move_pct', 0),
                    'raw_confidence': forecast.get('confidence', 0.5)
                }
            
            macro_gate = self._apply_macro_gating(macro_conditions) if macro_conditions else 1.0
            
            final_confidence = self._calibrate_confidence(
                ensemble_result['raw_confidence'],
                regime_confidence,
                macro_gate,
                risk_adjustment.get('confidence_adjustment', 0)
            )
            
            actionability = self._assess_actionability(
                ensemble_result['direction'],
                final_confidence,
                ensemble_result['expected_move'],
                current_regime
            )
            
            current_price = forecast.get('current_price', 0)
            expected_move = ensemble_result['expected_move']
            
            return {
                'symbol': forecast.get('symbol'),
                'timestamp': datetime.utcnow().isoformat(),
                'prediction': {
                    'direction': ensemble_result['direction'],
                    'expected_move_pct': expected_move,
                    'target_price': current_price * (1 + expected_move / 100) if current_price else None,
                    'stop_loss_pct': self._calculate_stop_loss(expected_move, current_regime),
                    'take_profit_pct': self._calculate_take_profit(expected_move, current_regime)
                },
                'confidence': {
                    'overall': final_confidence,
                    'model_agreement': ensemble_result.get('agreement', 0.5),
                    'regime_confidence': regime_confidence,
                    'macro_adjustment': macro_gate
                },
                'regime_context': {
                    'current_regime': current_regime,
                    'regime_bias': risk_adjustment.get('bias', 'neutral'),
                    'position_multiplier': risk_adjustment.get('position_size_multiplier', 1.0)
                },
                'actionability': actionability,
                'model_contributions': self._get_model_contributions(model_signals, adjusted_weights),
                'forecast_horizon': '1 day',
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Ensemble prediction error: {e}")
            return self._error_prediction(forecast.get('symbol', 'UNKNOWN'), str(e))
    
    def _adjust_weights_for_regime(self, regime: str) -> Dict[str, float]:
        """Adjust model weights based on current regime"""
        adjusted = self.base_weights.copy()
        adjustments = self.regime_weight_adjustments.get(regime, {})
        
        for model, adj in adjustments.items():
            if model in adjusted:
                adjusted[model] *= adj
        
        total = sum(adjusted.values())
        return {k: v / total for k, v in adjusted.items()}
    
    def _weighted_ensemble(self, signals: Dict[str, Dict], weights: Dict[str, float]) -> Dict[str, Any]:
        """Combine model signals with weights"""
        weighted_move = 0
        weighted_confidence = 0
        bullish_weight = 0
        bearish_weight = 0
        
        for model, signal in signals.items():
            weight = weights.get(model, 0.25)
            weighted_move += signal.get('expected_move', 0) * weight
            weighted_confidence += signal.get('confidence', 0.5) * weight
            
            direction = signal.get('direction', 'neutral')
            strength = signal.get('signal_strength', 0.5)
            
            if direction == 'bullish':
                bullish_weight += weight * strength
            elif direction == 'bearish':
                bearish_weight += weight * strength
        
        total_directional = bullish_weight + bearish_weight
        agreement = max(bullish_weight, bearish_weight) / total_directional if total_directional > 0 else 0.5
        
        if bullish_weight > bearish_weight + 0.1:
            direction = 'bullish'
        elif bearish_weight > bullish_weight + 0.1:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        return {
            'direction': direction,
            'expected_move': weighted_move,
            'raw_confidence': weighted_confidence,
            'agreement': agreement,
            'bullish_weight': bullish_weight,
            'bearish_weight': bearish_weight
        }
    
    def _apply_macro_gating(self, macro_conditions: Dict[str, Any]) -> float:
        """Apply macro risk gating to reduce confidence during high-risk periods"""
        gate = 1.0
        
        vix = macro_conditions.get('vix', 20)
        if vix > 30:
            gate *= 0.7
        elif vix > 25:
            gate *= 0.85
        
        if macro_conditions.get('fed_meeting_today', False):
            gate *= 0.6
        
        if macro_conditions.get('major_earnings', False):
            gate *= 0.8
        
        if macro_conditions.get('geopolitical_risk', 'low') == 'high':
            gate *= 0.7
        
        return max(gate, 0.3)
    
    def _calibrate_confidence(self, raw_confidence: float, regime_confidence: float,
                             macro_gate: float, regime_adjustment: float) -> float:
        """Calibrate final confidence score"""
        base = raw_confidence * 0.6 + regime_confidence * 0.4
        
        adjusted = base * macro_gate + regime_adjustment
        
        return max(0.1, min(0.95, adjusted))
    
    def _assess_actionability(self, direction: str, confidence: float, 
                             expected_move: float, regime: str) -> Dict[str, Any]:
        """Assess how actionable the prediction is"""
        if direction == 'neutral' or abs(expected_move) < 0.3:
            level = 'low'
            rationale = 'No clear directional signal'
        elif confidence < 0.4:
            level = 'low'
            rationale = 'Low confidence in prediction'
        elif confidence < 0.6:
            level = 'medium'
            rationale = 'Moderate confidence signal'
        elif regime == 'volatile':
            level = 'medium'
            rationale = 'Signal present but volatile regime requires caution'
        else:
            level = 'high'
            rationale = 'Strong signal with favorable regime'
        
        recommended_size = {
            'low': 0.25,
            'medium': 0.5,
            'high': 1.0
        }
        
        return {
            'level': level,
            'rationale': rationale,
            'recommended_position_size': recommended_size.get(level, 0.5),
            'trade_conviction': 'strong' if confidence > 0.7 else ('moderate' if confidence > 0.5 else 'weak')
        }
    
    def _calculate_stop_loss(self, expected_move: float, regime: str) -> float:
        """Calculate suggested stop loss percentage"""
        base_stop = max(abs(expected_move) * 1.5, 1.0)
        
        regime_multipliers = {
            'bull': 1.0,
            'bear': 0.8,
            'range': 1.2,
            'volatile': 1.5
        }
        
        return base_stop * regime_multipliers.get(regime, 1.0)
    
    def _calculate_take_profit(self, expected_move: float, regime: str) -> float:
        """Calculate suggested take profit percentage"""
        if expected_move == 0:
            return 1.0
        
        regime_multipliers = {
            'bull': 1.5,
            'bear': 1.2,
            'range': 1.0,
            'volatile': 0.8
        }
        
        return abs(expected_move) * regime_multipliers.get(regime, 1.0)
    
    def _get_model_contributions(self, signals: Dict[str, Dict], 
                                 weights: Dict[str, float]) -> List[Dict[str, Any]]:
        """Get contribution breakdown by model"""
        contributions = []
        
        for model, signal in signals.items():
            weight = weights.get(model, 0.25)
            contributions.append({
                'model': model,
                'weight': round(weight * 100, 1),
                'direction': signal.get('direction', 'neutral'),
                'signal_strength': round(signal.get('signal_strength', 0) * 100, 1),
                'expected_move': round(signal.get('expected_move', 0), 2)
            })
        
        return sorted(contributions, key=lambda x: x['weight'], reverse=True)
    
    def _error_prediction(self, symbol: str, error: str) -> Dict[str, Any]:
        """Return error prediction structure"""
        return {
            'symbol': symbol,
            'timestamp': datetime.utcnow().isoformat(),
            'prediction': {
                'direction': 'neutral',
                'expected_move_pct': 0,
                'target_price': None,
                'stop_loss_pct': None,
                'take_profit_pct': None
            },
            'confidence': {
                'overall': 0,
                'model_agreement': 0,
                'regime_confidence': 0,
                'macro_adjustment': 1.0
            },
            'regime_context': {},
            'actionability': {
                'level': 'low',
                'rationale': f'Error: {error}',
                'recommended_position_size': 0,
                'trade_conviction': 'none'
            },
            'model_contributions': [],
            'forecast_horizon': '1 day',
            'status': 'error',
            'error': error
        }
