"""
Crypto Ensemble Predictor

Combines signals from multiple crypto analyzers using regime-aware
weighting to generate final predictions.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CryptoEnsemblePredictor:
    """
    Ensemble predictor for cryptocurrency.
    
    Combines:
    - Technical analysis signals
    - Orderflow signals
    - Market profile signals
    - VWAP signals
    
    Uses regime-aware weighting and risk gating.
    """
    
    def __init__(self):
        self.base_weights = {
            'technical': 0.30,
            'orderflow': 0.30,
            'profile': 0.20,
            'vwap': 0.20
        }
        
        self.regime_weight_adjustments = {
            'TRENDING': {'technical': 1.3, 'orderflow': 1.0, 'profile': 0.8, 'vwap': 0.9},
            'RANGING': {'technical': 0.8, 'orderflow': 0.9, 'profile': 1.3, 'vwap': 1.2},
            'VOLATILE': {'technical': 0.7, 'orderflow': 1.2, 'profile': 1.0, 'vwap': 1.1},
            'MIXED': {'technical': 1.0, 'orderflow': 1.0, 'profile': 1.0, 'vwap': 1.0}
        }
    
    def generate_prediction(self, 
                           technical: Dict[str, Any],
                           orderflow: Dict[str, Any],
                           profile: Dict[str, Any],
                           vwap: Dict[str, Any],
                           risk_gate: Dict[str, Any],
                           regime: str = 'MIXED',
                           regime_confidence: float = 0.5) -> Dict[str, Any]:
        """
        Generate ensemble prediction.
        
        Args:
            technical: Technical analyzer output
            orderflow: Orderflow analyzer output
            profile: Profile analyzer output
            vwap: VWAP analyzer output
            risk_gate: Risk gate evaluation
            regime: Detected market regime
            regime_confidence: Confidence in regime detection
            
        Returns:
            Dictionary with ensemble prediction
        """
        try:
            weights = self._calculate_regime_weights(regime, regime_confidence)
            
            raw_scores = {
                'technical': technical.get('raw_score', 0),
                'orderflow': orderflow.get('raw_score', 0),
                'profile': profile.get('raw_score', 0),
                'vwap': vwap.get('raw_score', 0)
            }
            
            contributions = {}
            total_weight = 0
            weighted_sum = 0
            
            for signal, score in raw_scores.items():
                weight = weights.get(signal, 0.25)
                contribution = score * weight
                contributions[signal] = round(contribution, 4)
                weighted_sum += contribution
                total_weight += weight
            
            ensemble_score_raw = weighted_sum / total_weight if total_weight > 0 else 0
            
            gate_multiplier = risk_gate.get('gate_multiplier', 1.0)
            ensemble_score_gated = ensemble_score_raw * gate_multiplier
            
            perf_multiplier = self._calculate_performance_multiplier()
            ensemble_score_final = ensemble_score_gated * perf_multiplier
            
            prob_up = 1 / (1 + np.exp(-ensemble_score_final * 2))
            
            direction, confidence = self._determine_direction_confidence(ensemble_score_final, prob_up)
            
            return {
                'ensemble_score_raw': round(ensemble_score_raw, 4),
                'ensemble_score_gated': round(ensemble_score_gated, 4),
                'ensemble_score_final': round(ensemble_score_final, 4),
                'macro_gate_multiplier': gate_multiplier,
                'performance_multiplier': perf_multiplier,
                'prob_up': round(prob_up, 4),
                'direction': direction,
                'confidence': confidence,
                'contributions': contributions,
                'regime_weights': weights,
                'technical_bias': technical.get('bias', 0),
                'orderflow_bias': orderflow.get('bias', 0),
                'auction_bias': profile.get('bias', 0),
                'vwap_bias': vwap.get('bias', 0),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Ensemble prediction error: {e}")
            return {
                'ensemble_score_raw': 0,
                'ensemble_score_final': 0,
                'prob_up': 0.5,
                'direction': 'NEUTRAL',
                'confidence': 'LOW',
                'status': 'error'
            }
    
    def _calculate_regime_weights(self, regime: str, regime_confidence: float) -> Dict[str, float]:
        """Calculate regime-adjusted weights"""
        adjustments = self.regime_weight_adjustments.get(regime, self.regime_weight_adjustments['MIXED'])
        
        blend_factor = min(1.0, regime_confidence)
        
        weights = {}
        for signal, base_weight in self.base_weights.items():
            adjustment = adjustments.get(signal, 1.0)
            blended_adjustment = 1.0 + (adjustment - 1.0) * blend_factor
            weights[signal] = base_weight * blended_adjustment
        
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def _calculate_performance_multiplier(self) -> float:
        """
        Calculate performance-based multiplier.
        This would ideally track historical prediction accuracy.
        """
        return 1.0
    
    def _determine_direction_confidence(self, score: float, prob_up: float) -> tuple:
        """Determine direction and confidence level"""
        if abs(score) < 0.1:
            direction = 'NEUTRAL'
            confidence = 'LOW'
        elif score > 0:
            direction = 'UP'
            if prob_up > 0.7:
                confidence = 'HIGH'
            elif prob_up > 0.55:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'
        else:
            direction = 'DOWN'
            prob_down = 1 - prob_up
            if prob_down > 0.7:
                confidence = 'HIGH'
            elif prob_down > 0.55:
                confidence = 'MEDIUM'
            else:
                confidence = 'LOW'
        
        return direction, confidence


class CryptoRegimeDetector:
    """
    Detect market regime for crypto markets.
    
    Regimes:
    - TRENDING: Strong directional movement
    - RANGING: Sideways consolidation
    - VOLATILE: High volatility, uncertain direction
    - MIXED: No clear regime
    """
    
    def __init__(self):
        self.adx_trending_threshold = 25
        self.adx_weak_threshold = 15
        self.vol_high_threshold = 2.0
    
    def detect(self, adx: Optional[float], 
               vwap_z: Optional[float], 
               vol_pct: Optional[float]) -> Dict[str, Any]:
        """
        Detect current market regime.
        
        Args:
            adx: Average Directional Index
            vwap_z: Z-score from VWAP
            vol_pct: Volatility percentage
            
        Returns:
            Dictionary with regime and confidence
        """
        try:
            adx_val = adx if adx is not None else 20
            vwap_z_val = abs(vwap_z) if vwap_z is not None else 0
            vol_val = vol_pct if vol_pct is not None else 1.0
            
            if vol_val > self.vol_high_threshold:
                regime = 'VOLATILE'
                confidence = min(1.0, vol_val / 4.0)
            elif adx_val > self.adx_trending_threshold:
                regime = 'TRENDING'
                confidence = min(1.0, (adx_val - 25) / 25 + 0.5)
            elif adx_val < self.adx_weak_threshold and vwap_z_val < 1:
                regime = 'RANGING'
                confidence = 0.6
            else:
                regime = 'MIXED'
                confidence = 0.4
            
            return {
                'regime': regime,
                'regime_confidence': round(confidence, 2),
                'adx': adx_val,
                'vwap_z': vwap_z_val,
                'vol_pct': vol_val
            }
            
        except Exception as e:
            logger.error(f"Regime detection error: {e}")
            return {
                'regime': 'MIXED',
                'regime_confidence': 0.3
            }
